"""
Last.fm API client for scoring data.
"""

import asyncio
import httpx

from .config import settings


class LastFmClient:
    def __init__(self):
        self.api_key = settings.LASTFM_API_KEY
        self.base_url = "http://ws.audioscrobbler.com/2.0/"
        self.default_timeout_seconds = 8.0
        self.long_timeout_seconds = 12.0
        self.max_retries = 2
        self.retry_backoff_seconds = 1.0

    async def _fetch_json(self, params: dict, timeout: float) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))
        if last_exc:
            raise last_exc
        return {}

    async def get_track_info(self, artist: str, track: str) -> dict:
        """Get track info including playcount/listeners."""
        if not self.api_key:
            return {"listeners": 0, "playcount": 0, "tags": []}
        params = {
            "method": "track.getInfo",
            "artist": artist,
            "track": track,
            "api_key": self.api_key,
            "format": "json"
        }
        data = await self._fetch_json(params, self.default_timeout_seconds)
        track_info = data.get("track", {})
        return {
            "listeners": int(track_info.get("listeners", 0)),
            "playcount": int(track_info.get("playcount", 0)),
            "tags": track_info.get("toptags", {}).get("tag", [])
        }

    async def get_artist_info(self, artist: str) -> dict:
        """Get artist info including biography/summary."""
        if not self.api_key:
            return {"summary": "", "content": "", "stats": {}, "tags": []}
        params = {
            "method": "artist.getInfo",
            "artist": artist,
            "api_key": self.api_key,
            "format": "json"
        }
        data = await self._fetch_json(params, self.default_timeout_seconds)
        artist_info = data.get("artist", {})
        bio_data = artist_info.get("bio", {})
        return {
            "summary": bio_data.get("summary", ""),
            "content": bio_data.get("content", ""),
            "stats": artist_info.get("stats", {}),  # playcount, listeners
            "tags": artist_info.get("tags", {}).get("tag", []),  # genres/tags
            "images": artist_info.get("image", [])  # image list with #text
        }

    async def get_similar_artists(self, artist: str, limit: int = 5) -> list:
        """Get similar artists from Last.fm."""
        if not self.api_key:
            return []
        params = {
            "method": "artist.getSimilar",
            "artist": artist,
            "limit": limit,
            "api_key": self.api_key,
            "format": "json"
        }
        data = await self._fetch_json(params, self.default_timeout_seconds)
        similar_artists = data.get("similarartists", {}).get("artist", [])
        return [
            {
                "name": artist_info.get("name", ""),
                "match": float(artist_info.get("match", 0)),
                "url": artist_info.get("url", ""),
                "image": artist_info.get("image", [])
            }
            for artist_info in similar_artists
        ]

    async def get_top_artists_by_tag(self, tag: str, limit: int = 50, page: int = 1) -> list:
        """Get top artists for a given tag."""
        if not self.api_key:
            return []
        params = {
            "method": "tag.gettopartists",
            "tag": tag,
            "limit": limit,
            "page": page,
            "api_key": self.api_key,
            "format": "json"
        }
        data = await self._fetch_json(params, self.long_timeout_seconds)
        return data.get("topartists", {}).get("artist", [])

    async def get_album_info(self, artist: str, album: str) -> dict:
        """Get album info including wiki/summary."""
        if not self.api_key:
            return {}
        params = {
            "method": "album.getInfo",
            "artist": artist,
            "album": album,
            "api_key": self.api_key,
            "format": "json"
        }
        data = await self._fetch_json(params, self.default_timeout_seconds)
        return data.get("album", {}) or {}


# Global client
lastfm_client = LastFmClient()
