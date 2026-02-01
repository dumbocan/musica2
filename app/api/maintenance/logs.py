"""
Maintenance logs endpoints.
"""

from typing import Any, Dict

from fastapi import APIRouter, Query

from ...core.log_buffer import clear_log_entries, get_log_entries

router = APIRouter(prefix="/logs", tags=["maintenance"])


@router.get("")
@router.get("/")
async def get_maintenance_logs(
    since_id: int | None = Query(None, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    scope: str = Query("all", pattern="^(all|maintenance|errors)$"),
) -> Dict[str, Any]:
    """Get maintenance logs."""
    items, last_id = get_log_entries(since_id, limit)
    if scope == "maintenance":
        tokens = ("[maintenance]", "[discography]", "[audit]", "[youtube_prefetch]", "backfill", "refresh-missing")
        prefixes = (
            "app.core.maintenance",
            "app.api.maintenance",
            "app.services.library_expansion",
            "app.core.data_freshness",
            "app.core.youtube_prefetch",
        )
        filtered = []
        for entry in items:
            logger_name = str(entry.get("logger") or "")
            message = str(entry.get("message") or "")
            if logger_name.startswith(prefixes):
                filtered.append(entry)
                continue
            if any(token in message for token in tokens):
                filtered.append(entry)
        items = filtered
    elif scope == "errors":
        items = [entry for entry in items if str(entry.get("level") or "").upper() in {"ERROR", "WARNING"}]
    return {"items": items, "last_id": last_id}


@router.post("/clear")
async def clear_maintenance_logs() -> Dict[str, Any]:
    """Clear maintenance logs."""
    clear_log_entries()
    return {"cleared": True}
