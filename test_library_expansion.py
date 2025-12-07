#!/usr/bin/env python3
"""
Test script for automatic library expansion feature.
Tests how a single artist search expands into 10+ artists and 50+ tracks.
"""

import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.core.db import create_db_and_tables, get_session
from app.core.data_freshness import data_freshness_manager
from app.core.spotify import spotify_client
from app.crud import get_artist_by_spotify_id
from app.models.base import Artist, Track
from sqlmodel import select


async def setup_test_environment():
    """Setup clean test environment."""
    print("🔧 Setting up test environment...")
    create_db_and_tables()
    print("✅ Database ready")


async def simulate_user_artist_search(user_id: int, query: str):
    """Simulate a user searching for an artist and library auto-expansion."""
    print(f"\n👤 User {user_id} initiating search: '{query}'")
    print("=" * 60)

    try:
        # 1. Search artists on Spotify (as the API would do)
        print("🎵 Step 1: Searching artists on Spotify...")
        artists = await spotify_client.search_artists(query, limit=1)
        if not artists:
            print("❌ No artists found")
            return

        first_artist = artists[0]
        artist_name = first_artist['name']
        artist_spotify_id = first_artist['id']
        followers = first_artist.get('followers', {}).get('total', 0)

        print(f"✅ Found: {artist_name}")
        print(f"   Spotify ID: {artist_spotify_id}")
        print(f"   Followers: {followers:,}")

        # 2. Check if artist exists in our DB
        print("
📚 Step 2: Checking database...")
        existing_artist = get_artist_by_spotify_id(artist_spotify_id)

        if existing_artist:
            print(f"✅ Artist exists in DB (ID: {existing_artist.id})")

            # Check if data is fresh
            should_refresh = await data_freshness_manager.should_refresh_artist(existing_artist)
            if should_refresh:
                print("🔄 Artist data is stale, refreshing...")
                await data_freshness_manager.refresh_artist_data(artist_spotify_id)
            else:
                print("✨ Artist data is fresh")

        else:
            print("🆕 New artist - will be saved during expansion")

        # 3. Trigger automatic library expansion
        print("
🚀 Step 3: Library auto-expansion starting...")

        expansion_results = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=artist_name,
            main_artist_spotify_id=artist_spotify_id,
            similar_count=10,  # 10 similar artists
            tracks_per_artist=5  # 5 tracks each
        )

        # 4. Display detailed results
        print("
📊 EXPANSION RESULTS:")
        print("-" * 70)
        print(f"🎯 Main Artist: {expansion_results['main_artist']}")
        print(f"🎸 Similar Artists Added: {expansion_results['similar_artists_found']}")
        print(f"🎵 Total Tracks Added: {expansion_results['total_tracks_added']}")
        print(f"📈 Library Growth: {expansion_results['total_library_growth']}")

        # Show detailed track information for each similar artist
        if expansion_results['expansion_details']:
            print(f"\n🎼 DETALLES COMPLETOS POR ARTISTA:")

            # Get track details from database
            session = get_session()
            try:
                for i, detail in enumerate(expansion_results['expansion_details'][:3], 1):  # Show first 3 artists in detail
                    artist_name = detail['artist_name']
                    print(f"\n{i}. 🎤 {artist_name} (Similaridad: {detail['match_score']:.2f})")
                    print(f"   Followers: {detail['followers']:,}")

                    # Get tracks for this artist from database
                    artist_in_db = session.exec(
                        select(Artist).where(Artist.name == artist_name)
                    ).first()

                    if artist_in_db:
                        tracks = session.exec(
                            select(Track)
                            .where(Track.artist_id == artist_in_db.id)
                            .order_by(Track.popularity.desc())
                            .limit(8)
                        ).all()

                        print(f"   🎵 Top 8 tracks agregadas:")
                        for j, track in enumerate(tracks[:8], 1):
                            album_name = "Top Hits"  # Mock album name for expansion tracks
                            popularity_reason = "Popular en Spotify" if track.popularity >= 80 else f"Popularidad {track.popularity}"
                            print(f"      {j}. '{track.name}' | Álbum: '{album_name}' | Duración: {track.duration_ms//1000}s")
                            print(f"         📊 Razón: {popularity_reason} | Reproducciones Last.fm: {track.lastfm_listeners:,}")

            finally:
                session.close()

        # 5. Show final database stats
        print("
📈 FINAL DATABASE STATUS:")
        report = await data_freshness_manager.get_data_freshness_report()

        artists_stats = report['artists']
        print(f"Artists: {artists_stats['total']} total")
        print(f"   Fresh: {artists_stats['fresh']} ({artists_stats['freshness_percentage']:.1f}%)")
        print(f"   Stale: {artists_stats['stale']}")

        print("
✅ Library expansion completed successfully!"
        return expansion_results

    except Exception as e:
        print(f"❌ Error during library expansion: {str(e)}")
        return None


async def demonstrate_multi_user_scenarios():
    """Demonstrate how different users have different library expansions."""
    print("🎭 AUDIO2 AUTOMATIC LIBRARY EXPANSION DEMO")
    print("=" * 70)

    await setup_test_environment()

    # Scenario 1: User 1 searches Eminem
    print("\n" + "="*70)
    print("🎯 SCENARIO 1: User 1 searches 'Eminem'")
    print("="*70)

    eminem_results = await simulate_user_artist_search(user_id=1, query="Eminem")

    # Scenario 2: New User searches Gorillaz
    print("\n" + "="*70)
    print("🎯 SCENARIO 2: User 2 searches 'Gorillaz' (Different user, different tastes)")
    print("="*70)

    gorillaz_results = await simulate_user_artist_search(user_id=2, query="Gorillaz")

    # Summary
    print("\n" + "="*70)
    print("🎉 DEMO SUMMARY")
    print("="*70)

    if eminem_results and gorillaz_results:
        eminem_growth = eminem_results['similar_artists_found']
        eminem_tracks = eminem_results['total_tracks_added']
        gorillaz_growth = gorillaz_results['similar_artists_found']
        gorillaz_tracks = gorillaz_results['total_tracks_added']

        print(f"""
📊 RESULTS COMPARISON:
   Eminem search → {eminem_growth} similar artists, {eminem_tracks} tracks
   Gorillaz search → {gorillaz_growth} similar artists, {gorillaz_tracks} tracks
   Total library: {(eminem_growth + gorillaz_growth)} artists, {(eminem_tracks + gorillaz_tracks)} tracks
        """)

    print("🎵 Audio2 automatically creates personalized music collections!")
    print("   Each search expands into a rich, interconnected music network."
    # Show user personalization
    print("
🎯 KEY ADVANTAGES:"    print("   ✅ Multi-user: Different users, different collections"    print("   ✅ Automatic: No manual curation needed"    print("   ✅ Smart: Uses Last.fm similarity algorithms"    print("   ✅ Efficient: Prevents duplicate storage"    print("   ✅ Fresh: Always up-to-date metadata"


if __name__ == "__main__":
    asyncio.run(demonstrate_multi_user_scenarios())
