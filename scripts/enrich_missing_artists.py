#!/usr/bin/env python3
"""Enrich artists missing key data using Spotify + Last.fm."""

import asyncio

from sqlmodel import select

from app.core.db import get_session
from app.models.base import Artist
from app.core.spotify import spotify_client
from app.core.lastfm import lastfm_client
from app.crud import save_artist

MISSING_FIELDS = {"image", "bio", "genres"}


def _should_enrich(artist: Artist) -> bool:
    if not artist.spotify_id:
        return False
    missing = False
    # Check image_path_id (new filesystem-first) or fallback to images field
    if not artist.image_path_id and (not artist.images or artist.images.strip() in {"[]", ""}):
        missing = True
    if not artist.genres or artist.genres.strip() in {"[]", ""}:
        missing = True
    if not artist.bio_summary:
        missing = True
    return missing


async def enrich_artist(artist: Artist) -> bool:
    updated = False

    if artist.spotify_id:
        spotify_data = await spotify_client.get_artist(artist.spotify_id)
        if spotify_data:
            save_artist(spotify_data)
            updated = True

    if not artist.bio_summary and artist.name:
        lastfm = await lastfm_client.get_artist_info(artist.name)
        summary = lastfm.get("summary")
        content = lastfm.get("content")
        tags = [t.get("name") for t in lastfm.get("tags", []) if t.get("name")]
        if summary or content or tags:
            with get_session() as session:
                db_artist = session.exec(select(Artist).where(Artist.id == artist.id)).first()
                if db_artist:
                    db_artist.bio_summary = summary or db_artist.bio_summary
                    db_artist.bio_content = content or db_artist.bio_content
                    if tags and (not db_artist.genres or db_artist.genres.strip() in {"[]", ""}):
                        db_artist.genres = str(tags)
                    session.add(db_artist)
                    session.commit()
                    updated = True
    return updated


async def main():
    with get_session() as session:
        artists = session.exec(select(Artist)).all()
    targets = [artist for artist in artists if _should_enrich(artist)]
    print(f"Found {len(targets)} artists with missing data")

    for artist in targets:
        try:
            await enrich_artist(artist)
        except Exception as exc:
            print(f"Failed to enrich {artist.name}: {exc}")
        await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())
