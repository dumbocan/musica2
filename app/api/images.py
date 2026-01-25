"""
Image endpoints - filesystem-first approach.

Images are stored in storage/images/ with paths in DB.
This allows nginx/CDN to serve files directly while keeping DB small.
"""

import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from urllib.parse import unquote

from ..core.image_db_store import (
    store_image,
    get_image_path,
    get_image_stats as _get_image_stats,
    delete_images_for_entity,
    IMAGE_STORAGE,
)
from ..core.db import get_session
from ..models.base import StoredImagePath
from sqlmodel import select

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/proxy")
async def proxy_image(
    url: str = Query(..., description="Original image URL"),
    size: int = Query(512, ge=32, le=1024, description="Max dimension in px")
):
    """
    Fetch and cache an image from external URL.

    First checks if we already have this image cached.
    If not, downloads from source and stores in storage/.
    Returns the image file.
    """
    decoded_url = unquote(url)

    # Try to find by URL
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.source_url == decoded_url
        ).limit(1)
        stored = session.exec(stmt).first()

    if stored:
        image_path = get_image_path(stored.entity_type, stored.id, size)
        if image_path and os.path.exists(image_path):
            return FileResponse(image_path, media_type="image/webp")

    # Not cached, download and store
    result = await store_image(
        entity_type="external",
        entity_id=None,
        source_url=decoded_url
    )

    if result:
        image_path = get_image_path("external", result.id, size)
        if image_path and os.path.exists(image_path):
            return FileResponse(image_path, media_type="image/webp")

    raise HTTPException(status_code=400, detail="Unable to fetch image")


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_image(
    entity_type: str,
    entity_id: int,
    size: int = Query(512, ge=32, le=1024, description="Image size in px")
):
    """
    Get image for an entity (artist, album, track).

    Images are served from storage/images/ directly.
    Falls back to searching by entity name for legacy cached images.
    """
    # Get entity name for fallback lookup (especially for artists with legacy cache)
    entity_name = None
    if entity_type == "artist":
        with get_session() as session:
            from ..models.base import Artist
            entity = session.get(Artist, entity_id)
            if entity:
                entity_name = entity.name

    image_path = get_image_path(entity_type, entity_id, size, entity_name)

    if image_path and os.path.exists(image_path):
        return FileResponse(image_path, media_type="image/webp")

    raise HTTPException(status_code=404, detail="Image not found")


@router.get("/entity/{entity_type}/{entity_id}/info")
async def get_entity_image_info(
    entity_type: str,
    entity_id: int
):
    """Get image metadata for an entity."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        ).limit(1)
        stored = session.exec(stmt).first()

    if not stored:
        raise HTTPException(status_code=404, detail="Image not found")

    return {
        "entity_type": stored.entity_type,
        "entity_id": stored.entity_id,
        "source_url": stored.source_url,
        "content_hash": stored.content_hash,
        "original_width": stored.original_width,
        "original_height": stored.original_height,
        "format": stored.format,
        "sizes_available": {
            "128": stored.path_128 is not None,
            "256": stored.path_256 is not None,
            "512": stored.path_512 is not None,
            "1024": stored.path_1024 is not None,
        },
        "created_at": stored.created_at.isoformat(),
    }


@router.post("/entity/{entity_type}/{entity_id}/cache")
async def cache_entity_image(
    entity_type: str,
    entity_id: int,
    url: str = Query(..., description="Image URL to cache")
):
    """
    Pre-cache an image for an entity.

    Downloads from URL and stores in storage/ for future requests.
    """
    decoded_url = unquote(url)
    result = await store_image(entity_type, entity_id, decoded_url)

    if result:
        return {
            "message": "Image cached successfully",
            "image_id": result.id,
            "content_hash": result.content_hash,
        }

    raise HTTPException(status_code=400, detail="Unable to cache image")


@router.delete("/entity/{entity_type}/{entity_id}")
async def delete_entity_images(
    entity_type: str,
    entity_id: int
):
    """Delete all cached images for an entity from DB and disk."""
    count = delete_images_for_entity(entity_type, entity_id)
    return {"message": f"Deleted {count} image files"}


@router.get("/stats")
def get_image_stats():
    """Get image storage statistics."""
    stats = _get_image_stats()
    return stats


@router.get("/storage-path")
def get_storage_path():
    """Get the storage path for images (for nginx config)."""
    return {"path": str(IMAGE_STORAGE)}
