"""
Modular YouTube API - split from original youtube.py for better maintainability.
This module exports all YouTube-related endpoints through separate router modules.
"""

from fastapi import APIRouter

# Import all sub-routers
try:
    from .search import router as search_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import search router: {e}")
    search_router = None

try:
    from .downloads import router as downloads_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import downloads router: {e}")
    downloads_router = None

try:
    from .links import router as links_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import links router: {e}")
    links_router = None

try:
    from .prefetch import router as prefetch_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import prefetch router: {e}")
    prefetch_router = None

try:
    from .usage import router as usage_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import usage router: {e}")
    usage_router = None

try:
    from .fallback import router as fallback_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import fallback router: {e}")
    fallback_router = None

# Create main youtube router
youtube_router = APIRouter(prefix="/youtube", tags=["youtube"])

# Include all sub-routers if they exist
if search_router:
    youtube_router.include_router(search_router)
if downloads_router:
    youtube_router.include_router(downloads_router)
if links_router:
    youtube_router.include_router(links_router)
if prefetch_router:
    youtube_router.include_router(prefetch_router)
if usage_router:
    youtube_router.include_router(usage_router)
if fallback_router:
    youtube_router.include_router(fallback_router)

# Export for main.py
__all__ = ["youtube_router"]
