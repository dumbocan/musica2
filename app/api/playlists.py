"""
Playlist endpoints: CRUD operations for playlists.
"""

from typing import List, Optional
from fastapi import APIRouter, Path, HTTPException, Query
from ..crud import (
    create_playlist, update_playlist, delete_playlist,
    add_track_to_playlist, remove_track_from_playlist
)
from ..core.db import get_session
from ..models.base import Playlist, PlaylistTrack, Track
from sqlmodel import select

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.post("/")
def create_new_playlist(
    name: str = Query(..., description="Playlist name"),
    description: str = Query("", description="Playlist description"),
    user_id: int = Query(1, description="User ID")
) -> Playlist:
    """Create a new playlist."""
    playlist = create_playlist(name, description, user_id)
    return playlist


@router.get("/")
def get_playlists() -> List[Playlist]:
    """Get all playlists from DB."""
    with get_session() as session:
        playlists = session.exec(select(Playlist)).all()
    return playlists


@router.get("/id/{playlist_id}")
def get_playlist(playlist_id: int = Path(..., description="Local playlist ID")) -> Playlist:
    """Get single playlist by local ID."""
    with get_session() as session:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


@router.get("/id/{playlist_id}/tracks")
def get_playlist_tracks(playlist_id: int = Path(..., description="Local playlist ID")) -> List[Track]:
    """Get all tracks in a playlist."""
    with get_session() as session:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get playlist tracks with track data
        playlist_tracks = session.exec(
            select(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.order)
        ).all()

        track_ids = [pt.track_id for pt in playlist_tracks]
        tracks = session.exec(select(Track).where(Track.id.in_(track_ids))).all()

        return tracks


@router.put("/id/{playlist_id}")
def update_playlist_endpoint(
    playlist_id: int = Path(..., description="Local playlist ID"),
    name: Optional[str] = Query(None, description="New playlist name"),
    description: Optional[str] = Query(None, description="New playlist description")
) -> Playlist:
    """Update playlist name and/or description."""
    playlist = update_playlist(playlist_id, name, description)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


@router.delete("/id/{playlist_id}")
def delete_playlist_endpoint(playlist_id: int = Path(..., description="Local playlist ID")):
    """Delete playlist and its tracks."""
    ok = delete_playlist(playlist_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Playlist and related data deleted"}


@router.post("/id/{playlist_id}/tracks/{track_id}")
def add_track_to_playlist_endpoint(
    playlist_id: int = Path(..., description="Local playlist ID"),
    track_id: int = Path(..., description="Local track ID")
):
    """Add track to playlist."""
    playlist_track = add_track_to_playlist(playlist_id, track_id)
    if not playlist_track:
        raise HTTPException(status_code=404, detail="Playlist or track not found, or track already in playlist")
    return {"message": "Track added to playlist", "playlist_track": playlist_track}


@router.delete("/id/{playlist_id}/tracks/{track_id}")
def remove_track_from_playlist_endpoint(
    playlist_id: int = Path(..., description="Local playlist ID"),
    track_id: int = Path(..., description="Local track ID")
):
    """Remove track from playlist."""
    ok = remove_track_from_playlist(playlist_id, track_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Playlist, track, or playlist-track relationship not found")
    return {"message": "Track removed from playlist"}
