"""
Album endpoints: tracks, save to DB, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.spotify import spotify_client
from ..crud import save_album
from ..core.db import get_session
from ..models.base import Album, Track
from sqlmodel import select

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/{spotify_id}/tracks")
async def get_album_tracks(spotify_id: str = Path(..., description="Spotify album ID")) -> List[dict]:
    """Get all tracks for an album via Spotify API."""
    tracks = await spotify_client.get_album_tracks(spotify_id)
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

    from ..crud import save_track, get_artist_by_spotify_id
    artist_id = album.artist_id

    for track_data in tracks_data:
        save_track(track_data, album.id, artist_id)

    return {"message": "Album and tracks saved to DB", "album": album.dict(), "tracks_saved": len(tracks_data)}


@router.get("/")
def get_albums() -> List[Album]:
    """Get all saved albums from DB."""
    with get_session() as session:
        albums = session.exec(select(Album)).all()
    return albums


@router.get("/id/{album_id}")
def get_album(album_id: int = Path(..., description="Local album ID")) -> Album:
    """Get single album by local ID."""
    with get_session() as session:
        album = session.exec(select(Album).where(Album.id == album_id)).first()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
    return album
