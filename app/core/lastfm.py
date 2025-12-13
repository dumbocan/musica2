"""
Last.fm API client for scoring data.
"""

import httpx

from .config import settings


class LastFmClient:
    def __init__(self):
        self.api_key = settings.LASTFM_API_KEY
        self.base_url = "http://ws.audioscrobbler.com/2.0/"

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
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
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
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            artist_info = data.get("artist", {})
            bio_data = artist_info.get("bio", {})
            return {
                "summary": bio_data.get("summary", ""),
                "content": bio_data.get("content", ""),
                "stats": artist_info.get("stats", {}),  # playcount, listeners
                "tags": artist_info.get("tags", {}).get("tag", [])  # genres/tags
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
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

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


# Global client
lastfm_client = LastFmClient()
