#!/usr/bin/env python3
"""
Script para vincular archivos descargados con la base de datos.

Proceso:
1. Escanear carpeta downloads
2. Para cada archivo: obtener artista (carpeta) y canción (nombre archivo)
3. Si artista no existe → crear registro básico
4. Buscar canción por NOMBRE en BD (fuzzy match, sin importar artist_id)
5. Crear YouTubeDownload con el path del archivo

Usage:
    python scripts/sync_downloads_by_name.py [--dry-run]
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select

from app.core.config import settings
from app.core.db import get_session
from app.models.base import Artist, Track, YouTubeDownload
from app.crud import normalize_name


def clean_name(name: str) -> str:
    """Limpiar nombre para comparación."""
    name = Path(name).stem
    # Quitar sufijo de video ID (11 chars alphanum al final)
    name = re.sub(r'-[a-zA-Z0-9_-]{11}$', '', name)
    # Quitar sufijos comunes
    name = re.sub(r'\s*-\s*(Remix|Extended|Mix|Edit|Slowride|Live|Session|Instrumental|Explicit)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(\d+\)\s*$', '', name)
    # Normalizar
    return normalize_name(name.replace('-', ' ').replace('_', ' ').lower().strip())


def find_artist_by_folder(session, folder_name: str) -> Optional[Artist]:
    """Buscar artista por nombre de carpeta."""
    normalized = normalize_name(folder_name)

    # Buscar por nombre normalizado
    artist = session.exec(
        select(Artist).where(Artist.normalized_name == normalized)
    ).first()
    if artist:
        return artist

    # Buscar sin guiones
    without_hyphens = folder_name.replace('-', ' ').replace('_', ' ')
    normalized2 = normalize_name(without_hyphens)
    artist = session.exec(
        select(Artist).where(Artist.normalized_name == normalized2)
    ).first()
    if artist:
        return artist

    return None


def find_track_by_name(session, track_name: str) -> Optional[Track]:
    """Buscar canción por nombre en toda la BD (sin importar artista)."""
    # Nombre simple sin extensión
    name_simple = Path(track_name).stem.replace('-', ' ').replace('_', ' ')
    # Quitar video ID suffix
    name_simple = re.sub(r'\s+[a-zA-Z0-9_-]{11}$', '', name_simple)
    # Quitar sufijos comunes
    name_simple = re.sub(r'\s*-\s*(Remix|Extended|Mix|Edit|Slowride|Live|Session|Instrumental|Explicit)$', '', name_simple, flags=re.IGNORECASE)
    name_simple = name_simple.strip()

    # Extraer palabras clave principales (primeros 3-4 words)
    words = name_simple.split()[:4]
    keywords = ' '.join(words)

    # Buscar por palabras clave (más flexible)
    tracks = session.exec(
        select(Track).where(
            Track.name.ilike(f'%{keywords}%')
        ).limit(20)
    ).all()

    if not tracks:
        return None

    # Devolver mejor match (priorizar coincidencia más larga)
    best_match = None
    best_score = 0
    for track in tracks:
        # Score por cuántas palabras coinciden
        track_words = set(track.name.lower().split())
        file_words = set(name_simple.lower().split())
        common = track_words & file_words
        score = len(common)
        if score > best_score:
            best_score = score
            best_match = track

    return best_match


def create_artist_if_not_exists(session, folder_name: str) -> Artist:
    """Crear artista si no existe."""
    artist = find_artist_by_folder(session, folder_name)
    if artist:
        return artist

    # Crear nuevo artista
    now = datetime.utcnow()
    artist = Artist(
        name=folder_name.replace('-', ' ').replace('_', ' ').title(),
        normalized_name=normalize_name(folder_name),
        last_refreshed_at=now,
    )
    session.add(artist)
    session.flush()
    print(f"    + Nuevo artista creado: {artist.name}")
    # Recargar para obtener ID
    session.refresh(artist)
    return artist


def process_downloads(download_dir: Path, dry_run: bool = False) -> dict:
    """Escanear downloads y vincular con BD."""
    stats = {
        'scanned': 0,
        'matched': 0,
        'created': 0,
        'skipped': 0,
        'artists_created': 0,
        'errors': 0,
    }
    audio_exts = {'.mp3', '.m4a', '.webm', '.ogg', '.flac', '.wav'}

    # Recolectar archivos
    files_by_artist: dict[str, list[Path]] = {}
    if download_dir.exists():
        for item in sorted(download_dir.rglob('*')):
            if item.is_file() and item.suffix.lower() in audio_exts:
                parts = item.relative_to(download_dir).parts
                if len(parts) >= 2:
                    artist_folder = parts[0]
                    if artist_folder not in files_by_artist:
                        files_by_artist[artist_folder] = []
                    files_by_artist[artist_folder].append(item)

    print(f"\n📁 {len(files_by_artist)} carpetas de artistas, {sum(len(f) for f in files_by_artist.values())} archivos")

    with get_session() as session:
        for folder_key, files in files_by_artist.items():
            if not files:
                continue

            # Crear o encontrar artista
            added_artist = False
            try:
                artist = create_artist_if_not_exists(session, folder_key)
                if artist and not artist.spotify_id:
                    # Check if it's a newly created artist (no spotify_id means it might be new)
                    added_artist = True
            except Exception as e:
                print(f"    ⚠️  Error creando artista {folder_key}: {e}")
                continue

            for file_path in files:
                stats['scanned'] += 1
                if added_artist:
                    stats['artists_created'] += 1
                    added_artist = False  # Only count once
                filename = file_path.name

                # Buscar canción por NOMBRE
                track = find_track_by_name(session, filename)

                if not track:
                    print(f"    ❌ Canción no encontrada: {filename}")
                    stats['skipped'] += 1
                    continue

                # Calcular path relativo
                try:
                    rel_path = str(file_path.relative_to(download_dir))
                except ValueError:
                    rel_path = str(file_path)

                # Verificar si ya existe YouTubeDownload
                if track.spotify_id:
                    existing = session.exec(
                        select(YouTubeDownload).where(
                            YouTubeDownload.spotify_track_id == track.spotify_id
                        )
                    ).first()
                else:
                    existing = None

                if existing:
                    # Ver si necesita actualizar path
                    if existing.download_path != rel_path:
                        if dry_run:
                            print(f"    🔧 Actualizar path: {track.name}")
                        else:
                            existing.download_path = rel_path
                            existing.download_status = 'completed'
                            existing.updated_at = datetime.utcnow()
                            session.add(existing)
                            print(f"    ✅ Path actualizado: {track.name}")
                    else:
                        stats['matched'] += 1
                else:
                    # Crear nuevo YouTubeDownload
                    if dry_run:
                        print(f"    ➕ Crear: {track.name}")
                        stats['created'] += 1
                    else:
                        download = YouTubeDownload(
                            spotify_track_id=track.spotify_id or '',
                            spotify_artist_id=artist.spotify_id if artist and artist.spotify_id else '',
                            youtube_video_id='',  # Sin video_id
                            download_path=rel_path,
                            download_status='completed',
                        )
                        session.add(download)
                        print(f"    ➕ Creado: {track.name}")
                        stats['created'] += 1

        if not dry_run:
            session.commit()

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sincronizar downloads con BD por nombre')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar sin cambios')
    args = parser.parse_args()

    download_dir = Path(settings.DOWNLOAD_ROOT)
    print(f"\n📁 Carpeta downloads: {download_dir.absolute()}")
    print(f"   Existe: {download_dir.exists()}")

    if not download_dir.exists():
        print("❌ La carpeta no existe!")
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "EJECUTANDO"
    print(f"\n{mode} - Vinculando archivos con BD por nombre...")
    print("-" * 60)

    stats = process_downloads(download_dir, dry_run=args.dry_run)

    print("-" * 60)
    print("\n📊 Resumen:")
    print(f"   Escaneados: {stats['scanned']}")
    print(f"   Emparejados: {stats['matched']}")
    print(f"   Creados: {stats['created']}")
    print(f"   Saltados: {stats['skipped']}")
    print(f"   Artistas creados: {stats['artists_created']}")
    print(f"   Errores: {stats['errors']}")

    if args.dry_run:
        print("\n💡 Ejecutar sin --dry-run para aplicar cambios")

    return 0


if __name__ == '__main__':
    main()
