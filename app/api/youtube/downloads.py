"""
YouTube download management endpoints.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep
from ...core.youtube import youtube_client
from ...models.base import YouTubeDownload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/download", tags=["youtube"])
stream_router = APIRouter(tags=["youtube"])


async def _mark_youtube_download_status(
    session: AsyncSession,
    video_id: str,
    status: str,
    *,
    error_message: str | None = None,
    download_path: str | None = None,
    format_type: str | None = None,
    file_size: int | None = None,
) -> None:
    stmt = select(YouTubeDownload).where(YouTubeDownload.youtube_video_id == video_id)
    rows = (await session.exec(stmt)).all()
    if not rows:
        return
    # DB column is TIMESTAMP WITHOUT TIME ZONE, keep this naive UTC datetime.
    now = datetime.utcnow()
    for row in rows:
        row.download_status = status
        row.updated_at = now
        if error_message is not None:
            row.error_message = error_message
        if download_path:
            row.download_path = download_path
        if format_type:
            row.format_type = format_type
        if file_size is not None:
            row.file_size = file_size
    for row in rows:
        session.add(row)
    await session.commit()


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
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Download audio for a YouTube video."""
    await _mark_youtube_download_status(session, video_id, "downloading", error_message=None)
    try:
        result = await youtube_client.download_audio(video_id, format_quality=quality, output_format=format)
    except HTTPException as exc:
        await _mark_youtube_download_status(
            session,
            video_id,
            "error",
            error_message=str(exc.detail),
            format_type=format,
        )
        raise
    file_path = result.get("file_path")
    file_size = result.get("file_size")
    if file_path:
        await _mark_youtube_download_status(
            session,
            video_id,
            "completed",
            error_message=None,
            download_path=file_path,
            format_type=format,
            file_size=file_size if isinstance(file_size, int) else None,
        )
    return result


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
    session: AsyncSession = Depends(SessionDep),
):
    """Stream audio from YouTube; cache file on disk if requested."""
    if cache:
        # Stable path: ensure a local file exists first, then serve it.
        status = await youtube_client.get_download_status(video_id, format)
        if status.get("exists"):
            file_path = status.get("file_path")
            file_size = status.get("file_size")
            if file_path:
                await _mark_youtube_download_status(
                    session,
                    video_id,
                    "completed",
                    error_message=None,
                    download_path=file_path,
                    format_type=format,
                    file_size=file_size if isinstance(file_size, int) else None,
                )
                return FileResponse(path=file_path, media_type="audio/mp4" if format == "m4a" else "audio/webm")

        await _mark_youtube_download_status(session, video_id, "downloading", error_message=None)
        try:
            result = await youtube_client.download_audio(video_id, output_format=format)
        except HTTPException as exc:
            await _mark_youtube_download_status(
                session,
                video_id,
                "error",
                error_message=str(exc.detail),
                format_type=format,
            )
            # In cache mode we require full file; avoid partial/fragile stream responses.
            raise HTTPException(status_code=502, detail=f"Unable to cache audio file: {exc.detail}")

        file_path = result.get("file_path")
        if not file_path:
            await _mark_youtube_download_status(
                session,
                video_id,
                "error",
                error_message="Download finished without file_path",
                format_type=format,
            )
            raise HTTPException(status_code=500, detail="Download failed - file not created")

        file_size = result.get("file_size")
        await _mark_youtube_download_status(
            session,
            video_id,
            "completed",
            error_message=None,
            download_path=file_path,
            format_type=format,
            file_size=file_size if isinstance(file_size, int) else None,
        )
        return FileResponse(path=file_path, media_type="audio/mp4" if format == "m4a" else "audio/webm")

    await _mark_youtube_download_status(session, video_id, "downloading", error_message=None)
    data = await youtube_client.stream_audio_to_device(
        video_id=video_id,
        output_format=format,
        cache=cache,
    )
    if data.get("type") == "file":
        file_path = data.get("file_path")
        file_size = None
        if file_path and Path(file_path).exists():
            file_size = Path(file_path).stat().st_size
        await _mark_youtube_download_status(
            session,
            video_id,
            "completed",
            error_message=None,
            download_path=file_path,
            format_type=(Path(file_path).suffix.lstrip(".") if file_path else format),
            file_size=file_size,
        )
        return FileResponse(path=data["file_path"], media_type=data.get("media_type", "audio/mp4"))
    if data.get("type") == "stream":
        async def tracked_stream():
            bytes_sent = 0
            try:
                async for chunk in data["stream"]:
                    bytes_sent += len(chunk)
                    yield chunk
                cache_path = data.get("cache_file_path")
                if cache and cache_path and Path(cache_path).exists():
                    await _mark_youtube_download_status(
                        session,
                        video_id,
                        "completed",
                        error_message=None,
                        download_path=cache_path,
                        format_type=Path(cache_path).suffix.lstrip(".") or format,
                        file_size=Path(cache_path).stat().st_size,
                    )
                elif bytes_sent > 0:
                    # Reproduced by stream but file not cached to disk.
                    await _mark_youtube_download_status(
                        session,
                        video_id,
                        "link_found",
                        error_message=None,
                        format_type=format,
                    )
            except Exception as exc:
                await _mark_youtube_download_status(
                    session,
                    video_id,
                    "error",
                    error_message=str(exc),
                    format_type=format,
                )
                raise

        return StreamingResponse(tracked_stream(), media_type=data.get("media_type", "audio/mp4"))
    raise HTTPException(status_code=500, detail="Invalid stream response")
