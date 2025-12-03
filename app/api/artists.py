"""
Artist endpoints: search, discography, etc.
"""

from typing import List

from fastapi import APIRouter, Query, Path, HTTPException

from ..core.spotify import spotify_client
from ..crud import save_artist, delete_artist
from ..core.db import get_session
from ..models.base import Artist
from sqlmodel import select

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/search")
async def search_artists(q: str = Query(..., description="Artist name to search")) -> List[dict]:
    """Search for artists by name using Spotify API."""
    artists = await spotify_client.search_artists(q)
    return artists


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
