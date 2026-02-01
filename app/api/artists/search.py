"""
Artist search and discovery endpoints.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["artists"])


@router.get("/")
async def search_artists(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search artists by name."""
    # TODO: Implement artist search
    return {"artists": [], "total": 0}


@router.get("/auto-download")
async def search_artists_auto_download(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search artists with auto-download functionality."""
    # TODO: Implement auto-download search
    return {"artists": [], "total": 0}
