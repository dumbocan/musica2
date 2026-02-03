#!/usr/bin/env python3
"""
Script to repopulate the database with downloaded audio files.

This script:
1. Scans the downloads folder for audio files
2. For each file, searches for matching tracks in the database by NAME
3. If a match is found, creates/updates YouTubeDownload with correct path
4. Uses existing video_id from database when available

Usage:
    python scripts/repair_download_db.py [--dry-run] [--limit N]
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select
from sqlalchemy import func

from app.core.config import settings
from app.core.db import get_session
from app.models.base import Artist, Track, YouTubeDownload
from app.crud import normalize_name


def clean_track_name(name: str) -> str:
    """Clean track name for comparison."""
    # Remove file extension
    name = Path(name).stem
    # Remove video ID suffix (11 chars alphanum at end)
    name = re.sub(r'-[a-zA-Z0-9_-]{11}$', '', name)
    # Remove common suffixes
    name = re.sub(r'\s*-\s*(Remix|Extended|Mix|Edit|Slowride|Live|Session|Instrumental|Explicit)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    # Normalize
    return normalize_name(name.replace('-', ' ').replace('_', ' ').lower().strip())


def find_track_by_name_in_db(session, track_name: str, artist_id: Optional[int] = None) -> Optional[Track]:
    """Find track in database by cleaned name."""
    cleaned = clean_track_name(track_name)

    # Build query
    if artist_id:
        # Search within specific artist
        result = session.exec(
            select(Track).where(Track.artist_id == artist_id)
        ).all()
        # Fuzzy match
        for track in result:
            track_cleaned = clean_track_name(track.name)
            if cleaned == track_cleaned or cleaned in track_cleaned or track_cleaned in cleaned:
                return track
    else:
        # Search all tracks with similar name (case insensitive partial match)
        result = session.exec(
            select(Track).where(
                (func.lower(Track.name).ilike(f'%{cleaned}%')) |
                (Track.name.ilike(f'%{track_name}%'))
            ).limit(20)
        ).all()

        if result:
            # Return best match
            for track in result:
                track_cleaned = clean_track_name(track.name)
                if cleaned == track_cleaned:
                    return track
            return result[0]

    return None


def find_artist_by_name(session, folder_name: str) -> Optional[Artist]:
    """Find artist by folder name."""
    normalized_folder = normalize_name(folder_name)

    # Try exact match
    result = session.exec(
        select(Artist).where(Artist.normalized_name == normalized_folder)
    ).first()
    if result:
        return result

    # Try without hyphens
    without_hyphens = folder_name.replace('-', ' ').replace('_', ' ')
    normalized_no_hyphen = normalize_name(without_hyphens)
    result = session.exec(
        select(Artist).where(Artist.normalized_name == normalized_no_hyphen)
    ).first()
    if result:
        return result

    # Try fuzzy
    all_artists = session.exec(select(Artist).limit(200)).all()
    for artist in all_artists:
        if not artist.normalized_name:
            continue
        folder_test = folder_name.lower().replace('-', '').replace('_', '')
        artist_test = (artist.normalized_name or '').lower().replace('-', '').replace('_', '')
        if folder_test == artist_test or folder_test in artist_test or artist_test in folder_test:
            return artist

    return None


def process_download_folder(download_dir: Path, dry_run: bool = False) -> dict:
    """Scan downloads folder and match files to database tracks by name."""
    stats = {
        'scanned': 0,
        'matched': 0,
        'repaired': 0,
        'created': 0,
        'skipped': 0,
        'errors': 0,
        'artist_not_found': 0,
        'track_not_found': 0,
    }
    audio_extensions = {'.mp3', '.m4a', '.webm', '.ogg', '.flac', '.wav'}

    # Collect all audio files
    all_files: list[tuple[Path, str]] = []  # (path, artist_folder)
    if download_dir.exists():
        for item in sorted(download_dir.rglob('*')):
            if item.is_file() and item.suffix.lower() in audio_extensions:
                parts = item.relative_to(download_dir).parts
                if len(parts) >= 2:
                    artist_folder = parts[0]
                    all_files.append((item, artist_folder))

    print(f"\n📁 Found {len(all_files)} audio files")

    # Group by artist for efficient lookup
    files_by_artist: dict[str, list[Path]] = {}
    for file_path, artist_folder in all_files:
        if artist_folder not in files_by_artist:
            files_by_artist[artist_folder] = []
        files_by_artist[artist_folder].append(file_path)

    with get_session() as session:
        for folder_key, files in files_by_artist.items():
            if not files:
                continue

            # Find artist
            artist = find_artist_by_name(session, folder_key)

            if not artist:
                print(f"  ⚠️  Artist not found: {folder_key}")
                stats['artist_not_found'] += len(files)
                stats['skipped'] += len(files)
                continue

            print(f"  🎵 {artist.name}: {len(files)} files")

            for file_path in files:
                stats['scanned'] += 1
                filename = file_path.name

                # Find track by NAME in database
                track = find_track_by_name_in_db(session, filename, artist.id)

                if not track:
                    # Try without artist constraint
                    track = find_track_by_name_in_db(session, filename)
                    if track:
                        print(f"    ⚠️  Different artist: {filename} -> {track.artist_id}")

                if not track:
                    print(f"    ❌ Track not found in DB: {filename}")
                    stats['track_not_found'] += 1
                    stats['skipped'] += 1
                    continue

                # Calculate relative path
                try:
                    rel_path = str(file_path.relative_to(download_dir))
                except ValueError:
                    rel_path = str(file_path)

                # Get existing YouTubeDownload
                existing = None
                video_id = None

                if track.spotify_id:
                    existing = session.exec(
                        select(YouTubeDownload).where(
                            YouTubeDownload.spotify_track_id == track.spotify_id
                        )
                    ).first()
                    video_id = existing.youtube_video_id if existing and existing.youtube_video_id else None

                # If no video_id, search in other tracks with same name
                if not video_id:
                    # Search any track with similar name that has video_id
                    similar_tracks = session.exec(
                        select(Track, YouTubeDownload)
                        .join(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id, isouter=True)
                        .where(
                            (Track.name.ilike(f'%{track.name}%'))
                        )
                        .limit(10)
                    ).all()

                    for t, d in similar_tracks:
                        if d and d.youtube_video_id and d.download_status in ('completed', 'link_found'):
                            video_id = d.youtube_video_id
                            print(f"    🔍 Found video_id from similar: {t.name[:30]} -> {video_id}")
                            break

                if existing:
                    # Check if needs repair
                    needs_repair = (
                        existing.download_status != 'completed' or
                        not existing.download_path or
                        existing.download_path != rel_path
                    )

                    if needs_repair and video_id:
                        if dry_run:
                            print(f"    🔧 Would repair: {track.name}")
                            stats['repaired'] += 1
                        else:
                            existing.download_status = 'completed'
                            existing.download_path = rel_path
                            existing.updated_at = datetime.utcnow()
                            session.add(existing)
                            print(f"    ✅ Repaired: {track.name}")
                            stats['repaired'] += 1
                    elif existing.download_status == 'completed':
                        stats['matched'] += 1
                    else:
                        print(f"    ℹ️  Status: {existing.download_status} - {track.name}")
                        stats['matched'] += 1
                else:
                    # Need video_id to create
                    if video_id:
                        if dry_run:
                            print(f"    ➕ Would create: {track.name}")
                            stats['created'] += 1
                        else:
                            download_entry = YouTubeDownload(
                                spotify_track_id=track.spotify_id,
                                spotify_artist_id=artist.spotify_id or '',
                                youtube_video_id=video_id,
                                download_path=rel_path,
                                download_status='completed',
                            )
                            session.add(download_entry)
                            print(f"    ➕ Created: {track.name}")
                            stats['created'] += 1
                    else:
                        print(f"    ⚠️  No video_id: {track.name}")
                        stats['skipped'] += 1

            if not dry_run:
                session.commit()

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Repair download database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of files to process')
    args = parser.parse_args()

    download_dir = Path(settings.DOWNLOAD_ROOT)
    print(f"\n📁 Download directory: {download_dir.absolute()}")
    print(f"   Exists: {download_dir.exists()}")

    if not download_dir.exists():
        print("❌ Download directory does not exist!")
        sys.exit(1)

    print(f"\n{'🔍 DRY RUN' if args.dry_run else '🚀 RUNNING'} - Matching files to database tracks by NAME...")
    print("-" * 60)

    stats = process_download_folder(download_dir, dry_run=args.dry_run)

    print("-" * 60)
    print("\n📊 Summary:")
    print(f"   Scanned: {stats['scanned']}")
    print(f"   Matched: {stats['matched']}")
    print(f"   Repaired: {stats['repaired']}")
    print(f"   Created: {stats['created']}")
    print(f"   Skipped: {stats['skipped']}")
    print(f"   Artist not found: {stats['artist_not_found']}")
    print(f"   Track not found: {stats['track_not_found']}")
    print(f"   Errors: {stats['errors']}")

    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")

    return 0


if __name__ == '__main__':
    main()
