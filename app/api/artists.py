"""
Artist endpoints: search, discography, etc.
"""

import logging
import json
import ast
from typing import List

from fastapi import APIRouter, Query, Path, HTTPException, BackgroundTasks
from sqlalchemy import desc, asc, func

logger = logging.getLogger(__name__)

from ..core.spotify import spotify_client
from ..crud import save_artist, delete_artist, update_artist_bio
from ..core.db import get_session
from ..models.base import Artist
from ..core.lastfm import lastfm_client
from ..core.auto_download import auto_download_service
from ..core.data_freshness import data_freshness_manager
from ..core.image_proxy import proxy_image_list
from sqlmodel import select
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/artists", tags=["artists"])


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
                    include_youtube_links=True,  # Find YouTube links for all tracks
                    include_full_albums=True  # Save complete discography with artwork
                )

            # Now trigger REAL downloads for the main artist (testing)
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
async def get_artist_albums(spotify_id: str = Path(..., description="Spotify artist ID")) -> List[dict]:
    """Get all albums for an artist via Spotify API."""
    albums = await spotify_client.get_artist_albums(spotify_id)
    return albums


@router.post("/save/{spotify_id}")
async def save_artist_to_db(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Fetch artist from Spotify and save to DB."""
    artist_data = await spotify_client.get_artist(spotify_id)
    if not artist_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")
    artist = save_artist(artist_data)
    return {"message": "Artist saved to DB", "artist": artist.dict()}


@router.post("/{spotify_id}/sync-discography")
async def sync_artist_discography(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Sync artist's discography: fetch and save new albums/tracks from Spotify."""
    with get_session() as session:
        artist = session.exec(select(Artist).where(Artist.spotify_id == spotify_id)).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not saved locally")

    # Fetch all albums
    albums_data = await spotify_client.get_artist_albums(spotify_id)

    from ..crud import save_album
    synced_albums = 0
    synced_tracks = 0

    for album_data in albums_data:
        album = save_album(album_data)
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
    albums_data = await spotify_client.get_artist_albums(spotify_id)

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
async def get_artist_info(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get artist info from Spotify + Last.fm bio/tags/listeners (no DB write)."""
    from ..core.lastfm import lastfm_client
    from ..services.library_expansion import save_artist_discography

    spotify_data = await spotify_client.get_artist(spotify_id)
    if not spotify_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")
    # Proxy images
    try:
        spotify_data["images"] = proxy_image_list(spotify_data.get("images", []), size=512)
    except Exception:
        pass

    lastfm_data = {}
    try:
        name = spotify_data.get("name")
        if name:
            lastfm_data = await lastfm_client.get_artist_info(name)
    except Exception as exc:
        # Don't fail the request on Last.fm issues
        print(f"[artist_info] lastfm fetch failed for {spotify_id}: {exc}")
        lastfm_data = {}

    # Persist artist/albums/tracks in background (best effort)
    try:
        asyncio.create_task(save_artist_discography(spotify_id))
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


@router.get("/{spotify_id}/info")
async def get_artist_info(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get artist info from Spotify + Last.fm bio/tags/listeners (no DB write)."""
    from ..core.lastfm import lastfm_client

    spotify_data = await spotify_client.get_artist(spotify_id)
    if not spotify_data:
        raise HTTPException(status_code=404, detail="Artist not found on Spotify")

    lastfm_data = {}
    try:
        name = spotify_data.get("name")
        if name:
            lastfm_data = await lastfm_client.get_artist_info(name)
    except Exception as exc:
        # Don't fail the request on Last.fm issues
        print(f"[artist_info] lastfm fetch failed for {spotify_id}: {exc}")
        lastfm_data = {}

    return {
        "spotify": spotify_data,
        "lastfm": lastfm_data
    }


@router.get("/{spotify_id}/related")
async def get_related_artists(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get related artists using Last.fm (with listeners/playcount) enriched with Spotify search."""
    from ..core.config import settings
    from ..core.lastfm import lastfm_client
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
        print(f"[related] Last.fm similar failed for {main_name}: {exc}")
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
    from ..models.base import Album, Track
    from ..core.db import get_session
    from sqlmodel import select

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
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    order: str = Query(
        "pop-desc",
        pattern="^(pop-desc|pop-asc|name-asc)$",
        description="Ordering for returned artists"
    )
) -> dict:
    """Get saved artists with pagination, ordering, and ensure cached images are proxied."""
    order_by_map = {
        "pop-desc": [desc(Artist.popularity), asc(Artist.id)],
        "pop-asc": [asc(Artist.popularity), asc(Artist.id)],
        "name-asc": [asc(Artist.name), asc(Artist.id)]
    }
    order_by_clause = order_by_map.get(order, order_by_map["pop-desc"])
    with get_session() as session:
        total = session.exec(select(func.count()).select_from(Artist)).one()
        statement = select(Artist).order_by(*order_by_clause).offset(offset).limit(limit)
        artists = session.exec(statement).all()
        needs_commit = False
        for artist in artists:
            stored_images = _parse_images_field(artist.images)
            if _is_proxied_images(stored_images):
                continue
            proxied = proxy_image_list(stored_images, size=256)
            if not proxied and artist.spotify_id:
                try:
                    spotify_data = await spotify_client.get_artist(artist.spotify_id)
                    proxied = proxy_image_list(spotify_data.get("images", []), size=256)
                except Exception as exc:
                    logger.warning("Failed to refresh artist %s images: %s", artist.spotify_id, exc)
                    proxied = []
            if proxied:
                artist.images = json.dumps(proxied)
                session.add(artist)
                needs_commit = True
        if needs_commit:
            session.commit()
    return {"items": artists, "total": int(total)}


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
    artist = save_artist(artist_data)

    # Get albums
    albums_data = await spotify_client.get_artist_albums(spotify_id)

    saved_albums = 0
    saved_tracks = 0

    for album_data in albums_data:
        album_id = album_data['id']
        tracks_data = await spotify_client.get_album_tracks(album_id)

        # Save album and tracks
        from ..crud import save_album, save_track
        album = save_album(album_data)
        if album.spotify_id:  # Album was saved (not duplicate)
            saved_albums += 1
            artist_id = album.artist_id
            for track_data in tracks_data:
                save_track(track_data, album.id, artist_id)
                saved_tracks += 1

    return {
        "message": "Full discography saved to DB",
        "artist": artist.dict(),
        "saved_albums": saved_albums,
        "saved_tracks": saved_tracks
    }

@router.post("/enrich_bio/{artist_id}")
async def enrich_artist_bio(artist_id: int = Path(..., description="Local artist ID")):
    """Fetch and enrich artist bio from Last.fm."""
    with get_session() as session:
        artist = session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

    # Fetch Last.fm bio using artist name
    bio_data = await lastfm_client.get_artist_info(artist.name)
    bio_summary = bio_data['summary']
    bio_content = bio_data['content']

    # Update DB
    updated_artist = update_artist_bio(artist_id, bio_summary, bio_content)
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
async def refresh_artist_data(spotify_id: str = Path(..., description="Spotify artist ID")):
    """
    Force refresh all data for an artist from external APIs.

    Updates artist metadata, checks for new albums/tracks, and freshens all data.
    """
    try:
        # First ensure artist exists locally
        session = get_session()
        try:
            artist = session.exec(select(Artist).where(Artist.spotify_id == spotify_id)).first()
            if not artist:
                raise HTTPException(status_code=404, detail="Artist not found locally. Save artist first.")
        finally:
            session.close()

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
async def check_artist_content_changes(spotify_id: str = Path(..., description="Spotify artist ID")):
    """
    Check what new content is available for an artist since last sync.

    Returns new albums and tracks found on Spotify.
    """
    try:
        # First ensure artist exists locally
        session = get_session()
        try:
            artist = session.exec(select(Artist).where(Artist.spotify_id == spotify_id)).first()
            if not artist:
                raise HTTPException(status_code=404, detail="Artist not found locally. Save artist first.")
        finally:
            session.close()

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
