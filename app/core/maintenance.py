"""
Background maintenance tasks (daily refresh).
"""
import asyncio
import logging

from sqlmodel import select

from .db import get_session
from ..models.base import UserFavorite
from ..services.library_expansion import save_artist_discography

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
        except Exception as exc:
            logger.error("[maintenance] daily refresh failed: %s", exc)
        await asyncio.sleep(24 * 60 * 60)
