"""
Track maintenance action statuses so the UI can persist toggle states.
"""
from __future__ import annotations

from threading import Lock
from typing import Any, Awaitable, Callable

AVAILABLE_ACTIONS = {
    "albums_missing",
    "albums_incomplete",
    "youtube_links",
    "metadata_refresh",
    "chart_backfill",
    "audit",
    "images_backfill",
    "repair_album_images",
}

_lock = Lock()
_statuses: dict[str, bool] = {action: False for action in AVAILABLE_ACTIONS}


def set_action_status(action: str, value: bool) -> None:
    if action not in AVAILABLE_ACTIONS:
        return
    with _lock:
        _statuses[action] = value


def get_action_statuses() -> dict[str, bool]:
    with _lock:
        return dict(_statuses)


async def run_with_action_status(
    action: str,
    coro: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    set_action_status(action, True)
    try:
        return await coro(*args, **kwargs)
    finally:
        set_action_status(action, False)
