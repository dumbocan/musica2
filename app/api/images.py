"""
Image endpoints - filesystem-first approach.

Images are stored under STORAGE_ROOT/images with paths in DB.
This allows nginx/CDN to serve files directly while keeping DB small.
"""

import os
import ast
import json
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from urllib.parse import unquote, parse_qs, urlparse

from ..core.image_db_store import (
    store_image,
    get_image_path,
    get_image_stats as _get_image_stats,
    delete_images_for_entity,
    IMAGE_STORAGE,
    IMAGE_SIZES,
    find_by_source_url,
)
from ..core.db import get_session
from ..models.base import StoredImagePath
from sqlmodel import select

router = APIRouter(prefix="/images", tags=["images"])
_IMAGE_CACHE_SECONDS = 86400
_REPAIR_LIMIT_DEFAULT = 200


def _extract_primary_image_url(images: object) -> str | None:
    if not images:
        return None
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except json.JSONDecodeError:
            try:
                images = ast.literal_eval(images)
            except (ValueError, SyntaxError):
                return None
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if isinstance(first, dict):
        url = first.get("url")
    else:
        url = first
    if not isinstance(url, str):
        return None
    if url.startswith("/images/proxy?"):
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if "url" in query_params:
            return unquote(query_params["url"][0])
    return url


def _clear_entity_image_path(entity_type: str, entity_id: int) -> None:
    with get_session() as session:
        if entity_type == "artist":
            from ..models.base import Artist
            row = session.get(Artist, entity_id)
        elif entity_type == "album":
            from ..models.base import Album
            row = session.get(Album, entity_id)
        else:
            row = None
        if row and getattr(row, "image_path_id", None):
            row.image_path_id = None
            session.add(row)
            session.commit()


async def _repair_album_image(album_id: int, source_url: str | None, download_missing: bool) -> bool:
    if not source_url:
        return False
    existing = find_by_source_url(source_url)
    if existing:
        with get_session() as session:
            from ..models.base import Album
            album_row = session.get(Album, album_id)
            if album_row:
                album_row.image_path_id = existing.id
                session.add(album_row)
                session.commit()
        return True
    if not download_missing:
        return False
    delete_images_for_entity("album", album_id)
    _clear_entity_image_path("album", album_id)
    result = await store_image("album", album_id, source_url)
    if result:
        with get_session() as session:
            from ..models.base import Album
            album_row = session.get(Album, album_id)
            if album_row and not album_row.image_path_id:
                album_row.image_path_id = result.id
                session.add(album_row)
                session.commit()
        return True
    return False


async def _repair_artist_albums(artist_id: int, limit: int, download_missing: bool) -> dict:
    from ..models.base import Album
    with get_session() as session:
        albums = session.exec(
            select(Album)
            .where(Album.artist_id == artist_id)
            .order_by(Album.id.asc())
            .limit(limit)
        ).all()
    repaired = 0
    scanned = 0
    for album in albums:
        scanned += 1
        url = _extract_primary_image_url(album.images)
        if await _repair_album_image(album.id, url, download_missing):
            repaired += 1
    return {"scanned": scanned, "repaired": repaired}


@router.post("/repair/artist/{artist_id}")
async def repair_artist_images(
    artist_id: int,
    background_tasks: BackgroundTasks,
    background: bool = Query(True, description="Run repair in background"),
    limit: int = Query(_REPAIR_LIMIT_DEFAULT, ge=1, le=1000),
    download_missing: bool = Query(False, description="Download when not in local image DB"),
):
    """Repair album images for a specific artist (useful for mismatched album covers)."""
    if background and background_tasks is not None:
        background_tasks.add_task(_repair_artist_albums, artist_id, limit, download_missing)
        return {"status": "queued", "artist_id": artist_id, "limit": limit}
    return await _repair_artist_albums(artist_id, limit, download_missing)


def _resolve_stored_image_path(stored: StoredImagePath, size: int) -> str | None:
    """Resolve a stored image path for a given size, with fallbacks."""
    size_key = f"path_{size}"
    path = getattr(stored, size_key, None)
    if path:
        return str(IMAGE_STORAGE / path) if not os.path.isabs(path) else path
    for s in sorted(IMAGE_SIZES, reverse=True):
        size_key = f"path_{s}"
        path = getattr(stored, size_key, None)
        if path:
            return str(IMAGE_STORAGE / path) if not os.path.isabs(path) else path
    return None


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
        image_path = _resolve_stored_image_path(stored, size)
        if image_path and os.path.exists(image_path):
            return FileResponse(
                image_path,
                media_type="image/webp",
                headers={"Cache-Control": f"private, max-age={_IMAGE_CACHE_SECONDS}"},
            )

    # Not cached, download and store
    result = await store_image(
        entity_type="external",
        entity_id=None,
        source_url=decoded_url
    )

    if result:
        image_path = _resolve_stored_image_path(result, size)
        if image_path and os.path.exists(image_path):
            return FileResponse(
                image_path,
                media_type="image/webp",
                headers={"Cache-Control": f"private, max-age={_IMAGE_CACHE_SECONDS}"},
            )

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
    Falls back to downloading from the URL stored in the entity's images field
    and associating it with the entity.
    """
    from urllib.parse import parse_qs, urlparse, unquote
    import json

    # Get entity info
    entity_name = None
    entity_images = None
    if entity_type == "artist":
        with get_session() as session:
            from ..models.base import Artist
            entity = session.get(Artist, entity_id)
            if entity:
                entity_name = entity.name
                entity_images = entity.images
    elif entity_type == "album":
        with get_session() as session:
            from ..models.base import Album
            entity = session.get(Album, entity_id)
            if entity:
                entity_name = entity.name  # Use album name for search
                entity_images = entity.images

    expected_url = _extract_primary_image_url(entity_images)
    # Validate stored image matches the entity's current primary URL
    stored = None
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        ).limit(1)
        stored = session.exec(stmt).first()
    if stored and expected_url and stored.source_url != expected_url:
        delete_images_for_entity(entity_type, entity_id)
        _clear_entity_image_path(entity_type, entity_id)
        stored = None

    # Try to get from storedimagepath first
    image_path = get_image_path(entity_type, entity_id, size, entity_name)

    if image_path and os.path.exists(image_path):
        return FileResponse(
            image_path,
            media_type="image/webp",
            headers={"Cache-Control": f"private, max-age={_IMAGE_CACHE_SECONDS}"},
        )

    # Fallback: if entity has images field, download and store for this entity
    if entity_images:
        try:
            if isinstance(entity_images, str):
                # Try JSON first, then Python literal_eval (for single-quote strings)
                try:
                    images_data = json.loads(entity_images)
                except json.JSONDecodeError:
                    images_data = ast.literal_eval(entity_images)
            else:
                images_data = entity_images

            if isinstance(images_data, list) and len(images_data) > 0:
                # Get the largest image (usually first)
                first_img = images_data[0]
                if isinstance(first_img, dict):
                    url = first_img.get("url")
                else:
                    url = first_img

                if url:
                    # Extract real URL if it's a proxy URL
                    if url.startswith("/images/proxy?"):
                        parsed = urlparse(url)
                        query_params = parse_qs(parsed.query)
                        if "url" in query_params:
                            url = unquote(query_params["url"][0])

                    # Download and store for this entity
                    result = await store_image(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        source_url=url
                    )

                    if result:
                        # Update entity's image_path_id
                        if entity_type == "artist":
                            with get_session() as session:
                                from ..models.base import Artist
                                artist = session.get(Artist, entity_id)
                                if artist:
                                    artist.image_path_id = result.id
                                    session.add(artist)
                                    session.commit()
                        elif entity_type == "album":
                            with get_session() as session:
                                from ..models.base import Album
                                album = session.get(Album, entity_id)
                                if album:
                                    album.image_path_id = result.id
                                    session.add(album)
                                    session.commit()

                        # Return the image
                        image_path = get_image_path(entity_type, entity_id, size, entity_name)
                        if image_path and os.path.exists(image_path):
                            return FileResponse(
                                image_path,
                                media_type="image/webp",
                                headers={"Cache-Control": f"private, max-age={_IMAGE_CACHE_SECONDS}"},
                            )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

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
