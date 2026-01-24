"""
Image endpoints - DB-first approach.

Images are stored in the database with multiple size variants.
This replaces the old proxy-based approach that fetched from external APIs on every request.
"""

from fastapi import APIRouter, HTTPException, Query, Response
from urllib.parse import unquote

from ..core.image_db_store import (
    store_image,
    get_image_from_db,
    get_cache_stats,
    delete_images_for_entity,
)
from ..core.db import get_session
from ..models.base import StoredImage
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
    If not, downloads from source and stores in DB.
    Returns the resized image.
    """
    decoded_url = unquote(url)

    with get_session() as session:
        stmt = select(StoredImage).where(
            StoredImage.source_url == decoded_url
        ).limit(1)
        stored = session.exec(stmt).first()

        if stored:
            # Return cached image
            image_data = get_image_from_db(stored.entity_type, stored.id, size)
            if image_data:
                return Response(content=image_data[0], media_type="image/webp")

        # Not cached, download and store
        result = await store_image(
            entity_type="external",
            entity_id=None,
            source_url=decoded_url
        )

        if result:
            image_data = get_image_from_db("external", result.id, size)
            if image_data:
                return Response(content=image_data[0], media_type="image/webp")

    raise HTTPException(status_code=400, detail="Unable to fetch image")


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_image(
    entity_type: str,
    entity_id: int,
    size: int = Query(512, ge=32, le=1024, description="Image size in px")
):
    """
    Get image for an entity (artist, album, track, user).

    This is the DB-first approach - images are stored locally.
    """
    result = get_image_from_db(entity_type, entity_id, size)
    if result:
        return Response(content=result[0], media_type="image/webp")

    raise HTTPException(status_code=404, detail="Image not found")


@router.post("/entity/{entity_type}/{entity_id}/cache")
async def cache_entity_image(
    entity_type: str,
    entity_id: int,
    url: str = Query(..., description="Image URL to cache")
):
    """
    Pre-cache an image for an entity.

    Downloads from URL and stores in DB for future requests.
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
    """Delete all cached images for an entity."""
    count = delete_images_for_entity(entity_type, entity_id)
    return {"message": f"Deleted {count} images"}


@router.get("/stats")
def get_image_stats():
    """Get image cache statistics."""
    stats = get_cache_stats()
    return stats
