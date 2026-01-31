"""
Modular maintenance API - split from original maintenance.py for better maintainability.
This module exports all maintenance-related endpoints through separate router modules.
"""

from fastapi import APIRouter

# Import all sub-routers
try:
    from .control import router as control_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import control router: {e}")
    control_router = None

try:
    from .backfill import router as backfill_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import backfill router: {e}")
    backfill_router = None

try:
    from .logs import router as logs_router
except ImportError as e:
    print(f"⚠️ Warning: Could not import logs router: {e}")
    logs_router = None

# Create main maintenance router
maintenance_router = APIRouter(prefix="/maintenance", tags=["maintenance"])

# Include all sub-routers if they exist
if control_router:
    maintenance_router.include_router(control_router)
if backfill_router:
    maintenance_router.include_router(backfill_router)
if logs_router:
    maintenance_router.include_router(logs_router)

# Export for main.py
__all__ = ["maintenance_router"]
