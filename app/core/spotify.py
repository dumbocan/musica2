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

    async def get_recommendations(self, seed_artists: List[str] = None, seed_tracks: List[str] = None, seed_genres: List[str] = None, limit: int = 20) -> List[dict]:
        """Get music recommendations based on seeds."""
        endpoint = "/recommendations"
        params = {"limit": limit}
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
            except Exception as e:
                # Continue if one album fails
                continue

        # Sort by popularity and return top N
        sorted_tracks = sorted(
            all_tracks,
            key=lambda x: (x.get('weighted_popularity', 0), x.get('popularity', 0)),
            reverse=True
        )

        return sorted_tracks[:limit]


# Global client instance
spotify_client = SpotifyClient()
