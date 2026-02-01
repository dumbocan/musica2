"""
Modular artists API - split from original artists.py for better maintainability.
This module exports all artists-related endpoints through separate router modules.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

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
@artists_router.get("/{spotify_id}/info")
async def get_artist_info_alias(
    spotify_id: str,
    session: AsyncSession = Depends(SessionDep),
) -> Dict[str, Any]:
    """Alias for /artists/info/{spotify_id}/info."""
    from .info import get_artist_info

    return await get_artist_info(spotify_id=spotify_id, session=session)


@artists_router.get("/{spotify_id}/albums")
async def get_artist_albums_alias(
    spotify_id: str,
    refresh: bool = Query(False, description="Force refresh from Spotify if available"),
    session: AsyncSession = Depends(SessionDep),
) -> Any:
    """Alias for /artists/discography/{spotify_id}/albums."""
    from .discography import get_artist_albums

    return await get_artist_albums(spotify_id=spotify_id, refresh=refresh, session=session)


@artists_router.get("/spotify/{spotify_id}/local")
async def get_local_artist_by_spotify_id_alias(
    spotify_id: str,
    session: AsyncSession = Depends(SessionDep),
) -> Any:
    """Alias for /artists/info/spotify/{spotify_id}/local."""
    from .info import get_local_artist_by_spotify_id

    return await get_local_artist_by_spotify_id(spotify_id=spotify_id, session=session)


@artists_router.post("/refresh-missing")
async def refresh_missing_artists_alias(
    limit: int = Query(200, ge=1, le=1000, description="Artists to refresh"),
    use_spotify: bool = Query(True, description="Use Spotify for missing metadata"),
    use_lastfm: bool = Query(True, description="Use Last.fm for missing metadata"),
) -> Dict[str, Any]:
    """Alias for /artists/management/refresh-missing - refresh missing artist metadata."""
    logger.info(
        "[refresh-missing-alias] Starting refresh with limit=%s, spotify=%s, lastfm=%s",
        limit,
        use_spotify,
        use_lastfm,
    )
    from .management import refresh_missing_artist_metadata

    return await refresh_missing_artist_metadata(
        limit=limit,
        use_spotify=use_spotify,
        use_lastfm=use_lastfm,
    )


# Export for main.py
__all__ = ["artists_router"]
