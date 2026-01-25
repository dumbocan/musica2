"""
Image storage service - filesystem-first approach.

Images are stored in storage/images/ and paths kept in DB.
Keeps DB small while allowing direct file serving via nginx/CDN.
"""

import hashlib
import re
from typing import Optional
from pathlib import Path
from io import BytesIO

import httpx
from PIL import Image
from sqlmodel import select

from .db import get_session
from .time_utils import utc_now
from .image_cache import _is_safe_url
from ..models.base import StoredImagePath, Artist, Album, Track


# Storage configuration
STORAGE_ROOT = Path("storage")
IMAGE_STORAGE = STORAGE_ROOT / "images"
IMAGE_SIZES = [128, 256, 512, 1024]
DEFAULT_QUALITY = 80
MAX_ORIGINAL_SIZE = 2048


def _get_image_size_key(size: int) -> str:
    """Get field name for image size."""
    return f"path_{size}"


def _sanitize_filename(name: str) -> str:
    """Sanitize a name for use in file paths.

    Removes/replaces characters that are invalid in filenames.
    """
    # Replace common invalid chars with underscore
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    # Limit length
    name = name.strip()[:50]
    # Replace multiple underscores with single
    name = re.sub(r'_+', '_', name)
    # Remove leading/trailing underscores
    name = name.strip('_')
    return name if name else 'unknown'


def _get_entity_name(entity_type: str, entity_id: int) -> str:
    """Get human-readable name for an entity from DB.

    Returns sanitized name for use in file paths.
    """
    with get_session() as session:
        if entity_type == "artist":
            entity = session.get(Artist, entity_id)
            if entity:
                return _sanitize_filename(entity.name)
        elif entity_type == "album":
            entity = session.get(Album, entity_id)
            if entity:
                return _sanitize_filename(entity.name)
        elif entity_type == "track":
            entity = session.get(Track, entity_id)
            if entity:
                return _sanitize_filename(entity.name)
    return "unknown"


def _ensure_storage_dirs():
    """Create storage directories if they don't exist."""
    for size in IMAGE_SIZES:
        (IMAGE_STORAGE / str(size)).mkdir(parents=True, exist_ok=True)
    # Also create entity type directories
    for entity_type in ["artist", "album", "track"]:
        for size in IMAGE_SIZES:
            (IMAGE_STORAGE / str(size) / entity_type).mkdir(parents=True, exist_ok=True)


async def download_image(url: str) -> Optional[bytes]:
    """Download image from URL and return as WebP bytes."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            if 300 <= resp.status_code < 400:
                return None
            return resp.content
    except Exception:
        return None


def process_image(image_data: bytes) -> dict[str, bytes]:
    """Process image and generate all size variants.

    Returns dict with path_* keys and image bytes.
    """
    im = Image.open(BytesIO(image_data)).convert("RGB")
    width, height = im.size

    # Resize if too large
    max_dim = max(width, height)
    if max_dim > MAX_ORIGINAL_SIZE:
        im.thumbnail((MAX_ORIGINAL_SIZE, MAX_ORIGINAL_SIZE))
        width, height = im.size

    result = {"original": image_data}
    content_hash = hashlib.sha256(image_data).hexdigest()

    for size in IMAGE_SIZES:
        if max(width, height) <= size:
            # Image is smaller, use original for this size
            result[size] = image_data
        else:
            # Resize
            im_copy = im.copy()
            im_copy.thumbnail((size, size))
            buffer = BytesIO()
            im_copy.save(buffer, format="WEBP", quality=DEFAULT_QUALITY, method=6)
            result[size] = buffer.getvalue()

    return result, content_hash, width, height


def get_image_path(entity_type: str, entity_id: int, size: int = 512) -> Optional[str]:
    """Get image path for an entity from DB."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        ).limit(1)
        stored = session.exec(stmt).first()

        if not stored:
            return None

        # Update last accessed
        stored.last_accessed_at = utc_now()
        session.add(stored)
        session.commit()

        # Return best matching size
        size_key = _get_image_size_key(size)
        path = getattr(stored, size_key, None)
        if path:
            return str(IMAGE_STORAGE / path)

        # Fall back to smaller size
        for s in sorted(IMAGE_SIZES, reverse=True):
            pk = _get_image_size_key(s)
            p = getattr(stored, pk, None)
            if p:
                return str(IMAGE_STORAGE / p)

        return None


def find_by_hash(content_hash: str) -> Optional[StoredImagePath]:
    """Find stored image by content hash."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.content_hash == content_hash
        ).limit(1)
        return session.exec(stmt).first()


async def store_image(
    entity_type: str,
    entity_id: int,
    source_url: str,
    image_data: Optional[bytes] = None
) -> Optional[StoredImagePath]:
    """
    Download and store an image.

    Args:
        entity_type: Type of entity ('artist', 'album', 'track')
        entity_id: ID of the entity
        source_url: URL to download from if image_data not provided
        image_data: Pre-downloaded image data (optional)

    Returns:
        StoredImagePath instance or None on failure
    """
    # Download if not provided
    if image_data is None:
        if not _is_safe_url(source_url):
            return None
        image_data = await download_image(source_url)

    if not image_data:
        return None

    # Process image
    processed, content_hash, width, height = process_image(image_data)

    # Check if already stored
    existing = find_by_hash(content_hash)
    if existing:
        # Update entity reference if different
        if existing.entity_id != entity_id:
            with get_session() as session:
                existing.entity_id = entity_id
                existing.entity_type = entity_type
                existing.updated_at = utc_now()
                session.add(existing)
                session.commit()
        return existing

    # Ensure directories exist
    _ensure_storage_dirs()

    # Get human-readable name for the entity
    entity_name = _get_entity_name(entity_type, entity_id) if entity_id else "external"
    content_hash_short = content_hash[:8]  # Shorter hash for readability

    # Save files to disk and build paths
    paths = {}

    for size, data in processed.items():
        if size == "original":
            continue
        # Path like: "artist/metallica__abc12345_512.webp"
        # Format: {entity_name}__{hash_short}_{size}.webp
        filename = f"{entity_name}__{content_hash_short}_{size}.webp"
        full_path = IMAGE_STORAGE / str(size) / entity_type / filename

        # Create folder if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Save file
        full_path.write_bytes(data)
        paths[f"path_{size}"] = f"{size}/{entity_type}/{filename}"

    # Store in DB
    with get_session() as session:
        stored = StoredImagePath(
            entity_type=entity_type,
            entity_id=entity_id,
            source_url=source_url,
            content_hash=content_hash,
            original_width=width,
            original_height=height,
            format="webp",
            file_size_bytes=len(image_data),
            **paths
        )
        session.add(stored)
        session.commit()
        session.refresh(stored)
        return stored


def delete_images_for_entity(entity_type: str, entity_id: int) -> int:
    """Delete all images for an entity from DB and disk. Returns count deleted."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        )
        images = session.exec(stmt).all()

        # Delete files from disk
        deleted_files = 0
        for img in images:
            for size in IMAGE_SIZES:
                path_key = f"path_{size}"
                path = getattr(img, path_key, None)
                if path:
                    full_path = IMAGE_STORAGE / path
                    if full_path.exists():
                        full_path.unlink()
                        deleted_files += 1

        # Delete from DB
        for img in images:
            session.delete(img)
        session.commit()
        return deleted_files


def get_image_stats() -> dict:
    """Get image storage statistics."""
    with get_session() as session:
        images = session.exec(select(StoredImagePath)).all()
        total_size = sum(img.file_size_bytes or 0 for img in images)

        # Count files on disk
        file_count = 0
        disk_size = 0
        for size in IMAGE_SIZES:
            size_folder = IMAGE_STORAGE / str(size)
            if size_folder.exists():
                for f in size_folder.rglob("*.webp"):
                    file_count += 1
                    disk_size += f.stat().st_size

        return {
            "total_images": len(images),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files_on_disk": file_count,
            "disk_size_mb": round(disk_size / (1024 * 1024), 2),
            "storage_path": str(IMAGE_STORAGE),
        }
