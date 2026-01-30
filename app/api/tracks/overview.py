"""
Track overview and listing endpoints.

Provides track lists with metadata and filtering capabilities.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Track, Artist, Album, YouTubeDownload
from ...core.config import settings

logger = logging.getLogger(__name__)

def _select_best_downloads(
    downloads: list,
) -> dict:
    """Select the best download for each Spotify track ID."""
    download_map = {}
    for download in downloads:
        if not download.spotify_track_id:
            continue
        existing = download_map.get(download.spotify_track_id)
        if not existing:
            download_map[download.spotify_track_id] = download
            continue
        existing_has_path = bool(existing.download_path)
        new_has_path = bool(download.download_path)
        if new_has_path and not existing_has_path:
            download_map[download.spotify_track_id] = download
            continue
        if existing_has_path and not new_has_path:
            continue
        existing_has_video = bool(existing.youtube_video_id)
        new_has_video = bool(download.youtube_video_id)
        if new_has_video and not existing_has_video:
            download_map[download.spotify_track_id] = download
            continue
        if new_has_video == existing_has_video:
            if download.updated_at and existing.updated_at and download.updated_at > existing.updated_at:
                download_map[download.spotify_track_id] = download
    return download_map

router = APIRouter(prefix="/overview", tags=["tracks"])

@router.get("/")
def get_tracks_overview(
    request: Request,
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    limit: int = Query(200, ge=1, le=1000, description="Límite de resultados"),
    filter: Optional[str] = Query(None, description="Filtro: favorite, downloaded, youtube"),
    search: Optional[str] = Query(None, description="Búsqueda de tracks"),
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Return tracks with artist, album, and cache status."""
    from sqlalchemy import func, or_, exists, and_
    from pathlib import Path as FsPath
    from ...models.base import UserFavorite, FavoriteTargetType, UserHiddenArtist
    import re
    
    def normalize_search(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def normalized_column(column):
        return func.regexp_replace(func.lower(column), "[^a-z0-9]+", " ", "g")

    if user_id is None:
        user_id = getattr(request.state, "user_id", None)
    
    # Check if user has hidden artists
    hidden_exists = None
    if user_id:
        hidden_exists = exists(
            select(1).where(
                (UserHiddenArtist.user_id == user_id) &
                (UserHiddenArtist.artist_id == Track.artist_id)
            )
        )

    with get_session() as sync_session:
        base_query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .order_by(Track.id.asc())
        )
        
        if hidden_exists is not None:
            base_query = base_query.where(~hidden_exists)

        # Search functionality
        search_term = normalize_search(search) if search else ""
        if search_term:
            pattern = f"%{search_term}%"
            base_query = base_query.where(
                or_(
                    normalized_column(Track.name).ilike(pattern),
                    normalized_column(Artist.name).ilike(pattern),
                    normalized_column(Album.name).ilike(pattern),
                )
            )

        # Filter functionality
        if filter:
            link_exists = exists(
                select(1).where(
                    (YouTubeDownload.spotify_track_id == Track.spotify_id)
                    & (YouTubeDownload.youtube_video_id.is_not(None))
                    & (YouTubeDownload.youtube_video_id != "")
                )
            )
            file_exists = exists(
                select(1).where(
                    (YouTubeDownload.spotify_track_id == Track.spotify_id)
                    & (YouTubeDownload.download_path.is_not(None))
                    & (YouTubeDownload.download_path != "")
                )
            )
            
            if filter == "favorites":
                if not user_id:
                    raise HTTPException(status_code=401, detail="User not authenticated")
                favorite_exists = exists(
                    select(1).where(
                        (UserFavorite.user_id == user_id)
                        & (UserFavorite.track_id == Track.id)
                        & (UserFavorite.target_type == FavoriteTargetType.TRACK)
                    )
                )
                base_query = base_query.where(favorite_exists)
            elif filter == "downloaded":
                base_query = base_query.where(file_exists)
            elif filter == "youtube":
                base_query = base_query.where(link_exists)

        rows = sync_session.exec(base_query.offset(offset).limit(limit)).all()

        # Get YouTube download info
        spotify_ids = [track.spotify_id for track, _, _ in rows if track.spotify_id]
        downloads = []
        if spotify_ids:
            downloads = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()

        download_map = _select_best_downloads(downloads)

        items = []
        for track, artist, album in rows:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None
            file_exists = FsPath(file_path).exists() if file_path else False
            
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
            })

    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "has_more": len(items) == limit,
    }

@router.get("/metrics")
async def get_tracks_metrics(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get tracks metrics and statistics."""
    # TODO: Implement tracks metrics
    return {
        "total_tracks": 0,
        "with_youtube": 0,
        "downloaded_count": 0,
        "favorites_count": 0
    }

@router.get("/favorites/{user_id}")
async def get_user_favorite_tracks(
    user_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get favorite tracks for a user."""
    # TODO: Get favorite tracks logic
    return {"tracks": [], "total": 0}
