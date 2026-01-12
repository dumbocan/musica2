"""
Helpers to persist artists/albums/tracks into the local DB.
"""

import asyncio
from typing import Iterable, Optional, List

from ..core.spotify import spotify_client
from ..crud import save_artist, save_album, save_track


async def save_artist_discography(spotify_artist_id: str) -> Optional[int]:
    """
    Fetch artist + albums + tracks from Spotify and persist to DB.
    Returns local artist ID if saved.
    """
    artist_data = await spotify_client.get_artist(spotify_artist_id)
    if not artist_data:
        return None
    artist = save_artist(artist_data)
    artist_id = artist.id

    albums_data = await spotify_client.get_artist_albums(spotify_artist_id, include_groups="album,single")
    for album_data in albums_data:
        album = save_album(album_data)
        if not album or not album.id:
            continue
        tracks_data = await spotify_client.get_album_tracks(album_data["id"])
        for track_data in tracks_data:
            save_track(track_data, album_id=album.id, artist_id=artist_id)
    return artist_id


async def save_artist_and_similars(main_artist_id: str, similar_artist_ids: Iterable[str], limit: int = 5):
    """Persist main artist and up to `limit` similar artists."""
    ids = [i for i in similar_artist_ids if i][:limit]
    tasks: List[asyncio.Task] = []
    tasks.append(asyncio.create_task(save_artist_discography(main_artist_id)))
    for sid in ids:
        tasks.append(asyncio.create_task(save_artist_discography(sid)))
    await asyncio.gather(*tasks, return_exceptions=True)
