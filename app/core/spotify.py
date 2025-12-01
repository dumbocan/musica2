"""
Spotify API client using Client Credentials flow.
"""

import base64
import json
from typing import Optional, List

import httpx
from pydantic import BaseModel

from .config import settings


class SpotifyClient:
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token_url = "https://accounts.spotify.com/api/token"
        self.base_url = "https://api.spotify.com/v1"
        self.access_token: Optional[str] = None

    async def get_access_token(self):
        """Obtain access token from Spotify."""
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode("utf-8")
        auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {"grant_type": "client_credentials"}

        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated request to Spotify API."""
        if not self.access_token:
            await self.get_access_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def search_artists(self, query: str, limit: int = 10) -> List[dict]:
        """Search for artists by name."""
        endpoint = "/search"
        params = {
            "q": query,
            "type": "artist",
            "limit": limit
        }
        response = await self._make_request(endpoint, params)
        return response.get("artists", {}).get("items", [])

    async def get_artist(self, artist_id: str) -> Optional[dict]:
        """Get artist details by ID."""
        endpoint = f"/artists/{artist_id}"
        response = await self._make_request(endpoint)
        return response

    async def get_artist_albums(self, artist_id: str, limit: int = 50, include_groups: str = "album") -> List[dict]:
        """Get albums for an artist. include_groups: album, single, compilation, appears_on."""
        endpoint = f"/artists/{artist_id}/albums"
        params = {
            "limit": limit,
            "include_groups": include_groups
        }
        response = await self._make_request(endpoint, params)
        return response.get("items", [])

    async def get_album_tracks(self, album_id: str, limit: int = 50) -> List[dict]:
        """Get tracks for an album."""
        endpoint = f"/albums/{album_id}/tracks"
        params = {"limit": limit}
        response = await self._make_request(endpoint, params)
        return response.get("items", [])


# Global client instance
spotify_client = SpotifyClient()
