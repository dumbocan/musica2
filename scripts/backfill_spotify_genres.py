import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlmodel import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.db import get_session  # noqa: E402
from app.core.spotify import spotify_client  # noqa: E402
from app.core.time_utils import utc_now  # noqa: E402
from app.models.base import Artist  # noqa: E402


@dataclass
class BackfillConfig:
    limit: int = 100
    sleep_seconds: float = 1.2
    per_request_timeout: float = 20.0
    max_errors: int = 5


async def run(config: BackfillConfig) -> None:
    with get_session() as session:
        artists = session.exec(
            select(Artist)
            .where(
                (Artist.genres.is_(None))
                | (Artist.genres == "")
                | (Artist.genres == "[]")
            )
            .order_by(Artist.popularity.desc(), Artist.id.asc())
            .limit(config.limit)
        ).all()

    updated = 0
    skipped = 0
    errors = 0
    for artist in artists:
        if not artist.spotify_id:
            skipped += 1
            continue
        try:
            data = await asyncio.wait_for(
                spotify_client.get_artist(artist.spotify_id),
                timeout=config.per_request_timeout
            )
        except asyncio.TimeoutError:
            errors += 1
            print(f"timeout: {artist.name}")
            if errors >= config.max_errors:
                print("too many timeouts; stopping")
                break
            await asyncio.sleep(config.sleep_seconds * 2)
            continue
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else None
            print(f"error: {artist.name} (status={status})")
            if status == 429:
                print("rate limited by Spotify; stopping")
                break
            errors += 1
            if errors >= config.max_errors:
                print("too many errors; stopping")
                break
            await asyncio.sleep(config.sleep_seconds * 2)
            continue
        except Exception as exc:
            errors += 1
            print(f"error: {artist.name} ({exc!r})")
            if errors >= config.max_errors:
                print("too many errors; stopping")
                break
            await asyncio.sleep(config.sleep_seconds * 2)
            continue
        if not data:
            skipped += 1
            await asyncio.sleep(config.sleep_seconds)
            continue

        genres = data.get("genres") or []
        if not genres:
            skipped += 1
            await asyncio.sleep(config.sleep_seconds)
            continue

        with get_session() as session:
            target = session.exec(select(Artist).where(Artist.id == artist.id)).first()
            if not target:
                skipped += 1
                continue
            now = utc_now()
            target.genres = json.dumps(genres)
            target.updated_at = now
            target.last_refreshed_at = now
            session.add(target)
            session.commit()
            updated += 1
            print(f"updated: {artist.name} -> {genres}")

        await asyncio.sleep(config.sleep_seconds)

    print(f"done: updated {updated}/{len(artists)}, skipped {skipped}")


if __name__ == "__main__":
    asyncio.run(run(BackfillConfig()))
