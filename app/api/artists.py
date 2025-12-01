"""
Artist endpoints: search, discography, etc.
"""

from typing import List

from fastapi import APIRouter, Query

from ..core.spotify import spotify_client

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/search")
async def search_artists(q: str = Query(..., description="Artist name to search")) -> List[dict]:
    """Search for artists by name using Spotify API."""
    artists = await spotify_client.search_artists(q)
    return artists
