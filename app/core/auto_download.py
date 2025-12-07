"""
Auto-download service for music tracks from YouTube.
Handles intelligent downloading based on Spotify metadata.
"""

import asyncio
import logging
from typing import List, Optional, Dict
from sqlmodel import select
from fastapi import BackgroundTasks

from app.core.youtube import youtube_client
from app.core.spotify import spotify_client
from app.models.base import YouTubeDownload, Track
from app.core.db import SessionDep

logger = logging.getLogger(__name__)

class AutoDownloadService:
    """Service for automatic music downloading from YouTube."""

    def __init__(self):
        self.max_concurrent_downloads = 3  # Limit concurrent downloads

    async def is_track_downloaded(self, spotify_track_id: str, format_type: str = "mp3") -> bool:
        """Check if a Spotify track is already downloaded."""
        # Use sync session for direct queries (simpler for testing)
        from app.core.db import get_session
        session = get_session()
        try:
            from app.models.base import YouTubeDownload
            download = session.query(YouTubeDownload).filter(
                YouTubeDownload.spotify_track_id == spotify_track_id,
                YouTubeDownload.format_type == format_type,
                YouTubeDownload.download_status == "completed"
            ).first()
            return download is not None
        finally:
            session.close()

    async def track_download_status(self, spotify_track_id: str, format_type: str = "mp3") -> Optional[str]:
        """Get download status for a track."""
        from app.core.db import get_session
        session = get_session()
        try:
            from app.models.base import YouTubeDownload
            download = session.query(YouTubeDownload).filter(
                YouTubeDownload.spotify_track_id == spotify_track_id,
                YouTubeDownload.format_type == format_type
            ).first()
            return download.download_status if download else None
        finally:
            session.close()

    async def download_track_background(
        self,
        spotify_track_id: str,
        spotify_artist_id: str,
        track_name: str,
        artist_name: str,
        format_type: str = "mp3"
    ):
        """Background task to download a single track."""
        try:
            logger.info(f"Starting background download for: {artist_name} - {track_name}")

            # Check if already being processed or completed
            status = await self.track_download_status(spotify_track_id, format_type)
            if status == "completed" or status == "downloading":
                logger.info(f"Track already processed or in progress: {spotify_track_id}")
                return

            # Mark as downloading - use sync session for background operations
            from app.core.db import get_session
            session = get_session()
            try:
                download = YouTubeDownload(
                    spotify_track_id=spotify_track_id,
                    spotify_artist_id=spotify_artist_id,
                    youtube_video_id="",  # Will be set after finding video
                    download_path="",
                    download_status="downloading",
                    format_type=format_type
                )
                session.add(download)
                session.commit()
                session.refresh(download)
                download_id = download.id  # Save ID for later use
            finally:
                session.close()

            # Find best YouTube video
            try:
                videos = await youtube_client.search_music_videos(
                    artist=artist_name,
                    track=track_name,
                    max_results=3
                )

                if not videos:
                    raise Exception("No YouTube videos found for track")

                best_video = videos[0]  # Take first (already scored)
                youtube_video_id = best_video['video_id']

                # Download the audio with clean filename
                result = await youtube_client.download_audio_for_track(
                    video_id=youtube_video_id,
                    artist_name=artist_name,
                    track_name=track_name,
                    output_format=format_type
                )

                # Update database with success
                from app.core.db import get_session
                session = get_session()
                try:
                    # Find the download record again
                    download_obj = session.query(YouTubeDownload).filter(
                        YouTubeDownload.id == download_id
                    ).first()
                    if download_obj:
                        download_obj.youtube_video_id = youtube_video_id
                        download_obj.download_path = result['file_path']
                        download_obj.download_status = "completed"
                        download_obj.file_size = result.get('file_size')
                        download_obj.duration_seconds = result.get('duration_seconds', {}).get('duration_seconds')
                        session.commit()
                finally:
                    session.close()

                logger.info(f"Successfully downloaded: {track_name} - Size: {result.get('file_size', 0)} bytes")

            except Exception as e:
                # Update with error
                from app.core.db import get_session
                session = get_session()
                try:
                    download_obj = session.query(YouTubeDownload).filter(
                        YouTubeDownload.id == download_id
                    ).first()
                    if download_obj:
                        download_obj.download_status = "error"
                        download_obj.error_message = str(e)
                        session.commit()
                finally:
                    session.close()

                logger.error(f"Failed to download {track_name}: {str(e)}")

        except Exception as e:
            logger.error(f"Critical error in background download: {str(e)}")

    async def auto_download_artist_top_tracks(
        self,
        artist_name: str,
        artist_spotify_id: str,
        limit: int = 5,
        background_tasks: BackgroundTasks = None
    ):
        """Automatically download top tracks for an artist if needed."""
        try:
            logger.info(f"Checking auto-download for artist: {artist_name}")

            # Get top tracks from Spotify
            top_tracks = await spotify_client.get_artist_top_tracks(artist_name, limit=limit)
            if not top_tracks:
                logger.warning(f"No tracks found for artist: {artist_name}")
                return

            logger.info(f"Found {len(top_tracks)} tracks for {artist_name}, checking downloads...")

            # Check which tracks need downloading
            tracks_to_download = []
            for track in top_tracks:
                if not await self.is_track_downloaded(track['id']):
                    tracks_to_download.append(track)
                    logger.info(f"Track needs download: {track['name']}")

            if not tracks_to_download:
                logger.info(f"All {len(top_tracks)} tracks for {artist_name} already downloaded")
                return

            logger.info(f"Starting downloads for {len(tracks_to_download)}/{len(top_tracks)} tracks")

            # Start background downloads
            for track in tracks_to_download[:self.max_concurrent_downloads]:  # Limit concurrent
                if background_tasks:
                    background_tasks.add_task(
                        self.download_track_background,
                        track['id'],
                        artist_spotify_id,
                        track['name'],
                        artist_name,
                        "mp3"
                    )
                else:
                    # Run directly if no background tasks available
                    await self.download_track_background(
                        track['id'],
                        artist_spotify_id,
                        track['name'],
                        artist_name,
                        "mp3"
                    )

        except Exception as e:
            logger.error(f"Error in auto_download_artist_top_tracks: {str(e)}")
            raise

    async def get_artist_download_progress(self, artist_spotify_id: str) -> Dict[str, float]:
        """Get download progress for an artist's tracks."""
        from app.core.db import get_session
        session = get_session()
        try:
            from app.models.base import YouTubeDownload

            # Count total downloads for this artist
            total_downloads = session.query(YouTubeDownload).filter(
                YouTubeDownload.spotify_artist_id == artist_spotify_id
            ).count()

            # Count completed downloads
            completed_downloads = session.query(YouTubeDownload).filter(
                YouTubeDownload.spotify_artist_id == artist_spotify_id,
                YouTubeDownload.download_status == "completed"
            ).count()

            return {
                "total_expected": 5,  # We target top 5
                "total_downloads": total_downloads,
                "completed_downloads": completed_downloads,
                "progress_percentage": (completed_downloads / 5) * 100 if total_downloads > 0 else 0,
                "status": "completed" if completed_downloads >= 5 else "in_progress" if completed_downloads > 0 else "not_started"
            }
        finally:
            session.close()

# Global service instance
auto_download_service = AutoDownloadService()
