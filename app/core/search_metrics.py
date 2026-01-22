"""
Lightweight in-memory search metrics for observability and tuning.
"""

from threading import Lock
from typing import Dict, Optional

_metrics_lock = Lock()
_metrics: Dict[str, Dict[str, int]] = {
    "local": {},
    "external": {},
}


def _record(category: str, user_id: Optional[int]) -> None:
    key = str(user_id or "anon")
    bucket = _metrics.get(category)
    if bucket is None:
        return
    with _metrics_lock:
        bucket[key] = bucket.get(key, 0) + 1
        bucket["global"] = bucket.get("global", 0) + 1


def record_local_resolution(user_id: Optional[int]) -> None:
    """Call when a search is resolved purely from local data."""
    _record("local", user_id)


def record_external_resolution(user_id: Optional[int]) -> None:
    """Call when search hits external APIs."""
    _record("external", user_id)


def get_search_metrics() -> Dict[str, Dict[str, int]]:
    """Return a snapshot of current search metrics."""
    with _metrics_lock:
        return {
            "local": dict(_metrics["local"]),
            "external": dict(_metrics["external"]),
        }
