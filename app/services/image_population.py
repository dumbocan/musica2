"""
Populate local image storage for artists and albums.
"""
from __future__ import annotations

import ast
import json
from typing import Callable, Optional
from urllib.parse import parse_qs, unquote, urlparse

from sqlmodel import select

from ..core.db import get_session
from ..core.image_db_store import store_image
from ..core.image_proxy import is_placeholder_image
from ..models.base import Artist, Album, StoredImagePath


def _extract_real_url(url: str) -> str:
    if url.startswith("/images/proxy?"):
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if "url" in query_params and query_params["url"]:
            return unquote(query_params["url"][0])
    return url


def _parse_images(images_field) -> list[str]:
    if not images_field:
        return []
    parsed = None
    if isinstance(images_field, str):
        try:
            parsed = json.loads(images_field)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(images_field)
            except Exception:
                parsed = None
    else:
        parsed = images_field

    urls: list[str] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                url = item.get("url") or item.get("#text")
            else:
                url = item
            if isinstance(url, str) and url:
                url = _extract_real_url(url)
                if not is_placeholder_image(url):
                    urls.append(url)
    return urls


def _existing_entity_ids(entity_type: str) -> set[int]:
    with get_session() as session:
        rows = session.exec(
            select(StoredImagePath.entity_id).where(StoredImagePath.entity_type == entity_type)
        ).all()
    return {row for row in rows if isinstance(row, int)}


async def backfill_images(
    *,
    limit_artists: Optional[int] = None,
    limit_albums: Optional[int] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    logger=None,
) -> dict:
    should_stop = should_stop or (lambda: False)
    stats = {
        "artists_total": 0,
        "artists_migrated": 0,
        "artists_skipped": 0,
        "albums_total": 0,
        "albums_migrated": 0,
        "albums_skipped": 0,
    }

    artist_existing = _existing_entity_ids("artist")
    album_existing = _existing_entity_ids("album")

    with get_session() as session:
        artist_query = select(Artist).order_by(Artist.id.asc())
        if limit_artists:
            artist_query = artist_query.limit(limit_artists)
        artists = session.exec(artist_query).all()
    stats["artists_total"] = len(artists)

    for artist in artists:
        if should_stop():
            return stats
        if not artist or not artist.id:
            continue
        if artist.image_path_id or artist.id in artist_existing:
            stats["artists_skipped"] += 1
            continue
        urls = _parse_images(artist.images)
        if not urls:
            stats["artists_skipped"] += 1
            continue
        result = await store_image("artist", artist.id, urls[0])
        if result:
            with get_session() as session:
                artist_row = session.get(Artist, artist.id)
                if artist_row and not artist_row.image_path_id:
                    artist_row.image_path_id = result.id
                    session.add(artist_row)
                    session.commit()
            stats["artists_migrated"] += 1
        else:
            stats["artists_skipped"] += 1
        if logger and stats["artists_migrated"] and stats["artists_migrated"] % 50 == 0:
            logger.info("[images] migrated %d artists", stats["artists_migrated"])

    with get_session() as session:
        album_query = select(Album).order_by(Album.id.asc())
        if limit_albums:
            album_query = album_query.limit(limit_albums)
        albums = session.exec(album_query).all()
    stats["albums_total"] = len(albums)

    for album in albums:
        if should_stop():
            return stats
        if not album or not album.id:
            continue
        if album.image_path_id or album.id in album_existing:
            stats["albums_skipped"] += 1
            continue
        urls = _parse_images(album.images)
        if not urls:
            stats["albums_skipped"] += 1
            continue
        result = await store_image("album", album.id, urls[0])
        if result:
            with get_session() as session:
                album_row = session.get(Album, album.id)
                if album_row and not album_row.image_path_id:
                    album_row.image_path_id = result.id
                    session.add(album_row)
                    session.commit()
            stats["albums_migrated"] += 1
        else:
            stats["albums_skipped"] += 1
        if logger and stats["albums_migrated"] and stats["albums_migrated"] % 50 == 0:
            logger.info("[images] migrated %d albums", stats["albums_migrated"])

    return stats
