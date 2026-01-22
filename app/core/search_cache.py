"""Persistent cache helpers for normalized search payloads."""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..models.base import SearchCacheEntry
from .time_utils import utc_now

logger = logging.getLogger(__name__)

SEARCH_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


async def read_cached_search(
    session: AsyncSession,
    cache_key: str,
    ttl_seconds: int = SEARCH_CACHE_TTL_SECONDS,
) -> Optional[dict]:
    if not cache_key:
        return None
    stmt = select(SearchCacheEntry).where(SearchCacheEntry.cache_key == cache_key)
    entry = await session.exec(stmt)
    cached = entry.first()
    if not cached:
        return None
    age = (utc_now() - cached.updated_at).total_seconds()
    if age > ttl_seconds:
        return None
    try:
        return json.loads(cached.payload)
    except json.JSONDecodeError:
        logger.warning("[search_cache] invalid payload for %s", cache_key)
        return None


async def write_cached_search(
    session: AsyncSession,
    cache_key: str,
    payload: dict,
    context: Optional[str] = None,
) -> None:
    if not cache_key or payload is None:
        return
    try:
        payload_text = json.dumps(payload)
    except TypeError as exc:
        logger.warning("[search_cache] payload not serializable: %s", exc)
        return
    stmt = select(SearchCacheEntry).where(SearchCacheEntry.cache_key == cache_key)
    entry = await session.exec(stmt)
    existing = entry.first()
    now = utc_now()
    if existing:
        existing.payload = payload_text
        existing.context = context
        existing.updated_at = now
        session.add(existing)
    else:
        new_entry = SearchCacheEntry(
            cache_key=cache_key,
            context=context,
            payload=payload_text,
            created_at=now,
            updated_at=now,
        )
        session.add(new_entry)
    try:
        await session.commit()
    except Exception as exc:
        logger.warning("[search_cache] commit failed for %s: %s", cache_key, exc)
        await session.rollback()
