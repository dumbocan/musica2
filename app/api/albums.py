"""
Album endpoints: tracks, save to DB, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.spotify import spotify_client
from ..core.config import settings
from ..core.lastfm import lastfm_client
from ..core.image_proxy import proxy_image_list
from ..crud import save_album, delete_album
from ..core.db import get_session
from ..models.base import Album
from sqlmodel import select

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("/spotify/{spotify_id}")
async def get_album_from_spotify(spotify_id: str = Path(..., description="Spotify album ID")):
    """Get album details and tracks directly from Spotify."""
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Spotify credentials not configured")
    try:
        album = await spotify_client.get_album(spotify_id)
        if not album:
            raise HTTPException(status_code=404, detail="Album not found on Spotify")
        tracks = await spotify_client.get_album_tracks(spotify_id)
        album["tracks"] = tracks
        album["images"] = proxy_image_list(album.get("images", []), size=512)
        # Enrich with Last.fm wiki if possible
        try:
            artist_name = (album.get("artists") or [{}])[0].get("name")
            album_name = album.get("name")
            if artist_name and album_name and settings.LASTFM_API_KEY:
                lfm_info = await lastfm_client.get_album_info(artist_name, album_name)
                album["lastfm"] = lfm_info
        except Exception:
            album["lastfm"] = {}
        return album
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching album from Spotify: {e}")


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

    from ..crud import save_track
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


@router.delete("/id/{album_id}")
def delete_album_endpoint(album_id: int = Path(..., description="Local album ID")):
    """Delete album unless favorited."""
    try:
        ok = delete_album(album_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Album not found")
        return {"message": "Album deleted"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/id/{album_id}")
def get_album(album_id: int = Path(..., description="Local album ID")) -> Album:
    """Get single album by local ID."""
    with get_session() as session:
        album = session.exec(select(Album).where(Album.id == album_id)).first()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
    return album
