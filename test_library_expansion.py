#!/usr/bin/env python3
"""
Sanity test for the library expansion flow.

- Busca un artista en Spotify (por defecto "Eminem").
- Guarda el artista + álbumes + tracks en la base de datos usando el orquestador interno.
- Verifica que los campos nuevos (descarga/lyrics/last_refreshed) existan y muestra un resumen.

Requisitos:
- Variables de entorno en .env con SPOTIFY_CLIENT_ID/SECRET (y opcional LASTFM_API_KEY).
- DATABASE_URL apuntando a tu Postgres.
"""

import asyncio
import sys
from typing import Optional

from sqlmodel import select

from app.core.config import settings
from app.core.db import create_db_and_tables, get_session
from app.core.spotify import spotify_client
from app.services.library_expansion import save_artist_discography
from app.models.base import Artist, Album, Track


async def expand_artist(query: str) -> Optional[int]:
    """Search an artist on Spotify and persist full discography."""
    print(f"🔍 Buscando artista en Spotify: '{query}'")
    artists = await spotify_client.search_artists(query, limit=1)
    if not artists:
        print("❌ No se encontró el artista.")
        return None

    artist = artists[0]
    spotify_id = artist["id"]
    print(f"✅ Encontrado: {artist['name']} ({spotify_id}) - followers: {artist.get('followers', {}).get('total', 0):,}")

    print("💾 Guardando discografía completa en la base de datos...")
    local_id = await save_artist_discography(spotify_id)
    if not local_id:
        print("❌ No se pudo guardar el artista.")
        return None
    print(f"✅ Guardado en DB con id local {local_id}")
    return local_id


def summarize_db(local_artist_id: int):
    """Print a compact summary of what was stored."""
    with get_session() as session:
        artist = session.exec(select(Artist).where(Artist.id == local_artist_id)).first()
        albums = session.exec(select(Album).where(Album.artist_id == local_artist_id)).all()
        tracks = session.exec(select(Track).where(Track.artist_id == local_artist_id)).all()

        print("\n📊 RESUMEN EN BASE DE DATOS")
        print("-" * 60)
        print(f"🎤 Artista: {artist.name} | Popularidad: {artist.popularity} | Followers: {artist.followers:,}")
        print(f"   last_refreshed_at: {artist.last_refreshed_at}")
        print(f"💿 Álbumes guardados: {len(albums)}")
        print(f"🎵 Tracks guardados: {len(tracks)}")

        sample = tracks[:5]
        if sample:
            print("\n🧪 Muestra de tracks (campos nuevos incluidos):")
            for t in sample:
                print(
                    f" - {t.name} | pop {t.popularity} | "
                    f"download_status={t.download_status} | "
                    f"lyrics_source={t.lyrics_source} | "
                    f"last_refreshed_at={t.last_refreshed_at}"
                )


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Eminem"

    # Preflight: env vars
    if not (settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET):
        print("❌ Faltan SPOTIFY_CLIENT_ID/SECRET en .env")
        return

    print("🗄️ Creando tablas si no existen...")
    create_db_and_tables()

    artist_id = await expand_artist(query)
    if artist_id:
        summarize_db(artist_id)
        print("\n✅ Test completado.")


if __name__ == "__main__":
    asyncio.run(main())
