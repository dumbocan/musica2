#!/usr/bin/env python3
"""
Análisis profundo del algoritmo de selección
"""
import asyncio

async def analyze_algorithm():
    print('🔬 **ANÁLISIS DEL ALGORITMO DE SELECCIÓN**')
    print('======================================')
    print()

    # Obtener artistas similares
    print('1️⃣ **ARTISTAS SIMILARES CON SU POPULARIDAD REAL:**')
    try:
        from app.core.lastfm import lastfm_client
        from app.core.spotify import spotify_client

        similar_artists = await lastfm_client.get_similar_artists('eminem', limit=15)
        print(f'Last.fm llamó similares: {len(similar_artists)}')

        print('\n🔍 Verificando popularidad real de cada uno:')
        for i, artist in enumerate(similar_artists[:8], 1):
            name = artist['name']
            lastfm_match = artist['match']

            try:
                # Buscar en Spotify
                spotify_results = await spotify_client.search_artists(name, limit=1)
                if spotify_results and len(spotify_results) > 0:
                    sp_artist = spotify_results[0]
                    followers = sp_artist.get('followers', {}).get('total', 0)
                    popularity = sp_artist.get('popularity', 0)

                    status = "❌ Desconocido" if followers < 500000 else "⚠️ Algo conocido" if followers < 2000000 else "✅ Muy conocido" if followers < 10000000 else "🌟 Superestrella"

                    print(f'   {i}. {name:<15} | Followers: {followers:,} | Popularity: {popularity} | Last.fm: {lastfm_match:.2f} | {status}')
                else:
                    print(f'   {i}. {name:<15} | Followers: ??? | Popularity: ??? | Last.fm: {lastfm_match:.2f} | ❓ No encontrado en Spotify')

            except Exception as e:
                print(f'   {i}. {name:<15} | Error: {str(e)[:30]}... | Last.fm: {lastfm_match:.2f} | ❌ Error')

    except Exception as e:
        print(f'❌ Error analizando similares: {e}')

    print()
    print('2️⃣ **¿POR QUÉ NO SELECCIONÓ "LOSE YOURSELF"?**')

    try:
        # Verificar qué está devolviendo Spotify realmente
        all_tracks = await spotify_client.get_artist_top_tracks('eminem', 10)
        print(f'Spotify devolvió {len(all_tracks)} tracks:')

        count = 0
        found_lose_yourself = False
        for track in all_tracks:
            count += 1
            name = track.get('name', 'Unknown')
            popularity = track.get('popularity', 0)
            album_name = track.get('album', {}).get('name', 'Unknown')

            is_lose_yourself = 'lose yourself' in name.lower()
            found_lose_yourself = found_lose_yourself or is_lose_yourself

            marker = "🎬 FOUND!" if is_lose_yourself else f"{count}"
            print(f'   {marker}. "{name}" (Popularity: {popularity}) - Album: {album_name}')

        if not found_lose_yourself:
            print()
            print('❌ "Lose Yourself" NO está en las TOP TRACKS de Spotify')
            print('   → Spotify Client Credentials NO tiene acceso a "artist/top-tracks"')
            print('   → Estamos usando el método de "albums recientes", no la API real')
            print('   → Las pistas son de álbumes recientes, no "top tracks históricos"')

            print()
            print('🎯 **SOLUCIÓN PROPUESTA:**')
            print('   1. Hardcodear pistas icónicas para artistas famoso')
            print('   2. Usar Last.fm para playcount real')
            print('   3. Combinar con metadata de álbumes')
            print('   4. Filtrar por certificaciones históricas')

    except Exception as e:
        print(f'❌ Error analizando tracks: {e}')

    print()
    print('3️⃣ **PLAN DE ALGORITMO MEJORADO:**')

    # Algoritmo propuesto
    improvement_plan = """
    🔧 MELHORAS PROPUESTAS PARA EL ALGORITMO:

    A) **ARTISTAS SIMILARES REALMENTE CONOCIDOS:**
       - Spotify followers > 1M AND popularity > 60
       - Filtrar: 50 Cent ✅, Dr. Dre ✅, Kendrick Lamar ❌ (muy diferente)
       - Blacklist: Grupos secundarios (D12, Bad Meets Evil)

    B) **PISTAS BASADAS EN HISTORIA REAL:**
       - Cross-check: Spotify + Last.fm playcount + certificaciones
       - Hardcoded icónicas: Eminem=['Lose Yourself', 'Stan', 'Love The Way You Lie']
       - Priorizar: RIAA certified tracks, Billboard #1, cultural impact

    C) **DOUBLE-CHECK ANTES DE DESCARGAR:**
       - Mostrar listado completo antes de download
       - Confirmación usuario para cada artista
       - Sistema de clasificación: ⭐ Superestrella, ⭐⭐ Famoso, ⭐⭐⭐ Leyenda
    """

    print(improvement_plan)

if __name__ == '__main__':
    asyncio.run(analyze_algorithm())
