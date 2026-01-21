from __future__ import annotations

import logging
import threading
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Tuple

_BUFFER_MAX = 2000
_buffer: Deque[Dict[str, object]] = deque(maxlen=_BUFFER_MAX)
_lock = threading.Lock()
_next_id = 1
_installed = False
_handler: _LogBufferHandler | None = None


class _LogBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name == "uvicorn.access":
            return
        global _next_id
        try:
            message = record.getMessage()
            if record.exc_info:
                message = f"{message}\n{''.join(traceback.format_exception(*record.exc_info))}".rstrip()
            elif record.exc_text:
                message = f"{message}\n{record.exc_text}".rstrip()

            ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            line = f"{ts} {record.levelname} {record.name}: {message}"

            with _lock:
                entry = {
                    "id": _next_id,
                    "ts": ts,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": message,
                    "line": line,
                }
                _buffer.append(entry)
                _next_id += 1
        except Exception:
            # Avoid breaking logging on handler failure
            return


def _attach_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    for existing in logger.handlers:
        if existing is handler:
            return
    logger.addHandler(handler)


def install_log_buffer() -> None:
    global _installed, _handler
    if _installed:
        return
    handler = _LogBufferHandler()
    handler.setLevel(logging.INFO)
    _handler = handler
    root_logger = logging.getLogger()
    _attach_handler(root_logger, handler)
    # Capture uvicorn logs that do not propagate to root.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        _attach_handler(logging.getLogger(name), handler)
    # Ensure maintenance loggers emit INFO so the UI can show progress.
    for name in (
        "app.core.maintenance",
        "app.api.maintenance",
        "app.services.library_expansion",
        "app.core.data_freshness",
        "app.core.youtube_prefetch",
    ):
        logger = logging.getLogger(name)
        if logger.level in (0, logging.WARNING, logging.ERROR, logging.CRITICAL):
            logger.setLevel(logging.INFO)
    _installed = True


def get_log_entries(since_id: int | None, limit: int) -> Tuple[List[Dict[str, object]], int | None]:
    with _lock:
        items = list(_buffer)
    if since_id is not None:
        items = [entry for entry in items if int(entry.get("id", 0)) > since_id]
    if limit and len(items) > limit:
        items = items[-limit:]
    last_id = int(items[-1]["id"]) if items else (int(_buffer[-1]["id"]) if _buffer else None)
    return items, last_id


def clear_log_entries() -> None:
    global _next_id
    with _lock:
        _buffer.clear()
        _next_id = 1
