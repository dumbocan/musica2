from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from .config import settings


_lock = threading.Lock()
_last_prune_at: datetime | None = None


def _log_path() -> Path:
    root = (settings.STORAGE_ROOT or "storage").strip() or "storage"
    return Path(root).expanduser() / "logs" / "ytdlp_fallback.log"


def get_ytdlp_log_path() -> str:
    return str(_log_path())


def _ensure_log_dir() -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)


def _parse_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _retention_cutoff() -> datetime:
    retention_days = max(1, int(getattr(settings, "LOG_RETENTION_DAYS", 30)))
    return datetime.now(timezone.utc) - timedelta(days=retention_days)


def _should_prune(now: datetime) -> bool:
    if _last_prune_at is None:
        return True
    return now - _last_prune_at > timedelta(hours=6)


def _prune_locked(cutoff: datetime) -> None:
    path = _log_path()
    if not path.exists():
        return
    kept: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = payload.get("ts")
            if not isinstance(ts, str):
                continue
            parsed = _parse_ts(ts)
            if parsed is None or parsed >= cutoff:
                kept.append(json.dumps(payload, ensure_ascii=True))
    tmp_path = path.with_suffix(".log.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for line in kept:
            handle.write(f"{line}\n")
    tmp_path.replace(path)


def append_ytdlp_log(entry: Dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    payload = dict(entry)
    payload.setdefault("ts", now.isoformat())
    payload.setdefault("source", "ytdlp")
    with _lock:
        _ensure_log_dir()
        if _should_prune(now):
            _prune_locked(_retention_cutoff())
            global _last_prune_at
            _last_prune_at = now
        path = _log_path()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{json.dumps(payload, ensure_ascii=True)}\n")


def read_ytdlp_logs(limit: int = 200) -> List[Dict[str, Any]]:
    path = _log_path()
    if not path.exists():
        return []
    cutoff = _retention_cutoff()
    items: List[Dict[str, Any]] = []
    with _lock:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = payload.get("ts")
                if isinstance(ts, str):
                    parsed = _parse_ts(ts)
                    if parsed is not None and parsed < cutoff:
                        continue
                items.append(payload)
        if len(items) > limit:
            items = items[-limit:]
    return items


def count_ytdlp_logs() -> int:
    path = _log_path()
    if not path.exists():
        return 0
    cutoff = _retention_cutoff()
    count = 0
    with _lock:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = payload.get("ts")
                if isinstance(ts, str):
                    parsed = _parse_ts(ts)
                    if parsed is not None and parsed < cutoff:
                        continue
                count += 1
    return count
