"""
Image proxy/resize endpoint.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from urllib.parse import unquote

from ..core.image_cache import fetch_and_resize

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/proxy")
async def proxy_image(
    url: str = Query(..., description="Image URL"),
    size: int = Query(512, description="Max dimension in px")
):
    path = await fetch_and_resize(unquote(url), size=size)
    if not path:
        raise HTTPException(status_code=400, detail="Unable to fetch image")
    return FileResponse(path, media_type="image/webp")
