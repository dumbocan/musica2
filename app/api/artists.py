"""
Artist endpoints: search, discography, etc.
"""

from typing import List

from fastapi import APIRouter, Query, Path, HTTPException

from ..core.spotify import spotify_client
from ..crud import save_artist

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
