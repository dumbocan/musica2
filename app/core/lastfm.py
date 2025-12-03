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
        params = {
            "method": "track.getInfo",
            "artist": artist,
            "track": track,
            "api_key": self.api_key,
            "format": "json"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            track_info = data.get("track", {})
            return {
                "listeners": int(track_info.get("listeners", 0)),
                "playcount": int(track_info.get("playcount", 0)),
                "tags": track_info.get("toptags", {}).get("tag", [])
            }


# Global client
lastfm_client = LastFmClient()
