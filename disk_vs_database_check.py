#!/usr/bin/env python3
"""
Comparación completa: archivos en disco vs registros en base de datos
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, '.')

from app.core.db import get_session
from app.models.base import YouTubeDownload
from sqlmodel import select

def compare_disk_vs_database():
    print('🔍 COMPARACIÓN: ARCHIVOS EN DISCO vs BASE DE DATOS')
    print('=' * 75)

    # 1. Obtener todos los registros de BD
    session = get_session()
    try:
        downloads_db = session.exec(select(YouTubeDownload)).all()
        completed_downloads = [d for d in downloads_db if d.download_status == 'completed']

        print('📊 BD - REGISTROS DE DESCARGAS:')
        db_files = {}
        for download in completed_downloads:
            filepath = download.download_path
            db_files[filepath] = download

        print(f'   • Total registros completados: {len(completed_downloads)}')
        for i, download in enumerate(completed_downloads[:5], 1):
            print(f'     {i}. {download.download_path} ({download.download_status})')
        if len(completed_downloads) > 5:
            print(f'     ... y {len(completed_downloads) - 5} más')
        print()

        # 2. Obtener todos los archivos en disco
        downloads_dir = Path('downloads')
        disk_files = set()
        file_details = {}

        if downloads_dir.exists():
            for mp3_file in downloads_dir.rglob('*.mp3'):
                relative_path = str(mp3_file.relative_to('.'))
                disk_files.add(relative_path)
                file_size = mp3_file.stat().st_size
                file_details[relative_path] = file_size

        print('💾 DISCO - ARCHIVOS .MP3 ENCONTRADOS:')
        print(f'   • Total archivos MP3 en disco: {len(disk_files)}')
        sorted_disk_files = sorted(disk_files)
        for i, filepath in enumerate(sorted_disk_files[:10], 1):
            size_mb = file_details[filepath] / (1024 * 1024)
            print(f'     {i}. {filepath} ({size_mb:.1f} MB)')
        if len(disk_files) > 10:
            print(f'     ... y {len(disk_files) - 10} más')
        print()

        # 3. COMPARACIÓN: DB vs DISCO
        print('🎯 ANÁLISIS DE SINCRO:')
        db_completed_paths = set(download.download_path for download in completed_downloads)

        # Archivos en DB pero no en disco
        only_in_db = db_completed_paths - disk_files

        # Archivos en disco pero no en DB
        only_in_disk = disk_files - db_completed_paths

        # Archivos en ambos
        in_both = db_completed_paths & disk_files

        print(f'   ✅ Archivos en BD y disco (sincronizados): {len(in_both)}')
        print(f'   ⚠️  Archivos solo en BD: {len(only_in_db)}')
        print(f'   ⚠️  Archivos solo en disco: {len(only_in_disk)}')

        if only_in_db:
            print('   DETALLE - Solo en BD:')
            for path in only_in_db:
                print(f'     • {path}')

        if only_in_disk:
            print('   DETALLE - Solo en disco:')
            for path in sorted(only_in_disk)[:10]:  # Mostrar máximo 10
                size_mb = file_details[path] / (1024 * 1024)
                print(f'     • {path} ({size_mb:.1f} MB)')
            if len(only_in_disk) > 10:
                print(f'     ... y {len(only_in_disk) - 10} más archivos solo en disco')

        print()
        print('📈 ESTADÍSTICAS GENERALES:')
        total_size_db = sum(download.file_size or 0 for download in completed_downloads)
        total_size_disk = sum(file_details.get(path, 0) for path in disk_files)

        print(f'   • Tamaño total BD: {total_size_db / (1024*1024):.1f} MB')
        print(f'   • Tamaño total disco: {total_size_disk / (1024*1024):.1f} MB')

        # Verificación final
        if len(only_in_db) == 0 and len(only_in_disk) == 0:
            print('   ✅ PERFECTAMENTE SINCRONIZADO - No discrepancias')
        else:
            print(f'   ⚠️  HAY DISCREPANCIAS: {len(only_in_db)} solo en BD, {len(only_in_disk)} solo en disco')

        # 4. ANÁLISIS POR ARTISTA
        print('\n🎤 ANÁLISIS POR ARTISTA:')
        artist_summary = {}

        # Agrupar por artista desde BD
        for download in completed_downloads:
            if '/' in download.download_path:
                artist_folder = download.download_path.split('/')[1].replace('-', ' ')
                if artist_folder not in artist_summary:
                    artist_summary[artist_folder] = {'db_count': 0, 'disk_count': 0}
                artist_summary[artist_folder]['db_count'] += 1

        # Contar archivos en disco por artista
        for filepath in disk_files:
            if '/' in filepath:
                artist_folder = filepath.split('/')[1].replace('-', ' ')
                if artist_folder in artist_summary:
                    artist_summary[artist_folder]['disk_count'] += 1

        print('   Artista                  | DB | Disco | Estado')
        print('   --------------------------|----|-------|--------')
        for artist, counts in sorted(artist_summary.items()):
            status = '✅ OK' if counts['db_count'] == counts['disk_count'] else '⚠️  DIF'
            print(f"   {artist[:23]:<23} | {counts['db_count']:>2} | {counts['disk_count']:>5} | {status}")

        print()
        print('=' * 75)
        print('🎉 ANÁLISIS COMPLETADO')

    finally:
        session.close()

if __name__ == "__main__":
    compare_disk_vs_database()
