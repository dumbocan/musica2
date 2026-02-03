"""
YouTube link management endpoints (DB-first + refresh fallback).
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends, Request
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep
from ...core.youtube import youtube_client
from ...models.base import Track, Artist, Album, YouTubeDownload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["youtube"])


def _is_valid_youtube_video_id(value: str | None) -> bool:
    if not value:
        return False
    return len(value) == 11 and all(ch.isalnum() or ch in "_-" for ch in value)


class BatchLinksRequest(BaseModel):
    spotify_track_ids: list[str]


class RefreshTrackRequest(BaseModel):
    artist: str | None = None
    track: str | None = None
    album: str | None = None


def _build_link_response(spotify_track_id: str, row: YouTubeDownload | None) -> Dict[str, Any]:
    if not row or not _is_valid_youtube_video_id(row.youtube_video_id):
        return {
            "spotify_track_id": spotify_track_id,
            "youtube_video_id": None,
            "youtube_url": None,
            "status": "missing",
        }
    return {
        "spotify_track_id": spotify_track_id,
        "youtube_video_id": row.youtube_video_id,
        "youtube_url": f"https://www.youtube.com/watch?v={row.youtube_video_id}",
        "status": row.download_status or "link_found",
    }


async def _get_best_download_row(session: AsyncSession, spotify_track_id: str) -> YouTubeDownload | None:
    rows = (await session.exec(
        select(YouTubeDownload)
        .where(YouTubeDownload.spotify_track_id == spotify_track_id)
        .order_by(YouTubeDownload.updated_at.desc())
    )).all()
    if not rows:
        return None
    for row in rows:
        if _is_valid_youtube_video_id(row.youtube_video_id):
            return row
    return rows[0]


@router.post("/links")
async def get_track_links_batch(
    payload: BatchLinksRequest,
    request: Request,
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Return YouTube link status for a batch of Spotify track IDs."""
    _ = getattr(request.state, "user_id", None)
    items = []
    for spotify_track_id in payload.spotify_track_ids[:500]:
        row = await _get_best_download_row(session, spotify_track_id)
        items.append(_build_link_response(spotify_track_id, row))
    return {"items": items}


@router.get("/track/{spotify_track_id}/link")
async def get_track_youtube_link(
    spotify_track_id: str,
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Get current cached YouTube link for a track."""
    row = await _get_best_download_row(session, spotify_track_id)
    return _build_link_response(spotify_track_id, row)


@router.post("/track/{spotify_track_id}/refresh")
async def refresh_track_youtube_link(
    spotify_track_id: str,
    payload: RefreshTrackRequest | None = None,
    artist: str | None = Query(default=None),
    track: str | None = Query(default=None),
    album: str | None = Query(default=None),
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """
    Refresh YouTube link for a track:
    1) Prefer existing DB link
    2) Search YouTube by artist/track (from query or DB)
    3) Persist link in YouTubeDownload
    """
    existing = await _get_best_download_row(session, spotify_track_id)
    if existing and _is_valid_youtube_video_id(existing.youtube_video_id):
        return _build_link_response(spotify_track_id, existing)

    track_row = (await session.exec(select(Track).where(Track.spotify_id == spotify_track_id))).first()
    artist_name = artist or (payload.artist if payload else None)
    track_name = track or (payload.track if payload else None)
    album_name = album or (payload.album if payload else None)
    artist_spotify_id = ""

    if track_row:
        if not track_name:
            track_name = track_row.name
        artist_row = (await session.exec(select(Artist).where(Artist.id == track_row.artist_id))).first()
        album_row = (
            (await session.exec(select(Album).where(Album.id == track_row.album_id))).first()
            if track_row.album_id
            else None
        )
        if artist_row:
            artist_name = artist_name or artist_row.name
            artist_spotify_id = artist_row.spotify_id or ""
        if album_row:
            album_name = album_name or album_row.name

    if not artist_name or not track_name:
        return {
            "spotify_track_id": spotify_track_id,
            "youtube_video_id": None,
            "youtube_url": None,
            "status": "missing",
            "error_message": "Missing artist/track metadata",
        }

    try:
        videos = await youtube_client.search_music_videos(
            artist=artist_name,
            track=track_name,
            album=album_name,
            max_results=5,
        )
    except Exception as exc:
        logger.warning("YouTube refresh failed for %s: %s", spotify_track_id, exc)
        return {
            "spotify_track_id": spotify_track_id,
            "youtube_video_id": None,
            "youtube_url": None,
            "status": "error",
            "error_message": str(exc),
        }

    if not videos:
        return {
            "spotify_track_id": spotify_track_id,
            "youtube_video_id": None,
            "youtube_url": None,
            "status": "missing",
        }

    best = videos[0]
    video_id = best.get("video_id") or best.get("id")
    if not video_id:
        return {
            "spotify_track_id": spotify_track_id,
            "youtube_video_id": None,
            "youtube_url": None,
            "status": "missing",
        }

    now = datetime.utcnow()
    row = existing
    if not row:
        row = YouTubeDownload(
            spotify_track_id=spotify_track_id,
            spotify_artist_id=artist_spotify_id,
            youtube_video_id=video_id,
            download_path="",
            download_status="link_found",
            format_type="m4a",
        )
    else:
        row.youtube_video_id = video_id
        row.download_status = "link_found"
    row.updated_at = now
    session.add(row)
    await session.commit()

    return _build_link_response(spotify_track_id, row)
