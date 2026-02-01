#!/usr/bin/env python3
"""
Migrate all cached images from old cache/ to new storage/images/.

This script:
1. Reads all .webp files from cache/images/
2. Processes them with the new storage system
3. Creates entries in the DB with proper paths

Usage: python scripts/migrate_all_images.py [--dry-run]
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.image_cache import CACHE_DIR  # noqa: E402
from app.core.image_db_store import store_image, IMAGE_STORAGE, _ensure_storage_dirs  # noqa: E402


async def _migrate_image(webp_file: Path) -> tuple[bool, str]:
    """Migrate a single image file."""
    try:
        image_data = webp_file.read_bytes()
        result = await store_image(
            entity_type="migrated",
            entity_id=None,
            source_url=f"cache://{webp_file.name}",
            image_data=image_data
        )
        return result is not None, ""
    except Exception as e:
        return False, str(e)


async def migrate_all(dry_run: bool = True):
    """Migrate all images from old cache to new storage."""
    old_cache = Path(CACHE_DIR)
    new_storage = IMAGE_STORAGE

    if not old_cache.exists():
        print(f"ℹ️  Old cache not found: {old_cache}")
        return

    webp_files = list(old_cache.glob("*.webp"))
    print(f"📁 Found {len(webp_files)} images in old cache")
    print(f"📁 Will migrate to: {new_storage}")

    if not dry_run:
        _ensure_storage_dirs()

    migrated = 0
    errors = 0
    duplicates = 0

    for webp_file in webp_files:
        if dry_run:
            print(f"  [DRY-RUN] {webp_file.name}")
        else:
            success, error = await _migrate_image(webp_file)
            if success:
                migrated += 1
                if migrated % 50 == 0:
                    print(f"  ✅ Migrated {migrated}...")
            else:
                if "Duplicate" in error or "already exists" in error:
                    duplicates += 1
                else:
                    errors += 1
                    print(f"  ❌ {webp_file.name}: {error}")

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Results:")
    print(f"  Total: {len(webp_files)}")
    print(f"  Migrated: {migrated}")
    print(f"  Duplicates: {duplicates}")
    print(f"  Errors: {errors}")

    if not dry_run:
        print(f"\n💡 Old cache still exists at: {old_cache}")
        print("   Delete it after verifying migration:")
        print(f"   rm -rf {old_cache}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        sys.argv.remove("--dry-run")

    asyncio.run(migrate_all(dry_run=dry_run))
