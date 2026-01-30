"""
Artist discography and album endpoints.
Migrated from original artists.py for better modularity.
"""

import asyncio
import json
import ast
import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Path, Request
from sqlalchemy import desc, asc, func, exists
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ...core.db import get_session, SessionDep
from ...core.spotify import spotify_client
from ...models.base import Artist, Album, Track, YouTubeDownload
from ...core.config import settings
from ...core.image_proxy import proxy_image_list, has_valid_images
from ...core.time_utils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discography", tags=["artists"])
ARTIST_REFRESH_DAYS = 7


def _parse_images_field(raw) -> list:
    """Parse images field from JSON or string format."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return []


@router.get("/{spotify_id}/albums")
async def get_artist_albums(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    refresh: bool = Query(False, description="Force refresh from Spotify if available"),
    session: AsyncSession = Depends(SessionDep),
) -> List[dict]:
    """Get all albums for an artist via Spotify API."""
    artist = (await session.exec(
        select(Artist).where(Artist.spotify_id == spotify_id)
    )).first()
    albums: list[dict] = []
    local_count = 0
    if artist:
        local_albums = (await session.exec(
            select(Album)
            .where(Album.artist_id == artist.id)
            .order_by(desc(Album.release_date), asc(Album.id))
        )).all()
        for album in local_albums:
            if not album.spotify_id:
                continue
            images = _parse_images_field(album.images)
            albums.append({
                "id": album.spotify_id,
                "name": album.name,
                "release_date": album.release_date,
                "total_tracks": album.total_tracks,
                "images": proxy_image_list(images, size=384),
                "label": album.label,
                "artists": [{"id": artist.spotify_id, "name": artist.name}] if artist.spotify_id else [{"name": artist.name}],
                "image_path_id": album.image_path_id,
                "local_id": album.id,
            })
        local_count = len(albums)

    if refresh:
        asyncio.create_task(_refresh_artist_albums(spotify_id))

    needs_spotify = not albums
    if not refresh and artist and not needs_spotify and local_count:
        try:
            total = await asyncio.wait_for(
                spotify_client.get_artist_albums_total(
                    spotify_id,
                    include_groups="album,single,compilation",
                ),
                timeout=3.0,
            )
            if total is not None and total > local_count:
                needs_spotify = True
        except Exception as exc:
            logger.info(
                "Spotify albums total check failed for %s: %r",
                spotify_id,
                exc,
                exc_info=True,
            )

    if needs_spotify:
        try:
            spotify_albums = await asyncio.wait_for(
                spotify_client.get_artist_albums(
                    spotify_id,
                    include_groups="album,single,compilation",
                    fetch_all=not refresh,
                ),
                timeout=10.0,
            )
        except Exception as exc:
            logger.warning("Spotify albums fetch failed for %s: %r", spotify_id, exc, exc_info=True)
            spotify_albums = []
        if spotify_albums:
            albums = spotify_albums
            asyncio.create_task(_persist_albums(spotify_albums))

    if artist:
        stale_at = artist.last_refreshed_at
        if not stale_at or (utc_now() - stale_at) > timedelta(days=ARTIST_REFRESH_DAYS):
            try:
                from ...services.library_expansion import save_artist_discography
                asyncio.create_task(save_artist_discography(spotify_id))
            except Exception:
                pass
    album_ids = [album.get("id") for album in albums if album.get("id")]

    counts: dict[str, int] = {}
    local_tracks: dict[str, set[str]] = {}
    downloaded_tracks: set[str] = set()

    if album_ids:
        rows = (await session.exec(
            select(
                Album.spotify_id,
                func.count(func.distinct(YouTubeDownload.spotify_track_id)).label("link_count"),
            )
            .join(Track, Track.album_id == Album.id)
            .join(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            .where(
                Album.spotify_id.in_(album_ids),
                YouTubeDownload.youtube_video_id.is_not(None),
                YouTubeDownload.youtube_video_id != "",
                YouTubeDownload.download_status.in_(("link_found", "completed")),
            )
            .group_by(Album.spotify_id)
        )).all()
        counts = {album_spotify_id: int(count) for album_spotify_id, count in rows}

        local_rows = (await session.exec(
            select(Album.spotify_id, Track.spotify_id)
            .join(Track, Track.album_id == Album.id)
            .where(
                Album.spotify_id.in_(album_ids),
                Track.spotify_id.is_not(None),
            )
        )).all()
        for album_spotify_id, track_spotify_id in local_rows:
            if track_spotify_id:
                local_tracks.setdefault(album_spotify_id, set()).add(track_spotify_id)

        download_rows = (await session.exec(
            select(YouTubeDownload.spotify_track_id)
            .where(
                YouTubeDownload.spotify_artist_id == spotify_id,
                YouTubeDownload.youtube_video_id.is_not(None),
                YouTubeDownload.youtube_video_id != "",
                YouTubeDownload.download_status.in_(("link_found", "completed")),
            )
        )).all()
        downloaded_tracks = {row[0] for row in download_rows if row[0]}

    for album in albums:
        album_id = album.get("id")
        if not album_id:
            continue
        album["images"] = proxy_image_list(album.get("images", []), size=384)

        current_count = counts.get(album_id, 0)

        if downloaded_tracks and current_count < len(downloaded_tracks):
            track_ids = local_tracks.get(album_id)
            if not track_ids:
                continue
            matched = sum(1 for tid in track_ids if tid in downloaded_tracks)
            if matched > current_count:
                current_count = matched
                counts[album_id] = matched

        album["youtube_links_available"] = current_count

    return albums


async def _persist_albums(albums_data: list[dict]) -> None:
    """Persist albums to database."""
    from ...crud import save_album

    for album_data in albums_data:
        try:
            await save_album(album_data)
        except Exception as exc:
            logger.warning(
                "Failed to persist album %s: %r",
                album_data.get("id") if isinstance(album_data, dict) else None,
                exc,
                exc_info=True,
            )


async def _refresh_artist_albums(spotify_id: str) -> None:
    """Refresh artist albums from Spotify."""
    try:
        albums_data = await spotify_client.get_artist_albums(
            spotify_id,
            include_groups="album,single,compilation",
            fetch_all=True,
        )
    except Exception as exc:
        logger.warning(
            "Spotify albums refresh failed for %s: %r",
            spotify_id,
            exc,
            exc_info=True,
        )
        return

    if not albums_data:
        return
    await _persist_albums(albums_data)