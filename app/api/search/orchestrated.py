"""
Orchestrated search endpoints.

Handles the main search functionality that combines multiple sources.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.get("/")
async def search_orchestrated(
    request: Request,
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Orchestrated search combining multiple sources."""
    # TODO: Move search_orchestrated logic from original search.py
    # This should combine Spotify, Last.fm, and local results
    return {"results": [], "total": 0, "query": query}


@router.get("/system/status")
async def get_search_system_status(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get search system status."""
    # TODO: Implement search status
    return {"status": "operational", "sources": ["local", "spotify", "lastfm"]}


@router.get("/status")
async def get_search_status(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get search system status."""
    # TODO: Implement status check
    return {
        "status": "active",
        "local_index_size": 0,
        "external_apis": {
            "spotify": bool(settings.SPOTIFY_CLIENT_ID),
            "lastfm": bool(settings.LASTFM_API_KEY),
            "youtube": bool(settings.YOUTUBE_API_KEY)
        }
    }
