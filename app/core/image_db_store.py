"""
Image storage service - filesystem-first approach.

Images are stored under STORAGE_ROOT/images and paths kept in DB.
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
from .config import settings
from ..models.base import StoredImagePath, Artist, Album, Track


# Storage configuration
_raw_storage_root = (settings.STORAGE_ROOT or "storage").strip()
STORAGE_ROOT = Path(_raw_storage_root).expanduser()
IMAGE_STORAGE = STORAGE_ROOT / "images"
IMAGE_SIZES = [256, 512]
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


def _get_entity_name(entity_type: str, entity_id: int) -> tuple[str, Optional[str]]:
    """Get human-readable name for an entity from DB.

    Returns (entity_name, parent_name) for path structure.
    For artists: (artist_name, None)
    For albums: (album_name, artist_name)
    For tracks: (track_name, artist_name or album_name)
    """
    with get_session() as session:
        if entity_type == "artist":
            entity = session.get(Artist, entity_id)
            if entity:
                return _sanitize_filename(entity.name), None
        elif entity_type == "album":
            entity = session.get(Album, entity_id)
            if entity:
                album_name = _sanitize_filename(entity.name)
                artist_name = None
                if entity.artist_id:
                    artist = session.get(Artist, entity.artist_id)
                    if artist:
                        artist_name = _sanitize_filename(artist.name)
                return album_name, artist_name
        elif entity_type == "track":
            entity = session.get(Track, entity_id)
            if entity:
                track_name = _sanitize_filename(entity.name)
                parent_name = None
                if entity.album_id:
                    album = session.get(Album, entity.album_id)
                    if album:
                        parent_name = _sanitize_filename(album.name)
                return track_name, parent_name
    return "unknown", None


def _ensure_storage_dirs():
    """Create storage directories if they don't exist."""
    # Just ensure root exists - subdirs created dynamically
    IMAGE_STORAGE.mkdir(parents=True, exist_ok=True)


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


def get_image_path(entity_type: str, entity_id: int, size: int = 512, entity_name: Optional[str] = None) -> Optional[str]:
    """Get image path for an entity from DB.

    Searches by entity_id first, then falls back to entity_name (sanitized folder name),
    then falls back to searching by the path pattern from the entity's images.
    """
    with get_session() as session:
        # First try: search by entity_id
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        ).limit(1)
        stored = session.exec(stmt).first()

        # Fallback: search by entity_name (for legacy data where entity_id was None)
        if not stored and entity_name and entity_type == "artist":
            sanitized_name = _sanitize_filename(entity_name)
            stmt = select(StoredImagePath).where(
                StoredImagePath.entity_type == entity_type,
                StoredImagePath.path_256.like(f"{sanitized_name}/%"),
            ).limit(1)
            stored = session.exec(stmt).first()

        # Fallback: try to find by path pattern based on entity name
        if not stored and entity_name:
            sanitized_name = _sanitize_filename(entity_name)
            # Try to find any image path that contains the entity name in the folder structure
            stmt = select(StoredImagePath).where(
                (StoredImagePath.entity_type == entity_type) &
                (
                    (StoredImagePath.path_256.like(f"%/{sanitized_name}/%")) |
                    (StoredImagePath.path_256.like(f"{sanitized_name}/%"))
                )
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
            path_obj = Path(path)
            if path_obj.is_absolute():
                return str(path_obj)
            return str(IMAGE_STORAGE / path_obj)

        # Fall back to smaller size
        for s in sorted(IMAGE_SIZES, reverse=True):
            pk = _get_image_size_key(s)
            p = getattr(stored, pk, None)
            if p:
                p_obj = Path(p)
                if p_obj.is_absolute():
                    return str(p_obj)
                return str(IMAGE_STORAGE / p_obj)

        return None


def find_by_hash(content_hash: str) -> Optional[StoredImagePath]:
    """Find stored image by content hash."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.content_hash == content_hash
        ).limit(1)
        return session.exec(stmt).first()


def find_by_source_url(source_url: str) -> Optional[StoredImagePath]:
    """Find stored image by source URL."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.source_url == source_url
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
        # Only reuse if this exact entity already owns the stored image.
        if existing.entity_id == entity_id and existing.entity_type == entity_type:
            return existing

    # Ensure directories exist
    _ensure_storage_dirs()

    # Get human-readable names for the entity
    entity_name, parent_name = _get_entity_name(entity_type, entity_id) if entity_id else ("external", None)
    content_hash_short = content_hash[:8]  # Shorter hash for readability

    # Build path structure based on entity type
    # Format: artist_name/entityname__hash_size.webp
    #         artist_name/album_name/albumname__hash_size.webp
    paths = {}

    if entity_type == "artist":
        # Artist images go directly in artist folder
        artist_folder = entity_name
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / artist_folder / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = f"{artist_folder}/{filename}"

    elif entity_type in ("album", "track"):
        # Albums/tracks go in parent_name/entity_name/
        if parent_name:
            entity_folder = Path(parent_name) / entity_name
        else:
            # Fallback if no parent
            entity_folder = Path(entity_name)
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / entity_folder / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = str(entity_folder / filename)

    else:
        # Fallback for other types
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / entity_type / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = f"{entity_type}/{filename}"

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

        # Count files on disk - new structure has artist/album folders
        file_count = 0
        disk_size = 0
        if IMAGE_STORAGE.exists():
            for f in IMAGE_STORAGE.rglob("*.webp"):
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
