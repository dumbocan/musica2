"""
Spotify API client using Client Credentials flow.
"""

import asyncio
import base64
import time
from typing import Optional, List

import httpx

from .config import settings


class SpotifyClient:
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token_url = "https://accounts.spotify.com/api/token"
        self.base_url = "https://api.spotify.com/v1"
        self.access_token: Optional[str] = None
        self.default_timeout_seconds = 8.0
        self.token_timeout_seconds = 10.0
        self.max_retries = 2
        self.retry_backoff_seconds = 2.0
        self.min_interval_seconds = 1.0
        self.cooldown_base_seconds = 10.0
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._cooldown_until = 0.0
        self._cooldown_lock = asyncio.Lock()

    async def _throttle(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            wait_time = self.min_interval_seconds - (now - self._last_request_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request_time = time.monotonic()

    async def _respect_cooldown(self) -> None:
        async with self._cooldown_lock:
            now = time.monotonic()
            wait_time = self._cooldown_until - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)

    async def _set_cooldown(self, delay_seconds: float) -> None:
        async with self._cooldown_lock:
            target = time.monotonic() + max(delay_seconds, 0.0)
            if target > self._cooldown_until:
                self._cooldown_until = target

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        timeout = timeout or self.default_timeout_seconds
        last_exc: Exception | None = None
        retriable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(self.max_retries + 1):
            try:
                await self._respect_cooldown()
                await self._throttle()
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        data=data,
                    )
                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                    delay = retry_after or max(
                        self.retry_backoff_seconds * (attempt + 1),
                        self.cooldown_base_seconds
                    )
                    await self._set_cooldown(delay)
                    await response.aclose()
                    if attempt < self.max_retries:
                        await asyncio.sleep(delay)
                        continue
                    return response
                if response.status_code in retriable_statuses and attempt < self.max_retries:
                    await response.aclose()
                    await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))
                    continue
                return response
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError("Spotify request failed")

    async def get_access_token(self):
        """Obtain access token from Spotify."""
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Spotify credentials are not configured. Set SPOTIFY_CLIENT_ID/SECRET in .env.")

        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode("utf-8")
        auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {"grant_type": "client_credentials"}

        response = await self._request(
            "POST",
            self.token_url,
            headers=headers,
            data=data,
            timeout=self.token_timeout_seconds,
        )
        response.raise_for_status()
        token_data = response.json()
        self.access_token = token_data["access_token"]

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated request to Spotify API."""
        if not self.access_token:
            await self.get_access_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = await self._request(
            "GET",
            f"{self.base_url}{endpoint}",
            headers=headers,
            params=params,
            timeout=self.default_timeout_seconds,
        )
        # If token expired, refresh once
        if response.status_code == 401:
            await self.get_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = await self._request(
                "GET",
                f"{self.base_url}{endpoint}",
                headers=headers,
                params=params,
                timeout=self.default_timeout_seconds,
            )
        response.raise_for_status()
        return response.json()

    async def get_recommendations(
        self,
        seed_artists: List[str] = None,
        seed_tracks: List[str] = None,
        seed_genres: List[str] = None,
        limit: int = 20,
        market: Optional[str] = "US",
    ) -> List[dict]:
        """Get music recommendations based on seeds."""
        endpoint = "/recommendations"
        params = {"limit": limit}
        if market:
            params["market"] = market
        if seed_artists:
            params["seed_artists"] = ",".join(seed_artists)
        if seed_tracks:
            params["seed_tracks"] = ",".join(seed_tracks)
        if seed_genres:
            params["seed_genres"] = ",".join(seed_genres)

        response = await self._make_request(endpoint, params)
        tracks = response.get("tracks", [])

        # Extract unique artists from tracks
        artists = []
        seen_artists = set()
        for track in tracks:
            for artist in track["artists"]:
                if artist["id"] not in seen_artists:
                    artists.append(artist)
                    seen_artists.add(artist["id"])

        return {"tracks": tracks, "artists": artists}

    async def search_artists(self, query: str, limit: int = 10, offset: int = 0) -> List[dict]:
        """Search for artists by name."""
        endpoint = "/search"
        params = {
            "q": query,
            "type": "artist",
            "limit": limit,
            "offset": max(offset, 0)
        }
        response = await self._make_request(endpoint, params)
        return response.get("artists", {}).get("items", [])

    async def search_tracks(self, query: str, limit: int = 10, offset: int = 0) -> List[dict]:
        """Search for tracks by name."""
        endpoint = "/search"
        params = {
            "q": query,
            "type": "track",
            "limit": limit,
            "offset": max(offset, 0)
        }
        response = await self._make_request(endpoint, params)
        return response.get("tracks", {}).get("items", [])

    async def get_artist(self, artist_id: str) -> Optional[dict]:
        """Get artist details by ID."""
        endpoint = f"/artists/{artist_id}"
        response = await self._make_request(endpoint)
        return response

    async def get_artist_albums(
        self,
        artist_id: str,
        limit: int = 50,
        include_groups: str = "album,single",
    ) -> List[dict]:
        """Get albums for an artist. include_groups: album, single, compilation, appears_on."""
        endpoint = f"/artists/{artist_id}/albums"
        params = {
            "limit": limit,
            "include_groups": include_groups
        }
        response = await self._make_request(endpoint, params)
        return response.get("items", [])

    async def get_album(self, album_id: str) -> Optional[dict]:
        """Get album details by ID."""
        endpoint = f"/albums/{album_id}"
        response = await self._make_request(endpoint)
        return response

    async def get_album_tracks(self, album_id: str, limit: int = 50) -> List[dict]:
        """Get tracks for an album."""
        endpoint = f"/albums/{album_id}/tracks"
        params = {"limit": limit}
        response = await self._make_request(endpoint, params)
        return response.get("items", [])

    async def get_track(self, track_id: str) -> Optional[dict]:
        """Get track details by ID."""
        endpoint = f"/tracks/{track_id}"
        response = await self._make_request(endpoint)
        return response

    async def get_artist_top_tracks(self, artist_name: str, limit: int = 5) -> List[dict]:
        """
        Get top tracks for an artist.
        Since Spotify doesn't have a direct "artist top tracks" endpoint in Client Credentials flow,
        we'll get the most popular tracks from their most recent albums.
        """
        # First, search for the artist to get their ID
        artists = await self.search_artists(artist_name, limit=1)
        if not artists:
            return []

        artist_id = artists[0]['id']

        # Get artist's albums (sorted by release date, so most recent first)
        albums = await self.get_artist_albums(artist_id, limit=10, include_groups="album")

        if not albums:
            return []

        # Get tracks from the most recent/popular albums
        all_tracks = []
        for album in albums[:3]:  # Check first 3 albums
            try:
                tracks = await self.get_album_tracks(album['id'], limit=20)
                for track in tracks:
                    # Add album info to track for better context
                    track['album'] = {
                        'name': album['name'],
                        'release_date': album['release_date'],
                        'images': album.get('images', [])
                    }
                    # Weight by popularity and recency
                    track['weighted_popularity'] = track.get('popularity', 0)
                    all_tracks.append(track)
            except Exception:
                # Continue if one album fails
                continue

        # Sort by popularity and return top N
        sorted_tracks = sorted(
            all_tracks,
            key=lambda x: (x.get('weighted_popularity', 0), x.get('popularity', 0)),
            reverse=True
        )

        return sorted_tracks[:limit]

    async def get_related_artists(self, artist_id: str) -> List[dict]:
        """Get related artists from Spotify."""
        endpoint = f"/artists/{artist_id}/related-artists"
        response = await self._make_request(endpoint)
        return response.get("artists", [])


# Global client instance
spotify_client = SpotifyClient()
