"""
Album endpoints: tracks, etc.
"""

from typing import List

from fastapi import APIRouter, Path

from ..core.spotify import spotify_client

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/{spotify_id}/tracks")
async def get_album_tracks(spotify_id: str = Path(..., description="Spotify album ID")) -> List[dict]:
    """Get all tracks for an album via Spotify API."""
    tracks = await spotify_client.get_album_tracks(spotify_id)
    return tracks
