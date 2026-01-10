#!/usr/bin/env python3
"""
Test script for multi-user data freshness system.
Tests searching Eminem and Gorillaz with different users.
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.core.db import create_db_and_tables
from app.core.data_freshness import data_freshness_manager
from app.crud import (
    save_artist, get_artist_by_spotify_id, save_album, save_track,
)
from app.core.spotify import spotify_client
from app.core.lastfm import lastfm_client


async def setup_test_data():
    """Setup test environment."""
    print("🔧 Setting up test environment...")

    # Create tables
    create_db_and_tables()

    print("✅ Database ready")


async def test_user_search(user_id: int, query: str):
    """Test artist search for a user."""
    print(f"\n👤 User {user_id} searching for: {query}")

    try:
        # 1. Search artists via Spotify
        artists = await spotify_client.search_artists(query, limit=5)
        if not artists:
            print(f"❌ No artists found for {query}")
            return

        # Take first result
        first_artist = artists[0]
        print(f"🎤 Found artist: {first_artist['name']} (ID: {first_artist['id']})")

        # 2. Check if we already have this artist in DB
        existing_artist = get_artist_by_spotify_id(first_artist['id'])
        if existing_artist:
            print(f"📚 Artist already in DB (ID: {existing_artist.id})")

            # Check if data needs refresh
            needs_refresh = await data_freshness_manager.should_refresh_artist(existing_artist)
            if needs_refresh:
                print("🔄 Artist data is stale, refreshing...")
                success = await data_freshness_manager.refresh_artist_data(first_artist['id'])
                if success:
                    print("✅ Artist data refreshed")

                    # Check for new content
                    new_content = await data_freshness_manager.check_for_new_artist_content(first_artist['id'])
                    print(f"🎵 New content discovered: {new_content}")

                else:
                    print("❌ Failed to refresh artist data")
            else:
                print(f"✨ Artist data is fresh (last updated: {existing_artist.updated_at})")

        else:
            # Save new artist to DB
            print("💾 Saving new artist to DB...")
            artist = save_artist(first_artist)
            print(f"✅ Artist saved (ID: {artist.id})")

            # Get biography from Last.fm
            try:
                bio_data = await lastfm_client.get_artist_info(artist.name)
                if bio_data:
                    from app.crud import update_artist_bio
                    update_artist_bio(artist.id, bio_data['summary'], bio_data['content'])
                    print("📝 Artist bio updated from Last.fm")
            except Exception as bio_error:
                print(f"⚠️ Could not fetch bio: {bio_error}")

            # Also save some top tracks for the artist (test data freshness)
            try:
                print("🎵 Fetching and saving top tracks...")
                top_tracks = await spotify_client.get_artist_top_tracks(first_artist['name'], limit=3)
                if top_tracks:
                    for track_data in top_tracks:
                        # Create a mock album for testing
                        mock_album_data = {
                            'id': f"test_album_{artist.id}",
                            'name': f"{first_artist['name']} hits",
                            'release_date': '2020-01-01',
                            'total_tracks': 10,
                            'images': [{"url": ""}],
                            'artists': [{"id": first_artist['id'], "name": first_artist['name']}]
                        }
                        album = save_album(mock_album_data)
                        save_track(track_data, album.id, artist.id)
                    print(f"✅ Saved {len(top_tracks)} top tracks")
                else:
                    print("⚠️ No top tracks found")
            except Exception as track_error:
                print(f"⚠️ Could not save tracks: {track_error}")

        # 3. Get fresh tracks for this artist
        print(f"🎼 Getting fresh tracks for {first_artist['name']}...")
        tracks = await data_freshness_manager.get_fresh_artist_tracks(first_artist['id'], limit=5)
        print(f"📀 Found {len(tracks)} tracks")

        for i, track in enumerate(tracks[:3], 1):  # Show first 3
            print(f"   {i}. {track.name} (Popularity: {track.popularity}, Last.fm: {track.lastfm_listeners})")

        # 4. Show data freshness report
        print("📊 Data freshness status after search:")
        report = await data_freshness_manager.get_data_freshness_report()
        print(f"   Artists: {report['artists']['total']} total, {report['artists']['fresh']} fresh")
        print(f"   Downloads: {report['downloads']['total_attempts']} attempts, {report['downloads']['completed']} completed")

    except Exception as e:
        print(f"❌ Error during search: {str(e)}")


async def run_multi_user_test():
    """Run the multi-user test."""
    print("🎭 MULTI-USER DATA FRESHNESS TEST")
    print("=" * 50)

    await setup_test_data()

    # Test User 1: Search Eminem
    await test_user_search(user_id=1, query="Eminem")

    # Small delay between users
    await asyncio.sleep(1)

    # Test User 2: Search Gorillaz
    await test_user_search(user_id=2, query="Gorillaz")

    # Show final data freshness report
    print("\n📈 FINAL DATA FRESHNESS REPORT")
    print("=" * 40)

    try:
        report = await data_freshness_manager.get_data_freshness_report()
        print(f"Artists: {report['artists']['total']} total")
        print(f"  - Fresh: {report['artists']['fresh']} ({report['artists']['freshness_percentage']:.1f}%)")
        print(f"  - Stale: {report['artists']['stale']}")
        print(f"Downloads: {report['downloads']['total_attempts']} attempts")
        print(f"  - Completed: {report['downloads']['completed']} ({report['downloads']['completion_rate']:.1f}%)")

    except Exception as report_error:
        print(f"❌ Error generating report: {report_error}")

    print("\n🎉 Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_multi_user_test())
