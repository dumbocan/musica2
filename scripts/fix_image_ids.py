#!/usr/bin/env python3
"""Fix entity_id in StoredImagePath for artists and albums."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_session
from app.models.base import Artist, Album, StoredImagePath
from sqlmodel import select


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = name.strip()[:50]
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    return name if name else 'unknown'


def fix_artists():
    """Fix artist entity_id based on path."""
    fixed = 0
    with get_session() as session:
        artists = session.exec(select(Artist)).all()
        for artist in artists:
            sanitized = sanitize_filename(artist.name)

            stmt = select(StoredImagePath).where(
                StoredImagePath.entity_type == 'artist',
                StoredImagePath.path_256.like(f'{sanitized}/%')
            ).limit(1)
            stored = session.exec(stmt).first()

            if stored and stored.entity_id != artist.id:
                print(f'Arreglando artist: {artist.name} (DB id={artist.id}, Stored id={stored.entity_id})')
                stored.entity_id = artist.id
                artist.image_path_id = stored.id
                session.add(stored)
                session.add(artist)
                fixed += 1

        session.commit()
    return fixed


def fix_albums():
    """Fix album entity_id based on path."""
    fixed = 0
    with get_session() as session:
        albums = session.exec(select(Album)).all()
        for album in albums:
            if not album.artist_id:
                continue

            # Get artist name
            artist = session.get(Artist, album.artist_id)
            if not artist:
                continue

            artist_name = sanitize_filename(artist.name)
            album_name = sanitize_filename(album.name)

            stmt = select(StoredImagePath).where(
                StoredImagePath.entity_type == 'album',
                StoredImagePath.path_256.like(f'{artist_name}/{album_name}/%')
            ).limit(1)
            stored = session.exec(stmt).first()

            if stored and stored.entity_id != album.id:
                print(f'Arreglando album: {album.name} by {artist.name} (DB id={album.id}, Stored id={stored.entity_id})')
                stored.entity_id = album.id
                album.image_path_id = stored.id
                session.add(stored)
                session.add(album)
                fixed += 1

        session.commit()
    return fixed


if __name__ == "__main__":
    print('Arreglando artistas...')
    artist_fixed = fix_artists()
    print(f'Artistas corregidos: {artist_fixed}')

    print('\nArreglando albums...')
    album_fixed = fix_albums()
    print(f'Albums corregidos: {album_fixed}')

    print(f'\nTotal corregidos: {artist_fixed + album_fixed}')
