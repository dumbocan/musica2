"""
YouTube download and management endpoints.

Handles YouTube downloads, status tracking, and file management.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Track, YouTubeDownload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/downloads", tags=["tracks"])


@router.get("/{track_id}")
async def get_track_download_status(
    track_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get download status for a track."""
    from sqlmodel import select

    # Get track info
    with get_session() as sync_session:
        track = sync_session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Get YouTube download info
        download = None
        if track.spotify_id:
            download = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == track.spotify_id)
            ).first()

        # Determine status
        if not download:
            return {
                "track_id": track_id,
                "spotify_track_id": track.spotify_id,
                "youtube_status": "not_found",
                "download_status": "not_found",
                "file_path": None,
                "file_exists": False,
                "video_url": None,
                "video_id": None
            }

        # Check file existence
        file_path = download.download_path
        file_exists = Path(file_path).exists() if file_path else False
        video_url = f"https://www.youtube.com/watch?v={download.youtube_video_id}" if download.youtube_video_id else None

        # Determine combined status
        youtube_status = download.download_status
        if file_exists and youtube_status != "completed":
            youtube_status = "completed"
        elif download.youtube_video_id and not youtube_status:
            youtube_status = "link_found"

        return {
            "track_id": track_id,
            "spotify_track_id": track.spotify_id,
            "youtube_status": youtube_status,
            "download_status": download.download_status,
            "file_path": file_path,
            "file_exists": file_exists,
            "video_url": video_url,
            "video_id": download.youtube_video_id,
            "download_progress": download.download_progress if download else 0,
            "file_size": download.file_size if download else 0,
            "created_at": download.created_at.isoformat() if download.created_at else None,
            "updated_at": download.updated_at.isoformat() if download.updated_at else None
        }


@router.post("/{track_id}")
async def start_track_download(
    track_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Start YouTube download for a track."""
    from sqlmodel import select

    # Get track info
    with get_session() as sync_session:
        track = sync_session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Check for existing download
        if track.spotify_id:
            existing = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == track.spotify_id)
            ).first()

            if existing and existing.download_status in ("downloading", "completed"):
                return {
                    "message": "Download already in progress or completed",
                    "track_id": track_id,
                    "download_status": existing.download_status
                }

        # Create or update download record
        download = existing if existing else YouTubeDownload(
            spotify_track_id=track.spotify_id,
            download_status="pending"
        )

        if existing:
            download.download_status = "pending"
            sync_session.add(download)

        try:
            # In real implementation, this would trigger background YouTube download
            # For now, we'll mark as started
            download.download_status = "started"
            download.started_at = datetime.utcnow()
            sync_session.commit()

            # TODO: Integrate with youtube_client.start_download(track_id)
            logger.info(f"Download started for track {track_id}")

            return {
                "message": "Download started",
                "track_id": track_id,
                "download_status": "started"
            }

        except Exception as e:
            download.download_status = "failed"
            download.error_message = str(e)
            sync_session.commit()
            logger.error(f"Download failed for track {track_id}: {e}")

            return {
                "message": "Download failed",
                "track_id": track_id,
                "download_status": "failed",
                "error": str(e)
            }


@router.get("/{track_id}/file")
async def get_track_download_file(
    track_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get downloaded track file."""
    from sqlmodel import select

    # Get download info
    with get_session() as sync_session:
        track = sync_session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Get download
        download = None
        if track.spotify_id:
            download = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == track.spotify_id)
            ).first()

        if not download or not download.download_path:
            return {
                "message": "File not available",
                "track_id": track_id,
                "file_exists": False
            }

        # Check file existence
        file_path = Path(download.download_path)
        if not file_path.exists():
            return {
                "message": "File not found on disk",
                "track_id": track_id,
                "file_path": download.download_path,
                "file_exists": False
            }

        # In real implementation, this would serve the file
        # For now, return file info
        return {
            "message": "File available",
            "track_id": track_id,
            "file_path": download.download_path,
            "file_exists": True,
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "mime_type": "audio/mpeg",  # Default, should detect real type
            "download_url": f"/downloads/track/{track_id}/file-content"
        }
