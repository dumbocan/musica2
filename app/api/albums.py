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
