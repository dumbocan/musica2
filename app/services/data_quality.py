"""Helpers to inspect missing metadata so we can schedule enrichment jobs later."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import json

from sqlmodel import select

from app.core.db import get_session
from app.models.base import Artist

REPORT_DIR = Path("cache/data_quality")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = REPORT_DIR / "artists_missing_fields.json"


def collect_artist_quality_report(limit: int | None = None) -> List[Dict[str, str]]:
    """Return all artists missing key fields with the reason."""
    with get_session() as session:
        statement = select(Artist)
        if limit:
            statement = statement.limit(limit)
        artists = session.exec(statement).all()

    report: List[Dict[str, str]] = []
    for artist in artists:
        missing: List[str] = []
        # Check image_path_id (new filesystem-first approach)
        if not artist.image_path_id:
            missing.append("image")
        if not artist.genres or artist.genres.strip() in {"[]", ""}:
            missing.append("genres")
        if not artist.bio_summary:
            missing.append("bio")
        if not missing:
            continue
        report.append(
            {
                "id": artist.id,
                "name": artist.name,
                "spotify_id": artist.spotify_id,
                "missing": ",".join(missing),
            }
        )
    return report


def write_report(limit: int | None = None) -> List[Dict[str, str]]:
    """Collect and persist the report to cache/data_quality for inspection."""
    report = collect_artist_quality_report(limit=limit)
    payload = {
        "summary": {
            "total_missing": len(report),
        },
        "artists": report,
    }
    REPORT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report
