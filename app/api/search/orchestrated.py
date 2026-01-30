"""
Orchestrated search endpoints.

Handles the main search functionality that combines multiple sources.
"""

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Artist, Album, Track
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrated", tags=["search"])

@router.get("/")
async def search_orchestrated(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Search query"),
    user_id: int = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Orchestrated search with caching and fallbacks."""
    # TODO: Move search_orchestrated logic from original search.py
    # This should combine local DB search with external APIs
    pass

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
