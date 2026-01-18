"""
Track endpoints: list, etc.
"""

import asyncio
from datetime import datetime, date
from typing import List
import re
from pathlib import Path as FsPath
import logging

from fastapi import APIRouter, Path, HTTPException, Query, Request, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, exists, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.db import get_session, SessionDep
from ..models.base import (
    Track,
    Artist,
    Album,
    YouTubeDownload,
    UserFavorite,
    TrackChartStats,
    ChartEntryRaw,
    TrackChartEntry,
    PlayHistory,
)
from ..crud import update_track_lastfm, update_track_spotify_data, record_play
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from ..core.time_utils import utc_now
from ..services.billboard import (
    extract_primary_artist,
    normalize_artist_name,
    normalize_track_title,
)
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracks", tags=["tracks"])


class TrackResolveRequest(BaseModel):
    spotify_track_ids: List[str]


def _select_best_downloads(
    downloads: list[YouTubeDownload],
) -> dict[str, YouTubeDownload]:
    download_map: dict[str, YouTubeDownload] = {}
    for download in downloads:
        if not download.spotify_track_id:
            continue
        existing = download_map.get(download.spotify_track_id)
        if not existing:
            download_map[download.spotify_track_id] = download
            continue
        existing_has_path = bool(existing.download_path)
        new_has_path = bool(download.download_path)
        if new_has_path and not existing_has_path:
            download_map[download.spotify_track_id] = download
            continue
        if existing_has_path and not new_has_path:
            continue
        existing_has_video = bool(existing.youtube_video_id)
        new_has_video = bool(download.youtube_video_id)
        if new_has_video and not existing_has_video:
            download_map[download.spotify_track_id] = download
            continue
        if new_has_video == existing_has_video:
            if download.updated_at and existing.updated_at and download.updated_at > existing.updated_at:
                download_map[download.spotify_track_id] = download
    return download_map


def _compute_chart_stats_from_raw(
    session,
    track: Track,
    artist_name: str | None,
    raw_cache: dict[str, list[ChartEntryRaw]] | None = None,
) -> list[TrackChartStats]:
    if not track.name or not artist_name:
        return []
    artist_norm = normalize_artist_name(artist_name)
    title_norm = normalize_track_title(track.name)
    if not artist_norm or not title_norm:
        return []

    cache_key = artist_norm
    if raw_cache is not None and cache_key in raw_cache:
        raw_rows = raw_cache[cache_key]
    else:
        artist_term = extract_primary_artist(artist_name) or artist_name
        raw_rows = session.exec(
            select(ChartEntryRaw).where(
                (ChartEntryRaw.chart_source == "billboard")
                & (ChartEntryRaw.artist.ilike(f"%{artist_term}%"))
            )
        ).all()
        if raw_cache is not None:
            raw_cache[cache_key] = raw_rows

    existing_entries = session.exec(
        select(
            TrackChartEntry.chart_source,
            TrackChartEntry.chart_name,
            TrackChartEntry.chart_date,
        ).where(TrackChartEntry.track_id == track.id)
    ).all()
    existing_entry_keys = {
        (source, name, chart_date) for source, name, chart_date in existing_entries
    }

    stats_map: dict[str, dict] = {}
    for row in raw_rows:
        if normalize_artist_name(row.artist) != artist_norm:
            continue
        if normalize_track_title(row.title) != title_norm:
            continue
        entry_key = (row.chart_source, row.chart_name, row.chart_date)
        if entry_key not in existing_entry_keys:
            session.add(
                TrackChartEntry(
                    track_id=track.id,
                    chart_source=row.chart_source,
                    chart_name=row.chart_name,
                    chart_date=row.chart_date,
                    rank=row.rank,
                )
            )
            existing_entry_keys.add(entry_key)
        chart_key = row.chart_name
        current = stats_map.get(chart_key)
        if not current:
            current = {
                "chart_source": row.chart_source,
                "chart_name": chart_key,
                "best_position": row.rank,
                "weeks_on_chart": 0,
                "weeks_at_one": 0,
                "weeks_top5": 0,
                "weeks_top10": 0,
                "first_chart_date": row.chart_date,
                "last_chart_date": row.chart_date,
            }
            stats_map[chart_key] = current
        rank = int(row.rank or 0)
        current["weeks_on_chart"] += 1
        current["best_position"] = (
            rank if current["best_position"] is None else min(current["best_position"], rank)
        )
        if rank == 1:
            current["weeks_at_one"] += 1
        if rank <= 5:
            current["weeks_top5"] += 1
        if rank <= 10:
            current["weeks_top10"] += 1
        current["first_chart_date"] = min(current["first_chart_date"], row.chart_date)
        current["last_chart_date"] = max(current["last_chart_date"], row.chart_date)

    if not stats_map:
        return []

    stats_rows: list[TrackChartStats] = []
    for chart_name, computed in stats_map.items():
        stats = session.exec(
            select(TrackChartStats).where(
                (TrackChartStats.track_id == track.id)
                & (TrackChartStats.chart_source == computed["chart_source"])
                & (TrackChartStats.chart_name == chart_name)
            )
        ).first()
        if not stats:
            stats = TrackChartStats(
                track_id=track.id,
                chart_source=computed["chart_source"],
                chart_name=chart_name,
            )
        stats.best_position = computed["best_position"]
        stats.weeks_on_chart = computed["weeks_on_chart"]
        stats.weeks_at_one = computed["weeks_at_one"]
        stats.weeks_top5 = computed["weeks_top5"]
        stats.weeks_top10 = computed["weeks_top10"]
        stats.first_chart_date = computed["first_chart_date"]
        stats.last_chart_date = computed["last_chart_date"]
        stats.updated_at = utc_now()
        session.add(stats)
        stats_rows.append(stats)

    session.commit()
    return stats_rows


def _load_best_position_dates(
    session,
    track_ids: list[int],
) -> dict[tuple[int, str, str], date]:
    if not track_ids:
        return {}
    rows = session.exec(
        select(
            TrackChartEntry.track_id,
            TrackChartEntry.chart_source,
            TrackChartEntry.chart_name,
            func.min(TrackChartEntry.chart_date),
        )
        .join(
            TrackChartStats,
            and_(
                TrackChartStats.track_id == TrackChartEntry.track_id,
                TrackChartStats.chart_source == TrackChartEntry.chart_source,
                TrackChartStats.chart_name == TrackChartEntry.chart_name,
                TrackChartEntry.rank == TrackChartStats.best_position,
            ),
        )
        .where(TrackChartEntry.track_id.in_(track_ids))
        .group_by(
            TrackChartEntry.track_id,
            TrackChartEntry.chart_source,
            TrackChartEntry.chart_name,
        )
    ).all()
    return {
        (track_id, chart_source, chart_name): chart_date
        for track_id, chart_source, chart_name, chart_date in rows
        if chart_date
    }


@router.get("/")
def get_tracks() -> List[Track]:
    """Get all saved tracks from DB."""
    with get_session() as session:
        tracks = session.exec(select(Track)).all()
    return tracks


@router.post("/resolve")
def resolve_tracks(payload: TrackResolveRequest) -> dict:
    """Resolve Spotify track IDs to local track IDs."""
    spotify_ids = [track_id for track_id in payload.spotify_track_ids if track_id]
    if not spotify_ids:
        return {"items": []}
    with get_session() as session:
        rows = session.exec(
            select(Track.id, Track.spotify_id)
            .where(Track.spotify_id.in_(spotify_ids))
        ).all()
    items = [
        {"track_id": track_id, "spotify_track_id": spotify_id}
        for track_id, spotify_id in rows
        if spotify_id
    ]
    return {"items": items}


@router.post("/play/{track_id}")
def record_track_play(
    request: Request,
    track_id: int = Path(..., description="Track ID"),
) -> dict:
    """Record a play for a track (counts in play history)."""
    user_id = getattr(request.state, "user_id", None) or 1
    play_history = record_play(track_id, user_id=user_id)
    if not play_history:
        raise HTTPException(status_code=404, detail="Track not found")
    return {
        "message": "Play recorded",
        "play_history": play_history.dict(),
    }


@router.get("/chart-stats")
def get_track_chart_stats(
    spotify_ids: str | None = Query(None, description="Comma-separated Spotify track IDs"),
    track_ids: str | None = Query(None, description="Comma-separated local track IDs"),
) -> dict:
    """Return Billboard chart stats for the provided tracks."""
    spotify_list = [t for t in (spotify_ids or "").split(",") if t]
    track_id_list = [int(t) for t in (track_ids or "").split(",") if t.isdigit()]
    if not spotify_list and not track_id_list:
        raise HTTPException(status_code=400, detail="Missing spotify_ids or track_ids")

    with get_session() as session:
        id_map: dict[int, str | None] = {}
        if spotify_list:
            rows = session.exec(
                select(Track.id, Track.spotify_id).where(Track.spotify_id.in_(spotify_list))
            ).all()
            for track_id, spotify_id in rows:
                id_map[track_id] = spotify_id
        if track_id_list:
            rows = session.exec(
                select(Track.id, Track.spotify_id).where(Track.id.in_(track_id_list))
            ).all()
            for track_id, spotify_id in rows:
                id_map.setdefault(track_id, spotify_id)

        if not id_map:
            return {"items": []}

        stats_rows = session.exec(
            select(TrackChartStats).where(TrackChartStats.track_id.in_(list(id_map.keys())))
        ).all()

        existing_ids = {row.track_id for row in stats_rows}
        missing_ids = [track_id for track_id in id_map.keys() if track_id not in existing_ids]
        if missing_ids:
            raw_cache: dict[str, list[ChartEntryRaw]] = {}
            track_rows = session.exec(
                select(Track, Artist)
                .join(Artist, Artist.id == Track.artist_id)
                .where(Track.id.in_(missing_ids))
            ).all()
            for track, artist in track_rows:
                stats_rows.extend(
                    _compute_chart_stats_from_raw(session, track, artist.name, raw_cache)
                )

        priority = {
            "billboard-global-200": 0,
            "hot-100": 1,
        }
        chosen: dict[int, TrackChartStats] = {}
        for row in stats_rows:
            current = chosen.get(row.track_id)
            if not current:
                chosen[row.track_id] = row
                continue
            current_rank = priority.get(current.chart_name, 99)
            next_rank = priority.get(row.chart_name, 99)
            if next_rank < current_rank:
                chosen[row.track_id] = row

        best_date_map = _load_best_position_dates(session, list(id_map.keys()))

        items = []
        for track_id, spotify_id in id_map.items():
            stat = chosen.get(track_id)
            if not stat or stat.best_position is None:
                continue
            best_date = best_date_map.get(
                (track_id, stat.chart_source, stat.chart_name)
            )
            items.append(
                {
                    "track_id": track_id,
                    "spotify_track_id": spotify_id,
                    "chart_source": stat.chart_source,
                    "chart_name": stat.chart_name,
                    "chart_best_position": stat.best_position,
                    "chart_best_position_date": best_date.isoformat() if best_date else None,
                    "chart_weeks_at_one": stat.weeks_at_one,
                    "chart_weeks_top5": stat.weeks_top5,
                    "chart_weeks_top10": stat.weeks_top10,
                }
            )
    return {"items": items}


@router.get("/overview")
def get_tracks_overview(
    request: Request,
    verify_files: bool = Query(False, description="Check file existence on disk"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(200, ge=1, le=1000, description="Pagination limit"),
    include_summary: bool = Query(True, description="Include aggregate summary counts"),
    after_id: int | None = Query(None, ge=0, description="Return tracks after this ID"),
    filter: str | None = Query(None, description="Filter: withLink, noLink, hasFile, missingFile"),
    search: str | None = Query(None, description="Search by track, artist, or album"),
) -> dict:
    """
    Return tracks with artist, album, cached YouTube link/status and local file info.
    Useful for the frontend "Tracks" page so users can see what is ready for streaming/downloading.
    """
    def normalize_search(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def normalized_column(column):
        return func.regexp_replace(func.lower(column), "[^a-z0-9]+", " ", "g")

    summary = None
    if filter == "all":
        filter = None
    filter = filter or None
    if filter and filter not in {"withLink", "noLink", "hasFile", "missingFile", "favorites"}:
        raise HTTPException(status_code=400, detail="Invalid filter value")
    search_term = normalize_search(search) if search else ""
    is_filtered_query = bool(filter or search_term)
    if include_summary:
        with get_session() as session:
            total, with_link, with_file = session.exec(
                select(
                    func.count(Track.id),
                    func.count(func.distinct(Track.id)).filter(
                        and_(
                            YouTubeDownload.youtube_video_id.is_not(None),
                            YouTubeDownload.youtube_video_id != ""
                        )
                    ),
                    func.count(func.distinct(Track.id)).filter(
                        and_(
                            YouTubeDownload.download_path.is_not(None),
                            YouTubeDownload.download_path != ""
                        )
                    ),
                )
                .select_from(Track)
                .outerjoin(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            ).one()
        total = int(total or 0)
        with_link = int(with_link or 0)
        with_file = int(with_file or 0)
        summary = {
            "total": total,
            "with_link": with_link,
            "with_file": with_file,
            "missing_link": max(total - with_link, 0),
            "missing_file": max(total - with_file, 0),
        }

    with get_session() as session:
        base_query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .order_by(Track.id.asc())
        )

        if search_term:
            pattern = f"%{search_term}%"
            base_query = base_query.where(
                or_(
                    normalized_column(Track.name).ilike(pattern),
                    normalized_column(Artist.name).ilike(pattern),
                    normalized_column(Album.name).ilike(pattern),
                )
            )

        if filter:
            link_exists = exists(
                select(1).where(
                    (YouTubeDownload.spotify_track_id == Track.spotify_id)
                    & (YouTubeDownload.youtube_video_id.is_not(None))
                    & (YouTubeDownload.youtube_video_id != "")
                )
            )
            file_exists = exists(
                select(1).where(
                    (YouTubeDownload.spotify_track_id == Track.spotify_id)
                    & (YouTubeDownload.download_path.is_not(None))
                    & (YouTubeDownload.download_path != "")
                )
            )
            if filter == "favorites":
                user_id = getattr(request.state, "user_id", None)
                if not user_id:
                    raise HTTPException(status_code=401, detail="User not authenticated")
                favorite_exists = exists(
                    select(1).where(
                        (UserFavorite.user_id == user_id)
                        & (UserFavorite.track_id == Track.id)
                    )
                )
            if filter == "withLink":
                base_query = base_query.where(link_exists)
            elif filter == "noLink":
                base_query = base_query.where(~link_exists)
            elif filter == "hasFile":
                base_query = base_query.where(file_exists)
            elif filter == "missingFile":
                base_query = base_query.where(~file_exists)
            elif filter == "favorites":
                base_query = base_query.where(favorite_exists)

        if after_id is not None:
            base_query = base_query.where(Track.id > after_id)
        else:
            base_query = base_query.offset(offset)
        rows = session.exec(base_query.limit(limit + 1)).all()

        filtered_total = None
        if is_filtered_query:
            count_query = select(func.count(Track.id)).join(Artist, Artist.id == Track.artist_id).outerjoin(Album, Album.id == Track.album_id)
            if search_term:
                pattern = f"%{search_term}%"
                count_query = count_query.where(
                    or_(
                        normalized_column(Track.name).ilike(pattern),
                        normalized_column(Artist.name).ilike(pattern),
                        normalized_column(Album.name).ilike(pattern),
                    )
                )
            if filter:
                link_exists = exists(
                    select(1).where(
                        (YouTubeDownload.spotify_track_id == Track.spotify_id)
                        & (YouTubeDownload.youtube_video_id.is_not(None))
                        & (YouTubeDownload.youtube_video_id != "")
                    )
                )
                file_exists = exists(
                    select(1).where(
                        (YouTubeDownload.spotify_track_id == Track.spotify_id)
                        & (YouTubeDownload.download_path.is_not(None))
                        & (YouTubeDownload.download_path != "")
                    )
                )
                if filter == "favorites":
                    user_id = getattr(request.state, "user_id", None)
                    if not user_id:
                        raise HTTPException(status_code=401, detail="User not authenticated")
                    favorite_exists = exists(
                        select(1).where(
                            (UserFavorite.user_id == user_id)
                            & (UserFavorite.track_id == Track.id)
                        )
                    )
                if filter == "withLink":
                    count_query = count_query.where(link_exists)
                elif filter == "noLink":
                    count_query = count_query.where(~link_exists)
                elif filter == "hasFile":
                    count_query = count_query.where(file_exists)
                elif filter == "missingFile":
                    count_query = count_query.where(~file_exists)
                elif filter == "favorites":
                    count_query = count_query.where(favorite_exists)
            filtered_total = session.exec(count_query).one()

    raw_rows = rows
    has_more = len(raw_rows) > limit
    track_rows = raw_rows[:limit]
    track_ids = [track.id for track, _, _ in track_rows]
    spotify_ids = [track.spotify_id for track, _, _ in track_rows if track.spotify_id]
    downloads = []
    if spotify_ids:
        with get_session() as session:
            downloads = session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()

    download_map = _select_best_downloads(downloads)

    chart_stats_map: dict[int, TrackChartStats] = {}
    best_date_map: dict[tuple[int, str, str], date] = {}
    if track_ids:
        with get_session() as session:
            stats_rows = session.exec(
                select(TrackChartStats).where(TrackChartStats.track_id.in_(track_ids))
            ).all()
            existing_ids = {row.track_id for row in stats_rows}
            raw_cache: dict[str, list[ChartEntryRaw]] = {}
            for track, artist, _ in track_rows:
                if track.id in existing_ids:
                    continue
                stats_rows.extend(
                    _compute_chart_stats_from_raw(session, track, artist.name if artist else None, raw_cache)
                )
        priority = {
            "billboard-global-200": 0,
            "hot-100": 1,
        }
        for row in stats_rows:
            current = chart_stats_map.get(row.track_id)
            if not current:
                chart_stats_map[row.track_id] = row
                continue
            current_rank = priority.get(current.chart_name, 99)
            next_rank = priority.get(row.chart_name, 99)
            if next_rank < current_rank:
                chart_stats_map[row.track_id] = row
        best_date_map = _load_best_position_dates(session, list(chart_stats_map.keys()))

    items = []
    for track, artist, album in track_rows:
        download = download_map.get(track.spotify_id) if track.spotify_id else None
        youtube_video_id = (download.youtube_video_id or None) if download else None
        youtube_status = download.download_status if download else None
        youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
        file_path = download.download_path if download else None
        if file_path:
            file_exists = FsPath(file_path).exists() if verify_files else True
        else:
            file_exists = False
        if file_exists:
            youtube_status = "completed"
        elif youtube_video_id and not youtube_status:
            youtube_status = "link_found"
        chart_stats = chart_stats_map.get(track.id)
        best_date = None
        if chart_stats:
            best_date = best_date_map.get(
                (track.id, chart_stats.chart_source, chart_stats.chart_name)
            )

        items.append({
            "track_id": track.id,
            "track_name": track.name,
            "spotify_track_id": track.spotify_id,
            "artist_name": artist.name if artist else None,
            "artist_spotify_id": artist.spotify_id if artist else None,
            "album_name": album.name if album else None,
            "album_spotify_id": album.spotify_id if album else None,
            "duration_ms": track.duration_ms,
            "popularity": track.popularity,
            "youtube_video_id": youtube_video_id,
            "youtube_status": youtube_status,
            "youtube_url": youtube_url,
            "local_file_path": file_path,
            "local_file_exists": file_exists,
            "chart_source": chart_stats.chart_source if chart_stats else None,
            "chart_name": chart_stats.chart_name if chart_stats else None,
            "chart_best_position": chart_stats.best_position if chart_stats else None,
            "chart_best_position_date": best_date.isoformat() if best_date else None,
            "chart_weeks_at_one": chart_stats.weeks_at_one if chart_stats else 0,
            "chart_weeks_top5": chart_stats.weeks_top5 if chart_stats else 0,
            "chart_weeks_top10": chart_stats.weeks_top10 if chart_stats else 0,
        })

    next_after = track_rows[-1][0].id if track_rows else after_id
    response = {
        "items": items,
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_after": next_after if has_more else None,
    }
    if summary:
        response["summary"] = summary
    if filtered_total is not None:
        response["filtered_total"] = int(filtered_total or 0)
    return response


@router.get("/recently-added")
async def get_recently_added_tracks(
    limit: int = Query(10, ge=1, le=50, description="Number of tracks to return"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
    session: AsyncSession = Depends(SessionDep),
) -> dict:
    """Return the most recently added tracks."""
    statement = (
        select(Track, Artist, Album)
        .join(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .order_by(Track.created_at.desc(), Track.id.desc())
        .limit(limit)
    )
    rows = (await session.exec(statement)).all()
    spotify_ids = [track.spotify_id for track, _, _ in rows if track.spotify_id]
    downloads = []
    if spotify_ids:
        downloads = (await session.exec(
            select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
        )).all()

    download_map = _select_best_downloads(downloads)

    items = []
    for track, artist, album in rows:
        download = download_map.get(track.spotify_id) if track.spotify_id else None
        youtube_video_id = (download.youtube_video_id or None) if download else None
        youtube_status = download.download_status if download else None
        youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
        file_path = download.download_path if download else None
        if file_path:
            file_exists = FsPath(file_path).exists() if verify_files else True
        else:
            file_exists = False
        if file_exists:
            youtube_status = "completed"
        elif youtube_video_id and not youtube_status:
            youtube_status = "link_found"

        items.append({
            "track_id": track.id,
            "track_name": track.name,
            "spotify_track_id": track.spotify_id,
            "artist_name": artist.name if artist else None,
            "artist_spotify_id": artist.spotify_id if artist else None,
            "album_name": album.name if album else None,
            "album_spotify_id": album.spotify_id if album else None,
            "duration_ms": track.duration_ms,
            "popularity": track.popularity,
            "youtube_video_id": youtube_video_id,
            "youtube_status": youtube_status,
            "youtube_url": youtube_url,
            "local_file_path": file_path,
            "local_file_exists": file_exists,
        })

    return {"items": items}


@router.get("/most-played")
def get_most_played_tracks(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of tracks to return"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
) -> dict:
    """Return most played tracks for the current user."""
    user_id = getattr(request.state, "user_id", None) or 1
    with get_session() as session:
        rows = session.exec(
            select(
                PlayHistory.track_id,
                func.count(PlayHistory.id).label("play_count"),
                func.max(PlayHistory.played_at).label("last_played_at"),
            )
            .where(PlayHistory.user_id == user_id)
            .group_by(PlayHistory.track_id)
            .order_by(func.count(PlayHistory.id).desc(), func.max(PlayHistory.played_at).desc())
            .limit(limit)
        ).all()
        if not rows:
            return {"items": []}

        track_ids = [row[0] for row in rows]
        track_rows = session.exec(
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.id.in_(track_ids))
        ).all()

        track_map = {track.id: (track, artist, album) for track, artist, album in track_rows}
        spotify_ids = [
            track.spotify_id
            for track, _, _ in track_rows
            if track.spotify_id
        ]
        downloads = []
        if spotify_ids:
            downloads = session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()
        download_map = _select_best_downloads(downloads)

        items = []
        for track_id, play_count, last_played_at in rows:
            row = track_map.get(track_id)
            if not row:
                continue
            track, artist, album = row
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None
            if file_path:
                file_exists = FsPath(file_path).exists() if verify_files else True
            else:
                file_exists = False
            if file_exists:
                youtube_status = "completed"
            elif youtube_video_id and not youtube_status:
                youtube_status = "link_found"

            items.append({
                "track_id": track.id,
                "track_name": track.name,
                "spotify_track_id": track.spotify_id,
                "artist_name": artist.name if artist else None,
                "artist_spotify_id": artist.spotify_id if artist else None,
                "album_name": album.name if album else None,
                "album_spotify_id": album.spotify_id if album else None,
                "duration_ms": track.duration_ms,
                "popularity": track.popularity,
                "youtube_video_id": youtube_video_id,
                "youtube_status": youtube_status,
                "youtube_url": youtube_url,
                "local_file_path": file_path,
                "local_file_exists": file_exists,
                "play_count": int(play_count or 0),
                "last_played_at": last_played_at.isoformat() if last_played_at else None,
            })

    return {"items": items}


@router.get("/recent-plays")
def get_recent_play_history(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of plays to return"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
) -> dict:
    """Return most recent plays for the current user."""
    user_id = getattr(request.state, "user_id", None) or 1
    with get_session() as session:
        rows = session.exec(
            select(PlayHistory, Track, Artist, Album)
            .join(Track, Track.id == PlayHistory.track_id)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(PlayHistory.user_id == user_id)
            .order_by(PlayHistory.played_at.desc(), PlayHistory.id.desc())
            .limit(limit)
        ).all()

        if not rows:
            return {"items": []}

        spotify_ids = [track.spotify_id for _, track, _, _ in rows if track.spotify_id]
        downloads = []
        if spotify_ids:
            downloads = session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()
        download_map = _select_best_downloads(downloads)

        items = []
        for play, track, artist, album in rows:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None
            if file_path:
                file_exists = FsPath(file_path).exists() if verify_files else True
            else:
                file_exists = False
            if file_exists:
                youtube_status = "completed"
            elif youtube_video_id and not youtube_status:
                youtube_status = "link_found"

            items.append({
                "track_id": track.id,
                "track_name": track.name,
                "spotify_track_id": track.spotify_id,
                "artist_name": artist.name if artist else None,
                "artist_spotify_id": artist.spotify_id if artist else None,
                "album_name": album.name if album else None,
                "album_spotify_id": album.spotify_id if album else None,
                "duration_ms": track.duration_ms,
                "popularity": track.popularity,
                "youtube_video_id": youtube_video_id,
                "youtube_status": youtube_status,
                "youtube_url": youtube_url,
                "local_file_path": file_path,
                "local_file_exists": file_exists,
                "played_at": play.played_at.isoformat() if play.played_at else None,
            })

    return {"items": items}


@router.get("/recommendations")
async def get_track_recommendations(
    seed_tracks: str | None = Query(None, description="Comma-separated Spotify track IDs"),
    seed_artists: str | None = Query(None, description="Comma-separated Spotify artist IDs"),
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations"),
) -> dict:
    """Get Spotify track recommendations based on seed tracks/artists."""
    from ..core.config import settings
    track_ids = [t for t in (seed_tracks or "").split(",") if t]
    artist_ids = [a for a in (seed_artists or "").split(",") if a]
    if not track_ids and not artist_ids:
        raise HTTPException(status_code=400, detail="Missing seed_tracks or seed_artists")
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Spotify credentials not configured")
    track_ids = list(dict.fromkeys(track_ids))[:5]
    artist_ids = list(dict.fromkeys(artist_ids))[:5]
    try:
        return await spotify_client.get_recommendations(
            seed_tracks=track_ids or None,
            seed_artists=artist_ids or None,
            limit=limit,
        )
    except Exception as exc:
        logger.warning("[tracks/recommendations] Spotify failed: %s", exc)

    # Fallback: derive artists and search their top tracks via Spotify search
    try:
        artist_seeds: list[str] = []
        if artist_ids:
            artist_seeds = artist_ids
        else:
            for track_id in track_ids:
                track_data = await spotify_client.get_track(track_id)
                if not track_data:
                    continue
                for artist in track_data.get("artists", []):
                    artist_id = artist.get("id")
                    if artist_id:
                        artist_seeds.append(artist_id)
        artist_seeds = list(dict.fromkeys(artist_seeds))[:5]
        fallback_tracks: list[dict] = []
        for artist_id in artist_seeds:
            artist_data = await spotify_client.get_artist(artist_id)
            if not artist_data:
                continue
            artist_name = artist_data.get("name")
            if not artist_name:
                continue
            results = await spotify_client.search_tracks(f"artist:{artist_name}", limit=4)
            fallback_tracks.extend(results)
        if fallback_tracks:
            seen = set()
            unique_tracks = []
            for track in fallback_tracks:
                track_id = track.get("id")
                if not track_id or track_id in seen:
                    continue
                seen.add(track_id)
                unique_tracks.append(track)
            return {"tracks": unique_tracks[:limit], "artists": []}
    except Exception as fallback_exc:
        logger.warning("[tracks/recommendations] fallback failed: %s", fallback_exc)

    raise HTTPException(status_code=502, detail="Spotify recommendations failed")


@router.get("/id/{track_id}")
def get_track(track_id: int = Path(..., description="Local track ID")) -> Track:
    """Get single track by local ID."""
    with get_session() as session:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
    return track


@router.post("/enrich/{track_id}")
async def enrich_track_with_lastfm(
    track_id: int = Path(..., description="Local track ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """Enrich track with Last.fm playcount/listeners."""
    # Get track with artist
    track = (await session.exec(
        select(Track).join(Artist).where(Track.id == track_id)
    )).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    artist_name = track.artist.name
    track_name = track.name

    # Fetch from Last.fm
    lastfm_data = await lastfm_client.get_track_info(artist_name, track_name)
    listeners = lastfm_data['listeners']
    playcount = lastfm_data['playcount']

    # Update DB
    updated_track = await asyncio.to_thread(update_track_lastfm, track_id, listeners, playcount)
    return {"message": f"Track enriched: playcount={playcount}, listeners={listeners}", "track": updated_track}


@router.post("/bulk-enrich-lastfm")
async def bulk_enrich_tracks_lastfm(
    limit: int = 50,
    session: AsyncSession = Depends(SessionDep),
):
    """Bulk enrich tracks without Last.fm data."""
    # Get tracks that don't have Last.fm data yet
    tracks_to_enrich = (await session.exec(
        select(Track).join(Artist).where(
            (Track.lastfm_listeners.is_(None)) |
            (Track.lastfm_listeners == 0)
        ).limit(limit)
    )).all()

    if not tracks_to_enrich:
        return {"message": "No tracks need enrichment", "processed": 0}

    enriched_count = 0

    for i, track in enumerate(tracks_to_enrich):
        try:
            track_with_artist = (await session.exec(
                select(Track).join(Artist).where(Track.id == track.id)
            )).first()

            if not track_with_artist:
                continue

            artist_name = track_with_artist.artist.name
            track_name = track_with_artist.name

            # Fetch from Last.fm
            lastfm_data = await lastfm_client.get_track_info(artist_name, track_name)
            listeners = lastfm_data['listeners']
            playcount = lastfm_data['playcount']

            # Update DB
            await asyncio.to_thread(update_track_lastfm, track.id, listeners, playcount)
            enriched_count += 1

            # Log progress every 10 tracks
            if (i + 1) % 10 == 0:
                logger.info("Enriched %s/%s tracks", i + 1, len(tracks_to_enrich))

        except Exception as e:
            logger.warning("Error enriching track %s: %s", track.name, e)
            continue

    return {
        "message": "Bulk enrichment completed",
        "processed": enriched_count,
        "total_found": len(tracks_to_enrich)
    }


@router.post("/enrich-spotify/{track_id}")
async def enrich_track_with_spotify(
    track_id: int = Path(..., description="Local track ID"),
    session: AsyncSession = Depends(SessionDep),
):
    """Enrich track with Spotify popularity and preview_url."""
    track = (await session.exec(select(Track).where(Track.id == track_id))).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not track.spotify_id:
        raise HTTPException(status_code=400, detail="Track has no Spotify ID")

    # Get fresh Spotify data
    spotify_data = await spotify_client.get_track(track.spotify_id)
    if not spotify_data:
        raise HTTPException(status_code=404, detail="Track not found on Spotify")

    # Update track with Spotify data
    await asyncio.to_thread(update_track_spotify_data, track_id, spotify_data)

    return {
        "message": "Track enriched with Spotify data",
        "track_id": track_id,
        "spotify_popularity": spotify_data.get('popularity'),
        "has_preview": bool(spotify_data.get('preview_url'))
    }


@router.post("/bulk-enrich-spotify")
async def bulk_enrich_tracks_spotify(
    limit: int = 20,
    session: AsyncSession = Depends(SessionDep),
):
    """Bulk enrich tracks with missing Spotify data (popularity, preview_url)."""
    tracks_to_enrich = (await session.exec(
        select(Track).where(
            Track.spotify_id.is_not(None),
            Track.spotify_id != '',
            (
                (Track.popularity.is_(None)) |
                (Track.popularity == 0) |
                (Track.preview_url.is_(None)) |
                (Track.preview_url == '')
            )
        ).limit(limit)
    )).all()

    if not tracks_to_enrich:
        return {"message": "No tracks need Spotify enrichment", "processed": 0}

    enriched_count = 0

    for i, track in enumerate(tracks_to_enrich):
        try:
            # Get fresh Spotify data
            spotify_data = await spotify_client.get_track(track.spotify_id)
            if spotify_data:
                # Update track with Spotify data
                await asyncio.to_thread(update_track_spotify_data, track.id, spotify_data)
                enriched_count += 1

                # Log progress every 5 tracks
                if (i + 1) % 5 == 0:
                    logger.info(
                        "Enriched %s/%s tracks with Spotify data",
                        i + 1,
                        len(tracks_to_enrich),
                    )

        except Exception as e:
            logger.warning("Error enriching track %s: %s", track.name, e)
            continue

    return {
        "message": "Bulk Spotify enrichment completed",
        "processed": enriched_count,
        "total_found": len(tracks_to_enrich)
    }
