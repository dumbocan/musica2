#!/usr/bin/env python3

import sys
import os

# Add the project directory to the path
sys.path.append(os.path.dirname(__file__))

from app.core.db import get_session, create_db_and_tables
from app.models.base import Track, Artist
from datetime import datetime

def create_test_track():
    # Create tables first
    create_db_and_tables()

    session = get_session()
    try:
        # Check if artist exists, create if not
        artist = session.exec(select(Artist).where(Artist.id == 1)).first()
        if not artist:
            artist = Artist(
                id=1,
                name="Test Artist",
                normalized_name="test artist",
                genres="[]",
                images="[]",
                popularity=50,
                followers=1000
            )
            session.add(artist)
            session.commit()
            session.refresh(artist)
            print(f"Created artist with ID: {artist.id}")

        # Check if track exists, create if not
        track = session.exec(select(Track).where(Track.id == 1)).first()
        if not track:
            track = Track(
                id=1,
                name="Test Track",
                artist_id=1,
                album_id=None,
                duration_ms=180000,
                popularity=60,
                preview_url="http://example.com/preview.mp3",
                external_url="http://example.com/full.mp3"
            )
            session.add(track)
            session.commit()
            session.refresh(track)
            print(f"Created track with ID: {track.id}")
        else:
            print(f"Track with ID 1 already exists: {track.name}")

        return track
    finally:
        session.close()

if __name__ == "__main__":
    from sqlmodel import select
    create_test_track()
