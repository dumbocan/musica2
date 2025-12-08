#!/usr/bin/env python3
"""
Test: Force complete library expansion for Eminem + 8 similar artists.
This will show exactly what's being saved to the database.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.core.data_freshness import data_freshness_manager

async def test_full_discography():
    print("🎵 TESTING COMPLETE DISCOGRAPHY EXPANSION FOR EMINEM")
    print("=" * 60)

    try:
        # Force complete expansion of Eminem library
        result = await data_freshness_manager.expand_user_library_from_full_discography(
            main_artist_name="Eminem",
            main_artist_spotify_id="7dGJo4pcD2V6oG8kP0tJRR",  # Eminem Spotify ID
            similar_count=8,
            tracks_per_artist=8,
            include_youtube_links=True,
            include_full_albums=True
        )

        print("✅ EXPANSION RESULT:")
        print(f"Main Artist: {result['main_artist']}")
        print(f"Similar Artists Processed: {result['similar_artists_processed']}")
        print(f"Total Artists Processed: {result['total_artists_processed']}")
        print(f"Total Albums Processed: {result['total_albums_processed']}")
        print(f"Total Tracks Processed: {result['total_tracks_processed']}")

        print("\n🎯 FULL LIBRARY EXPANSION DETAILS:")
        print(result['expansion_details'])

        print("\n📊 DATABASE CHECK - Run this in psql:")
        print("SELECT a.name, COUNT(al.id), COUNT(t.id) FROM artist a LEFT JOIN album al ON a.id=al.artist_id LEFT JOIN track t ON al.id=t.album_id GROUP BY a.id, a.name ORDER BY COUNT(al.id) DESC;")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the async test
    asyncio.run(test_full_discography())
