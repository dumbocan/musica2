"""
Main artists listing endpoint.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Path, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Artist
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["artists"])

@router.get("/")
async def get_artists(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get all artists with pagination."""
    # TODO: Implement artists listing
    return {"artists": [], "total": 0, "offset": offset, "limit": limit}