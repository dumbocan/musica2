"""
YouTube download management endpoints.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from ...core.youtube import youtube_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/download", tags=["youtube"])
stream_router = APIRouter(tags=["youtube"])


@router.get("/{video_id}")
async def get_download_status(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
) -> Dict[str, Any]:
    """Get download status for a YouTube video."""
    return await youtube_client.get_download_status(video_id, format)


@router.post("/{video_id}")
async def start_download(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
    quality: str = Query("bestaudio"),
) -> Dict[str, Any]:
    """Download audio for a YouTube video."""
    return await youtube_client.download_audio(video_id, format_quality=quality, output_format=format)


@router.get("/{video_id}/status")
async def get_download_progress(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
) -> Dict[str, Any]:
    """Get download file presence status."""
    return await youtube_client.get_download_status(video_id, format)


@router.get("/{video_id}/file")
async def get_download_file(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
):
    """Serve downloaded file if present."""
    status = await youtube_client.get_download_status(video_id, format)
    if not status.get("exists"):
        raise HTTPException(status_code=404, detail="Downloaded file not found")
    file_path = Path(status["file_path"])
    media_type = "audio/mpeg" if format == "mp3" else "audio/mp4" if format == "m4a" else "audio/webm"
    return FileResponse(path=file_path, media_type=media_type, filename=f"{video_id}.{format}")


@router.delete("/{video_id}")
async def delete_download(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
) -> Dict[str, Any]:
    """Delete downloaded file."""
    deleted = await youtube_client.delete_download(video_id, format)
    return {"video_id": video_id, "format": format, "deleted": deleted}


@stream_router.get("/stream/{video_id}")
async def stream_audio(
    video_id: str,
    format: str = Query("m4a", pattern="^(m4a|webm)$"),
    cache: bool = Query(True),
):
    """Stream audio from YouTube; cache file on disk if requested."""
    data = await youtube_client.stream_audio_to_device(
        video_id=video_id,
        output_format=format,
        cache=cache,
    )
    if data.get("type") == "file":
        return FileResponse(path=data["file_path"], media_type=data.get("media_type", "audio/mp4"))
    if data.get("type") == "stream":
        return StreamingResponse(data["stream"], media_type=data.get("media_type", "audio/mp4"))
    raise HTTPException(status_code=500, detail="Invalid stream response")
