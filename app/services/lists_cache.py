"""
Cache service for curated lists.
Stores pre-computed lists in memory with TTL for fast retrieval.
"""

import time
import threading
from typing import Any
from datetime import datetime
from sqlmodel import select
from app.core.db import get_session
from app.models.base import Track, Artist, Album, UserFavorite, YouTubeDownload, PlayHistory
from app.services.smart_lists import SmartListsService

# Cache storage: {cache_key: {"data": [...], "expires_at": timestamp, "last_updated": datetime}}
_lists_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()

# Default TTL: 5 minutes
DEFAULT_TTL_SECONDS = 300

# List configurations
LIST_CONFIGS = {
    "favorites-with-link": {"limit": 50, "description": "Favoritos con enlace de YouTube"},
    "downloaded": {"limit": 50, "description": "Música descargada"},
    "discovery": {"limit": 50, "description": "Descubrimiento"},
    "top-year": {"limit": 50, "description": "Mejores del último año"},
    "most-played": {"limit": 50, "description": "Más reproducidas"},
    "genre-suggestions": {"limit": 50, "description": "Géneros parecidos"},
}


def _is_valid_youtube_id(value: str | None) -> bool:
    """Validate YouTube video ID (11 chars)."""
    if not value or len(value) != 11:
        return False
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", value))


def _track_to_dict(track: Track, artist: Artist | None, album: Album | None,
                   download: YouTubeDownload | None) -> dict:
    """Convert track to dictionary for curated lists."""
    image_url = None
    if album and album.images:
        try:
            import json
            images = json.loads(album.images)
            if images and len(images) > 0:
                image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
        except Exception:
            pass

    if not image_url and artist and artist.images:
        try:
            import json
            images = json.loads(artist.images)
            if images and len(images) > 0:
                image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
        except Exception:
            pass

    valid_video_id = None
    if download and _is_valid_youtube_id(download.youtube_video_id):
        valid_video_id = download.youtube_video_id

    file_path = track.download_path or (download.download_path if download else None)

    return {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "image_url": image_url,
        "videoId": valid_video_id,
        "download_path": file_path,
        "download_status": download.download_status if download else None,
        "artist_name": artist.name if artist else None,
        "artist_spotify_id": artist.spotify_id if artist else None,
        "album_name": album.name if album else None,
        "album_spotify_id": album.spotify_id if album else None,
    }


def _generate_list(list_type: str, user_id: int = 1, limit: int = 50) -> list[dict]:
    """Generate a single curated list."""
    with get_session() as session:
        service = SmartListsService(session)

        if list_type == "favorites-with-link":
            # Get favorites with valid YouTube links
            query = (
                select(Track, Artist, Album, YouTubeDownload)
                .join(UserFavorite, UserFavorite.track_id == Track.id)
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
                .outerjoin(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "TRACK")
                .where(YouTubeDownload.youtube_video_id.is_not(None))
            )
            rows = session.exec(query.limit(limit * 2)).all()  # Get more to filter
            results = []
            for track, artist, album, download in rows:
                if len(results) >= limit:
                    break
                if _is_valid_youtube_id(download.youtube_video_id if download else None):
                    results.append(_track_to_dict(track, artist, album, download))
            return results

        elif list_type == "downloaded":
            # Get downloaded tracks
            query = (
                select(Track, Artist, Album, YouTubeDownload)
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
                .outerjoin(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
                .where(
                    (YouTubeDownload.download_path.is_not(None))
                    | (Track.download_path.is_not(None))
                )
                .order_by(Track.popularity.desc())
            )
            rows = session.exec(query.limit(limit)).all()
            return [_track_to_dict(track, artist, album, download) for track, artist, album, download in rows]

        elif list_type == "discovery":
            # Random tracks not played recently
            from sqlalchemy import func
            query = (
                select(Track, Artist, Album)
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
                .outerjoin(PlayHistory, PlayHistory.track_id == Track.id)
                .where(PlayHistory.id.is_(None))
                .order_by(func.random())
            )
            rows = session.exec(query.limit(limit)).all()
            return [_track_to_dict(track, artist, album, None) for track, artist, album in rows]

        elif list_type == "top-year":
            return service.get_top_tracks_last_year(user_id, limit)

        elif list_type == "most-played":
            return service.get_most_played(user_id, limit)

        elif list_type == "genre-suggestions":
            return service.get_genre_suggestions(user_id, limit)

        return []


def get_cached_list(list_type: str, user_id: int = 1, force_refresh: bool = False) -> dict:
    """
    Get a curated list from cache or generate it.

    Returns:
        dict with keys: items, last_updated, is_cached
    """
    cache_key = f"{list_type}:{user_id}"

    with _cache_lock:
        # Check cache
        if not force_refresh and cache_key in _lists_cache:
            cached = _lists_cache[cache_key]
            if time.time() < cached["expires_at"]:
                return {
                    "items": cached["data"],
                    "last_updated": cached["last_updated"],
                    "is_cached": True,
                    "total": len(cached["data"])
                }

    # Generate list
    config = LIST_CONFIGS.get(list_type, {"limit": 50})
    items = _generate_list(list_type, user_id, config["limit"])

    # Update cache
    with _cache_lock:
        _lists_cache[cache_key] = {
            "data": items,
            "expires_at": time.time() + DEFAULT_TTL_SECONDS,
            "last_updated": datetime.now()
        }

    return {
        "items": items,
        "last_updated": datetime.now(),
        "is_cached": False,
        "total": len(items)
    }


def get_all_cached_lists(user_id: int = 1) -> dict:
    """Get all curated lists from cache or generate them."""
    results = {}
    for list_type in LIST_CONFIGS.keys():
        results[list_type] = get_cached_list(list_type, user_id)
    return results


def invalidate_cache(list_type: str | None = None, user_id: int | None = None):
    """Invalidate cache for specific list or all lists."""
    with _cache_lock:
        if list_type is None and user_id is None:
            # Clear all cache
            _lists_cache.clear()
        elif list_type and user_id is None:
            # Clear specific list type for all users
            keys_to_remove = [k for k in _lists_cache.keys() if k.startswith(f"{list_type}:")]
            for key in keys_to_remove:
                del _lists_cache[key]
        elif list_type and user_id:
            # Clear specific list for specific user
            cache_key = f"{list_type}:{user_id}"
            if cache_key in _lists_cache:
                del _lists_cache[cache_key]
        elif user_id and list_type is None:
            # Clear all lists for specific user
            keys_to_remove = [k for k in _lists_cache.keys() if k.endswith(f":{user_id}")]
            for key in keys_to_remove:
                del _lists_cache[key]


def get_cache_status() -> dict:
    """Get current cache status for monitoring."""
    with _cache_lock:
        return {
            "cached_entries": len(_lists_cache),
            "entries": [
                {
                    "key": key,
                    "items_count": len(value["data"]),
                    "expires_in_seconds": max(0, value["expires_at"] - time.time()),
                    "last_updated": value["last_updated"]
                }
                for key, value in _lists_cache.items()
            ]
        }
