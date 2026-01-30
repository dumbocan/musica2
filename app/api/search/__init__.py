"""
Search endpoints module.

This module contains search-related functionality split into
manageable, focused sub-modules.
"""

from fastapi import APIRouter

# Import all sub-routers
from .orchestrated import router as orchestrated_router
from .artist_profile import router as artist_profile_router
from .tracks_quick import router as tracks_quick_router

# Main router
router = APIRouter(prefix="/search", tags=["search"])

# Include all sub-routers
router.include_router(orchestrated_router, prefix="/orchestrated")
router.include_router(artist_profile_router, prefix="/artist-profile")
router.include_router(tracks_quick_router, prefix="/tracks-quick")

# Export main router for app/main.py
__all__ = ["router"]
