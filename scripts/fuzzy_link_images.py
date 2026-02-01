#!/usr/bin/env python3
"""
Fuzzy-link StoredImagePath rows to artists/albums without image_path_id.

Strategy:
1) Try exact sanitized folder matches against StoredImagePath.path_*.
2) If no exact match, try fuzzy matching on folder names (SequenceMatcher).
3) If still missing and filesystem is available, search storage/images directly.

This does NOT download images; it only links existing paths.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import select

from app.core.db import get_session
from app.core.image_db_store import IMAGE_STORAGE, _sanitize_filename, _get_image_size_key
from app.models.base import Artist, Album, StoredImagePath


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(IMAGE_STORAGE))
    except Exception:
        return str(path)


def _find_best_match(name: str, candidates: Iterable[str], threshold: float) -> Optional[str]:
    best = None
    best_ratio = 0.0
    target = _normalize_name(name)
    for cand in candidates:
        ratio = difflib.SequenceMatcher(a=target, b=_normalize_name(cand)).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = cand
    if best and best_ratio >= threshold:
        return best
    return None


def _pick_image_paths(folder: Path, base_name: str) -> dict[int, Path]:
    candidates: dict[int, Path] = {}
    for size in (256, 512, 1024, 128):
        pattern = f"{base_name}__*_{size}.webp"
        matches = sorted(folder.glob(pattern))
        if matches:
            candidates[size] = matches[0]
    return candidates


def _ensure_stored(
    *,
    entity_type: str,
    entity_id: int,
    image_paths: dict[int, Path],
    source_tag: str,
) -> Optional[StoredImagePath]:
    if not image_paths:
        return None
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
        for size, path in image_paths.items():
            setattr(stored, _get_image_size_key(size), _relative_path(path))
        if not stored.content_hash:
            stored.content_hash = content_hash
        if not stored.file_size_bytes and file_size_bytes:
            stored.file_size_bytes = file_size_bytes
        session.add(stored)
        session.commit()
        session.refresh(stored)
        return stored


def _load_stored_by_path(entity_type: str) -> dict[tuple[str, str | None], StoredImagePath]:
    """Map (artist_folder, album_folder?) -> StoredImagePath for fast lookup."""
    result: dict[tuple[str, str | None], StoredImagePath] = {}
    with get_session() as session:
        rows = session.exec(
            select(StoredImagePath).where(StoredImagePath.entity_type == entity_type)
        ).all()
    for row in rows:
        path = row.path_256 or row.path_512 or row.path_128 or row.path_1024 or ""
        if not path:
            continue
        parts = Path(path).parts
        if not parts:
            continue
        if entity_type == "artist":
            artist_dir = parts[0]
            result[(artist_dir, None)] = row
        elif entity_type == "album":
            if len(parts) >= 2:
                result[(parts[0], parts[1])] = row
    return result


def link_artists(threshold: float, use_fs: bool) -> int:
    updated = 0
    stored_map = _load_stored_by_path("artist")
    stored_keys = [k[0] for k in stored_map.keys()]
    with get_session() as session:
        artists = session.exec(select(Artist).where(Artist.image_path_id.is_(None))).all()
    for artist in artists:
        if not artist or not artist.id:
            continue
        sanitized = _sanitize_filename(artist.name)
        stored = stored_map.get((sanitized, None))
        if not stored:
            best = _find_best_match(artist.name, stored_keys, threshold)
            if best:
                stored = stored_map.get((best, None))
        if stored and stored.entity_id is None:
            with get_session() as session:
                row = session.get(StoredImagePath, stored.id)
                art = session.get(Artist, artist.id)
                if not row or not art:
                    continue
                row.entity_id = art.id
                art.image_path_id = row.id
                session.add(row)
                session.add(art)
                session.commit()
                updated += 1
                continue
        if stored and stored.entity_id == artist.id:
            with get_session() as session:
                art = session.get(Artist, artist.id)
                if art and art.image_path_id != stored.id:
                    art.image_path_id = stored.id
                    session.add(art)
                    session.commit()
                    updated += 1
            continue
        if use_fs:
            artist_dir = IMAGE_STORAGE / sanitized
            if not artist_dir.exists():
                continue
            image_paths = _pick_image_paths(artist_dir, sanitized)
            stored_row = _ensure_stored(
                entity_type="artist",
                entity_id=artist.id,
                image_paths=image_paths,
                source_tag=f"images/{artist_dir.name}",
            )
            if stored_row:
                with get_session() as session:
                    art = session.get(Artist, artist.id)
                    if art and art.image_path_id != stored_row.id:
                        art.image_path_id = stored_row.id
                        session.add(art)
                        session.commit()
                        updated += 1
    return updated


def link_albums(threshold: float, use_fs: bool) -> int:
    updated = 0
    stored_map = _load_stored_by_path("album")
    stored_keys = list(stored_map.keys())
    with get_session() as session:
        albums = session.exec(select(Album).where(Album.image_path_id.is_(None))).all()
    for album in albums:
        if not album or not album.id or not album.artist_id:
            continue
        with get_session() as session:
            artist = session.get(Artist, album.artist_id)
        if not artist:
            continue
        artist_dir = _sanitize_filename(artist.name)
        album_dir = _sanitize_filename(album.name)
        stored = stored_map.get((artist_dir, album_dir))
        if not stored:
            # fuzzy match by album folder within same artist
            candidates = [k for k in stored_keys if k[0] == artist_dir]
            if candidates:
                best_album = _find_best_match(album.name, [c[1] for c in candidates if c[1]], threshold)
                if best_album:
                    stored = stored_map.get((artist_dir, best_album))
        if stored and stored.entity_id is None:
            with get_session() as session:
                row = session.get(StoredImagePath, stored.id)
                alb = session.get(Album, album.id)
                if not row or not alb:
                    continue
                row.entity_id = alb.id
                alb.image_path_id = row.id
                session.add(row)
                session.add(alb)
                session.commit()
                updated += 1
                continue
        if stored and stored.entity_id == album.id:
            with get_session() as session:
                alb = session.get(Album, album.id)
                if alb and alb.image_path_id != stored.id:
                    alb.image_path_id = stored.id
                    session.add(alb)
                    session.commit()
                    updated += 1
            continue
        if use_fs:
            album_folder = IMAGE_STORAGE / artist_dir / album_dir
            if not album_folder.exists():
                continue
            image_paths = _pick_image_paths(album_folder, album_dir)
            stored_row = _ensure_stored(
                entity_type="album",
                entity_id=album.id,
                image_paths=image_paths,
                source_tag=f"images/{artist_dir}/{album_dir}",
            )
            if stored_row:
                with get_session() as session:
                    alb = session.get(Album, album.id)
                    if alb and alb.image_path_id != stored_row.id:
                        alb.image_path_id = stored_row.id
                        session.add(alb)
                        session.commit()
                        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuzzy link images to DB entities")
    parser.add_argument("--threshold", type=float, default=0.92, help="Similarity threshold (0-1)")
    parser.add_argument("--no-fs", action="store_true", help="Do not touch filesystem")
    args = parser.parse_args()

    use_fs = not args.no_fs
    artists_updated = link_artists(args.threshold, use_fs)
    albums_updated = link_albums(args.threshold, use_fs)
    print(f"Artists updated: {artists_updated}")
    print(f"Albums updated: {albums_updated}")


if __name__ == "__main__":
    main()
