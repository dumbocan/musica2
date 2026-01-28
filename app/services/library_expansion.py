"""
Helpers to persist artists/albums/tracks into the local DB.
"""

import asyncio
import logging
from typing import Iterable, Optional, List

from ..core.spotify import spotify_client
from ..core.data_freshness import data_freshness_manager
from ..crud import save_artist, save_album

logger = logging.getLogger(__name__)
_expansion_tasks: dict[str, asyncio.Task] = {}


def schedule_artist_expansion(
    spotify_artist_id: str,
    artist_name: str,
    include_youtube_links: bool = True,
) -> None:
    if not spotify_artist_id or not artist_name:
        return
    existing = _expansion_tasks.get(spotify_artist_id)
    if existing and not existing.done():
        return

    async def _run() -> None:
        try:
            await data_freshness_manager.expand_user_library_from_full_discography(
                main_artist_name=artist_name,
                main_artist_spotify_id=spotify_artist_id,
                similar_count=0,
                tracks_per_artist=0,
                include_youtube_links=include_youtube_links,
                include_full_albums=True,
            )
        except Exception as exc:
            logger.warning(
                "[discography] expansion failed for %s: %r",
                spotify_artist_id,
                exc,
                exc_info=True,
            )
        finally:
            _expansion_tasks.pop(spotify_artist_id, None)

    _expansion_tasks[spotify_artist_id] = asyncio.create_task(_run())


async def save_artist_discography(spotify_artist_id: str) -> Optional[int]:
    """
    Fetch artist + albums + tracks from Spotify and persist to DB.
    Returns local artist ID if saved.
    """
    logger.info("[discography] start %s", spotify_artist_id)
    artist_data = await spotify_client.get_artist(spotify_artist_id)
    if not artist_data:
        logger.warning("[discography] artist not found on Spotify: %s", spotify_artist_id)
        return None
    artist_name = artist_data.get("name") or spotify_artist_id
    logger.info("[discography] artist %s (%s)", artist_name, spotify_artist_id)
    artist = await save_artist(artist_data)
    artist_id = artist.id

    albums_data = await spotify_client.get_artist_albums(
        spotify_artist_id,
        include_groups="album,single,compilation",
        fetch_all=True,
    )
    saved_tracks = 0
    for album_data in albums_data:
        album = await save_album(album_data)
        if not album or not album.id:
            continue
        try:
            tracks_data = await spotify_client.get_album_tracks(album_data["id"])
        except Exception as exc:
            logger.warning(
                "[discography] tracks fetch failed for album %s: %r",
                album_data.get("id"),
                exc,
                exc_info=True,
            )
            continue
        for track_data in tracks_data:
            # save_track is sync, call it directly
            from ..crud import save_track
            save_track(track_data, album_id=album.id, artist_id=artist_id)
            saved_tracks += 1
        album_name = album_data.get("name") or album_data.get("id")
        logger.info(
            "[discography] album %s — %s tracks=%s",
            artist_name,
            album_name,
            len(tracks_data),
        )
    logger.info(
        "[discography] completed %s albums=%s tracks=%s",
        artist_name,
        len(albums_data),
        saved_tracks,
    )
    return artist_id


async def save_artist_and_similars(main_artist_id: str, similar_artist_ids: Iterable[str], limit: int = 5):
    """Persist main artist and up to `limit` similar artists."""
    ids = [i for i in similar_artist_ids if i][:limit]
    tasks: List[asyncio.Task] = []
    tasks.append(asyncio.create_task(save_artist_discography(main_artist_id)))
    for sid in ids:
        tasks.append(asyncio.create_task(save_artist_discography(sid)))
    await asyncio.gather(*tasks, return_exceptions=True)
