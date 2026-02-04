"""
YouTube download management endpoints.
"""

import asyncio
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
from ...models.base import YouTubeDownload, Track, Artist, Album

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/download", tags=["youtube"])
stream_router = APIRouter(tags=["youtube"])
REPO_ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS_ROOT = REPO_ROOT / "downloads"


def _resolve_download_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    candidate = Path(raw_path.strip())
    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    options = [
        REPO_ROOT / candidate,
        DOWNLOADS_ROOT / candidate,
    ]
    for path in options:
        if path.exists():
            return path
    return None


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


async def _status_from_db_path(
    session: AsyncSession,
    video_id: str,
    requested_format: str,
) -> Dict[str, Any] | None:
    stmt = (
        select(YouTubeDownload)
        .where(YouTubeDownload.youtube_video_id == video_id)
        .where(YouTubeDownload.download_path.is_not(None))
        .order_by(YouTubeDownload.updated_at.desc())
    )
    row = (await session.exec(stmt)).first()
    if not row or not row.download_path:
        return None
    path = _resolve_download_path(row.download_path)
    if not path:
        return None
    actual_format = path.suffix.lstrip(".").lower() or (row.format_type or requested_format)
    return {
        "video_id": video_id,
        "format": actual_format,
        "exists": True,
        "file_path": str(path),
        "file_size": path.stat().st_size,
        "source": "db_path",
    }


def _media_type_from_path(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    if ext == "mp3":
        return "audio/mpeg"
    if ext in {"m4a", "mp4"}:
        return "audio/mp4"
    if ext == "webm":
        return "audio/webm"
    return "application/octet-stream"


async def _resolve_local_track_file(
    session: AsyncSession,
    *,
    track_id: int | None = None,
    spotify_track_id: str | None = None,
) -> Path | None:
    track: Track | None = None
    if track_id is not None:
        track = (await session.exec(select(Track).where(Track.id == track_id))).first()
    elif spotify_track_id:
        track = (await session.exec(select(Track).where(Track.spotify_id == spotify_track_id))).first()

    # First source of truth: Track.download_path (DB-first local index).
    if track and track.download_path:
        path = _resolve_download_path(track.download_path)
        if path:
            return path

    resolved_spotify_id = spotify_track_id or (track.spotify_id if track else None)
    if not resolved_spotify_id:
        return None

    # Fallback to YouTubeDownload rows (handles migrated/legacy entries).
    rows = (await session.exec(
        select(YouTubeDownload)
        .where(YouTubeDownload.spotify_track_id == resolved_spotify_id)
        .where(YouTubeDownload.download_path.is_not(None))
        .where(YouTubeDownload.download_path != "")
        .order_by(YouTubeDownload.updated_at.desc())
    )).all()
    for row in rows:
        path = _resolve_download_path(row.download_path)
        if path:
            return path
    return None


@router.get("/{video_id}")
async def get_download_status(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Get download status for a YouTube video."""
    status = await youtube_client.get_download_status(video_id, format)
    if status.get("exists"):
        return status
    db_status = await _status_from_db_path(session, video_id, format)
    return db_status or status


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
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Get download file presence status."""
    status = await youtube_client.get_download_status(video_id, format)
    if status.get("exists"):
        return status
    db_status = await _status_from_db_path(session, video_id, format)
    return db_status or status


@router.get("/{video_id}/file")
async def get_download_file(
    video_id: str,
    format: str = Query("mp3", pattern="^(mp3|m4a|webm)$"),
    session: AsyncSession = Depends(SessionDep),
):
    """Serve downloaded file if present."""
    status = await youtube_client.get_download_status(video_id, format)
    if not status.get("exists"):
        db_status = await _status_from_db_path(session, video_id, format)
        if db_status:
            status = db_status
        else:
            raise HTTPException(status_code=404, detail="Downloaded file not found")
    file_path = Path(status["file_path"])
    ext = file_path.suffix.lstrip(".").lower() or format
    media_type = "audio/mpeg" if ext == "mp3" else "audio/mp4" if ext == "m4a" else "audio/webm"
    return FileResponse(path=file_path, media_type=media_type, filename=f"{video_id}.{ext}")


@router.get("/by-track/{spotify_track_id}/file")
async def get_local_file_by_spotify_track(
    spotify_track_id: str,
    session: AsyncSession = Depends(SessionDep),
):
    """Serve local file by Spotify track ID without requiring a YouTube video ID."""
    path = await _resolve_local_track_file(session, spotify_track_id=spotify_track_id)
    if not path:
        raise HTTPException(status_code=404, detail="Local file not found for track")
    return FileResponse(path=path, media_type=_media_type_from_path(path), filename=path.name)


@router.get("/by-local-track/{track_id}/file")
async def get_local_file_by_local_track(
    track_id: int,
    session: AsyncSession = Depends(SessionDep),
):
    """Serve local file by local track ID without requiring a YouTube video ID."""
    path = await _resolve_local_track_file(session, track_id=track_id)
    if not path:
        raise HTTPException(status_code=404, detail="Local file not found for track")
    return FileResponse(path=path, media_type=_media_type_from_path(path), filename=path.name)


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
    """Stream audio from YouTube with parallel caching to organized MP3 structure.

    Policy: Stream IMMEDIATELY, cache in PARALLEL (best-effort).
    Never wait for download before starting stream.
    """
    # Try to get track info for organized cache path (used for parallel download)
    artist_name = None
    track_name = None
    album_name = None

    yt = (await session.exec(
        select(YouTubeDownload).where(YouTubeDownload.youtube_video_id == video_id)
    )).first()

    if yt and yt.spotify_track_id:
        track = (await session.exec(
            select(Track).where(Track.spotify_id == yt.spotify_track_id)
        )).first()

        if track:
            if track.artist_id:
                artist = (await session.exec(
                    select(Artist).where(Artist.id == track.artist_id)
                )).first()
                if artist:
                    artist_name = artist.name

            if track.album_id:
                album = (await session.exec(
                    select(Album).where(Album.id == track.album_id)
                )).first()
                if album:
                    album_name = album.name

            track_name = track.name

    # Calculate organized cache path for parallel download
    cache_path = None
    should_download_mp3 = False
    if cache and artist_name and track_name:
        if album_name:
            cache_path = youtube_client.get_album_download_path(artist_name, album_name, track_name, "mp3")
        else:
            cache_path = youtube_client.get_artist_download_path(artist_name, track_name, "mp3")

        # Check if already downloaded
        if cache_path.exists():
            file_size = cache_path.stat().st_size
            await _mark_youtube_download_status(
                session,
                video_id,
                "completed",
                error_message=None,
                download_path=str(cache_path.relative_to(youtube_client.download_dir)),
                format_type="mp3",
                file_size=file_size,
            )
            return FileResponse(path=cache_path, media_type="audio/mp3")

        # Mark that we should download MP3 in background (but stream FIRST!)
        should_download_mp3 = True

    # STREAM FIRST - never wait for download!
    await _mark_youtube_download_status(session, video_id, "downloading", error_message=None)

    # Trigger parallel background download if needed (doesn't block the stream)
    if should_download_mp3 and cache_path:
        # Fire-and-forget background task to download MP3
        asyncio.create_task(_background_download_mp3(session, video_id, artist_name, track_name, album_name, str(cache_path)))

    # Stream immediately (best-effort, may fail if YouTube blocks)
    try:
        data = await youtube_client.stream_audio_to_device(
            video_id=video_id,
            output_format=format,
            cache=cache,
            output_path=Path(cache_path) if cache_path else None,
        )
    except HTTPException as exc:
        await _mark_youtube_download_status(
            session,
            video_id,
            "error",
            error_message=str(exc.detail),
            format_type=format,
        )
        raise HTTPException(status_code=502, detail=f"Unable to stream audio file: {exc.detail}")

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
                cache_path_val = data.get("cache_file_path")
                if cache and cache_path_val and Path(cache_path_val).exists():
                    await _mark_youtube_download_status(
                        session,
                        video_id,
                        "completed",
                        error_message=None,
                        download_path=cache_path_val,
                        format_type=Path(cache_path_val).suffix.lstrip(".") or format,
                        file_size=Path(cache_path_val).stat().st_size,
                    )
                elif bytes_sent > 0:
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
                logger.warning("Tracked stream failed for %s: %s", video_id, exc)
                return

        return StreamingResponse(tracked_stream(), media_type=data.get("media_type", "audio/mp4"))
    raise HTTPException(status_code=500, detail="Invalid stream response")


async def _background_download_mp3(
    session: AsyncSession,
    video_id: str,
    artist_name: str,
    track_name: str,
    album_name: str | None,
    cache_path: str,
):
    """Background task to download MP3 to cache. Does NOT block the stream."""
    try:
        result = await youtube_client.download_audio_for_track(
            video_id=video_id,
            artist_name=artist_name,
            track_name=track_name,
            album_name=album_name,
            output_format="mp3"
        )

        if result.get("status") in ("completed", "already_exists"):
            file_path = Path(result.get("file_path"))
            if file_path.exists():
                await _mark_youtube_download_status(
                    session,
                    video_id,
                    "completed",
                    error_message=None,
                    download_path=str(file_path.relative_to(youtube_client.download_dir)),
                    format_type="mp3",
                    file_size=file_path.stat().st_size,
                )
                logger.info(f"Background cache completed: {file_path.name}")
    except Exception as exc:
        logger.warning(f"Background cache failed for {video_id}: {exc}")
        # Don't fail the stream if background download fails
