"""
Main artists listing endpoint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import asc, desc, exists, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep
from ...core.image_proxy import proxy_image_list
from ...core.time_utils import utc_now
from ...models.base import Artist, FavoriteTargetType, UserFavorite, UserHiddenArtist


router = APIRouter(tags=["artists"])


def _parse_images_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
    else:
        parsed = raw
    return parsed if isinstance(parsed, list) else []


def _extract_url(entry) -> str | None:
    if isinstance(entry, dict):
        url = entry.get("url") or entry.get("#text")
    elif isinstance(entry, str):
        url = entry
    else:
        url = None
    return url if isinstance(url, str) else None


def _is_proxied_images(images: list) -> bool:
    if not images:
        return False
    return all((_extract_url(img) or "").startswith("/images/proxy") for img in images)


@router.get("/")
async def get_artists(
    request: Request,
    response: Response,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    order: str = Query("pop-desc", pattern="^(pop-desc|pop-asc|name-asc)$"),
    search: str | None = Query(None, description="Filter by artist name"),
    genre: str | None = Query(None, description="Filter by genre keyword"),
    session: AsyncSession = Depends(SessionDep),
    user_id: int | None = Query(None, ge=1, description="User ID for hidden artist filtering"),
) -> Dict[str, Any]:
    """Get saved artists with pagination, ordering, and favorite/hidden filters."""
    order_by_map = {
        "pop-desc": [desc(Artist.popularity), asc(Artist.id)],
        "pop-asc": [asc(Artist.popularity), asc(Artist.id)],
        "name-asc": [asc(Artist.name), asc(Artist.id)],
    }
    order_by_clause = order_by_map.get(order, order_by_map["pop-desc"])

    effective_user_id = user_id or getattr(request.state, "user_id", None)
    hidden_filter = None
    if effective_user_id:
        hidden_filter = ~exists(
            select(1).where(
                (UserHiddenArtist.user_id == effective_user_id)
                & (UserHiddenArtist.artist_id == Artist.id)
            )
        )

    total_query = select(func.count()).select_from(Artist)
    if search:
        total_query = total_query.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        total_query = total_query.where(func.lower(Artist.genres).like(f"%\"{genre_token}\"%"))
    if hidden_filter is not None:
        total_query = total_query.where(hidden_filter)

    total = (await session.exec(total_query)).one()

    last_modified_query = select(func.max(Artist.updated_at)).select_from(Artist)
    if search:
        last_modified_query = last_modified_query.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        last_modified_query = last_modified_query.where(func.lower(Artist.genres).like(f"%\"{genre_token}\"%"))
    if hidden_filter is not None:
        last_modified_query = last_modified_query.where(hidden_filter)
    last_modified = (await session.exec(last_modified_query)).one() or utc_now()

    if effective_user_id:
        favorite_flag = exists(
            select(1).where(
                (UserFavorite.user_id == effective_user_id)
                & (UserFavorite.target_type == FavoriteTargetType.ARTIST)
                & (UserFavorite.artist_id == Artist.id)
            )
        ).label("is_favorite")
        statement = (
            select(Artist, favorite_flag)
            .order_by(*order_by_clause)
            .offset(offset)
            .limit(limit)
        )
    else:
        statement = select(Artist).order_by(*order_by_clause).offset(offset).limit(limit)

    if search:
        statement = statement.where(Artist.name.ilike(f"%{search}%"))
    if genre:
        genre_token = genre.strip().lower()
        statement = statement.where(func.lower(Artist.genres).like(f"%\"{genre_token}\"%"))
    if hidden_filter is not None:
        statement = statement.where(hidden_filter)

    rows = (await session.exec(statement)).all()
    response_items = []
    for row in rows:
        if effective_user_id:
            artist, is_favorite = row
        else:
            artist, is_favorite = row, None
        payload = artist.dict()
        if is_favorite is not None:
            payload["is_favorite"] = bool(is_favorite)
        stored_images = _parse_images_field(artist.images)
        if stored_images and not _is_proxied_images(stored_images):
            proxied = proxy_image_list(stored_images, size=256)
            if proxied:
                payload["images"] = json.dumps(proxied)
        response_items.append(payload)

    payload = {"items": response_items, "total": int(total)}
    etag = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    if request.headers.get("if-none-match") == etag:
        response.headers["Cache-Control"] = "private, max-age=120"
        response.headers["ETag"] = etag
        response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
        response.status_code = 304
        return {}
    if isinstance(last_modified, datetime):
        try:
            ims = parsedate_to_datetime(request.headers.get("if-modified-since", ""))
        except (TypeError, ValueError):
            ims = None
        if ims and ims >= last_modified.replace(tzinfo=timezone.utc):
            response.headers["Cache-Control"] = "private, max-age=120"
            response.headers["ETag"] = etag
            response.headers["Last-Modified"] = format_datetime(
                last_modified.replace(tzinfo=timezone.utc), usegmt=True
            )
            response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
            response.status_code = 304
            return {}

    response.headers["Cache-Control"] = "private, max-age=120"
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = format_datetime(
        last_modified.replace(tzinfo=timezone.utc), usegmt=True
    )
    response.headers["Vary"] = "Authorization, Cookie, Accept-Encoding"
    return payload
