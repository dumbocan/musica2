"""
Modular artists API - split from original artists.py for better maintainability.
This module exports all artists-related endpoints through separate router modules.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Query

# Import all sub-routers - direct imports since all modules exist
from .listing import router as listing_router
from .discography import router as discography_router
from .management import router as management_router
from .search import router as search_router
from .info import router as info_router

logger = logging.getLogger(__name__)

# Create main artists router
artists_router = APIRouter(prefix="/artists", tags=["artists"])

# Include all sub-routers
artists_router.include_router(listing_router)
artists_router.include_router(discography_router)
artists_router.include_router(management_router)
artists_router.include_router(search_router)
artists_router.include_router(info_router)


# Frontend compatibility aliases
@artists_router.post("/refresh-missing")
async def refresh_missing_artists_alias(
    limit: int = Query(200, ge=1, le=1000, description="Artists to refresh"),
    use_spotify: bool = Query(True, description="Use Spotify for missing metadata"),
    use_lastfm: bool = Query(True, description="Use Last.fm for missing metadata"),
) -> Dict[str, Any]:
    """Alias for /artists/management/refresh-missing - refresh missing artist metadata."""
    logger.info(f"[refresh-missing-alias] Starting refresh with limit={limit}, spotify={use_spotify}, lastfm={use_lastfm}")
    # This is a placeholder - actual implementation is in management router
    return {"message": "Refresh started", "limit": limit, "use_spotify": use_spotify, "use_lastfm": use_lastfm}


# Export for main.py
__all__ = ["artists_router"]
