"""
Quick track search endpoints.

Provides fast track searching capabilities.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.get("/")
async def search_tracks_quick(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Track name"),
    artist: str = Query(None, description="Filter by artist name"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Quick track search with optional artist filter."""
    # TODO: Move search_tracks_quick logic from original search.py
    # This should be optimized for speed
    return {"tracks": [], "total": 0, "query": query}


@router.get("/album/{album_id}")
async def get_album_tracks_quick(
    album_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get tracks from an album quickly."""
    # TODO: Implement album tracks quick search
    return {"tracks": [], "total": 0, "album_id": album_id}
