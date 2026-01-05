"""
Background loop that keeps the YouTube link cache populated.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlmodel import select

from .db import get_session
from ..crud import save_youtube_download
from ..models.base import Track, Artist, Album, YouTubeDownload
from ..core.youtube import youtube_client

logger = logging.getLogger(__name__)
NOT_FOUND_COOLDOWN = timedelta(days=7)
ERROR_COOLDOWN = timedelta(hours=12)


async def youtube_prefetch_loop(poll_interval: int = 60):
    """
    Continuously look for tracks that are missing a YouTube link and cache them.
    """
    cooldown_until = None

    while True:
        if cooldown_until and datetime.utcnow() < cooldown_until:
            await asyncio.sleep(5)
            continue

        target_track = target_artist = target_album = None
        cutoff_error = datetime.utcnow() - ERROR_COOLDOWN
        cutoff_not_found = datetime.utcnow() - NOT_FOUND_COOLDOWN

        with get_session() as session:
            row = session.exec(
                select(Track, Artist, Album)
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
                .outerjoin(
                    YouTubeDownload,
                    YouTubeDownload.spotify_track_id == Track.spotify_id,
                )
                .where(
                    Track.spotify_id.is_not(None),
                    or_(
                        YouTubeDownload.spotify_track_id.is_(None),
                        and_(
                            YouTubeDownload.download_status == "error",
                            or_(
                                YouTubeDownload.updated_at.is_(None),
                                YouTubeDownload.updated_at < cutoff_error,
                            ),
                        ),
                        and_(
                            YouTubeDownload.download_status == "video_not_found",
                            or_(
                                YouTubeDownload.updated_at.is_(None),
                                YouTubeDownload.updated_at < cutoff_not_found,
                            ),
                        ),
                    ),
                )
                .order_by(Track.updated_at.desc())
            ).first()
            if row:
                target_track, target_artist, target_album = row

        if not target_track:
            await asyncio.sleep(60 * 30)
            continue

        try:
            artist_name = target_artist.name if target_artist else None
            if not artist_name:
                await asyncio.sleep(5)
                continue

            logger.info(
                "[youtube_prefetch] Fetching link for %s - %s",
                artist_name,
                target_track.name,
            )

            start = datetime.utcnow()
            videos = await youtube_client.search_music_videos(
                artist=artist_name,
                track=target_track.name,
                album=target_album.name if target_album else None,
                max_results=1,
            )

            if videos:
                best = videos[0]
                save_youtube_download({
                    "spotify_track_id": target_track.spotify_id,
                    "spotify_artist_id": target_artist.spotify_id if target_artist else None,
                    "youtube_video_id": best["video_id"],
                    "download_path": "",
                    "download_status": "link_found",
                })
                logger.info(
                    "[youtube_prefetch] Cached %s - %s in %.1fs",
                    artist_name,
                    target_track.name,
                    (datetime.utcnow() - start).total_seconds(),
                )
            else:
                save_youtube_download({
                    "spotify_track_id": target_track.spotify_id,
                    "spotify_artist_id": target_artist.spotify_id if target_artist else None,
                    "youtube_video_id": "",
                    "download_path": "",
                    "download_status": "video_not_found",
                    "error_message": "No video found",
                })
                logger.info(
                    "[youtube_prefetch] No video for %s - %s (%.1fs)",
                    artist_name,
                    target_track.name,
                    (datetime.utcnow() - start).total_seconds(),
                )

            await asyncio.sleep(youtube_client.min_interval_seconds)
        except HTTPException as exc:
            save_youtube_download({
                "spotify_track_id": target_track.spotify_id,
                "spotify_artist_id": target_artist.spotify_id if target_artist else None,
                "youtube_video_id": "",
                "download_path": "",
                "download_status": "error",
                "error_message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            })
            if exc.status_code in (403, 429):
                cooldown_until = datetime.utcnow() + timedelta(minutes=15)
                logger.warning("[youtube_prefetch] API quota hit (%s). Cooling down 15 minutes.", exc.status_code)
            await asyncio.sleep(poll_interval)
        except Exception as err:
            save_youtube_download({
                "spotify_track_id": target_track.spotify_id,
                "spotify_artist_id": target_artist.spotify_id if target_artist else None,
                "youtube_video_id": "",
                "download_path": "",
                "download_status": "error",
                "error_message": str(err),
            })
            logger.error("[youtube_prefetch] Failed to cache %s: %s", target_track.spotify_id, err)
            await asyncio.sleep(poll_interval)
