#!/usr/bin/env python3
"""
Audit library completeness in the local DB.

Checks:
- artists missing images/genres/bio
- artists with no albums
- albums with zero or incomplete tracks
- youtube link coverage
- chart stats coverage + chart scan state
- freshness by last_refreshed_at
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import func
from sqlmodel import select

from app.core.db import get_session
from app.core.image_proxy import has_valid_images
from app.models.base import (
    Album,
    Artist,
    ChartScanState,
    Track,
    TrackChartStats,
    YouTubeDownload,
)


def _parse_images_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return []


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _collect_stats(fresh_days: int) -> Dict[str, Any]:
    now = _utc_now()
    cutoff = now - timedelta(days=fresh_days)

    with get_session() as session:
        artist_total = session.exec(select(func.count(Artist.id))).one() or 0
        album_total = session.exec(select(func.count(Album.id))).one() or 0
        track_total = session.exec(select(func.count(Track.id))).one() or 0

        # Artists missing metadata
        artists = session.exec(select(Artist)).all()
        missing_images = 0
        missing_genres = 0
        missing_bio = 0
        for artist in artists:
            images = _parse_images_field(artist.images)
            if not has_valid_images(images):
                missing_images += 1
            if not artist.genres or artist.genres.strip() in {"", "[]"}:
                missing_genres += 1
            if not artist.bio_summary:
                missing_bio += 1

        # Albums per artist
        album_counts = dict(
            session.exec(
                select(Album.artist_id, func.count(Album.id))
                .group_by(Album.artist_id)
            ).all()
        )
        artists_no_albums = sum(1 for artist in artists if not album_counts.get(artist.id))

        # Tracks per album
        track_counts = dict(
            session.exec(
                select(Track.album_id, func.count(Track.id))
                .where(Track.album_id.is_not(None))
                .group_by(Track.album_id)
            ).all()
        )
        albums = session.exec(select(Album)).all()
        albums_no_tracks = 0
        albums_incomplete_tracks = 0
        for album in albums:
            count = int(track_counts.get(album.id, 0) or 0)
            if count == 0:
                albums_no_tracks += 1
            elif album.total_tracks and count < int(album.total_tracks):
                albums_incomplete_tracks += 1

        # YouTube coverage
        track_spotify_ids = session.exec(
            select(Track.spotify_id).where(Track.spotify_id.is_not(None))
        ).all()
        track_spotify_ids = [row for row in track_spotify_ids if isinstance(row, str)]

        link_ok_ids = set(
            session.exec(
                select(YouTubeDownload.spotify_track_id)
                .where(YouTubeDownload.youtube_video_id.is_not(None))
                .where(YouTubeDownload.youtube_video_id != "")
                .where(YouTubeDownload.download_status.in_(("link_found", "completed")))
            ).all()
        )
        tracks_with_links = sum(1 for tid in track_spotify_ids if tid in link_ok_ids)
        tracks_missing_links = max(0, len(track_spotify_ids) - tracks_with_links)

        status_counts = dict(
            session.exec(
                select(YouTubeDownload.download_status, func.count(YouTubeDownload.id))
                .group_by(YouTubeDownload.download_status)
            ).all()
        )

        # Chart stats coverage
        chart_track_count = session.exec(
            select(func.count(func.distinct(TrackChartStats.track_id)))
        ).one() or 0

        chart_states = session.exec(select(ChartScanState)).all()
        chart_state_rows = [
            {
                "chart_source": row.chart_source,
                "chart_name": row.chart_name,
                "last_scanned_date": row.last_scanned_date.isoformat() if row.last_scanned_date else None,
                "backfill_complete": row.backfill_complete,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in chart_states
        ]

        # Freshness (last_refreshed_at)
        fresh_artists = session.exec(
            select(func.count(Artist.id)).where(Artist.last_refreshed_at >= cutoff)
        ).one() or 0
        fresh_albums = session.exec(
            select(func.count(Album.id)).where(Album.last_refreshed_at >= cutoff)
        ).one() or 0
        fresh_tracks = session.exec(
            select(func.count(Track.id)).where(Track.last_refreshed_at >= cutoff)
        ).one() or 0

    return {
        "generated_at": now.isoformat(),
        "fresh_cutoff": cutoff.isoformat(),
        "totals": {
            "artists": int(artist_total),
            "albums": int(album_total),
            "tracks": int(track_total),
        },
        "missing_metadata": {
            "artists_missing_images": missing_images,
            "artists_missing_genres": missing_genres,
            "artists_missing_bio": missing_bio,
        },
        "library_gaps": {
            "artists_no_albums": artists_no_albums,
            "albums_no_tracks": albums_no_tracks,
            "albums_incomplete_tracks": albums_incomplete_tracks,
        },
        "youtube": {
            "tracks_with_links": tracks_with_links,
            "tracks_missing_links": tracks_missing_links,
            "download_status_counts": status_counts,
        },
        "charts": {
            "tracks_with_chart_stats": int(chart_track_count),
            "chart_states": chart_state_rows,
        },
        "freshness": {
            "artists_refreshed_recently": int(fresh_artists),
            "albums_refreshed_recently": int(fresh_albums),
            "tracks_refreshed_recently": int(fresh_tracks),
        },
    }


def _print_human(data: Dict[str, Any]) -> None:
    totals = data["totals"]
    print(f"Generated: {data['generated_at']}")
    print(f"Fresh cutoff: {data['fresh_cutoff']}")
    print("")
    print("Totals")
    print(f"- Artists: {totals['artists']}")
    print(f"- Albums:  {totals['albums']}")
    print(f"- Tracks:  {totals['tracks']}")
    print("")
    print("Missing metadata (artists)")
    print(f"- Images: {data['missing_metadata']['artists_missing_images']}")
    print(f"- Genres: {data['missing_metadata']['artists_missing_genres']}")
    print(f"- Bio:    {data['missing_metadata']['artists_missing_bio']}")
    print("")
    print("Library gaps")
    print(f"- Artists with no albums: {data['library_gaps']['artists_no_albums']}")
    print(f"- Albums with no tracks:  {data['library_gaps']['albums_no_tracks']}")
    print(f"- Albums incomplete:      {data['library_gaps']['albums_incomplete_tracks']}")
    print("")
    print("YouTube")
    print(f"- Tracks with links:    {data['youtube']['tracks_with_links']}")
    print(f"- Tracks missing links: {data['youtube']['tracks_missing_links']}")
    if data["youtube"]["download_status_counts"]:
        print("- Status counts:")
        for status, count in sorted(data["youtube"]["download_status_counts"].items()):
            print(f"  - {status}: {count}")
    print("")
    print("Charts")
    print(f"- Tracks with chart stats: {data['charts']['tracks_with_chart_stats']}")
    if data["charts"]["chart_states"]:
        print("- Chart scan states:")
        for row in data["charts"]["chart_states"]:
            print(
                f"  - {row['chart_source']}/{row['chart_name']}: "
                f"last_scanned={row['last_scanned_date']} backfill={row['backfill_complete']}"
            )
    print("")
    print("Freshness (last_refreshed_at)")
    print(f"- Artists refreshed recently: {data['freshness']['artists_refreshed_recently']}")
    print(f"- Albums refreshed recently:  {data['freshness']['albums_refreshed_recently']}")
    print(f"- Tracks refreshed recently:  {data['freshness']['tracks_refreshed_recently']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit library completeness in the DB.")
    parser.add_argument("--fresh-days", type=int, default=7, help="Days window for freshness checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    data = _collect_stats(args.fresh_days)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        _print_human(data)


if __name__ == "__main__":
    main()
