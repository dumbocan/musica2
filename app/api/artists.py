"""
Artist endpoints: search, discography, etc.
"""

from typing import List

from fastapi import APIRouter, Query, Path, HTTPException, BackgroundTasks

from ..core.spotify import spotify_client
from ..crud import save_artist, delete_artist, update_artist_bio
from ..core.db import get_session
from ..models.base import Artist
from ..core.lastfm import lastfm_client
from ..core.auto_download import auto_download_service
from sqlmodel import select
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/search")
async def search_artists(q: str = Query(..., description="Artist name to search")) -> List[dict]:
    """Search for artists by name using Spotify API."""
    artists = await spotify_client.search_artists(q)
    return artists


@router.get("/search-auto-download")
async def search_artists_auto_download(
    q: str = Query(..., description="Artist name to search"),
    background_tasks: BackgroundTasks = None
) -> dict:
    """
    Search for artists by name using Spotify API.

    Automatically triggers download of top 5 tracks for the first result.
    """
    artists = await spotify_client.search_artists(q)

    # Check if we have results and start auto-download for the first artist
    if artists and len(artists) > 0:
        first_artist = artists[0]  # Take the best match
        artist_spotify_id = first_artist.get('id')
        artist_name = first_artist.get('name')

        if artist_spotify_id:
            # Start background download of top 5 tracks
            await auto_download_service.auto_download_artist_top_tracks(
                artist_name=artist_name,
                artist_spotify_id=artist_spotify_id,
                limit=5,
                background_tasks=background_tasks
            )

            # Get progress status after triggering
            progress = await auto_download_service.get_artist_download_progress(artist_spotify_id)

            return {
                "query": q,
                "artists": artists,
                "auto_download_triggered": True,
                "triggered_for_artist": {
                    "name": artist_name,
                    "spotify_id": artist_spotify_id
                },
                "download_progress": progress
            }

    # No artists found or no auto-download triggered
    return {
        "query": q,
        "artists": artists,
        "auto_download_triggered": False,
        "message": "No artists found for auto-download trigger"
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

@router.get("/{spotify_id}/discography-with-save")
async def get_discography_with_save(spotify_id: str = Path(..., description="Spotify artist ID"), save: bool = Query(False, description="Save to database")):
    """Get complete discography from Spotify with option to save to DB."""
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

    saved_albums = 0
    saved_tracks = 0

    for album_data in albums_data:
        album_id = album_data['id']
        tracks_data = await spotify_client.get_album_tracks(album_id)
        album_data['tracks'] = tracks_data
        discography["albums"].append(album_data)

        if save:
            # Save album and tracks to DB
            from ..crud import save_album, save_track, get_artist_by_spotify_id
            album = save_album(album_data)
            if album.spotify_id:  # Album was saved (not duplicate)
                saved_albums += 1
                artist_id = album.artist_id
                for track_data in tracks_data:
                    save_track(track_data, album.id, artist_id)
                    saved_tracks += 1

    if save:
        # Save artist if not already saved
        from ..crud import save_artist
        artist = save_artist(artist_data)

    return {
        "discography": discography,
        "saved": save,
        "saved_albums": saved_albums,
        "saved_tracks": saved_tracks
    }

@router.get("/{spotify_id}/recommendations")
async def get_artist_recommendations(spotify_id: str = Path(..., description="Spotify artist ID")):
    """Get music recommendations based on artist (tracks and artists)."""
    recommendations = await spotify_client.get_recommendations(seed_artists=[spotify_id], limit=20)
    return recommendations


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


@router.get("/")
def get_artists() -> List[Artist]:
    """Get all saved artists from DB."""
    with get_session() as session:
        artists = session.exec(select(Artist)).all()
    return artists


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
    ok = delete_artist(artist_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Artist not found")
    return {"message": "Artist and related data deleted"}


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
