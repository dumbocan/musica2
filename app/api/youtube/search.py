"""
YouTube search endpoints.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["youtube"])

@router.get("/")
async def search_youtube(
    query: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search YouTube for videos."""
    # TODO: Implement YouTube search
    return {"videos": [], "total": 0, "query": query}


@router.get("/music")
async def search_youtube_music(
    query: str = Query(..., description="Music search query"),
    limit: int = Query(20, ge=1, le=50, description="Number of results"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search YouTube for music specifically."""
    # TODO: Implement YouTube music search
    return {"videos": [], "total": 0, "query": query}
