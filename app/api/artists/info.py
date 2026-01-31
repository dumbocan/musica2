"""
Artist information and details endpoints.
Migrated from original artists.py for better modularity.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ...core.db import get_session, SessionDep
from ...core.spotify import spotify_client
from ...core.lastfm import lastfm_client
from ...models.base import Artist, Track
from ...core.config import settings
from ...core.image_proxy import proxy_image_list, has_valid_images
from ...core.time_utils import utc_now
from ...services.library_expansion import schedule_artist_expansion

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/info", tags=["artists"])
ARTIST_REFRESH_DAYS = 7


@router.get("/{spotify_id}/info")
async def get_artist_info(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Get artist info from Spotify + Last.fm bio/tags/listeners (no DB write)."""
    local_artist = (await session.exec(
        select(Artist).where(Artist.spotify_id == spotify_id)
    )).first()
    spotify_data = None
    local_images = _parse_images_field(local_artist.images) if local_artist else []
    local_images_ok = has_valid_images(local_images)
    local_payload = None
    if local_artist:
        local_payload = {
            "id": local_artist.spotify_id,
            "name": local_artist.name,
            "images": proxy_image_list(local_images, size=384),
            "followers": {"total": local_artist.followers or 0},
            "popularity": local_artist.popularity or 0,
            "genres": _parse_genres_field(local_artist.genres),
            "image_path_id": local_artist.image_path_id,
        }
        if local_images_ok:
            spotify_data = local_payload
    else:
        try:
            spotify_data = await asyncio.wait_for(
                spotify_client.get_artist(spotify_id),
                timeout=6.0,
            )
        except Exception as exc:
            logger.warning("Spotify artist fetch failed for %s: %r", spotify_id, exc, exc_info=True)

        if not spotify_data:
            raise HTTPException(status_code=404, detail="Artist not found on Spotify")

        try:
            spotify_data["images"] = proxy_image_list(spotify_data.get("images", []), size=384)
        except Exception:
            pass
    if not spotify_data and local_payload:
        spotify_data = local_payload

    lastfm_data = {}
    try:
        name = spotify_data.get("name")
        if name:
            if local_artist and (local_artist.bio_summary or local_artist.bio_content):
                lastfm_data = {
                    "summary": local_artist.bio_summary or "",
                    "content": local_artist.bio_content or "",
                    "stats": {},
                    "tags": _parse_genres_field(local_artist.genres),
                    "images": [],
                }
            else:
                lastfm_data = await lastfm_client.get_artist_info(name)
    except Exception as exc:
        logger.warning("[artist_info] lastfm fetch failed for %s: %s", spotify_id, exc)
        lastfm_data = {}

    # Persist artist/albums/tracks in background when stale (best effort)
    try:
        needs_refresh = not local_artist
        if local_artist:
            stale_at = local_artist.last_refreshed_at
            needs_refresh = (
                not stale_at
                or (utc_now() - stale_at) > timedelta(days=ARTIST_REFRESH_DAYS)
                or not local_images_ok
            )
        if spotify_data and needs_refresh:
            schedule_artist_expansion(
                spotify_artist_id=spotify_data.get("id"),
                artist_name=spotify_data.get("name") or "",
                include_youtube_links=True,
            )
    except Exception:
        pass

    return {
        "spotify": spotify_data,
        "lastfm": lastfm_data
    }


@router.get("/{spotify_id}/recommendations")
async def get_artist_recommendations(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations"),
) -> Dict[str, Any]:
    """Get music recommendations based on artist (tracks and artists)."""
    recommendations = await spotify_client.get_recommendations(seed_artists=[spotify_id], limit=limit)
    return recommendations


@router.get("/{spotify_id}/related")
async def get_related_artists(
    spotify_id: str = Path(..., description="Spotify artist ID"),
) -> Dict[str, Any]:
    """Get related artists using Last.fm (with listeners/playcount) enriched with Spotify search."""
    if not settings.LASTFM_API_KEY:
        return {"top": [], "discover": []}

    # Get main artist name to feed Last.fm
    try:
        main_artist = await spotify_client.get_artist(spotify_id)
        main_name = main_artist.get("name") if main_artist else None
    except Exception:
        main_name = None

    if not main_name:
        return {"top": [], "discover": []}

    top = []
    discover = []

    # Related artists using Last.fm names, enriched with Spotify search (fast-ish)
    try:
        similar = await asyncio.wait_for(lastfm_client.get_similar_artists(main_name, limit=8), timeout=5.0)
    except Exception as exc:
        logger.warning("[related] Last.fm similar failed for %s: %s", main_name, exc)
        similar = []

    for s in similar:
        name = s.get("name")
        if not name:
            continue

        spotify_match = None
        try:
            found = await spotify_client.search_artists(name, limit=1)
            if found:
                spotify_match = found[0]
        except Exception:
            pass

        followers = spotify_match.get("followers", {}).get("total", 0) if spotify_match else 0
        if followers < 1_000_000:
            continue

        listeners = None
        playcount = None
        tags = []
        bio = ""
        try:
            info = await asyncio.wait_for(lastfm_client.get_artist_info(name), timeout=3.0)
            stats = info.get("stats", {}) or {}
            listeners = int(stats.get("listeners", 0) or 0)
            playcount = int(stats.get("playcount", 0) or 0)
            tags = info.get("tags", [])
            bio = info.get("summary", "") or ""
        except Exception:
            pass

        entry = {
            "name": name,
            "listeners": listeners,
            "playcount": playcount,
            "tags": tags,
            "bio": bio,
            "spotify": spotify_match
        }

        # Deduplicate by Spotify ID
        already = [a for a in top + discover if a.get("spotify", {}).get("id") == (spotify_match or {}).get("id")]
        if already:
            continue

        top.append(entry)

        if len(top) >= 12:
            break

    return {"top": top, "discover": discover}


@router.get("/id/{artist_id}")
async def get_artist_by_id(
    artist_id: int = Path(..., description="Local artist ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Artist:
    """Get artist by local ID."""
    with get_session() as sync_session:
        artist = sync_session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")
    return artist


@router.delete("/id/{artist_id}")
async def delete_artist(
    artist_id: int = Path(..., description="Local artist ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Delete artist by local ID."""
    from ...crud import delete_artist as delete_artist_db
    try:
        ok = delete_artist_db(artist_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Artist not found")
        return {"message": "Artist and related data deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/spotify/{spotify_id}/local")
async def get_local_artist_by_spotify_id(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Artist | None:
    """Get the locally stored artist by Spotify ID."""
    artist = (await session.exec(select(Artist).where(Artist.spotify_id == spotify_id))).first()
    return artist


@router.get("/id/{artist_id}/discography")
async def get_artist_discography_by_id(
    artist_id: int = Path(..., description="Local artist ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist with full discography: albums + tracks from DB."""
    artist = (await session.exec(
        select(Artist)
        .where(Artist.id == artist_id)
        .options(selectinload(Artist.albums))
    )).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # For each album, load tracks
    discography = {
        "artist": artist.dict(),
        "albums": []
    }
    for album in artist.albums:
        album_data = album.dict()
        tracks = (await session.exec(select(Track).where(Track.album_id == album.id))).all()
        album_data["tracks"] = [track.dict() for track in tracks]
        discography["albums"].append(album_data)

    return discography


def _parse_images_field(raw) -> list:
    """Parse images field from JSON or string format."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    import json
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        import ast
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return []


def _parse_genres_field(raw) -> list:
    """Parse genres field from JSON or string format."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [g.strip() for g in raw if isinstance(g, str) and g.strip()]
    import json
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    if isinstance(raw, str) and "," in raw:
        return [g.strip() for g in raw.split(",") if g.strip()]
    return []
