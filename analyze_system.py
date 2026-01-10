#!/usr/bin/env python3
"""
Script de análisis del sistema auto-download
"""
import asyncio

async def main():
    print('🎤 **ANÁLISIS PROFUNDO: Qué encontró el sistema para Eminem**')
    print('============================================================')
    print()

    # 1. Artistas similares según Last.fm
    print('1️⃣ **ARTISTAS SIMILARES ENCONTRADOS POR LAST.FM:**')
    try:
        from app.core.lastfm import lastfm_client

        similar_artists = await lastfm_client.get_similar_artists('eminem', limit=10)
        print(f'Last.fm encontró {len(similar_artists)} artistas similares:')
        for i, artist in enumerate(similar_artists, 1):
            name = artist['name']
            match = artist['match']
            print(f'   {i}. {name} (compatibilidad: {match:.2f})')

        similar_top = similar_artists[:5]  # Top 5 que usaríamos

    except Exception as e:
        print(f'❌ Error con Last.fm: {e}')
        similar_top = []

    print()
    print('2️⃣ **TOP TRACKS IDENTIFICADOS POR SPOTIFY:**')

    try:
        # 2. Top tracks que descargaría
        from app.core.spotify import spotify_client

        top_tracks = await spotify_client.get_artist_top_tracks('eminem', 5)
        print(f'Spotify identificó {len(top_tracks)} top tracks reales:')
        for i, track in enumerate(top_tracks[:5], 1):
            name = track.get('name', 'Unknown')
            popularity = track.get('popularity', 'N/A')
            print(f'   {i}. "{name}" (popularidad: {popularity})')

        print('\n📊 Resumen:')
        print('   🎤 Artista principal: Eminem')
        print(f'   🎵 Top tracks identificados: {len(top_tracks)}')
        print(f'   🎸 Artistas similares encontrados: {len(similar_top[:3])}')

        eminem_tracks = top_tracks[:3] if len(top_tracks) >= 3 else top_tracks
        print(f'   🎵 Tracks de Eminem a descargar: {len(eminem_tracks)}')

        print()
        print('🎯 **PLAN COMPLETO DE DESCARGA PROPUESTO:**')
        print('Artista principal:')
        print('   🎤 Eminem → descartar duplicados existentes')

        print('\nArtistas relacionados a descargar nuevas:')
        for i, artist in enumerate(similar_top[:5], 1):
            name = artist['name']
            match = artist['match']
            status = "✅ Usar" if i <= 3 else "⏳ Backup"
            print(f'   {i}. {name} → 3 mejores pistas (compatibilidad: {match:.2f}) {status}')

        print(
            f'\n🎪 **TOTAL DESCARGAS PROPUESTAS:** {len(eminem_tracks)} (Eminem) + {3 * 3} (related) = '
            f'{len(eminem_tracks) + 9} tracks'
        )

    except Exception as e:
        print(f'❌ Error con Spotify: {e}')
        print('Posible causa: Credenciales faltantes en .env')

if __name__ == '__main__':
    asyncio.run(main())
