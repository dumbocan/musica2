"""
Modular artists API - split from original artists.py for better maintainability.
This module exports all artists-related endpoints through separate router modules.
"""

from fastapi import APIRouter

# Import all sub-routers - direct imports since all modules exist
from .listing import router as listing_router
from .discography import router as discography_router
from .management import router as management_router
from .search import router as search_router
from .info import router as info_router

# Create main artists router
artists_router = APIRouter(prefix="/artists", tags=["artists"])

# Include all sub-routers
artists_router.include_router(listing_router)
artists_router.include_router(discography_router)
artists_router.include_router(management_router)
artists_router.include_router(search_router)
artists_router.include_router(info_router)

# Export for main.py
__all__ = ["artists_router"]