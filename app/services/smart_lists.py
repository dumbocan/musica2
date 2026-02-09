"""
Smart curated lists service based on user listening behavior and library.
Recovered and enhanced from the original lists.py functionality.
"""

import json
import re
import ast
from datetime import datetime, timedelta
from typing import Iterable
from sqlalchemy import desc, func, or_
from sqlmodel import select, Session
from app.models.base import (
    Album,
    Artist,
    PlayHistory,
    Track,
    UserFavorite,
    YouTubeDownload,
)


def _is_valid_youtube_video_id(value: str | None) -> bool:
    """Check if value is a valid YouTube video ID (11 chars)."""
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", value))


def _parse_genres(raw: str | None) -> list[str]:
    """Parse genres from JSON string or array."""
    def _sanitize(token: str) -> str:
        return token.strip().strip('"').strip("'").strip("{} ").strip('"').strip("'")

    if not raw:
        return []
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return []
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(g).strip() for g in parsed if isinstance(g, str) and g.strip()]
        except Exception:
            pass
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]
        return [
            _sanitize(genre)
            for genre in cleaned.split(",")
            if _sanitize(genre)
        ]
    if isinstance(raw, Iterable):
        return [_sanitize(str(item)) for item in raw if isinstance(item, str) and _sanitize(str(item))]
    return []


def _extract_primary_image_url(images: object) -> str | None:
    """Extract first image URL from JSON array."""
    if not images:
        return None
    parsed = images
    if isinstance(parsed, str):
        text = parsed.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return None
    if not isinstance(parsed, list) or not parsed:
        return None
    first = parsed[0]
    if isinstance(first, dict):
        url = first.get("url")
    else:
        url = first
    return str(url).strip() if isinstance(url, str) and url.strip() else None


def _track_to_dict(track: Track, artist: Artist | None, album: Album | None,
                   download: YouTubeDownload | None) -> dict:
    """Convert track to dictionary format for curated lists."""
    image_url = (
        _extract_primary_image_url(album.images if album else None) or
        _extract_primary_image_url(artist.images if artist else None)
    )

    valid_video_id = None
    if download:
        valid_video_id = download.youtube_video_id if _is_valid_youtube_video_id(
            download.youtube_video_id
        ) else None

    merged_download_path = track.download_path or (
        download.download_path if download and download.download_path else None
    )
    merged_download_status = track.download_status or (
        download.download_status if download else None
    )

    if merged_download_path and not merged_download_status:
        merged_download_status = "completed"

    return {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "is_favorite": bool(track.is_favorite),
        "download_status": merged_download_status,
        "download_path": merged_download_path,
        "artists": [{"id": artist.id, "name": artist.name, "spotify_id": artist.spotify_id}] if artist else [],
        "album": {
            "id": album.id,
            "spotify_id": album.spotify_id,
            "name": album.name,
            "release_date": album.release_date,
        } if album else None,
        "image_url": image_url,
        "videoId": valid_video_id,
    }


class SmartListsService:
    """Service for generating smart curated lists based on user behavior."""

    def __init__(self, session: Session):
        self.session = session

    def get_top_tracks_last_year(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get top tracks from last 365 days based on play count and ratings.
        Simplified version for better performance."""
        one_year_ago = datetime.now() - timedelta(days=365)

        # Optimized: Get recently played track IDs first (much faster)
        played_tracks_query = (
            select(PlayHistory.track_id)
            .where(PlayHistory.user_id == user_id)
            .where(PlayHistory.played_at >= one_year_ago)
            .distinct()
        )
        played_track_ids = [row[0] for row in self.session.exec(played_tracks_query).all()]

        if not played_track_ids:
            return []

        # Get tracks with those IDs, ordered by popularity and user score
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.id.in_(played_track_ids))
            .order_by(
                desc(Track.user_score),  # Higher rated first
                desc(Track.popularity),   # Then by popularity
            )
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_genre_suggestions(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get tracks from genres similar to user's favorites."""
        # Get user's favorite artists
        fav_artists_query = (
            select(Artist)
            .join(UserFavorite, UserFavorite.artist_id == Artist.id)
            .where(UserFavorite.user_id == user_id)
            .where(UserFavorite.target_type == "ARTIST")
        )
        favorite_artists = self.session.exec(fav_artists_query).all()

        # Extract genres from favorite artists
        user_genres = set()
        for artist in favorite_artists:
            if artist.genres:
                user_genres.update(_parse_genres(artist.genres))

        if not user_genres:
            return []

        # Find tracks from artists with similar genres
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(~Track.id.in_(
                select(UserFavorite.track_id)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "TRACK")
            ))  # Exclude already favorited
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit * 3)).all()

        # Filter by genre similarity
        results = []
        for track, artist, album in rows:
            if len(results) >= limit:
                break

            if artist and artist.genres:
                artist_genres = set(_parse_genres(artist.genres))
                # If artist shares at least one genre with user's favorites
                if artist_genres & user_genres:
                    results.append(_track_to_dict(track, artist, album, None))

        return results

    def get_related_artists_tracks(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get tracks from artists related to user's favorites."""
        # Get user's favorite artist IDs
        fav_query = (
            select(Artist.id)
            .join(UserFavorite, UserFavorite.artist_id == Artist.id)
            .where(UserFavorite.user_id == user_id)
            .where(UserFavorite.target_type == "ARTIST")
        )
        favorite_artist_ids = [row[0] for row in self.session.exec(fav_query).all()]

        if not favorite_artist_ids:
            return []

        # Find artists marked as similar to favorites
        # Note: This assumes you have a related_artists table or field
        # For now, we'll use genre similarity as a proxy
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(~Artist.id.in_(favorite_artist_ids))  # Exclude already favorited artists
            .where(~Track.id.in_(
                select(UserFavorite.track_id)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "TRACK")
            ))
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_discography(self, artist_id: int, limit: int = 50) -> list[dict]:
        """Get complete discography of an artist."""
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Artist.id == artist_id)
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_collaborations(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get tracks marked as collaborations."""
        # Look for tracks with "feat", "ft.", "featuring" in name
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(
                or_(
                    Track.name.ilike("%feat%"),
                    Track.name.ilike("%ft.%"),
                    Track.name.ilike("%featuring%"),
                )
            )
            .where(~Track.id.in_(
                select(UserFavorite.track_id)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "TRACK")
            ))
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_random_discovery(self, user_id: int, limit: int = 50) -> list[dict]:
        """Get random tracks from library for discovery."""
        import random

        # Get all track IDs not recently played
        recent_query = (
            select(PlayHistory.track_id)
            .where(PlayHistory.user_id == user_id)
            .where(PlayHistory.played_at >= datetime.now() - timedelta(days=30))
        )
        recent_track_ids = [row[0] for row in self.session.exec(recent_query).all()]

        # Get tracks excluding recent ones
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
        )

        if recent_track_ids:
            query = query.where(~Track.id.in_(recent_track_ids))

        rows = self.session.exec(query).all()

        # Shuffle and take limit
        rows_list = list(rows)
        random.shuffle(rows_list)

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows_list[:limit]
        ]

    def get_most_played(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get most played tracks of all time. Simplified for performance."""
        # Get tracks that have been played (from PlayHistory)
        played_tracks_query = (
            select(PlayHistory.track_id)
            .where(PlayHistory.user_id == user_id)
            .distinct()
        )
        played_track_ids = [row[0] for row in self.session.exec(played_tracks_query).all()]

        if not played_track_ids:
            return []

        # Return played tracks ordered by popularity
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.id.in_(played_track_ids))
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_never_played(self, user_id: int, limit: int = 50) -> list[dict]:
        """Get tracks never played by user."""
        played_query = select(PlayHistory.track_id).where(PlayHistory.user_id == user_id)
        played_ids = [row[0] for row in self.session.exec(played_query).all()]

        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
        )

        if played_ids:
            query = query.where(~Track.id.in_(played_ids))

        query = query.order_by(func.random())  # Random order for discovery

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_recently_added(self, limit: int = 20) -> list[dict]:
        """Get recently added tracks to library."""
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .order_by(desc(Track.created_at))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]

    def get_by_genre(self, genre: str, limit: int = 50) -> list[dict]:
        """Get tracks from a specific genre."""
        query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Artist.genres.ilike(f"%{genre}%"))
            .order_by(desc(Track.popularity))
        )

        rows = self.session.exec(query.limit(limit)).all()

        return [
            _track_to_dict(track, artist, album, None)
            for track, artist, album in rows
        ]
