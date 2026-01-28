"""
Artist endpoints: search, discography, etc.
"""

import asyncio
import logging
import json
import ast
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, format_datetime
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Query, Path, HTTPException, BackgroundTasks, Depends, Request, Response
from sqlalchemy import desc, asc, func, exists
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sqlalchemy.orm import selectinload

from ..core.spotify import spotify_client
from ..crud import (
    save_artist,
    delete_artist,
    update_artist_bio,
    hide_artist_for_user,
    unhide_artist_for_user,
)
from ..core.db import get_session, SessionDep
from ..models.base import Artist, Album, Track, YouTubeDownload, UserHiddenArtist, UserFavorite, FavoriteTargetType
from ..core.lastfm import lastfm_client
from ..core.genre_backfill import (
    derive_genres_from_artist_tags,
    derive_genres_from_tracks,
    extract_genres_from_lastfm_tags,
)
from ..core.time_utils import utc_now
from ..core.auto_download import auto_download_service
from ..core.data_freshness import data_freshness_manager
from ..core.image_proxy import proxy_image_list, has_valid_images
from ..services.data_quality import collect_artist_quality_report
from ..services.library_expansion import schedule_artist_expansion
from ..core.action_status import set_action_status
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["artists"])
ARTIST_REFRESH_DAYS = 7
_ARTISTS_CACHE_TTL_SECONDS = 120
_ARTISTS_CACHE: dict[str, dict] = {}


@router.get("/search")
async def search_artists(q: str = Query(..., description="Artist name to search")) -> List[dict]:
    """Search for artists by name using Spotify API."""
    try:
        artists = await spotify_client.search_artists(q)
        return artists
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Spotify search failed: {e}")


@router.get("/search-auto-download")
async def search_artists_auto_download(
    q: str = Query(..., description="Artist name to search"),
    user_id: int = Query(1, description="User ID for personalized recommendations"),
    expand_library: bool = Query(True, description="Auto-expand with similar artists"),
    include_youtube_links: bool = Query(False, description="Buscar links de YouTube durante la expansión"),
    auto_download_top_tracks: bool = Query(False, description="Descargar top tracks automáticamente (YouTube)"),
    background_tasks: BackgroundTasks = None
) -> dict:
    """
    Search for artists by name using Spotify API.

    NEW: Automatically expands library with 10 similar artists + 5 tracks each!
    """
    artists = await spotify_client.search_artists(q)

    # Check if we have results
    if artists and len(artists) > 0:
        first_artist = artists[0]  # Take the best match
        artist_spotify_id = first_artist.get('id')
        artist_name = first_artist.get('name')

        # RECORD USER SEARCH FOR ALGORITHM LEARNING
        try:
            from ..crud import record_artist_search
            record_artist_search(user_id, artist_name)
            logger.info(f"📝 Recorded artist search for user {user_id}: {artist_name}")
        except Exception as e:
            logger.warning(f"Failed to record artist search: {e}")

        if artist_spotify_id:
            expansion_results = None

            # NEW: Auto-expand library with similar artists
            if expand_library:
                logger.info(f"🚀 Expanding library for user {user_id} from artist {artist_name}")
                expansion_results = await data_freshness_manager.expand_user_library_from_full_discography(
                    main_artist_name=artist_name,
                    main_artist_spotify_id=artist_spotify_id,
                    similar_count=8,  # 8 similar artists
                    tracks_per_artist=8,  # Will save ALL tracks from ALL albums
                    include_youtube_links=include_youtube_links,  # Find YouTube links for all tracks
                    include_full_albums=True  # Save complete discography with artwork
                )

            # Optional: trigger downloads for the main artist
            if auto_download_top_tracks:
                await auto_download_service.auto_download_artist_top_tracks(
                    artist_name=artist_name,
                    artist_spotify_id=artist_spotify_id,
                    limit=3,  # Download top 3 tracks for testing
                    background_tasks=background_tasks
                )

            # Return enhanced response with expansion results
            return {
                "query": q,
                "user_id": user_id,
                "artists": artists,
                "main_artist_processed": {
                    "name": artist_name,
                    "spotify_id": artist_spotify_id,
                    "followers": first_artist.get('followers', {}).get('total', 0)
                },
                "library_expansion": expansion_results,
                "expand_library": expand_library
            }

    # No artists found
    return {
        "query": q,
        "user_id": user_id,
        "artists": artists,
        "library_expansion": None,
        "message": "No artists found for library expansion"
    }

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
                from ..services.library_expansion import save_artist_discography
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


@router.post("/save/{spotify_id}")
async def save_artist_to_db(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Fetch artist from Spotify and save to DB."""
    artist_data = await spotify_client.get_artist(spotify_id)
    if not artist_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")
    artist = await asyncio.to_thread(save_artist, artist_data)
    return {"message": "Artist saved to DB", "artist": artist.dict()}


@router.post("/{spotify_id}/sync-discography")
async def sync_artist_discography(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """Sync artist's discography: fetch and save new albums/tracks from Spotify."""
    artist = (await session.exec(select(Artist).where(Artist.spotify_id == spotify_id))).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not saved locally")

    # Fetch all albums
    albums_data = await spotify_client.get_artist_albums(
        spotify_id,
        include_groups="album,single,compilation",
        fetch_all=True,
    )

    from ..crud import save_album
    synced_albums = 0
    for album_data in albums_data:
        album = await save_album(album_data)
        # Since save_album saves tracks if album new, count
        if not album.spotify_id:  # If it was new, but since update, difficult to count
            synced_albums += 1

    return {"message": "Discography synced", "albums_processed": len(albums_data), "synced_albums": synced_albums}


@router.get("/{spotify_id}/full-discography")
async def get_full_discography(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get complete discography from Spotify: artist + albums + tracks."""
    # Get artist info
    artist_data = await spotify_client.get_artist(spotify_id)
    if not artist_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")

    # Get albums
    albums_data = await spotify_client.get_artist_albums(
        spotify_id,
        include_groups="album,single,compilation",
        fetch_all=True,
    )

    # For each album, get tracks
    discography = {
        "artist": artist_data,
        "albums": []
    }

    for album_data in albums_data:
        album_id = album_data['id']
        tracks_data = await spotify_client.get_album_tracks(album_id)
        album_data['tracks'] = tracks_data
        discography["albums"].append(album_data)

    return discography

@router.get("/{spotify_id}/info")
async def get_artist_info(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """Get artist info from Spotify + Last.fm bio/tags/listeners (no DB write)."""
    from ..core.lastfm import lastfm_client

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
        # Don't fail the request on Last.fm issues
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
async def get_artist_recommendations(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get music recommendations based on artist (tracks and artists)."""
    recommendations = await spotify_client.get_recommendations(seed_artists=[spotify_id], limit=20)
    return recommendations


@router.get("/{spotify_id}/related")
async def get_related_artists(spotify_id: str = Path(..., description="Spotify artist ID")):
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

    import asyncio

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


@router.get("/id/{artist_id}/discography")
def get_artist_discography(artist_id: int = Path(..., description="Local artist ID")):
    """Get artist with full discography: albums + tracks from DB."""
    with get_session() as session:
        # Get artist with albums
        artist = session.exec(
            select(Artist)
            .where(Artist.id == artist_id)
            .options(selectinload(Artist.albums))
        ).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

        # For each album, load tracks
        discography = {
            "artist": artist.dict(),
            "albums": []
        }
        for album in artist.albums:
            album_data = album.dict()
            tracks = session.exec(select(Track).where(Track.album_id == album.id)).all()
            album_data["tracks"] = [track.dict() for track in tracks]
            discography["albums"].append(album_data)

    return discography


@router.get("/spotify/{spotify_id}/local")
def get_artist_by_spotify(spotify_id: str) -> Artist | None:
    """Get the locally stored artist by Spotify ID."""
    with get_session() as session:
        artist = session.exec(select(Artist).where(Artist.spotify_id == spotify_id)).first()
        return artist


async def _persist_albums(albums_data: list[dict]) -> None:
    from ..crud import save_album

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


def _parse_genres_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return [g.strip() for g in raw if isinstance(g, str) and g.strip()]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
        except (ValueError, SyntaxError):
            return []
    if isinstance(raw, str) and "," in raw:
        return [g.strip() for g in raw.split(",") if g.strip()]
    return []


def _extract_url(entry) -> str | None:
    if isinstance(entry, dict):
        url = entry.get("url") or entry.get("#text")
    elif isinstance(entry, str):
        url = entry
    else:
        url = None
    return url if isinstance(url, str) else None


def _is_proxied_images(images: list) -> bool:
    if not images:
        return False
    return all((_extract_url(img) or "").startswith("/images/proxy") for img in images)




@router.get("/")
async def get_artists(
    request: Request,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    order: str = Query(
        "pop-desc",
        pattern="^(pop-desc|pop-asc|name-asc)$",
        description="Ordering for returned artists"
    ),
    search: str | None = Query(None, description="Filter by artist name"),
    genre: str | None = Query(None, description="Filter by genre keyword"),
    session: AsyncSession = Depends(SessionDep),
    user_id: int | None = Query(None, ge=1, description="User ID for hidden artist filtering"),
) -> dict:
    """Get saved artists with pagination, ordering, and ensure cached images are proxied."""
    order_by_map = {
        "pop-desc": [desc(Artist.popularity), asc(Artist.id)],
        "pop-asc": [asc(Artist.popularity), asc(Artist.id)],
        "name-asc": [asc(Artist.name), asc(Artist.id)]
    }
    order_by_clause = order_by_map.get(order, order_by_map["pop-desc"])
    effective_user_id = user_id or getattr(request.state, "user_id", None)
    cache_key = (
        f"user={effective_user_id or 'anon'}|offset={offset}|limit={limit}|order={order}"
        f"|search={(search or '').strip().lower()}|genre={(genre or '').strip().lower()}"
    )
    cached = _ARTISTS_CACHE.get(cache_key)
    if cached:
        cached_at = cached.get("ts")
        if cached_at and (utc_now().timestamp() - cached_at) < _ARTISTS_CACHE_TTL_SECONDS:
            etag = cached.get("etag")
            last_modified = cached.get("last_modified")
            if etag and request.headers.get("if-none-match") == etag:
                response.headers["Cache-Control"] = f"private, max-age={_ARTISTS_CACHE_TTL_SECONDS}"
                response.headers["X-Cache"] = "HIT"
                response.headers["ETag"] = etag
                if isinstance(last_modified, datetime):
                    response.headers["Last-Modified"] = format_datetime(
                        last_modified.replace(tzinfo=timezone.utc), usegmt=True
                    )
                response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
                response.status_code = 304
                return {}
            if isinstance(last_modified, datetime):
                try:
                    ims = parsedate_to_datetime(request.headers.get("if-modified-since", ""))
                except (TypeError, ValueError):
                    ims = None
                if ims and ims >= last_modified.replace(tzinfo=timezone.utc):
                    response.headers["Cache-Control"] = f"private, max-age={_ARTISTS_CACHE_TTL_SECONDS}"
                    response.headers["X-Cache"] = "HIT"
                    response.headers["ETag"] = etag or ""
                    response.headers["Last-Modified"] = format_datetime(
                        last_modified.replace(tzinfo=timezone.utc), usegmt=True
                    )
                    response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
                    response.status_code = 304
                    return {}
            response.headers["Cache-Control"] = f"private, max-age={_ARTISTS_CACHE_TTL_SECONDS}"
            response.headers["X-Cache"] = "HIT"
            if etag:
                response.headers["ETag"] = etag
            if isinstance(last_modified, datetime):
                response.headers["Last-Modified"] = format_datetime(
                    last_modified.replace(tzinfo=timezone.utc), usegmt=True
                )
            response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
            return cached.get("payload", {})
    hidden_filter = None
    if effective_user_id:
        hidden_filter = ~exists(
            select(1).where(
                (UserHiddenArtist.user_id == effective_user_id)
                & (UserHiddenArtist.artist_id == Artist.id)
            )
        )
    total_query = select(func.count()).select_from(Artist)
    if search:
        total_query = total_query.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        total_query = total_query.where(
            func.lower(Artist.genres).like(f"%\"{genre_token}\"%")
        )
    if hidden_filter is not None:
        total_query = total_query.where(hidden_filter)
    total = (await session.exec(total_query)).one()
    last_modified_query = select(func.max(Artist.updated_at)).select_from(Artist)
    if search:
        last_modified_query = last_modified_query.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        last_modified_query = last_modified_query.where(
            func.lower(Artist.genres).like(f"%\"{genre_token}\"%")
        )
    if hidden_filter is not None:
        last_modified_query = last_modified_query.where(hidden_filter)
    last_modified = (await session.exec(last_modified_query)).one()
    last_modified = last_modified or utc_now()
    if effective_user_id:
        favorite_flag = exists(
            select(1).where(
                (UserFavorite.user_id == effective_user_id)
                & (UserFavorite.target_type == FavoriteTargetType.ARTIST)
                & (UserFavorite.artist_id == Artist.id)
            )
        ).label("is_favorite")
        statement = (
            select(Artist, favorite_flag)
            .order_by(*order_by_clause)
            .offset(offset)
            .limit(limit)
        )
    else:
        statement = select(Artist).order_by(*order_by_clause).offset(offset).limit(limit)
    if search:
        statement = statement.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        statement = statement.where(
            func.lower(Artist.genres).like(f"%\"{genre_token}\"%")
        )
    if hidden_filter is not None:
        statement = statement.where(hidden_filter)
    rows = (await session.exec(statement)).all()
    response_items = []
    for row in rows:
        if effective_user_id:
            artist, is_favorite = row
        else:
            artist, is_favorite = row, None
        payload = artist.dict()
        if is_favorite is not None:
            payload["is_favorite"] = bool(is_favorite)
        stored_images = _parse_images_field(artist.images)
        if stored_images and not _is_proxied_images(stored_images):
            proxied = proxy_image_list(stored_images, size=256)
            if proxied:
                payload["images"] = json.dumps(proxied)
        response_items.append(payload)
    payload = {"items": response_items, "total": int(total)}
    etag = hashlib.sha1(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    _ARTISTS_CACHE[cache_key] = {
        "ts": utc_now().timestamp(),
        "payload": payload,
        "etag": etag,
        "last_modified": last_modified,
    }
    response.headers["Cache-Control"] = f"private, max-age={_ARTISTS_CACHE_TTL_SECONDS}"
    response.headers["X-Cache"] = "MISS"
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = format_datetime(
        last_modified.replace(tzinfo=timezone.utc), usegmt=True
    )
    response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
    return payload


@router.post("/refresh-genres")
async def refresh_artist_genres(
    limit: int = Query(50, ge=1, le=500, description="Artists to refresh"),
    tracks_per_artist: int = Query(3, ge=1, le=10, description="Tracks to sample per artist"),
    session: AsyncSession = Depends(SessionDep),
) -> dict:
    """Backfill missing genres using Last.fm track tags."""
    from ..core.config import settings
    if not settings.LASTFM_API_KEY:
        raise HTTPException(status_code=503, detail="LASTFM_API_KEY not configured")
    statement = select(Artist).order_by(desc(Artist.popularity), asc(Artist.id)).limit(limit)
    artists = (await session.exec(statement)).all()
    scanned = 0
    updated = 0
    for artist in artists:
        scanned += 1
        if _parse_genres_field(artist.genres):
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
) -> dict:
    """Backfill missing artist metadata (bio/genres/images) and refresh from Spotify when possible."""
    from ..core.maintenance import maintenance_stop_requested
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
def hide_artist_for_user_endpoint(
    artist_id: int = Path(..., description="Local artist ID"),
    user_id: int = Query(..., ge=1, description="User ID"),
):
    """Hide an artist for the specified user."""
    try:
        hidden = hide_artist_for_user(user_id, artist_id)
        return {"message": "Artist hidden", "hidden": hidden.dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/id/{artist_id}/hide")
def unhide_artist_for_user_endpoint(
    artist_id: int = Path(..., description="Local artist ID"),
    user_id: int = Query(..., ge=1, description="User ID"),
):
    """Remove user-specific hidden flag."""
    removed = unhide_artist_for_user(user_id, artist_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Hidden artist entry not found")
    return {"message": "Artist unhidden"}


@router.get("/id/{artist_id}")
def get_artist(artist_id: int = Path(..., description="Local artist ID")) -> Artist:
    """Get single artist by local ID."""
    with get_session() as session:
        artist = session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")
    return artist


@router.delete("/id/{artist_id}")
def delete_artist_end(artist_id: int = Path(..., description="Local artist ID")):
    """Delete artist and cascade to albums/tracks."""
    try:
        ok = delete_artist(artist_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Artist not found")
        return {"message": "Artist and related data deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{spotify_id}/save-full-discography")
async def save_full_discography(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Save complete discography to DB: artist + albums + tracks."""
    # Get artist info
    artist_data = await spotify_client.get_artist(spotify_id)
    if not artist_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")

    # Save artist
    from ..crud import save_artist
    artist = await save_artist(artist_data)

    # Get albums
    albums_data = await spotify_client.get_artist_albums(
        spotify_id,
        include_groups="album,single,compilation",
        fetch_all=True,
    )

    saved_albums = 0
    saved_tracks = 0

    for album_data in albums_data:
        album_id = album_data['id']
        tracks_data = await spotify_client.get_album_tracks(album_id)

        # Save album and tracks
        from ..crud import save_album, save_track
        album = await save_album(album_data)
        if album.spotify_id:  # Album was saved (not duplicate)
            saved_albums += 1
            artist_id = album.artist_id
            for track_data in tracks_data:
                await asyncio.to_thread(save_track, track_data, album.id, artist_id)
                saved_tracks += 1

    return {
        "message": "Full discography saved to DB",
        "artist": artist.dict(),
        "saved_albums": saved_albums,
        "saved_tracks": saved_tracks
    }

@router.post("/enrich_bio/{artist_id}")
async def enrich_artist_bio(
    artist_id: int = Path(..., description="Local artist ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """Fetch and enrich artist bio from Last.fm."""
    artist = (await session.exec(select(Artist).where(Artist.id == artist_id))).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # Fetch Last.fm bio using artist name
    bio_data = await lastfm_client.get_artist_info(artist.name)
    bio_summary = bio_data['summary']
    bio_content = bio_data['content']

    # Update DB
    updated_artist = await asyncio.to_thread(update_artist_bio, artist_id, bio_summary, bio_content)
    return {"message": "Artist bio enriched", "artist": updated_artist.dict() if updated_artist else {}}


@router.get("/{spotify_id}/download-progress")
async def get_artist_download_progress(spotify_id: str = Path(..., description="Spotify artist ID")):
    """
    Get download progress for an artist's top tracks.

    - **spotify_id**: Spotify artist ID
    - Returns progress percentage and status for the automatic downloads
    """
    try:
        progress = await auto_download_service.get_artist_download_progress(spotify_id)
        return {
            "artist_spotify_id": spotify_id,
            "progress": progress
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting download progress: {str(e)}")


@router.post("/{spotify_id}/download-top-tracks")
async def manual_download_top_tracks(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    background_tasks: BackgroundTasks = None,
    limit: int = Query(5, description="Number of top tracks to download (max 5 for testing)"),
    force: bool = Query(False, description="Force re-download even if already downloaded")
):
    """
    Manually trigger download of top tracks for an artist.

    - **spotify_id**: Spotify artist ID
    - **limit**: Number of tracks to download (5 max for testing phase)
    - **force**: If true, will re-download even already downloaded tracks
    - **background_tasks**: FastAPI background tasks for non-blocking execution
    """
    try:
        # Validate limit for testing phase
        if limit > 5:
            raise HTTPException(status_code=400, detail="Limit must be 5 or less during testing phase")

        # Get artist info from Spotify to get name
        artist_data = await spotify_client.get_artist(spotify_id)
        if not artist_data:
            raise HTTPException(status_code=404, detail="Artist not found on Spotify")

        artist_name = artist_data.get('name')

        # For forced downloads, we would need to modify the logic
        # For now, just trigger normal auto-download
        await auto_download_service.auto_download_artist_top_tracks(
            artist_name=artist_name,
            artist_spotify_id=spotify_id,
            limit=limit,
            background_tasks=background_tasks
        )

        return {
            "message": f"Download triggered for top {limit} tracks of {artist_name}",
            "artist_name": artist_name,
            "artist_spotify_id": spotify_id,
            "tracks_requested": limit,
            "will_execute_in_background": background_tasks is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering download: {str(e)}")


@router.post("/{spotify_id}/refresh-data")
async def refresh_artist_data(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Force refresh all data for an artist from external APIs.

    Updates artist metadata, checks for new albums/tracks, and freshens all data.
    """
    try:
        # First ensure artist exists locally
        artist = (await session.exec(select(Artist).where(Artist.spotify_id == spotify_id))).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found locally. Save artist first.")

        # Refresh artist metadata
        await data_freshness_manager.refresh_artist_data(spotify_id)

        # Check for new content
        new_content = await data_freshness_manager.check_for_new_artist_content(spotify_id)

        return {
            "message": f"Artist {spotify_id} data refreshed",
            "new_content_discovered": new_content,
            "data_freshened": True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing artist data: {str(e)}")


@router.get("/data-freshness-report")
async def get_data_freshness_report():
    """
    Get a comprehensive report on data freshness across the entire music library.
    """
    try:
        report = await data_freshness_manager.get_data_freshness_report()
        return {
            "data_freshness_report": report,
            "message": "Data freshness report generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating freshness report: {str(e)}")


@router.post("/bulk-refresh")
async def bulk_refresh_stale_data(max_artists: int = Query(10, description="Maximum artists to refresh")):
    """
    Perform bulk refresh of all stale artist data.

    - **max_artists**: Maximum number of artists to refresh in this batch
    - Useful for maintenance and keeping data fresh
    """
    try:
        result = await data_freshness_manager.bulk_refresh_stale_artists(max_artists)

        return {
            "bulk_refresh_result": result,
            "message": f"Bulk refresh completed for up to {max_artists} artists"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing bulk refresh: {str(e)}")


@router.get("/{spotify_id}/content-changes")
async def check_artist_content_changes(
    spotify_id: str = Path(..., description="Spotify artist ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Check what new content is available for an artist since last sync.

    Returns new albums and tracks found on Spotify.
    """
    try:
        # First ensure artist exists locally
        artist = (await session.exec(select(Artist).where(Artist.spotify_id == spotify_id))).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found locally. Save artist first.")

        # Check for new content
        new_content = await data_freshness_manager.check_for_new_artist_content(spotify_id)

        return {
            "artist_spotify_id": spotify_id,
            "new_content_available": new_content,
            "message": f"Found {new_content['new_albums']} new albums and {new_content['new_tracks']} new tracks"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking content changes: {str(e)}")
