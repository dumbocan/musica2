#!/usr/bin/env python3
"""
Algoritmo mejorado para selección inteligente de música
"""
import asyncio
from typing import List, Dict

# Hardcoded iconic tracks para artistas legendarios
ICONIC_TRACKS = {
    'eminem': [
        'Lose Yourself',      # Oscars, 8 Mile movie
        'Stan',              # Grammy winner, cultural phenomenon
        'Love The Way You Lie',  # First #1 Billboard in 8 years
        'Rap God',           # Guinness World Record
        'Not Afraid'         # Post-recovery anthem
    ],
    '50 cent': [
        'In Da Club',        # #1 Billboard, 2x platinum
        'P.I.M.P.',
        'Candy Shop',
        'Baby By Me'
    ],
    'dr. dre': [
        'Still D.R.E.',
        'Forgot About Dre',
        'Nuthin\''
    ],
    'royce da 5\'9"': [
        'Hip Hop',
        'Boom',
        'Kingdom Come'
    ],
    'snoop dogg': [
        'Gin & Juice',
        'Drop It Like It\'s Hot',
        'What\'s My Name?'
    ]
}

class SmartMusicSelector:
    """Selector inteligente de música basado en popularidad real"""

    def __init__(self):
        self.min_followers = 2_000_000  # 2M followers mínimo
        self.min_popularity = 70        # Popularity score mínimo
        self.blacklist = [
            'D12', 'Bad Meets Evil', 'Paul Rosenberg', 'Ca$his',
            'Stat Quo', 'Slaughterhouse'  # Grupos secundarios/artistas menores
        ]

    async def get_real_popular_artists(self, artist_name: str, limit: int = 10) -> List[Dict]:
        """
        Obtiene artistas similares PERO filtra por popularidad real

        Returns list of popular artists, not just music-math similar ones
        """
        from app.core.lastfm import lastfm_client
        from app.core.spotify import spotify_client

        print(f"🎵 Buscando artistas similares a '{artist_name}'...")

        # 1. Get similar artists from Last.fm
        similar_artists = await lastfm_client.get_similar_artists(artist_name, limit=20)

        print(f"📊 Last.fm encontró {len(similar_artists)} similares")

        # 2. Cross-check with Spotify for REAL popularity
        popular_artists = []

        for similar_artist in similar_artists:
            name = similar_artist['name']

            # Skip blacklisted artists (grupos secundarios, etc.)
            if any(blacklisted.lower() in name.lower() for blacklisted in self.blacklist):
                print(f"🚫 Saltando {name} (blacklisted)")
                continue

            try:
                # Check real Spotify popularity
                spotify_results = await spotify_client.search_artists(name, limit=1)
                if spotify_results:
                    sp_artist = spotify_results[0]
                    followers = sp_artist.get('followers', {}).get('total', 0)
                    popularity = sp_artist.get('popularity', 0)

                    # Filter for REAL stars
                    if followers >= self.min_followers and popularity >= self.min_popularity:
                        artist_data = {
                            'name': name,
                            'lastfm_match': similar_artist['match'],
                            'followers': followers,
                            'popularity': popularity,
                            'spotify_id': sp_artist.get('id'),
                            'genre': sp_artist.get('genres', [])[:2],  # Top 2 genres
                            'tier': "🌟 Superestrella" if followers > 10_000_000 else "⭐ Leyenda" if followers > 5_000_000 else "✅ Famoso"
                        }
                        popular_artists.append(artist_data)

            except Exception as e:
                print(f"⚠️ Error checkando {name}: {e}")

        # Sort by followers (real popularity)
        popular_artists.sort(key=lambda x: x['followers'], reverse=True)

        return popular_artists[:limit]

    async def get_smart_tracks_for_artist(self, artist_name: str, limit: int = 3) -> List[str]:
        """
        Devuelve pistas inteligentes para descargar:

        1. Si el artista tiene tracks icónicos hardcoded → usar esas
        2. Si no → usar algoritmo inteligente con Last.fm + Spotify
        """
        artist_key = artist_name.lower().replace(' ', '')

        # 1. Check for hardcoded iconic tracks (los mejores de la historia)
        if artist_key in ICONIC_TRACKS:
            iconic_tracks = ICONIC_TRACKS[artist_key][:limit]
            print(f"🎬 Usando pistas ICÓNICAS para {artist_name}: {iconic_tracks}")
            return iconic_tracks

        # 2. Fallback: smart algorithm
        print(f"🧠 Usando algoritmo inteligente para {artist_name}...")
        return await self._get_algorithm_tracks(artist_name, limit)

    async def _get_algorithm_tracks(self, artist_name: str, limit: int) -> List[str]:
        """
        Algoritmo inteligente para pistas:
        Cross-check Spotify + Last.fm + metadata
        """
        try:
            from app.core.spotify import spotify_client
            from app.core.lastfm import lastfm_client

            # Get artists' albums first
            albums = await spotify_client.get_artist_albums(artist_name, limit=5)

            # Get last.fm track info for scoring
            track_candidates = []

            for album in albums[:3]:  # Top 3 albums
                album_tracks = await spotify_client.get_album_tracks(album['id'])

                for track in album_tracks[:5]:  # Top 5 tracks per album
                    track_name = track['name']

                    # Skip intros/remixes
                    if any(skip_word in track_name.lower() for skip_word in
                           ['intro', 'outro', 'remix', 'live', 'acoustic']):
                        continue

                    # Check Last.fm listener counts
                    try:
                        track_info = await lastfm_client.get_track_info(artist_name, track_name)
                        listener_count = track_info.get('listeners', 0)

                        track_candidates.append({
                            'name': track_name,
                            'listeners': listener_count,
                            'popularity': track.get('popularity', 0),
                            'album': album.get('name', 'Unknown')
                        })

                    except Exception:
                        # Fallback without Last.fm
                        track_candidates.append({
                            'name': track_name,
                            'listeners': 0,
                            'popularity': track.get('popularity', 0),
                            'album': album.get('name', 'Unknown')
                        })

            # Sort by Last.fm listeners + Spotify popularity
            def score_track(track):
                listener_score = min(track['listeners'] / 1000, 10)  # Normalize to 0-10
                popularity_score = track['popularity'] / 10  # Normalize to 0-10
                return listener_score + popularity_score

            track_candidates.sort(key=score_track, reverse=True)

            # Return top tracks
            selected_tracks = [track['name'] for track in track_candidates[:limit]]

            print(f"🧠 Algoritmo seleccionó para {artist_name}: {selected_tracks}")
            return selected_tracks

        except Exception as e:
            print(f"❌ Error en algoritmo inteligente para {artist_name}: {e}")
            return []

async def main():
    """Demo del algoritmo mejorado"""

    selector = SmartMusicSelector()

    print('🚀 **ALGORITMO MEJORADO - DEMOSTRACIÓN**')
    print('=====================================')
    print()

    # 1. Test artists similares filtrados por popularidad REAL
    print('1️⃣ **ARTISTAS RELACIONADOS (FILTRADOS POR POPULARIDAD REAL):**')

    similar_artists = await selector.get_real_popular_artists('eminem', 5)

    print(f'\n🎯 Encontrados {len(similar_artists)} artistas realmente famosos relacionados con Eminem:')
    print(f'(Filtrado: >{selector.min_followers:,} followers + >{selector.min_popularity} popularity)')
    print()

    for i, artist in enumerate(similar_artists, 1):
        print(f'   {i}. {artist["name"]:<12} | {artist["tier"]} | {artist["followers"]:,} followers | Popularidad: {artist["popularity"]}')

    print()
    print('2️⃣ **PISTAS SELECCIONADAS POR ARTISTA:**')

    # Test tracks para diferentes artistas
    test_artists = ['eminem', '50 cent', 'dr. dre', 'royce da 5\'9"']

    for artist in test_artists:
        print(f'\n🎵 **{artist.upper()}**')
        tracks = await selector.get_smart_tracks_for_artist(artist, 3)

        for i, track in enumerate(tracks[:3], 1):
            print(f'   {i}. "{track}"')

    print()
    print('3️⃣ **RESUMEN DE MEJORAS:**')
    print('✅ Filtrado por 2M+ followers (50 Cent, Dr. Dre)')
    print('✅ Pistas icónicas hardcoded (Lose Yourself, In Da Club)')
    print('✅ Blacklist de artistas menores (D12, Bad Meets Evil)')
    print('✅ Popularidad vs compatibilidad musical')
    print('✅ Sistema de tiers: Superestrella/Famoso/Leyenda')

    print()
    print('🎯 **PLAN DE DESARGA PROpuesto:**')

    # Plan de descarga basado en los resultados
    main_artist = 'eminem'
    main_tracks = await selector.get_smart_tracks_for_artist(main_artist, 3)

    print(f'Artista principal: 🎤 **{main_artist.upper()}**')
    for i, track in enumerate(main_tracks, 1):
        status = "🎬 ICÓNICO" if track.lower().find('lose yourself') >= 0 else "⭐ HYPE"
        print(f'   ↳ {track} {status}')

    print(f'\nArtistas relacionados: {len(similar_artists)}')
    for i, artist in enumerate(similar_artists[:3], 1):
        tier = artist["tier"]
        name = artist["name"]
        print(f'   ↳ {name} ({tier})')
        # Podríamos mostrar tracks aquí también

if __name__ == '__main__':
    asyncio.run(main())
