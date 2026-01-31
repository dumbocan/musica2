"""
Artist profile search endpoints.

Provides detailed artist information and profiles.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Query, Depends, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

@router.get("/")
async def search_artist_profile(
    request: Request,
    artist_name: str = Query(..., description="Artist name"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search artist profile with detailed information."""
    # TODO: Move search_artist_profile logic from original search.py
    # This should return comprehensive artist information
    return {"artist": None, "profile": {}, "artist_name": artist_name}

@router.get("/artist/{artist_id}")
async def get_artist_profile_by_id(
    artist_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist profile by local ID."""
    # TODO: Implement get artist profile by ID
    return {"artist": None, "profile": {}, "artist_id": artist_id}

@router.get("/artist/{artist_id}/similar")
async def get_artist_similar(
    artist_id: int,
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get similar artists."""
    # TODO: Implement similar artists
    return {"similar_artists": [], "artist_id": artist_id}

@router.get("/{artist_id}")
async def get_artist_by_id(
    artist_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist profile by ID."""
    # TODO: Implement get_artist_by_id
    return {"artist": None, "profile": {}, "artist_id": artist_id}

@router.get("/{artist_id}/similar")
async def get_artist_similar_v2(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get similar artists."""
    # TODO: Implement similar artists logic
    return {"similar_artists": [], "artist_id": artist_id}
