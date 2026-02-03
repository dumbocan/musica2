#!/usr/bin/env python3
"""
Diagnostica inconsistencias de catalogo para un artista en la BD local.

Uso:
  ./venv/bin/python scripts/diagnose_artist_catalog.py --artist "50 cent"
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import func
from sqlmodel import select

# Ensure project root is on sys.path when running as script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import get_session
from app.models.base import Album, Artist, Track


@dataclass
class ArtistRow:
    id: int
    name: str
    spotify_id: str | None


def _print_header(text: str) -> None:
    print(f"\n=== {text} ===")


def _print_rows(rows: Iterable[tuple], limit: int | None = None) -> None:
    count = 0
    for row in rows:
        print(row)
        count += 1
        if limit is not None and count >= limit:
            break


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico de catalogo por artista")
    parser.add_argument("--artist", default="50 cent", help="Texto de busqueda del artista")
    parser.add_argument("--limit-albums", type=int, default=300, help="Maximo de albums a listar")
    parser.add_argument("--limit-tracks", type=int, default=120, help="Maximo de tracks a listar")
    args = parser.parse_args()

    artist_query = args.artist.strip().lower()
    if not artist_query:
        print("ERROR: --artist vacio", file=sys.stderr)
        return 2

    try:
        with get_session() as session:
            artists_raw = session.exec(
                select(Artist.id, Artist.name, Artist.spotify_id)
                .where(func.lower(Artist.name).like(f"%{artist_query}%"))
                .order_by(Artist.id.asc())
            ).all()
            artists = [ArtistRow(id=row[0], name=row[1], spotify_id=row[2]) for row in artists_raw]

            _print_header(f"Artistas que coinciden con '{args.artist}'")
            if not artists:
                print("No se encontro ningun artista.")
                return 0
            for item in artists:
                print((item.id, item.name, item.spotify_id))

            _print_header("Conteo por artista")
            artist_ids = [a.id for a in artists]
            for item in artists:
                album_count = session.exec(
                    select(func.count(Album.id)).where(Album.artist_id == item.id)
                ).one()
                track_count = session.exec(
                    select(func.count(Track.id)).where(Track.artist_id == item.id)
                ).one()
                print(
                    f"artist_id={item.id} name={item.name!r} "
                    f"albums={int(album_count or 0)} tracks={int(track_count or 0)} "
                    f"spotify_id={item.spotify_id}"
                )

            albums = session.exec(
                select(
                    Album.id,
                    Album.name,
                    Album.release_date,
                    Album.total_tracks,
                    Album.spotify_id,
                    Album.artist_id,
                    func.count(Track.id).label("tracks_in_db"),
                )
                .outerjoin(Track, Track.album_id == Album.id)
                .where(Album.artist_id.in_(artist_ids))
                .group_by(Album.id)
                .order_by(Album.id.asc())
                .limit(args.limit_albums)
            ).all()

            _print_header("Albums del/los artista(s) con tracks reales en BD")
            _print_rows(albums)
            print(f"albums_listados={len(albums)}")

            zero_track_albums = [row for row in albums if int(row[6] or 0) == 0]
            _print_header("Albums con 0 tracks (potencial inconsistencia)")
            _print_rows(zero_track_albums)
            print(f"albums_con_0_tracks={len(zero_track_albums)}")

            declared_mismatch = [
                row
                for row in albums
                if (row[3] or 0) > 0 and int(row[6] or 0) < int(row[3] or 0)
            ]
            _print_header("Albums incompletos (tracks_en_bd < total_tracks)")
            _print_rows(declared_mismatch)
            print(f"albums_incompletos={len(declared_mismatch)}")

            tracks = session.exec(
                select(Track.id, Track.name, Track.spotify_id, Track.album_id, Track.artist_id)
                .where(Track.artist_id.in_(artist_ids))
                .order_by(Track.id.asc())
                .limit(args.limit_tracks)
            ).all()
            _print_header("Tracks del/los artista(s)")
            _print_rows(tracks)
            print(f"tracks_listados={len(tracks)}")

            cross_artist_tracks = session.exec(
                select(
                    Track.id,
                    Track.name,
                    Track.artist_id,
                    Album.id,
                    Album.name,
                    Album.artist_id,
                )
                .join(Album, Album.id == Track.album_id)
                .where(Album.artist_id.in_(artist_ids))
                .where(Track.artist_id != Album.artist_id)
                .order_by(Track.id.asc())
            ).all()
            _print_header("Tracks en albums del artista pero con otro artist_id")
            _print_rows(cross_artist_tracks)
            print(f"tracks_cruzados={len(cross_artist_tracks)}")

    except Exception as exc:
        print(f"ERROR conectando/consultando BD: {exc!r}", file=sys.stderr)
        print(
            "Sugerencia: verifica Postgres y credenciales con "
            "`pg_isready -h 127.0.0.1 -p 5432` y `DATABASE_URL`.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
