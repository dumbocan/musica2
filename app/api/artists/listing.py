"""
Main artists listing endpoint.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Artist

logger = logging.getLogger(__name__)


router = APIRouter(tags=["artists"])

@router.get("/")
async def get_artists(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    search: Optional[str] = Query(None, description="Search by artist name"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get all artists with pagination and search."""
    from sqlmodel import select, func
    import re

    def normalize_search(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def normalized_column(column):
        return func.regexp_replace(func.lower(column), "[^a-z0-9]+", " ", "g")

    with get_session() as sync_session:
        base_query = select(Artist).order_by(Artist.name.asc())
        
        # Apply search filter
        if search:
            search_term = normalize_search(search)
            if search_term:
                pattern = f"%{search_term}%"
                base_query = base_query.where(
                    normalized_column(Artist.name).ilike(pattern)
                )
        
        # Apply pagination
        artists = sync_session.exec(base_query.offset(offset).limit(limit)).all()
        
        # Get total count
        total_query = select(func.count(Artist.id))
        if search:
            total_query = total_query.where(
                normalized_column(Artist.name).ilike(f"%{normalize_search(search)}%")
            )
        
        total = sync_session.exec(total_query).one()
        
        return {
            "artists": [
                {
                    "id": artist.id,
                    "spotify_id": artist.spotify_id,
                    "name": artist.name,
                    "genres": artist.genres,
                    "images": artist.images,
                    "popularity": artist.popularity,
                    "followers": artist.followers,
                    "created_at": artist.created_at.isoformat() if artist.created_at else None,
                    "updated_at": artist.updated_at.isoformat() if artist.updated_at else None
                }
                for artist in artists
            ],
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": len(artists) == limit
        }
