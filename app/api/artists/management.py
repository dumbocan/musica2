"""
Artist management and CRUD endpoints.
Migrated from original artists.py for better modularity.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy import asc, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from ...core.db import get_session, SessionDep
from ...core.spotify import spotify_client
from ...core.lastfm import lastfm_client
from ...models.base import Artist, Track
from ...core.config import settings
from ...core.genre_backfill import (
    derive_genres_from_artist_tags,
    derive_genres_from_tracks,
    extract_genres_from_lastfm_tags,
)
from ...core.time_utils import utc_now
from ...services.data_quality import collect_artist_quality_report
from ...core.action_status import set_action_status

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/management", tags=["artists"])


@router.post("/save/{spotify_id}")
async def save_artist_to_db(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Fetch artist from Spotify and save to DB."""
    from ...crud import save_artist
    artist_data = await spotify_client.get_artist(spotify_id)
    if not artist_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")
    artist = await asyncio.to_thread(save_artist, artist_data)
    return {"message": "Artist saved to DB", "artist": artist.dict()}


@router.post("/{spotify_id}/sync-discography")
async def sync_artist_discography(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Sync artist's discography: fetch and save new albums/tracks from Spotify."""
    from ...crud import save_album
    artist = (await session.exec(select(Artist).where(Artist.spotify_id == spotify_id))).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not saved locally")

    # Fetch all albums
    albums_data = await spotify_client.get_artist_albums(
        spotify_id,
        include_groups="album,single,compilation",
        fetch_all=True,
    )

    synced_albums = 0
    for album_data in albums_data:
        album = await save_album(album_data)
        if not album.spotify_id:
            synced_albums += 1

    return {"message": "Discography synced", "albums_processed": len(albums_data), "synced_albums": synced_albums}


@router.post("/refresh-genres")
async def refresh_artist_genres(
    limit: int = Query(50, ge=1, le=500, description="Artists to refresh"),
    tracks_per_artist: int = Query(3, ge=1, le=10, description="Tracks to sample per artist"),
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Backfill missing genres using Last.fm track tags."""
    if not settings.LASTFM_API_KEY:
        raise HTTPException(status_code=503, detail="LASTFM_API_KEY not configured")

    def parse_genres(raw):
        if not raw:
            return []
        if isinstance(raw, list):
            return [g.strip() for g in raw if isinstance(g, str) and g.strip()]
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        if isinstance(raw, str) and "," in raw:
            return [g.strip() for g in raw.split(",") if g.strip()]
        return []

    statement = select(Artist).order_by(desc(Artist.popularity), asc(Artist.id)).limit(limit)
    artists = (await session.exec(statement)).all()
    scanned = 0
    updated = 0
    for artist in artists:
        scanned += 1
        if parse_genres(artist.genres):
            continue
        track_rows = (await session.exec(
            select(Track.name)
            .where(Track.artist_id == artist.id)
            .order_by(desc(Track.popularity), asc(Track.id))
            .limit(tracks_per_artist)
        )).all()
        track_names = [row[0] for row in track_rows if row and row[0]]
        genres = await derive_genres_from_tracks(artist.name, track_names)
        if not genres:
            genres = await derive_genres_from_artist_tags(artist.name)
        if not genres:
            continue
        artist.genres = json.dumps(genres)
        artist.last_refreshed_at = utc_now()
        session.add(artist)
        updated += 1
    if updated:
        await session.commit()
    return {"scanned": scanned, "updated": updated}


@router.post("/refresh-missing")
async def refresh_missing_artist_metadata(
    limit: int = Query(50, ge=1, le=500, description="Artists to scan for missing data"),
    use_spotify: bool = Query(True, description="Attempt Spotify refresh when IDs exist"),
    use_lastfm: bool = Query(True, description="Fill missing bio/genres/images from Last.fm"),
) -> Dict[str, Any]:
    """Backfill missing artist metadata (bio/genres/images) and refresh from Spotify when possible."""
    from ...core.maintenance import maintenance_stop_requested
    missing_report = collect_artist_quality_report(limit=limit)
    set_action_status('metadata_refresh', True)
    try:
        spotify_updated = 0
        lastfm_updated = 0
        skipped = 0

        for entry in missing_report:
            if maintenance_stop_requested():
                logger.info("[refresh-missing] stop requested, aborting")
                break
            spotify_id = entry.get("spotify_id")
            if use_spotify and spotify_id:
                try:
                    data = await spotify_client.get_artist(spotify_id)
                    if data:
                        from ...crud import save_artist
                        save_artist(data)
                        spotify_updated += 1
                except Exception as exc:
                    logger.warning(
                        "[refresh-missing] Spotify refresh failed for %s: %r",
                        entry.get("name") or spotify_id,
                        exc,
                        exc_info=True
                    )

            if not use_lastfm or not entry.get("name"):
                skipped += 1
                continue

            with get_session() as session:
                artist = session.exec(select(Artist).where(Artist.id == entry["id"])).first()
            if not artist:
                skipped += 1
                continue

            missing_fields = set()
            if not artist.bio_summary:
                missing_fields.add("bio")
            if not artist.genres or artist.genres.strip() in {"", "[]"}:
                missing_fields.add("genres")
            if not artist.images or artist.images.strip() in {"", "[]"}:
                missing_fields.add("image")

            if not missing_fields:
                skipped += 1
                continue

            try:
                lastfm = await lastfm_client.get_artist_info(entry["name"])
            except Exception as exc:
                logger.warning(
                    "[refresh-missing] Last.fm fetch failed for %s: %r",
                    entry.get("name"),
                    exc,
                    exc_info=True
                )
                continue

            summary = lastfm.get("summary")
            tags = lastfm.get("tags")
            from ...core.image_proxy import proxy_image_list
            images = lastfm.get("images")
            proxied_images = None
            if "image" in missing_fields and images:
                proxied = proxy_image_list(images, size=384)
                if proxied:
                    proxied_images = proxied

            with get_session() as session:
                target = session.exec(select(Artist).where(Artist.id == entry["id"])).first()
                if not target:
                    skipped += 1
                    continue

                needs_commit = False
                if "bio" in missing_fields and summary:
                    target.bio_summary = summary
                    target.bio_content = lastfm.get("content", target.bio_content)
                    needs_commit = True
                if "genres" in missing_fields and tags:
                    genres = extract_genres_from_lastfm_tags(tags, artist_name=entry["name"])
                    if genres:
                        target.genres = json.dumps(genres)
                        needs_commit = True
                if proxied_images:
                    target.images = json.dumps(proxied_images)
                    needs_commit = True

                if needs_commit:
                    now = utc_now()
                    target.updated_at = now
                    target.last_refreshed_at = now
                    session.add(target)
                    session.commit()
                    lastfm_updated += 1

    except Exception as exc:
        logger.error("[refresh-missing] unexpected error: %r", exc, exc_info=True)
        raise

    finally:
        set_action_status('metadata_refresh', False)

    return {
        "scanned": len(missing_report),
        "spotify_updated": spotify_updated,
        "lastfm_updated": lastfm_updated,
        "skipped": skipped
    }


@router.post("/id/{artist_id}/hide")
async def hide_artist_for_user_endpoint(
    artist_id: int = Path(..., description="Local artist ID"),
    user_id: int = Query(..., ge=1, description="User ID"),
) -> Dict[str, Any]:
    """Hide an artist for the specified user."""
    from ...crud import hide_artist_for_user
    try:
        hidden = hide_artist_for_user(user_id, artist_id)
        return {"message": "Artist hidden", "hidden": hidden.dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/id/{artist_id}/hide")
async def unhide_artist_for_user_endpoint(
    artist_id: int = Path(..., description="Local artist ID"),
    user_id: int = Query(..., ge=1, description="User ID"),
) -> Dict[str, Any]:
    """Remove user-specific hidden flag."""
    from ...crud import unhide_artist_for_user
    removed = unhide_artist_for_user(user_id, artist_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Hidden artist entry not found")
    return {"message": "Artist unhidden"}
