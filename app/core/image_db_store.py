"""
DB-first image storage service.

Replaces filesystem cache with database storage for true API autonomy.
Images are downloaded once and stored in the database with multiple size variants.
"""

import hashlib
from typing import Optional
from io import BytesIO

import httpx
from PIL import Image
from sqlmodel import select

from .db import get_session
from .time_utils import utc_now
from .image_cache import _is_safe_url
from ..models.base import StoredImage, ImageSize


# Standard sizes to generate
IMAGE_SIZES = [128, 256, 512, 1024]
DEFAULT_QUALITY = 80
MAX_IMAGE_SIZE = 2048  # Max original image size to accept


def _get_image_size_enum(size: int) -> Optional[ImageSize]:
    """Get matching ImageSize enum or None."""
    size_map = {s.value: s for s in ImageSize}
    return size_map.get(size)


async def download_and_process_image(url: str) -> Optional[bytes]:
    """Download image from URL and return as WebP bytes."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            if 300 <= resp.status_code < 400:
                return None

            content = resp.content

        # Process image
        im = Image.open(BytesIO(content)).convert("RGB")

        # Resize if too large
        max_dim = max(im.width, im.height)
        if max_dim > MAX_IMAGE_SIZE:
            im.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

        # Convert to WebP
        buffer = BytesIO()
        im.save(buffer, format="WEBP", quality=DEFAULT_QUALITY, method=6)
        return buffer.getvalue()

    except Exception:
        return None


def get_image_from_db(
    entity_type: str,
    entity_id: int,
    size: int = 512
) -> Optional[tuple[bytes, str]]:
    """
    Get image from database, resizing on-demand if needed.

    Returns (image_bytes, content_type) or None if not found.
    """
    with get_session() as session:
        # Try to find existing image for this entity
        stmt = select(StoredImage).where(
            StoredImage.entity_type == entity_type,
            StoredImage.entity_id == entity_id,
        ).limit(1)
        stored = session.exec(stmt).first()

        if not stored:
            return None

        # Update last accessed
        stored.last_accessed_at = utc_now()
        session.add(stored)
        session.commit()

        # Return best matching size
        size_enum = _get_image_size_enum(size)
        if size_enum == ImageSize.THUMBNAIL and stored.image_128:
            return stored.image_128, "image/webp"
        elif size_enum == ImageSize.SMALL and stored.image_256:
            return stored.image_256, "image/webp"
        elif size_enum == ImageSize.MEDIUM and stored.image_512:
            return stored.image_512, "image/webp"
        elif size_enum == ImageSize.LARGE and stored.image_1024:
            return stored.image_1024, "image/webp"

        # Fall back to smaller size and resize on-demand
        for size_key in ["image_512", "image_256", "image_128"]:
            image_data = getattr(stored, size_key)
            if image_data:
                return image_data, "image/webp"

        return None


def get_image_by_hash(content_hash: str) -> Optional[StoredImage]:
    """Find stored image by its content hash."""
    with get_session() as session:
        stmt = select(StoredImage).where(
            StoredImage.content_hash == content_hash
        ).limit(1)
        return session.exec(stmt).first()


async def store_image(
    entity_type: str,
    entity_id: Optional[int],
    source_url: str,
    image_data: Optional[bytes] = None
) -> Optional[StoredImage]:
    """
    Download and store an image in the database.

    Args:
        entity_type: Type of entity ('artist', 'album', 'track', 'user')
        entity_id: ID of the entity (can be None for temporary storage)
        source_url: URL to download from if image_data not provided
        image_data: Pre-downloaded image data (optional)

    Returns:
        StoredImage instance or None on failure
    """
    # Download if not provided
    if image_data is None:
        if not _is_safe_url(source_url):
            return None
        image_data = await download_and_process_image(source_url)

    if not image_data:
        return None

    # Calculate hash
    content_hash = hashlib.sha256(image_data).hexdigest()

    # Check if already stored
    existing = get_image_by_hash(content_hash)
    if existing:
        # Update entity reference if provided
        if entity_id and existing.entity_id != entity_id:
            with get_session() as session:
                existing.entity_id = entity_id
                existing.entity_type = entity_type
                existing.updated_at = utc_now()
                session.add(existing)
                session.commit()
        return existing

    # Process and store all sizes
    try:
        im = Image.open(BytesIO(image_data)).convert("RGB")
        width, height = im.size

        sizes_data = {}
        for size in IMAGE_SIZES:
            if max(width, height) <= size:
                # Image is smaller than this size, store original
                if size == IMAGE_SIZES[0]:
                    sizes_data["image_128"] = image_data
                elif size == IMAGE_SIZES[1]:
                    sizes_data["image_256"] = image_data
                elif size == IMAGE_SIZES[2]:
                    sizes_data["image_512"] = image_data
                elif size == IMAGE_SIZES[3]:
                    sizes_data["image_1024"] = image_data
            else:
                # Resize
                im_copy = im.copy()
                im_copy.thumbnail((size, size))
                buffer = BytesIO()
                im_copy.save(buffer, format="WEBP", quality=DEFAULT_QUALITY, method=6)

                size_key = f"image_{size}"
                sizes_data[size_key] = buffer.getvalue()

        with get_session() as session:
            stored = StoredImage(
                entity_type=entity_type,
                entity_id=entity_id,
                source_url=source_url,
                content_hash=content_hash,
                width=width,
                height=height,
                format="webp",
                file_size_bytes=len(image_data),
                **sizes_data
            )
            session.add(stored)
            session.commit()
            session.refresh(stored)
            return stored

    except Exception:
        return None


def delete_images_for_entity(entity_type: str, entity_id: int) -> int:
    """Delete all images for an entity. Returns count deleted."""
    with get_session() as session:
        stmt = select(StoredImage).where(
            StoredImage.entity_type == entity_type,
            StoredImage.entity_id == entity_id,
        )
        images = session.exec(stmt).all()
        for img in images:
            session.delete(img)
        session.commit()
        return len(images)


def get_cache_stats() -> dict:
    """Get image cache statistics."""
    with get_session() as session:
        total = session.exec(select(StoredImage)).all()
        total_size = sum(img.file_size_bytes or 0 for img in total)
        return {
            "total_images": len(total),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
