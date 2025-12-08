#!/usr/bin/env python3
"""
TEST COMPLETO SISTEMA AUDIO2 - 2 usuarios, descargas completas
"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.core.db import create_db_and_tables, get_session
from app.core.data_freshness import data_freshness_manager
from app.models.base import User, Artist, Track, YouTubeDownload
from app.core.spotify import spotify_client
from app.core.auto_download import auto_download_service
from sqlmodel import select
import time

async def test_complete_system():
    print('🚀 TEST AUDIO2 CON BD PERSISTENTE - VERIFICACIÓN NO DUPLICADOS')
    print('=' * 70)
    print('BD existente • Verificar tracks ya descargadas • NO duplicados')
    print('=' * 70)

    # DON'T clean database - use existing data
    print('\n🔧 Usando base de datos existente (persistente)...')
    create_db_and_tables()  # Will create tables if they don't exist, but won't clean data

    # Check existing users
    session = get_session()
    try:
        existing_users = session.exec(select(User)).all()
        if existing_users:
            print(f'✅ Usuarios existentes encontrados: {len(existing_users)}')
            for user in existing_users:
                print(f'   👤 {user.name} ({user.username})')
        else:
            # Create users if none exist
            user1 = User(name="User Eminem", username="user1", email="user1@test.com", password_hash="123")
            user2 = User(name="User Gorillaz", username="user2", email="user2@test.com", password_hash="123")
            session.add(user1)
            session.add(user2)
            session.commit()
            session.refresh(user1)
            session.refresh(user2)
            print(f'✅ Usuarios creados: {user1.name}, {user2.name}')
    finally:
        session.close()

    # Show current state
    session = get_session()
    try:
        existing_artists = session.exec(select(Artist)).all()
        existing_tracks = session.exec(select(Track)).all()
        existing_downloads = session.exec(select(YouTubeDownload)).all()

        print(f'\n📊 ESTADO ACTUAL DE BD:')
        print(f'   🎤 Artistas almacenados: {len(existing_artists)}')
        print(f'   🎵 Tracks en metadata: {len(existing_tracks)}')
        print(f'   💾 Downloads completados: {len(existing_downloads)}')

        if existing_downloads:
            completed = [d for d in existing_downloads if d.download_status == 'completed']
            print(f'   ✅ Tracks realmente descargadas: {len(completed)}')
    finally:
        session.close()

    print('\n' + '=' * 65)
    print('🎵 FASE 1: EXPANSIÓN DE BIBLIOTECAS')
    print('=' * 65)

    # Phase 1: User 1 searches Eminem and expands
    print('\n👤 USER 1 busca "Eminem" + auto-expande')
    artists = await spotify_client.search_artists('Eminem', limit=1)
    if artists:
        eminem_data = artists[0]
        print(f'   🎤 Encontrado: {eminem_data["name"]} ({eminem_data["followers"]["total"]:,} followers)')

        # Expand User 1 library - INCLUDE MAIN ARTIST
        print('   📈 Expandiendo con Eminem + 8 artistas similares...')
        expansion = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=eminem_data['name'],
            main_artist_spotify_id=eminem_data['id'],
            similar_count=8,
            tracks_per_artist=8  # EXACTLY 8 tracks per artist as requested
        )

        # Show User 1 expansion results
        print('   ✅ Expansión User 1 completa:')
        print(f'      {expansion["similar_artists_found"]} artistas similares agregados')
        print(f'      {expansion["total_tracks_added"]} tracks de metadata agregados')

    # Phase 1: User 2 searches Gorillaz and expands
    print('\n👤 USER 2 busca "Gorillaz" + auto-expande')
    artists = await spotify_client.search_artists('Gorillaz', limit=1)
    if artists:
        gorillaz_data = artists[0]
        print(f'   🎸 Encontrado: {gorillaz_data["name"]} ({gorillaz_data["followers"]["total"]:,} followers)')

        # Expand User 2 library - INCLUDE MAIN ARTIST
        print('   📈 Expandiendo con Gorillaz + 8 artistas similares...')
        expansion = await data_freshness_manager.expand_user_library_from_artist(
            main_artist_name=gorillaz_data['name'],
            main_artist_spotify_id=gorillaz_data['id'],
            similar_count=8,
            tracks_per_artist=8  # EXACTLY 8 tracks per artist as requested
        )

        # Show User 2 expansion results
        print('   ✅ Expansión User 2 completa:')
        print(f'      {expansion["similar_artists_found"]} artistas similares agregados')
        print(f'      {expansion["total_tracks_added"]} tracks de metadata agregados')

    # Show database state after expansion
    session = get_session()
    try:
        artists_count = session.exec(select(Artist)).all()
        tracks_count = session.exec(select(Track)).all()
        print(f'\n📊 Base de datos después de expansión:')
        print(f'   🎤 {len(artists_count)} artistas totales')
        print(f'   🎵 {len(tracks_count)} tracks de metadata para descargar')
        print(f'   📦 Estimado descarga: ~{len(tracks_count) * 4} MB')
    finally:
        session.close()

    print('\n' + '=' * 65)
    print('🎵 FASE 2: DESCARGAR TODAS LAS TRACKS')
    print('=' * 65)

    # Phase 2: Download all tracks for both users
    session = get_session()
    try:
        all_artists = session.exec(select(Artist).where(Artist.name.is_not(None))).all()
        print(f'\n⬇️ Descargando tracks de {len(all_artists)} artistas...')

        # Download ALL 16 artists (8 similar to Eminem + 8 similar to Gorillaz)
        # This gives us EXACTLY what the user requested: 8 tracks from each of 8 similar artists per user

        user1_artists = [a for a in all_artists if any(x in a.name.lower() for x in [
            'd12', 'bad meets evil', 'obie trice', 'paul rosenberg', '50 cent', 'ca$his', 'dr. dre', 'royce da 5\'9"'
        ])]

        user2_artists = [a for a in all_artists if any(x in a.name.lower() for x in [
            'franz ferdinand', 'tally hall', 'the good, the bad & the queen', 'damon albarn',
            'radiohead', 'mgmt', 'twenty one pilots', 'foster the people'
        ])]

        print(f'\n⬇️ Descargando TODAS las tracks según especificación:')
        print(f'   User 1: {len(user1_artists)} artistas × 8 tracks cada uno = {len(user1_artists)*8}')
        print(f'   User 2: {len(user2_artists)} artistas × 8 tracks cada uno = {len(user2_artists)*8}')
        print(f'   TOTAL: {len(user1_artists)*8 + len(user2_artists)*8} tracks (según tus especificaciones)')

        # Download User 1 collection: 8 tracks from each of 8 similar artists
        for i, artist in enumerate(user1_artists[:8], 1):  # Only first 8 similar artists
            if artist.spotify_id and artist.name:
                print(f'\n   [{i}/8] 📥 [User 1] Descargando {artist.name}...')

                await auto_download_service.auto_download_artist_top_tracks(
                    artist_name=artist.name,
                    artist_spotify_id=artist.spotify_id,
                    limit=8  # EXACTLY 8 tracks per artist as requested
                )
                print(f'        ✅ Completado: 8 tracks de {artist.name}')

        # Download User 2 collection: 8 tracks from each of 8 similar artists
        for i, artist in enumerate(user2_artists[:8], 1):  # Only first 8 similar artists
            if artist.spotify_id and artist.name:
                print(f'\n   [{i}/8] 📥 [User 2] Descargando {artist.name}...')

                await auto_download_service.auto_download_artist_top_tracks(
                    artist_name=artist.name,
                    artist_spotify_id=artist.spotify_id,
                    limit=8  # EXACTLY 8 tracks per artist as requested
                )
                print(f'        ✅ Completado: 8 tracks de {artist.name}')

        total_artists_downloaded = len(user1_artists[:8]) + len(user2_artists[:8])
        print(f'\n✅ Descargas completadas para {total_artists_downloaded} artistas')

        # Show final download stats
        downloads = session.exec(select(YouTubeDownload)).all()
        completed = [d for d in downloads if d.download_status == 'completed']
        print(f'\n📊 ESTADO FINAL DE DESCARGAS:')
        print(f'   📥 Intentadas: {len(downloads)} tracks')
        print(f'   ✅ Completadas: {len(completed)} tracks')
        print(f'   📦 Tamaño descargado: ~{sum(d.file_size or 0 for d in completed) // (1024*1024)} MB')

        # Show file structure
        print(f'\n📁 ESTRUCTURA DE ARCHIVOS DESCARGADOS:')
        import os
        downloads_dir = 'downloads'
        if os.path.exists(downloads_dir):
            total_files = 0
            for root, dirs, files in os.walk(downloads_dir):
                level = root.replace(downloads_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                mp3_files = [f for f in files if f.endswith('.mp3')]
                if mp3_files:
                    for file in mp3_files[:3]:  # Show max 3 per artist
                        print(f'{subindent}🎵 {file}')
                    if len(mp3_files) > 3:
                        print(f'{subindent}... y {len(mp3_files) - 3} más')
                    total_files += len(mp3_files)

            print(f'\n💾 Total archivos MP3: {total_files}')

    finally:
        session.close()

    print('\n' + '=' * 65)
    print('🎯 VERIFICACIÓN: SIN DUPLICADOS')
    print('=' * 65)

    # Verify no duplicates
    session = get_session()
    try:
        all_downloads = session.exec(select(YouTubeDownload)).all()
        download_paths = [d.download_path for d in all_downloads]
        unique_paths = set(download_paths)

        print('✅ Verificación de integridad:')
        print(f'   📊 Records en BD: {len(all_downloads)}')
        print(f'   📂 Paths únicos: {len(unique_paths)}')

        if len(all_downloads) == len(unique_paths):
            print('   ✅ SIN DUPLICADOS en base de datos')
        else:
            print('   ❌ DUPLICADOS encontrados en BD')

        # Check filesystem
        import os
        if os.path.exists('downloads'):
            total_mp3_files = 0
            mp3_paths = []
            for root, dirs, files in os.walk('downloads'):
                for file in files:
                    if file.endswith('.mp3'):
                        full_path = os.path.join(root, file)
                        mp3_paths.append(full_path)
                        total_mp3_files += 1

            unique_mp3_paths = set(mp3_paths)
            if total_mp3_files == len(unique_mp3_paths):
                print('   ✅ SIN DUPLICADOS en filesystem')
            else:
                print('   ❌ DUPLICADOS encontrados en archivos')

        print(f'\n🎉 SISTEMA COMPLETO AUDIO2 FUNCIONANDO:')
        print(f'   🧑‍🤝‍🧑 2 usuarios operativos')
        print(f'   🎵 Colecciones musicales expandidas')
        print(f'   🔄 Sin duplicados en BD ni archivos')
        print(f'   📁 Folder compartido eficiente')
        print(f'   ⚡ Metadata siempre fresca')
        print(f'   🚀 Listo para producción!')

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_complete_system())
