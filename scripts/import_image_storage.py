#!/usr/bin/env python3
"""
Import existing images from storage/images into StoredImagePath and update image_path_id.

This script scans the filesystem layout:
  storage/images/<Artist>/<Artist>__*_{size}.webp
  storage/images/<Artist>/<Album>/<Album>__*_{size}.webp

It creates (or updates) StoredImagePath rows for artists and albums and
sets image_path_id accordingly. It does NOT download anything.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Optional

from sqlmodel import select

from app.core.db import get_session
from app.core.image_db_store import IMAGE_STORAGE, _sanitize_filename, _get_image_size_key
from app.models.base import Artist, Album, StoredImagePath


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _pick_image_paths(folder: Path, base_name: str) -> dict[int, Path]:
    candidates: dict[int, Path] = {}
    for size in (256, 512, 1024, 128):
        pattern = f"{base_name}__*_{size}.webp"
        matches = sorted(folder.glob(pattern))
        if matches:
            candidates[size] = matches[0]
    return candidates


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(IMAGE_STORAGE))
    except Exception:
        return str(path)


def _ensure_stored(
    *,
    entity_type: str,
    entity_id: int,
    image_paths: dict[int, Path],
    source_tag: str,
) -> Optional[StoredImagePath]:
    if not image_paths:
        return None

    # Pick best source for hash/size
    preferred = image_paths.get(512) or image_paths.get(256) or next(iter(image_paths.values()))
    content_hash = _hash_file(preferred)
    file_size_bytes = preferred.stat().st_size if preferred.exists() else None

    with get_session() as session:
        stored = session.exec(
            select(StoredImagePath).where(
                StoredImagePath.entity_type == entity_type,
                StoredImagePath.entity_id == entity_id,
            )
        ).first()

        if not stored:
            stored = StoredImagePath(
                entity_type=entity_type,
                entity_id=entity_id,
                source_url=f"local://{source_tag}",
                content_hash=content_hash,
                file_size_bytes=file_size_bytes,
                format="webp",
            )

        # Update paths
        for size, path in image_paths.items():
            key = _get_image_size_key(size)
            setattr(stored, key, _relative_path(path))

        # Update hash if missing
        if not stored.content_hash:
            stored.content_hash = content_hash
        if not stored.file_size_bytes and file_size_bytes:
            stored.file_size_bytes = file_size_bytes

        session.add(stored)
        session.commit()
        session.refresh(stored)
        return stored


def import_artists(base: Path) -> int:
    updated = 0
    with get_session() as session:
        artists = session.exec(select(Artist)).all()
    for artist in artists:
        if not artist or not artist.id:
            continue
        artist_dir = base / _sanitize_filename(artist.name)
        if not artist_dir.exists():
            continue
        image_paths = _pick_image_paths(artist_dir, _sanitize_filename(artist.name))
        stored = _ensure_stored(
            entity_type="artist",
            entity_id=artist.id,
            image_paths=image_paths,
            source_tag=f"images/{artist_dir.name}",
        )
        if stored:
            with get_session() as session:
                row = session.get(Artist, artist.id)
                if row and row.image_path_id != stored.id:
                    row.image_path_id = stored.id
                    session.add(row)
                    session.commit()
                    updated += 1
    return updated


def import_albums(base: Path) -> int:
    updated = 0
    with get_session() as session:
        albums = session.exec(select(Album)).all()
    for album in albums:
        if not album or not album.id or not album.artist_id:
            continue
        with get_session() as session:
            artist = session.get(Artist, album.artist_id)
        if not artist:
            continue
        artist_dir = base / _sanitize_filename(artist.name)
        album_dir = artist_dir / _sanitize_filename(album.name)
        if not album_dir.exists():
            continue
        image_paths = _pick_image_paths(album_dir, _sanitize_filename(album.name))
        stored = _ensure_stored(
            entity_type="album",
            entity_id=album.id,
            image_paths=image_paths,
            source_tag=f"images/{artist_dir.name}/{album_dir.name}",
        )
        if stored:
            with get_session() as session:
                row = session.get(Album, album.id)
                if row and row.image_path_id != stored.id:
                    row.image_path_id = stored.id
                    session.add(row)
                    session.commit()
                    updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Import storage/images into StoredImagePath")
    parser.add_argument("--root", default=str(IMAGE_STORAGE), help="Path to storage/images")
    args = parser.parse_args()

    base = Path(args.root).expanduser()
    if not base.exists():
        raise SystemExit(f"Missing images root: {base}")

    artists_updated = import_artists(base)
    albums_updated = import_albums(base)
    print(f"Artists updated: {artists_updated}")
    print(f"Albums updated: {albums_updated}")


if __name__ == "__main__":
    main()
