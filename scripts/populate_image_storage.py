#!/usr/bin/env python3
"""
Populate storage/images/ with images for all existing artists and albums in DB.

Structure:
    storage/images/
    ├── ArtistName/
    │   ├── ArtistName__hash_128.webp
    │   ├── ArtistName__hash_256.webp
    │   ├── ArtistName__hash_512.webp
    │   ├── ArtistName__hash_1024.webp
    │   └── AlbumName/
    │       ├── albumname__hash_128.webp
    │       ├── albumname__hash_256.webp
    │       └── ...

Usage: python scripts/populate_image_storage.py [--dry-run]
"""

import asyncio
import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx  # noqa: E402
from PIL import Image  # noqa: E402
from sqlmodel import select  # noqa: E402

from app.core.db import get_session  # noqa: E402
from app.core.image_db_store import (  # noqa: E402
    IMAGE_STORAGE, IMAGE_SIZES, DEFAULT_QUALITY, MAX_ORIGINAL_SIZE,
    _get_entity_name, find_by_hash, _ensure_storage_dirs
)
from app.core.time_utils import utc_now  # noqa: E402
from app.models.base import Artist, Album, StoredImagePath  # noqa: E402


def extract_real_url(url: str) -> str:
    """Extract real URL from proxy URLs like /images/proxy?url=..."""
    if url.startswith("/images/proxy?url="):
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if "url" in query_params:
            return unquote(query_params["url"][0])
    return url


def parse_images(images_field) -> list[str]:
    """Parse the images JSON field and return list of URLs."""
    if not images_field:
        return []

    try:
        if isinstance(images_field, str):
            parsed = json.loads(images_field)
        else:
            parsed = images_field

        if isinstance(parsed, list):
            urls = []
            for img in parsed:
                url = img.get("url") if isinstance(img, dict) else img
                if url:
                    urls.append(extract_real_url(url))
            return urls
    except json.JSONDecodeError:
        pass

    if isinstance(images_field, str):
        return [extract_real_url(url.strip()) for url in images_field.split(",") if url.strip()]

    return []


async def download_image(url: str) -> bytes | None:
    """Download image directly from URL."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception:
        return None


def process_image(image_data: bytes) -> tuple[dict, str, int, int]:
    """Process image and generate all size variants."""
    im = Image.open(BytesIO(image_data)).convert("RGB")
    width, height = im.size

    max_dim = max(width, height)
    if max_dim > MAX_ORIGINAL_SIZE:
        im.thumbnail((MAX_ORIGINAL_SIZE, MAX_ORIGINAL_SIZE))
        width, height = im.size

    result = {"original": image_data}
    content_hash = hashlib.sha256(image_data).hexdigest()

    for size in IMAGE_SIZES:
        if max(width, height) <= size:
            result[size] = image_data
        else:
            im_copy = im.copy()
            im_copy.thumbnail((size, size))
            buffer = BytesIO()
            im_copy.save(buffer, format="WEBP", quality=DEFAULT_QUALITY, method=6)
            result[size] = buffer.getvalue()

    return result, content_hash, width, height


async def store_image_for_entity(
    entity_type: str,
    entity_id: int,
    source_url: str
) -> StoredImagePath | None:
    """Store an image for an entity."""
    image_data = await download_image(source_url)
    if not image_data:
        return None

    processed, content_hash, width, height = process_image(image_data)

    # Check if already stored
    existing = find_by_hash(content_hash)
    if existing:
        if existing.entity_id != entity_id:
            with get_session() as session:
                existing.entity_id = entity_id
                existing.entity_type = entity_type
                existing.updated_at = utc_now()
                session.add(existing)
                session.commit()
        return existing

    # Get entity names for path
    entity_name, parent_name = _get_entity_name(entity_type, entity_id) if entity_id else ("external", None)
    content_hash_short = content_hash[:8]

    # Build paths
    paths = {}

    if entity_type == "artist":
        artist_folder = entity_name
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / artist_folder / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = f"{artist_folder}/{filename}"

    elif entity_type in ("album", "track"):
        if parent_name:
            entity_folder = Path(parent_name) / entity_name
        else:
            entity_folder = Path(entity_name)
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / entity_folder / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = str(entity_folder / filename)

    else:
        for size, data in processed.items():
            if size == "original":
                continue
            filename = f"{entity_name}__{content_hash_short}_{size}.webp"
            full_path = IMAGE_STORAGE / entity_type / filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            paths[f"path_{size}"] = f"{entity_type}/{filename}"

    # Store in DB
    with get_session() as session:
        stored = StoredImagePath(
            entity_type=entity_type,
            entity_id=entity_id,
            source_url=source_url,
            content_hash=content_hash,
            original_width=width,
            original_height=height,
            format="webp",
            file_size_bytes=len(image_data),
            **paths
        )
        session.add(stored)
        session.commit()
        session.refresh(stored)

        # Update entity's image_path_id
        if entity_type == "artist":
            artist = session.get(Artist, entity_id)
            if artist:
                artist.image_path_id = stored.id
                session.add(artist)
        elif entity_type == "album":
            album = session.get(Album, entity_id)
            if album:
                album.image_path_id = stored.id
                session.add(album)
        session.commit()

        return stored


def entity_has_image(entity_type: str, entity_id: int) -> bool:
    """Check if an entity already has an image stored."""
    with get_session() as session:
        stmt = select(StoredImagePath).where(
            StoredImagePath.entity_type == entity_type,
            StoredImagePath.entity_id == entity_id,
        ).limit(1)
        return session.exec(stmt).first() is not None


async def populate_for_entity(
    entity_type: str,
    entity_id: int,
    images_field,
    dry_run: bool
) -> tuple[int, int, int]:
    """Process one entity. Returns (total, migrated, skipped)."""
    urls = parse_images(images_field)
    if not urls:
        return 0, 0, 0

    # Skip if entity already has an image
    if entity_has_image(entity_type, entity_id):
        return 0, 0, 1  # count as skipped

    total = 1  # Only process first image
    migrated = 0
    skipped = 0

    url = urls[0]  # Take the first (largest) image only
    if dry_run:
        migrated += 1
        return 1, migrated, skipped

    try:
        result = await store_image_for_entity(entity_type, entity_id, url)
        if result:
            migrated += 1
        else:
            skipped += 1
    except Exception as e:
        print(f"  ❌ {entity_type} {entity_id}: {e}")
        skipped += 1

    return total, migrated, skipped


async def populate_all(dry_run: bool = True):
    """Populate image storage for all entities in DB."""
    if not dry_run:
        _ensure_storage_dirs()

    artists_total = artists_migrated = artists_skipped = 0
    albums_total = albums_migrated = albums_skipped = 0

    with get_session() as session:
        print("📄 Processing artists...")
        artists = session.exec(select(Artist)).all()
        artists_total = len(artists)

        for artist in artists:
            total, migrated, skipped = await populate_for_entity(
                "artist", artist.id, artist.images, dry_run
            )
            artists_migrated += migrated
            artists_skipped += skipped

            if artists_migrated % 50 == 0 and not dry_run:
                print(f"  ✅ Processed {artists_migrated} artists...")

    with get_session() as session:
        print("📄 Processing albums...")
        albums = session.exec(select(Album)).all()
        albums_total = len(albums)

        for album in albums:
            total, migrated, skipped = await populate_for_entity(
                "album", album.id, album.images, dry_run
            )
            albums_migrated += migrated
            albums_skipped += skipped

            if albums_migrated % 50 == 0 and not dry_run:
                print(f"  ✅ Processed {albums_migrated} albums...")

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Results:")
    print(f"  Artists: {artists_total} total, {artists_migrated} migrated, {artists_skipped} skipped")
    print(f"  Albums: {albums_total} total, {albums_migrated} migrated, {albums_skipped} skipped")
    print(f"  Total entities processed: {artists_total + albums_total}")

    if not dry_run and (artists_migrated > 0 or albums_migrated > 0):
        print(f"\n💡 Images stored in: {IMAGE_STORAGE}")
        print("   Structure: storage/images/ArtistName/[AlbumName/]filename.webp")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        sys.argv.remove("--dry-run")

    print(f"{'🔍 [DRY-RUN] ' if dry_run else '🚀 '}Populating image storage...")
    asyncio.run(populate_all(dry_run=dry_run))
