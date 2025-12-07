#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, '.')

from app.core.db import create_db_and_tables
from app.core.data_freshness import data_freshness_manager
from app.core.spotify import spotify_client

async def run_test():
    print('🚀 AUDIO2 EXPANSION TEST: 8 artists, 8 tracks each')
    print('=' * 55)

    # Setup
    create_db_and_tables()

    # User 1: Eminem
    print('\n👤 User 1 searches "Eminem"')
    artists = await spotify_client.search_artists('Eminem', limit=1)
    if artists:
        artist_data = artists[0]
        print(f'✅ Found: {artist_data["name"]}')

        expansion = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=artist_data['name'],
            main_artist_spotify_id=artist_data['id'],
            similar_count=8,
            tracks_per_artist=8
        )

        print('\n📊 EMINEM EXPANSION RESULTS:')
        print(f'• Similar artists added: {expansion["similar_artists_found"]}')
        print(f'• Total tracks added: {expansion["total_tracks_added"]}')
        print(f'• Library growth: {expansion["total_library_growth"]}')

        # Show similar artists
        print('\n🎸 SIMILAR ARTISTS FOUND:')
        for i, detail in enumerate(expansion['expansion_details'][:8], 1):
            artist_name = detail['artist_name']
            match_score = detail['match_score']
            followers = detail['followers']
            print(f'{i}. {artist_name} (match: {match_score:.2f}, {followers:,} followers)')

    # User 2: Gorillaz
    print('\n👤 User 2 searches "Gorillaz"')
    artists = await spotify_client.search_artists('Gorillaz', limit=1)
    if artists:
        artist_data = artists[0]
        print(f'✅ Found: {artist_data["name"]}')

        expansion = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=artist_data['name'],
            main_artist_spotify_id=artist_data['id'],
            similar_count=8,
            tracks_per_artist=8
        )

        print(f'\n📊 GORILLAZ EXPANSION:')
        print(f'• Similar artists added: {expansion["similar_artists_found"]}')
        print(f'• Total tracks added: {expansion["total_tracks_added"]}')

        # Show different artists for Gorillaz
        print('\n🎸 GORILLAZ SIMILAR ARTISTS:')
        for i, detail in enumerate(expansion['expansion_details'][:8], 1):
            artist_name = detail['artist_name']
            match_score = detail['match_score']
            followers = detail['followers']
            print(f'{i}. {artist_name} (match: {match_score:.2f}, {followers:,} followers)')

    # Final report
    report = await data_freshness_manager.get_data_freshness_report()
    print(f'\n📈 TOTAL DATABASE: {report["artists"]["total"]} artists')
    print(f'• Fresh data: {report["artists"]["fresh"]} artists ({report["artists"]["freshness_percentage"]:.1f}%)')

    print('\n✅ Test completed! Each user gets personalized music recommendations')

if __name__ == "__main__":
    asyncio.run(run_test())
