import argparse
import asyncio
import ast
import json
from typing import Iterable

from app.core.db import get_session
from app.core.image_db_store import delete_images_for_entity, store_image, find_by_source_url
from app.models.base import Album, Artist
from sqlmodel import select


def _parse_images(images_field) -> list[str]:
    if not images_field:
        return []
    if isinstance(images_field, str):
        try:
            parsed = json.loads(images_field)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(images_field)
            except (ValueError, SyntaxError):
                return []
    else:
        parsed = images_field
    if not isinstance(parsed, list):
        return []
    urls: list[str] = []
    for entry in parsed:
        if isinstance(entry, dict):
            url = entry.get("url") or entry.get("#text")
        elif isinstance(entry, str):
            url = entry
        else:
            url = None
        if isinstance(url, str) and url:
            urls.append(url)
    return urls


def _resolve_album_ids_by_artist_names(names: Iterable[str]) -> list[int]:
    with get_session() as session:
        artists = session.exec(
            select(Artist).where(Artist.name.in_(list(names)))
        ).all()
        artist_ids = [artist.id for artist in artists if artist and artist.id]
        if not artist_ids:
            return []
        albums = session.exec(
            select(Album).where(Album.artist_id.in_(artist_ids))
        ).all()
        return [album.id for album in albums if album and album.id]


async def repair_album_images(album_ids: list[int], dry_run: bool = False, download_missing: bool = False) -> int:
    repaired = 0
    with get_session() as session:
        albums = session.exec(
            select(Album).where(Album.id.in_(album_ids))
        ).all()
    for album in albums:
        if not album or not album.id:
            continue
        urls = _parse_images(album.images)
        if not urls:
            continue
        if dry_run:
            print(f"[dry-run] would repair album {album.id} - {album.name}")
            continue
        existing = find_by_source_url(urls[0])
        if existing:
            with get_session() as session:
                album_row = session.get(Album, album.id)
                if album_row:
                    album_row.image_path_id = existing.id
                    session.add(album_row)
                    session.commit()
            repaired += 1
            continue
        if not download_missing:
            continue
        delete_images_for_entity("album", album.id)
        with get_session() as session:
            album_row = session.get(Album, album.id)
            if album_row:
                album_row.image_path_id = None
                session.add(album_row)
                session.commit()
        result = await store_image("album", album.id, urls[0])
        if result:
            with get_session() as session:
                album_row = session.get(Album, album.id)
                if album_row and not album_row.image_path_id:
                    album_row.image_path_id = result.id
                    session.add(album_row)
                    session.commit()
            repaired += 1
    return repaired


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair album images for specific artists or album IDs.")
    parser.add_argument("--artist", action="append", default=[], help="Artist name to repair albums for.")
    parser.add_argument("--album-id", action="append", type=int, default=[], help="Album ID to repair.")
    parser.add_argument("--all-albums", action="store_true", help="Repair images for all albums.")
    parser.add_argument("--download-missing", action="store_true", help="Download when not in local image DB.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes.")
    args = parser.parse_args()

    album_ids = list({*args.album_id})
    if args.artist:
        album_ids.extend(_resolve_album_ids_by_artist_names(args.artist))
    if args.all_albums:
        with get_session() as session:
            album_ids.extend([row[0] for row in session.exec(select(Album.id)).all() if row and row[0]])
    album_ids = list({aid for aid in album_ids if aid})

    if not album_ids:
        print("No album IDs found. Use --artist or --album-id.")
        return

    repaired = asyncio.run(repair_album_images(album_ids, dry_run=args.dry_run, download_missing=args.download_missing))
    if not args.dry_run:
        print(f"Repaired {repaired} album images.")


if __name__ == "__main__":
    main()
