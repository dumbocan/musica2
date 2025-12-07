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
        async with SessionDep() as session:
            download = await session.get_first(
                select(YouTubeDownload).where(
                    YouTubeDownload.spotify_track_id == spotify_track_id,
                    YouTubeDownload.format_type == format_type,
                    YouTubeDownload.download_status == "completed"
                )
            )
            return download is not None

    async def track_download_status(self, spotify_track_id: str, format_type: str = "mp3") -> Optional[str]:
        """Get download status for a track."""
        async with SessionDep() as session:
            download = await session.get_first(
                select(YouTubeDownload).where(
                    YouTubeDownload.spotify_track_id == spotify_track_id,
                    YouTubeDownload.format_type == format_type
                )
            )
            return download.download_status if download else None

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

            # Mark as downloading
            async with SessionDep() as session:
                download = YouTubeDownload(
                    spotify_track_id=spotify_track_id,
                    spotify_artist_id=spotify_artist_id,
                    youtube_video_id="",  # Will be set after finding video
                    download_path="",
                    download_status="downloading",
                    format_type=format_type
                )
                session.add(download)
                await session.commit()
                await session.refresh(download)

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

                # Download the audio
                result = await youtube_client.download_audio(
                    video_id=youtube_video_id,
                    output_format=format_type
                )

                # Update database with success
                async with SessionDep() as session:
                    download.youtube_video_id = youtube_video_id
                    download.download_path = result['file_path']
                    download.download_status = "completed"
                    download.file_size = result.get('file_size')
                    download.duration_seconds = result.get('duration_seconds', {}).get('duration_seconds')
                    download.updated_at = download.created_at  # Will be auto-updated
                    await session.commit()

                logger.info(f"Successfully downloaded: {track_name} - Size: {result.get('file_size', 0)} bytes")

            except Exception as e:
                # Update with error
                async with SessionDep() as session:
                    download.download_status = "error"
                    download.error_message = str(e)
                    await session.commit()

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
        async with SessionDep() as session:
            total_downloads = await session.get_count(
                select(YouTubeDownload).where(
                    YouTubeDownload.spotify_artist_id == artist_spotify_id
                )
            )

            completed_downloads = await session.get_count(
                select(YouTubeDownload).where(
                    YouTubeDownload.spotify_artist_id == artist_spotify_id,
                    YouTubeDownload.download_status == "completed"
                )
            )

            return {
                "total_expected": 5,  # We target top 5
                "total_downloads": total_downloads,
                "completed_downloads": completed_downloads,
                "progress_percentage": (completed_downloads / 5) * 100 if total_downloads > 0 else 0,
                "status": "completed" if completed_downloads >= 5 else "in_progress" if completed_downloads > 0 else "not_started"
            }

# Global service instance
auto_download_service = AutoDownloadService()
