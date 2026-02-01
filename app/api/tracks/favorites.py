"""
Track favorites management endpoints.

Handles user favorites, ratings, and preferences.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Track, Artist, Album, YouTubeDownload, UserFavorite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["tracks"])


@router.post("/{track_id}/favorite")
async def add_to_favorites(
    track_id: int,
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Add a track to user favorites."""
    from sqlmodel import select

    # Get user ID from request if not provided
    if not user_id:
        user_id = getattr(request.state, "user_id", None)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Check if track exists
    with get_session() as sync_session:
        track = sync_session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Check if already favorited
        existing = sync_session.exec(
            select(UserFavorite).where(
                (UserFavorite.user_id == user_id)
                & (UserFavorite.track_id == track_id)
                & (UserFavorite.target_type == UserFavorite.FavoriteTargetType.TRACK)
            )
        ).first()

        if existing:
            return {
                "message": "Track already in favorites",
                "track_id": track_id,
                "already_favorited": True
            }

        # Add to favorites
        favorite = UserFavorite(
            user_id=user_id,
            track_id=track_id,
            target_type=UserFavorite.FavoriteTargetType.TRACK
        )
        sync_session.add(favorite)
        sync_session.commit()

        return {
            "message": "Track added to favorites",
            "track_id": track_id,
            "favorited_at": favorite.created_at.isoformat() if favorite.created_at else None
        }


@router.delete("/{track_id}/favorite")
async def remove_from_favorites(
    track_id: int,
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Remove a track from user favorites."""
    from sqlmodel import select

    # Get user ID from request if not provided
    if not user_id:
        user_id = getattr(request.state, "user_id", None)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_session() as sync_session:
        # Find and delete favorite
        favorite = sync_session.exec(
            select(UserFavorite).where(
                (UserFavorite.user_id == user_id)
                & (UserFavorite.track_id == track_id)
                & (UserFavorite.target_type == UserFavorite.FavoriteTargetType.TRACK)
            )
        ).first()

        if not favorite:
            return {
                "message": "Track not in favorites",
                "track_id": track_id,
                "was_favorited": False
            }

        # Delete the favorite
        sync_session.delete(favorite)
        sync_session.commit()

        return {
            "message": "Track removed from favorites",
            "track_id": track_id,
            "removed_at": datetime.utcnow().isoformat()
        }


@router.get("/{user_id}")
async def get_user_favorites(
    user_id: int,
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get user's favorite tracks."""
    from sqlmodel import select
    from pathlib import Path as FsPath
    from ...crud import _select_best_downloads

    with get_session() as sync_session:
        # Get favorite tracks with track and artist info
        base_query = (
            select(Track, Artist, Album)
            .join(UserFavorite, UserFavorite.track_id == Track.id)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(UserFavorite.user_id == user_id)
            .where(UserFavorite.target_type == UserFavorite.FavoriteTargetType.TRACK)
            .order_by(UserFavorite.created_at.desc(), Track.id.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = sync_session.exec(base_query).all()

        # Get YouTube info efficiently
        spotify_ids = [track.spotify_id for track, _, _ in rows if track.spotify_id]

        download_map = {}
        if spotify_ids:
            downloads = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()
            download_map = _select_best_downloads(downloads)

        # Build response items
        items = []
        for track, artist, album in rows:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None

            if verify_files and file_path:
                file_exists = FsPath(file_path).exists()
            else:
                file_exists = False

            if file_exists:
                youtube_status = "completed"
            elif youtube_video_id and not youtube_status:
                youtube_status = "link_found"

            items.append({
                "track_id": track.id,
                "track_name": track.name,
                "spotify_track_id": track.spotify_id,
                "artist_name": artist.name if artist else None,
                "artist_spotify_id": artist.spotify_id if artist else None,
                "album_name": album.name if album else None,
                "album_spotify_id": album.spotify_id if album else None,
                "duration_ms": track.duration_ms,
                "popularity": track.popularity,
                "youtube_video_id": youtube_video_id,
                "youtube_status": youtube_status,
                "youtube_url": youtube_url,
                "local_file_path": file_path,
                "local_file_exists": file_exists,
                "favorited_at": None,  # Would need to join UserFavorite to get created_at
            })

        # Get total count
        total = sync_session.exec(
            select(UserFavorite.id).where(
                (UserFavorite.user_id == user_id)
                & (UserFavorite.target_type == UserFavorite.FavoriteTargetType.TRACK)
            )
        ).count()

        return {
            "items": items,
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": len(rows) == limit,
        }
