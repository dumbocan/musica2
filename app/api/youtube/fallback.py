"""
yt-dlp fallback control and logs.
"""

from typing import Any, Dict

from fastapi import APIRouter, Query

from ...core.ytdlp_fallback_log import count_ytdlp_logs, get_ytdlp_log_path, read_ytdlp_logs
from ...core.youtube import youtube_client

router = APIRouter(prefix="/fallback", tags=["youtube"])


@router.get("/status")
async def get_fallback_status() -> Dict[str, Any]:
    return {
        "enabled": youtube_client.is_ytdlp_enabled(),
        "usage": youtube_client.get_ytdlp_usage(),
        "log_count": count_ytdlp_logs(),
        "log_path": get_ytdlp_log_path(),
    }


@router.post("/toggle")
async def toggle_fallback(
    enabled: bool = Query(..., description="Enable or disable yt-dlp fallback"),
) -> Dict[str, Any]:
    youtube_client.set_ytdlp_enabled(enabled)
    return {
        "enabled": youtube_client.is_ytdlp_enabled(),
    }


@router.get("/logs")
async def get_fallback_logs(
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    items = read_ytdlp_logs(limit=limit)
    return {
        "items": items,
        "count": count_ytdlp_logs(),
        "log_path": get_ytdlp_log_path(),
    }
