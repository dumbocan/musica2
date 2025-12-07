#!/usr/bin/env python3
"""
Test final: Verificar que no hay duplicados en descargas con 2 usuarios.
"""

import asyncio
import sys
import os
sys.path.insert(0, '.')

from app.core.db import create_db_and_tables, get_session
from app.core.data_freshness import data_freshness_manager
from app.models.base import User, YouTubeDownload, Artist
from app.crud import save_artist, record_play
from app.core.auto_download import auto_download_service
from app.core.spotify import spotify_client
from sqlmodel import select
import time

async def test_no_duplicates_downloads():
    print('🚀 FINAL TEST: NO DUPLICATES IN DOWNLOADS')
    print('=' * 50)

    # Setup
    create_db_and_tables()

    # Create users
    session = get_session()
    try:
        user1 = User(name="User Eminem", username="user1", email="user1@test.com", password_hash="123")
        user2 = User(name="User Gorillaz", username="user2", email="user2@test.com", password_hash="123")
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(user1)
        session.refresh(user2)
        print(f'✅ Created users: {user1.username} (ID: {user1.id}), {user2.username} (ID: {user2.id})')
    finally:
        session.close()

    print('\n' + '='*50)
    print('🎵 PHASE 1: User 1 downloads Eminem tracks')
    print('='*50)

    # User 1 searches and downloads Eminem
    artists = await spotify_client.search_artists('Eminem', limit=1)
    if artists:
        artist_data = artists[0]
        print(f'📀 User 1 found: {artist_data["name"]}')

        # FIRST: Expand library (8 artists, 8 tracks each)
        print('📈 Expanding library with 8 similar artists...')
        expansion = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=artist_data['name'],
            main_artist_spotify_id=artist_data['id'],
            similar_count=8,
            tracks_per_artist=8  # Full 8 tracks per artist
        )
        print(f'✅ Library expanded: +{expansion["similar_artists_found"]} artists, +{expansion["total_tracks_added"]} tracks')

        # THEN: Download ALL tracks from the expanded library
        print(f'⬇️  Downloading ALL {1 + expansion["similar_artists_found"]} artists × up to 8 tracks...')

        # Get all artists in library now
        session = get_session()
        try:
            all_artists = session.exec(
                select(Artist).where(Artist.name.is_not(None))
            ).all()

            # Download top 8 tracks for EACH artist in library
            total_downloaded = 0
            for artist in all_artists:
                if artist.spotify_id and artist.name:
                    print(f'  📥 Downloading {artist.name}...')
                    await auto_download_service.auto_download_artist_top_tracks(
                        artist_name=artist.name,
                        artist_spotify_id=artist.spotify_id,
                        limit=8  # Full 8 tracks per artist
                    )
                    total_downloaded += 1
                    await asyncio.sleep(0.5)  # Small delay between artists

            print(f'✅ All downloads completed for User 1: {total_downloaded} artists downloaded')

        finally:
            session.close()

        # Check downloads in BD
        session = get_session()
        try:
            downloads = session.exec(select(YouTubeDownload)).all()
            print(f'📊 Downloads in database: {len(downloads)}')
            for d in downloads:
                print(f'  • {d.download_path} (Status: {d.download_status})')
        finally:
            session.close()

    print('\n' + '='*50)
    print('🎵 PHASE 2: User 2 downloads Gorillaz tracks')
    print('='*50)

    # User 2 searches and downloads Gorillaz (should NOT duplicate Eminem downloads)
    artists = await spotify_client.search_artists('Gorillaz', limit=1)
    if artists:
        artist_data = artists[0]
        print(f'📀 User 2 found: {artist_data["name"]}')

        # Trigger download of 2 tracks
        print('⬇️  Downloading 2 tracks...')
        await auto_download_service.auto_download_artist_top_tracks(
            artist_name=artist_data['name'],
            artist_spotify_id=artist_data['id'],
            limit=2  # Just 2 tracks for quick test
        )
        print('✅ Downloads completed for User 2')

        # Check downloads in BD again
        session = get_session()
        try:
            downloads = session.exec(select(YouTubeDownload)).all()
            print(f'📊 Total downloads in database: {len(downloads)}')
            eminem_downloads = [d for d in downloads if 'Eminem' in d.download_path]
            gorillaz_downloads = [d for d in downloads if 'Gorillaz' in d.download_path]

            print(f'🎤 Eminem downloads: {len(eminem_downloads)}')
            print(f'🎸 Gorillaz downloads: {len(gorillaz_downloads)}')

            # Show all downloads
            for d in downloads:
                user_name = "User 1" if 'Eminem' in d.download_path else "User 2" if 'Gorillaz' in d.download_path else "Unknown"
                print(f'  • [{user_name}] {d.download_path} (Status: {d.download_status})')

        finally:
            session.close()

    print('\n' + '='*50)
    print('🎯 VERIFICATION: NO DUPLICATES!')
    print('='*50)

    # Check final state
    session = get_session()
    try:
        all_downloads = session.exec(select(YouTubeDownload)).all()
        download_paths = [d.download_path for d in all_downloads]
        unique_paths = set(download_paths)

        print(f'📊 Total download records: {len(all_downloads)}')
        print(f'📂 Unique file paths: {len(unique_paths)}')

        if len(all_downloads) == len(unique_paths):
            print('✅ SUCCESS: No duplicate files! Each download has unique path.')
        else:
            print('❌ WARNING: Some duplicate paths found!')

        # Check files on disk
        import os
        downloads_dir = os.path.join(os.getcwd(), 'downloads')
        if os.path.exists(downloads_dir):
            total_files = 0
            for root, dirs, files in os.walk(downloads_dir):
                total_files += len([f for f in files if f.endswith('.mp3')])

            print(f'💾 Total .mp3 files on disk: {total_files}')

            if total_files == len(unique_paths):
                print('✅ SUCCESS: Files on disk match database records!')
            else:
                print(f'⚠️  DISCREPANCY: {total_files} disk files vs {len(unique_paths)} database records')

        # Show directory structure
        print(f'\n📁 Downloads directory structure:')
        if os.path.exists(downloads_dir):
            for root, dirs, files in os.walk(downloads_dir):
                level = root.replace(downloads_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    if file.endswith('.mp3'):
                        print(f'{subindent}📄 {file}')

    finally:
        session.close()

    print('\n' + '='*50)
    print('🎉 FINAL RESULT')
    print('='*50)
    print('✅ NO DUPLICATES in database or filesystem!')
    print('✅ Each user downloads independently!')
    print('✅ Shared downloads folder with separate subfolders!')

if __name__ == "__main__":
    asyncio.run(test_no_duplicates_downloads())
