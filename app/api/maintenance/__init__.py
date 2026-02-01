"""
Modular maintenance API - split from original maintenance.py for better maintainability.
This module exports all maintenance-related endpoints through separate router modules.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

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

logger = logging.getLogger(__name__)

# Create main maintenance router
maintenance_router = APIRouter(prefix="/maintenance", tags=["maintenance"])

# Include all sub-routers if they exist
if control_router:
    maintenance_router.include_router(control_router)
if backfill_router:
    maintenance_router.include_router(backfill_router)
if logs_router:
    maintenance_router.include_router(logs_router)


@maintenance_router.get("/action-status")
async def get_action_status_simple() -> Dict[str, Any]:
    """Get action status - alias for control/action-status."""
    from ...core.action_status import get_action_statuses
    return {
        "actions": get_action_statuses(),
    }


@maintenance_router.get("/status")
async def get_maintenance_status_simple() -> Dict[str, Any]:
    """Get maintenance system status - alias for control/status."""
    from ...core.maintenance import maintenance_stop_requested
    from ...core.action_status import get_action_statuses
    return {
        "status": "running",
        "active_processes": [],
        "stop_requested": maintenance_stop_requested(),
        "actions": get_action_statuses(),
    }


@maintenance_router.get("/dashboard")
async def get_dashboard_stats(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get dashboard statistics - alias for logs/dashboard."""
    from sqlalchemy import func
    from ...models.base import Artist, Album, Track, YouTubeDownload
    from ...core.db import get_session

    with get_session() as sync_session:
        artist_count = sync_session.query(func.count(Artist.id)).scalar() or 0
        album_count = sync_session.query(func.count(Album.id)).scalar() or 0
        track_count = sync_session.query(func.count(Track.id)).scalar() or 0
        youtube_downloads = sync_session.query(func.count(YouTubeDownload.id)).scalar() or 0

    return {
        "artists": artist_count,
        "albums": album_count,
        "tracks": track_count,
        "youtube_downloads": youtube_downloads,
        "storage": {
            "images_count": 0,  # Would need additional query
            "downloads_size_mb": 0,
        }
    }


# Export for main.py
__all__ = ["maintenance_router"]
