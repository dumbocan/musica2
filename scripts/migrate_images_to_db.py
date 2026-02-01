#!/usr/bin/env python3
"""
Migrate images from old cache/ to new storage/images/.

Usage: python scripts/migrate_images_to_db.py [--dry-run]
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.image_cache import CACHE_DIR  # noqa: E402
from app.core.image_db_store import store_image, IMAGE_STORAGE  # noqa: E402


def migrate_images(dry_run: bool = True):
    """Migrate all images from old cache to new storage."""
    old_cache = Path(CACHE_DIR)
    new_storage = IMAGE_STORAGE

    if not old_cache.exists():
        print(f"ℹ️  Old cache not found: {old_cache}")
        print("   No migration needed.")
        return

    webp_files = list(old_cache.glob("*.webp"))
    print(f"📁 Found {len(webp_files)} images in old cache: {old_cache}")
    print(f"📁 New storage location: {new_storage}")

    migrated = 0
    errors = 0
    skipped = 0

    for webp_file in webp_files:
        if dry_run:
            print(f"  [DRY-RUN] Would migrate: {webp_file.name}")
        else:
            try:
                # Read image data
                image_data = webp_file.read_bytes()

                # Store in new system with entity_type="migrated"
                result = store_image(
                    entity_type="migrated",
                    entity_id=None,
                    source_url=f"file://{webp_file.relative_to(Path.cwd())}",
                    image_data=image_data
                )

                if result:
                    migrated += 1
                    print(f"  ✅ Migrated: {webp_file.name}")
                else:
                    skipped += 1
                    print(f"  ⚠️  Skipped (already exists): {webp_file.name}")

            except Exception as e:
                errors += 1
                print(f"  ❌ Error ({webp_file.name}): {e}")

    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Results:")
    print(f"  Total images: {len(webp_files)}")
    print(f"  Migrated: {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

    if not dry_run and migrated > 0:
        print(f"\n💡 Old cache still contains images at: {old_cache}")
        print("   You can delete it after verifying the migration:")
        print(f"   rm -rf {old_cache}")

    if dry_run:
        print("\n💡 Run without --dry-run to actually migrate")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        sys.argv.remove("--dry-run")

    migrate_images(dry_run=dry_run)
