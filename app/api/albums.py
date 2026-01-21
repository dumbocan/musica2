"""
Album endpoints: tracks, save to DB, etc.
"""

import ast
import json
import logging
import asyncio
from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.spotify import spotify_client
from ..core.config import settings
from ..core.lastfm import lastfm_client
from ..core.image_proxy import proxy_image_list
from ..crud import save_album, save_track, delete_album
from ..core.db import get_session
from ..models.base import Album, Artist, Track
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/albums", tags=["albums"])


async def _safe_timed(label: str, coro, timeout: float, default):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception as exc:
        logger.warning("%s failed after %ss: %r", label, timeout, exc, exc_info=True)
        return default


async def _backfill_album_tracks(spotify_id: str, album_id: int, artist_id: int) -> None:
    try:
        tracks = await spotify_client.get_album_tracks(spotify_id)
    except Exception as exc:
        logger.warning("Spotify album tracks backfill failed for %s: %r", spotify_id, exc, exc_info=True)
        return
    for track_data in tracks:
        try:
            save_track(track_data, album_id, artist_id)
        except Exception as exc:
            logger.warning(
                "Track save failed for album %s (%s): %r",
                spotify_id,
                track_data.get("id"),
                exc,
            )


@router.get("/spotify/{spotify_id}")
async def get_album_from_spotify(spotify_id: str = Path(..., description="Spotify album ID")):
    """Get album details and tracks directly from Spotify."""
    album_payload = None
    with get_session() as session:
        local_album = session.exec(select(Album).where(Album.spotify_id == spotify_id)).first()
        if local_album:
            artist = session.exec(select(Artist).where(Artist.id == local_album.artist_id)).first()
            if artist and artist.is_hidden:
                raise HTTPException(status_code=404, detail="Album not found")
            tracks = session.exec(select(Track).where(Track.album_id == local_album.id)).all()
            album_payload = _album_from_local(local_album, artist, tracks)
            if tracks:
                return album_payload
            # No tracks locally; backfill in background to keep UI fast
            if settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET:
                asyncio.create_task(_backfill_album_tracks(spotify_id, local_album.id, local_album.artist_id))
            return album_payload

    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return album_payload if album_payload is not None else {}
    try:
        tracks_timeout = 12.0
        album_timeout = 10.0
        if local_album and album_payload:
            tracks = await _safe_timed(
                "Spotify album tracks fetch",
                spotify_client.get_album_tracks(spotify_id),
                tracks_timeout,
                [],
            )
            if tracks:
                album_payload["tracks"] = tracks
                for track_data in tracks:
                    save_track(track_data, local_album.id, local_album.artist_id)
            return album_payload

        album_task = asyncio.create_task(
            _safe_timed(
                "Spotify album fetch",
                spotify_client.get_album(spotify_id),
                album_timeout,
                None,
            )
        )
        tracks_task = asyncio.create_task(
            _safe_timed(
                "Spotify album tracks fetch",
                spotify_client.get_album_tracks(spotify_id),
                tracks_timeout,
                [],
            )
        )
        album = await album_task
        if not album:
            raise HTTPException(status_code=504, detail="Spotify album lookup timed out")
        tracks = await tracks_task
        if tracks:
            album["tracks"] = tracks
        album["images"] = proxy_image_list(album.get("images", []), size=512)
        # Enrich with Last.fm wiki if possible
        try:
            artist_name = (album.get("artists") or [{}])[0].get("name")
            album_name = album.get("name")
            if artist_name and album_name and settings.LASTFM_API_KEY:
                lfm_info = await _safe_timed(
                    "Last.fm album info",
                    lastfm_client.get_album_info(artist_name, album_name),
                    6.0,
                    {},
                )
                album["lastfm"] = lfm_info
        except Exception:
            album["lastfm"] = {}
        if local_album and tracks:
            for track_data in tracks:
                save_track(track_data, local_album.id, local_album.artist_id)
        return album
    except HTTPException:
        raise
    except Exception as e:
        if album_payload is not None:
            return album_payload
        raise HTTPException(status_code=500, detail=f"Error fetching album from Spotify: {e}")


@router.get("/{spotify_id}/tracks")
async def get_album_tracks(spotify_id: str = Path(..., description="Spotify album ID")) -> List[dict]:
    """Get all tracks for an album via Spotify API."""
    local_album = None
    with get_session() as session:
        local_album = session.exec(select(Album).where(Album.spotify_id == spotify_id)).first()
        if local_album:
            artist = session.exec(select(Artist).where(Artist.id == local_album.artist_id)).first()
            if artist and artist.is_hidden:
                return []
            tracks = session.exec(select(Track).where(Track.album_id == local_album.id)).all()
            if tracks:
                return [_track_from_local(track, artist) for track in tracks]
    try:
        tracks = await _safe_timed(
            "Spotify album tracks fetch",
            spotify_client.get_album_tracks(spotify_id),
            12.0,
            [],
        )
    except Exception as exc:
        logger.warning("Spotify album tracks fetch failed for %s: %r", spotify_id, exc, exc_info=True)
        return []

    if local_album and tracks:
        for track_data in tracks:
            save_track(track_data, local_album.id, local_album.artist_id)
    return tracks


@router.post("/save/{spotify_id}")
async def save_album_to_db(spotify_id: str = Path(..., description="Spotify album ID")):
    """Fetch album and tracks from Spotify and save to DB."""
    album_data = await spotify_client._make_request(f"/albums/{spotify_id}")
    if not album_data:
        raise HTTPException(status_code=404, detail="Album not found on Spotify")
    # Fetch tracks
    tracks_data = await spotify_client.get_album_tracks(spotify_id)
    album = save_album(album_data)

    from ..crud import save_track
    artist_id = album.artist_id

    for track_data in tracks_data:
        save_track(track_data, album.id, artist_id)

    return {"message": "Album and tracks saved to DB", "album": album.dict(), "tracks_saved": len(tracks_data)}


@router.get("/")
def get_albums() -> List[Album]:
    """Get all saved albums from DB."""
    with get_session() as session:
        albums = session.exec(
            select(Album)
            .join(Artist, Album.artist_id == Artist.id)
            .where(Artist.is_hidden.is_(False))
        ).all()
    return albums


@router.delete("/id/{album_id}")
def delete_album_endpoint(album_id: int = Path(..., description="Local album ID")):
    """Delete album unless favorited."""
    try:
        ok = delete_album(album_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Album not found")
        return {"message": "Album deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/id/{album_id}")
def get_album(album_id: int = Path(..., description="Local album ID")) -> Album:
    """Get single album by local ID."""
    with get_session() as session:
        album = session.exec(
            select(Album)
            .join(Artist, Album.artist_id == Artist.id)
            .where(Album.id == album_id)
            .where(Artist.is_hidden.is_(False))
        ).first()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
    return album


def _parse_images_field(raw) -> list:
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


def _track_from_local(track: Track, artist: Artist | None) -> dict:
    return {
        "id": track.spotify_id or str(track.id),
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "external_urls": {"spotify": track.external_url} if track.external_url else {},
        "artists": [{"name": artist.name}] if artist else [],
    }


def _album_from_local(album: Album, artist: Artist | None, tracks: list[Track]) -> dict:
    images = proxy_image_list(_parse_images_field(album.images), size=512)
    payload = {
        "id": album.spotify_id or str(album.id),
        "name": album.name,
        "release_date": album.release_date,
        "images": images,
        "artists": [{"name": artist.name}] if artist else [],
    }
    if tracks:
        payload["tracks"] = [_track_from_local(track, artist) for track in tracks]
    else:
        payload["tracks"] = []
    return payload
