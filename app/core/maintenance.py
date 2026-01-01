"""
Background maintenance tasks (daily refresh).
"""
import asyncio
import logging

from sqlmodel import select

from .db import get_session
from ..models.base import UserFavorite
from ..services.library_expansion import save_artist_discography
from ..services.data_quality import collect_artist_quality_report
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from ..models.base import Artist
from ..crud import save_artist

logger = logging.getLogger(__name__)


async def daily_refresh_loop():
    """Daily job: refresh discography for favorited artists."""
    while True:
        try:
            with get_session() as session:
                favs = session.exec(
                    select(UserFavorite).where(UserFavorite.artist_id.is_not(None))
                ).all()
                artist_ids = {f.artist_id for f in favs if f.artist_id}
            logger.info("[maintenance] refreshing %d favorited artists", len(artist_ids))
            tasks = [asyncio.create_task(save_artist_discography(str(aid))) for aid in artist_ids if aid]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # After refreshing favorites, enrich artists missing metadata
            missing_report = collect_artist_quality_report()
            for entry in missing_report:
                try:
                    spotify_id = entry["spotify_id"]
                    if spotify_id:
                        data = await spotify_client.get_artist(spotify_id)
                        if data:
                            save_artist(data)
                    if "bio" in entry["missing"] and entry["name"]:
                        lastfm = await lastfm_client.get_artist_info(entry["name"])
                        summary = lastfm.get("summary")
                        if summary:
                            with get_session() as session:
                                artist = session.exec(select(Artist).where(Artist.id == entry["id"])).first()
                                if artist:
                                    artist.bio_summary = summary
                                    artist.bio_content = lastfm.get("content", artist.bio_content)
                                    session.add(artist)
                                    session.commit()
                except Exception as exc:
                    logger.warning("[maintenance] enrichment failed for %s: %s", entry.get("name"), exc)
        except Exception as exc:
            logger.error("[maintenance] daily refresh failed: %s", exc)
        await asyncio.sleep(24 * 60 * 60)
