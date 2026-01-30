"""
Modular tracks API - split from original tracks.py for better maintainability.
This module exports all tracks-related endpoints through separate router modules.
"""

from fastapi import APIRouter

# Import all sub-routers
try:
    from .overview import router as overview_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import overview router: {e}")
    overview_router = None

try:
    from .playback import router as playback_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import playback router: {e}")
    playback_router = None

try:
    from .downloads import router as downloads_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import downloads router: {e}")
    downloads_router = None

try:
    from .favorites import router as favorites_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import favorites router: {e}")
    favorites_router = None

# Create main tracks router
tracks_router = APIRouter(prefix="/tracks", tags=["tracks"])

# Include all sub-routers if they exist
if overview_router:
    tracks_router.include_router(overview_router)
if playback_router:
    tracks_router.include_router(playback_router)
if downloads_router:
    tracks_router.include_router(downloads_router)
if favorites_router:
    tracks_router.include_router(favorites_router)

# Export for main.py
__all__ = ["tracks_router"]