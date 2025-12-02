"""
Album endpoints: tracks, save to DB, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.spotify import spotify_client
from ..crud import save_album

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/{spotify_id}/tracks")
async def get_album_tracks(spotify_id: str = Path(..., description="Spotify album ID")) -> List[dict]:
    """Get all tracks for an album via Spotify API."""
    tracks = await spotify_client.get_album_tracks(spotify_id)
    return tracks


@router.post("/save/{spotify_id}")
async def save_album_to_db(spotify_id: str = Path(..., description="Spotify album ID")):
    """Fetch album from Spotify and save to DB."""
    album_data = await spotify_client._make_request(f"/albums/{spotify_id}")
    if not album_data:
        raise HTTPException(status_code=404, detail="Album not found on Spotify")
    album = save_album(album_data)
    return {"message": "Album saved to DB", "album": album.dict()}
