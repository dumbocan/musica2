"""
Playlist endpoints: CRUD operations for playlists.
"""

from typing import List, Optional
from fastapi import APIRouter, Path, HTTPException, Query
from ..crud import (
    create_playlist, update_playlist, delete_playlist,
    remove_track_from_playlist
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


@router.get("/id/{playlist_id}/tracks", response_model=None)
def get_playlist_tracks(playlist_id: int = Path(..., description="Local playlist ID")):
    """Get all tracks in a playlist with YouTube enrichment (same as tracks/overview)."""
    from ..models.base import YouTubeDownload, Artist, Album

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
        if not track_ids:
            return []

        # Get all YouTube downloads for these tracks (same logic as tracks/overview)
        all_downloads = session.exec(
            select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(
                select(Track.spotify_id).where(Track.id.in_(track_ids))
            ))
        ).all()
        download_map = {d.spotify_track_id: d for d in all_downloads}

        # Get tracks with artist info
        tracks_with_artist = session.exec(
            select(Track, Artist, Album)
            .outerjoin(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.id.in_(track_ids))
        ).all()

        # Build response with enrichment (same format as tracks/overview)
        items = []
        for track, artist, album in tracks_with_artist:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None

            # Determine videoId (same logic as TracksPage buildQueueItems)
            if file_path:
                video_id_for_player = None  # Will use local file via localTrackId
            elif youtube_video_id:
                video_id_for_player = youtube_video_id
            else:
                video_id_for_player = None

            items.append({
                "id": track.id,
                "name": track.name,
                "spotify_id": track.spotify_id,
                "duration_ms": track.duration_ms,
                "artist": {"name": artist.name, "spotify_id": artist.spotify_id} if artist else None,
                "album": {"name": album.name} if album else None,
                "youtube_video_id": youtube_video_id,
                "youtube_url": youtube_url,
                "youtube_status": youtube_status,
                "download_path": file_path,
                "local_file_exists": bool(file_path),
                "videoId": video_id_for_player,  # For frontend compatibility
            })

        return items


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
    """Add track to playlist. Returns 200 if already exists."""
    from ..models.base import PlaylistTrack

    with get_session() as session:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        track = session.exec(select(Track).where(Track.id == track_id)).first()

        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Check if already in playlist
        existing = session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id
            )
        ).first()

        if existing:
            return {"message": "Track already in playlist", "playlist_track": existing, "already_exists": True}

        # Add track
        max_order = session.exec(
            select(PlaylistTrack.order)
            .where(PlaylistTrack.playlist_id == playlist_id)
            .order_by(PlaylistTrack.order.desc())
            .limit(1)
        ).first()
        new_order = (max_order or 0) + 1

        playlist_track = PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            order=new_order
        )
        session.add(playlist_track)
        session.commit()
        session.refresh(playlist_track)

    return {"message": "Track added to playlist", "playlist_track": playlist_track, "already_exists": False}


@router.delete("/id/{playlist_id}/tracks/{track_id}")
def remove_track_from_playlist_endpoint(
    playlist_id: int = Path(..., description="Local playlist ID"),
    track_id: int = Path(..., description="Local track ID")
):
    """Remove track from playlist."""
    result = remove_track_from_playlist(playlist_id, track_id)

    if not result["success"]:
        status_code = 404 if result.get("error") == "not_found" else 500
        raise HTTPException(status_code=status_code, detail=result.get("message", "Unknown error"))

    return result
