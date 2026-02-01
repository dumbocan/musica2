"""
Modular maintenance API - split from original maintenance.py for better maintainability.
This module exports all maintenance-related endpoints through separate router modules.
"""

from typing import Any, Dict

from fastapi import APIRouter
from sqlalchemy import exists, func
from sqlmodel import select

from ...core.db import get_session
from ...models.base import Album, Artist, Track, YouTubeDownload

# Import all sub-routers
try:
    from .control import router as control_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import control router: {e}")
    control_router = None

try:
    from .backfill import router as backfill_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import backfill router: {e}")
    backfill_router = None

try:
    from .logs import router as logs_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import logs router: {e}")
    logs_router = None

# Create main maintenance router
maintenance_router = APIRouter(prefix="/maintenance", tags=["maintenance"])

# Include all sub-routers if they exist
if control_router:
    maintenance_router.include_router(control_router)
if backfill_router:
    maintenance_router.include_router(backfill_router)
if logs_router:
    maintenance_router.include_router(logs_router)


@maintenance_router.get("/dashboard")
async def get_dashboard_stats() -> Dict[str, Any]:
    """Get dashboard statistics."""
    with get_session() as session:
        total_artists = session.exec(select(func.count(Artist.id))).one()
        total_albums = session.exec(select(func.count(Album.id))).one()
        total_tracks = session.exec(select(func.count(Track.id))).one()
        artists_missing_images = session.exec(
            select(func.count(Artist.id)).where(Artist.image_path_id.is_(None))
        ).one()
        albums_missing_images = session.exec(
            select(func.count(Album.id)).where(Album.image_path_id.is_(None))
        ).one()
        albums_without_tracks = session.exec(
            select(func.count(Album.id)).where(
                ~exists(select(1).where(Track.album_id == Album.id))
            )
        ).one()
        tracks_with_spotify_id = session.exec(
            select(func.count(Track.id)).where(Track.spotify_id.is_not(None))
        ).one()
        tracks_with_local_file = session.exec(
            select(func.count(Track.id))
            .where(Track.download_path.is_not(None))
            .where(Track.download_path != "")
        ).one()
        youtube_link_exists = exists(
            select(1).where(
                (YouTubeDownload.spotify_track_id == Track.spotify_id)
                & YouTubeDownload.youtube_video_id.is_not(None)
            )
        )
        tracks_without_youtube = session.exec(
            select(func.count(Track.id)).where(~youtube_link_exists)
        ).one()
        youtube_links_total = session.exec(
            select(func.count(func.distinct(YouTubeDownload.spotify_track_id)))
            .where(YouTubeDownload.youtube_video_id.is_not(None))
        ).one()
        youtube_downloads_completed = session.exec(
            select(func.count(YouTubeDownload.id)).where(YouTubeDownload.download_status == "completed")
        ).one()
        youtube_links_pending = session.exec(
            select(func.count(func.distinct(YouTubeDownload.spotify_track_id)))
            .where(YouTubeDownload.youtube_video_id.is_not(None))
            .where(YouTubeDownload.youtube_video_id != "")
            .where(YouTubeDownload.download_status != "completed")
        ).one()
        youtube_links_failed = session.exec(
            select(func.count(func.distinct(YouTubeDownload.spotify_track_id)))
            .where(YouTubeDownload.youtube_video_id.is_(None) | (YouTubeDownload.youtube_video_id == ""))
            .where(YouTubeDownload.download_status.in_(("video_not_found", "error", "failed")))
        ).one()
    return {
        "artists_total": int(total_artists or 0),
        "albums_total": int(total_albums or 0),
        "tracks_total": int(total_tracks or 0),
        "artists_missing_images": int(artists_missing_images or 0),
        "albums_missing_images": int(albums_missing_images or 0),
        "albums_without_tracks": int(albums_without_tracks or 0),
        "tracks_without_youtube": int(tracks_without_youtube or 0),
        "tracks_with_spotify_id": int(tracks_with_spotify_id or 0),
        "tracks_with_local_file": int(tracks_with_local_file or 0),
        "youtube_links_total": int(youtube_links_total or 0),
        "youtube_downloads_completed": int(youtube_downloads_completed or 0),
        "youtube_links_pending": int(youtube_links_pending or 0),
        "youtube_links_failed": int(youtube_links_failed or 0),
    }


# Export for main.py
__all__ = ["maintenance_router"]
