#!/usr/bin/env python3
"""
Report of what should be downloaded by the Audio2 system.
Shows all artists and tracks in database that need downloading.
"""

import sys
sys.path.insert(0, '.')

from app.core.db import get_session
from app.models.base import Artist, Track, YouTubeDownload, User
from sqlmodel import select

def generate_download_report():
    print('🎵 AUDIO2 DOWNLOAD REPORT')
    print('=' * 70)
    print('Complete list of what should be downloaded\n')

    session = get_session()
    try:
        # Get all users
        users = session.exec(select(User)).all()
        print('👥 USERS IN SYSTEM:')
        for user in users:
            print(f'  • {user.name} ({user.username}) - ID: {user.id}')
        print()

        # Get all artists
        artists = session.exec(select(Artist)).all()
        print(f'🎤 TOTAL ARTISTS IN DATABASE: {len(artists)}')
        print()

        # Group artists by user collections - including main artists
        # User 1: Eminem + similar artists
        eminem_artists = [a for a in artists if a.name.lower() in ['eminem']]
        eminem_similar = [a for a in artists if a.name.lower() in [
            'd12', 'bad meets evil', 'obie trice', 'paul rosenberg', '50 cent', 'ca$his', 'dr. dre', 'royce da 5\'9"'
        ]]
        user1_collection = eminem_artists + eminem_similar

        # User 2: Gorillaz + similar artists
        gorillaz_artists = [a for a in artists if a.name.lower() in ['gorillaz']]
        gorillaz_similar = [a for a in artists if a.name.lower() in [
            'good, the bad & the queen', 'damon albarn', 'radiohead', 'mgmt', 'twenty one pilots', 'foster the people', 'franz ferdinand', 'tally hall'
        ]]
        user2_collection = gorillaz_artists + gorillaz_similar

        # Show User 1 collection: Eminem + 8 similar
        print('🎤 EMINEM USER COLLECTION (User 1) - 1 SEARCH = 9 ARTISTS:')
        print(f'   Total artists: {len(user1_collection)}')
        print('   Main artist searched:')
        for artist in eminem_artists:
            print(f'     ⭐ {artist.name} (Followers: {artist.followers:,})')
        print('   Similar artists added:')
        for i, artist in enumerate(eminem_similar, 1):
            print(f'     {i}. {artist.name} (Followers: {artist.followers:,})')
        print()

        # Show User 2 collection: Gorillaz + 8 similar
        print('🎸 GORILLAZ USER COLLECTION (User 2) - 1 SEARCH = 9 ARTISTS:')
        print(f'   Total artists: {len(user2_collection)}')
        print('   Main artist searched:')
        for artist in gorillaz_artists:
            print(f'     ⭐ {artist.name} (Followers: {artist.followers:,})')
        print('   Similar artists added:')
        has_similar = False
        for i, artist in enumerate(gorillaz_similar, 1):
            if artist:  # Only show if artist exists in database
                print(f'     {i}. {artist.name} (Followers: {artist.followers:,})')
                has_similar = True
        if not has_similar:
            print('     (Similar artists will be added during expansion)')
        print()

        # Get all tracks that should be downloaded
        tracks = session.exec(select(Track)).all()
        print(f'🎵 TOTAL TRACKS TO DOWNLOAD: {len(tracks)}')
        print()

        # Show track breakdown by artist
        print('📋 TRACK BREAKDOWN BY ARTIST:')
        artist_track_counts = {}
        for track in tracks:
            artist_name = session.exec(select(Artist).where(Artist.id == track.artist_id)).first()
            if artist_name:
                artist_name = artist_name.name
                if artist_name not in artist_track_counts:
                    artist_track_counts[artist_name] = 0
                artist_track_counts[artist_name] += 1

        # Sort by track count descending
        sorted_artists = sorted(artist_track_counts.items(), key=lambda x: x[1], reverse=True)

        for artist_name, track_count in sorted_artists:
            user_indicator = " [User 1]" if artist_name in [a.name for a in eminem_artists] else " [User 2]" if artist_name in [a.name for a in gorillaz_artists] else ""
            print(f'   {artist_name}{user_indicator}: {track_count} tracks')

        print()
        print('🎯 DOWNLOAD STATISTICS:')
        total_tracks = len(tracks)
        user1_tracks = sum(artist_track_counts[a.name] for a in eminem_artists if a.name in artist_track_counts)
        user2_tracks = sum(artist_track_counts[a.name] for a in gorillaz_artists if a.name in artist_track_counts)

        print(f'   • Total tracks in database: {total_tracks}')
        print(f'   • User 1 (Eminem) tracks: {user1_tracks}')
        print(f'   • User 2 (Gorillaz) tracks: {user2_tracks}')
        print(f'   • Estimated download size: ~{total_tracks * 4} MB (4MB per track avg)')

        # Show actual disk space and files
        print()
        print('💾 CURRENT DOWNLOAD STATUS:')
        downloads = session.exec(select(YouTubeDownload)).all()
        completed_downloads = [d for d in downloads if d.download_status == 'completed']

        print(f'   • Completed downloads: {len(completed_downloads)} / {len(downloads)} tracks')
        print(f'   • Files actually downloaded: {len(completed_downloads)}')

        if completed_downloads:
            total_size_bytes = sum(d.file_size or 0 for d in completed_downloads)
            total_size_mb = total_size_bytes / (1024 * 1024)
            print(f'   • Total size downloaded: {total_size_mb:.1f} MB')
            print()
            print('📄 COMPLETED DOWNLOADS:')
            for download in completed_downloads:
                print(f'   ✓ {download.download_path}')

        # Calculate what still needs downloading
        tracks_downloaded = len(completed_downloads)
        tracks_pending = total_tracks - tracks_downloaded

        print()
        print('🚀 DOWNLOAD QUEUE REMAINING:')
        print(f'   • Tracks pending download: {tracks_pending}')

        # Show pending downloads by artist
        if tracks:
            print('   • Breakdown by artist:')
            for artist_name, track_count in sorted_artists:
                print(f'     - {artist_name}: up to {track_count} tracks remaining')

    finally:
        session.close()

    print()
    print('=' * 70)
    print('🎉 AUDIO2 SYSTEM READY FOR MASS DOWNLOAD!')
    print('Each user should have access to their personalized music collection.')
    print('Files will be organized in shared folders but accessible by all.')

if __name__ == "__main__":
    generate_download_report()
