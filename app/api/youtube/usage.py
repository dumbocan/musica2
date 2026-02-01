"""
YouTube usage statistics endpoints.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter

from ...core.db import get_session
from ...models.base import YouTubeDownload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usage", tags=["youtube"])


@router.get("/")
async def get_youtube_usage() -> Dict[str, Any]:
    """Get YouTube API usage statistics."""
    with get_session() as session:
        from sqlalchemy import func

        # Get total downloads count
        total_downloads = session.query(func.count(YouTubeDownload.id)).scalar() or 0

        # Get completed downloads
        completed_downloads = session.query(func.count(YouTubeDownload.id)).filter(
            YouTubeDownload.download_status == "completed"
        ).scalar() or 0

        # Get pending downloads
        pending_downloads = session.query(func.count(YouTubeDownload.id)).filter(
            YouTubeDownload.download_status == "pending"
        ).scalar() or 0

        # Get failed downloads
        failed_downloads = session.query(func.count(YouTubeDownload.id)).filter(
            YouTubeDownload.download_status == "failed"
        ).scalar() or 0

        return {
            "total": total_downloads,
            "completed": completed_downloads,
            "pending": pending_downloads,
            "failed": failed_downloads,
        }
