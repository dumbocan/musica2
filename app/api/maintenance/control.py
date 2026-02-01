"""
Maintenance control endpoints.
"""

from typing import Any, Dict

from fastapi import APIRouter, Query

from ...core.action_status import AVAILABLE_ACTIONS, get_action_statuses, set_action_status
from ...core.config import settings
from ...core.maintenance import (
    is_maintenance_enabled,
    maintenance_status,
    request_maintenance_stop,
    set_maintenance_enabled,
    start_maintenance_background,
)

router = APIRouter(prefix="", tags=["maintenance"])


@router.get("/status")
async def get_maintenance_status(
    start: bool = Query(False, description="Start maintenance if not running"),
) -> Dict[str, Any]:
    if start and is_maintenance_enabled():
        start_maintenance_background(
            delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
            stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
        )
    return {
        "enabled": is_maintenance_enabled(),
        "running": maintenance_status(),
    }


@router.post("/toggle")
async def toggle_maintenance(
    enabled: bool = Query(..., description="Enable or disable maintenance"),
) -> Dict[str, Any]:
    """Toggle maintenance on/off at runtime."""
    set_maintenance_enabled(enabled)
    return {
        "enabled": is_maintenance_enabled(),
        "message": "Maintenance enabled" if enabled else "Maintenance disabled",
    }


@router.post("/start")
async def start_maintenance_process() -> Dict[str, Any]:
    """Start the maintenance background loops."""
    if not is_maintenance_enabled():
        return {
            "enabled": False,
            "running": False,
            "message": "Maintenance disabled",
        }
    start_maintenance_background(
        delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
        stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
    )
    return {
        "enabled": True,
        "running": maintenance_status(),
    }


@router.post("/stop")
async def stop_maintenance_process() -> Dict[str, Any]:
    """Stop all maintenance processes."""
    request_maintenance_stop()
    for action in AVAILABLE_ACTIONS:
        set_action_status(action, False)
    return {"stopped": True}


@router.get("/action-status")
async def get_action_status() -> Dict[str, Any]:
    """Get status of maintenance actions."""
    return {"actions": get_action_statuses()}
