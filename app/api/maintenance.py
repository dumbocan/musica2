"""
Maintenance control endpoints.
"""
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
import asyncio
import logging
import os
from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys
import random
from typing import Any, Awaitable, Callable
from sqlalchemy import or_, and_, func, exists
from sqlmodel import select, delete

from ..core.config import settings
from ..core.log_buffer import get_log_entries, clear_log_entries
from ..core.action_status import get_action_statuses, run_with_action_status, set_action_status
from ..core.maintenance import (
    start_maintenance_background,
    maintenance_status,
    register_maintenance_task,
    request_maintenance_stop,
    maintenance_stop_requested,
    _align_chart_date,
    _chart_start_date,
    _store_raw_entries,
    _apply_chart_entries,
)
from ..core.db import get_session
from ..core.spotify import spotify_client
from ..core.time_utils import utc_now
from ..crud import normalize_name, save_track, save_youtube_download
from ..models.base import (
    Artist,
    Album,
    Track,
    PlaylistTrack,
    UserFavorite,
    UserHiddenArtist,
    TrackTag,
    PlayHistory,
    TrackChartEntry,
    TrackChartStats,
    SearchAlias,
    SearchEntityType,
    YouTubeDownload,
    ChartScanState,
    FavoriteTargetType,
)
from ..services.billboard import fetch_chart_entries, normalize_artist_name

router = APIRouter(prefix="/maintenance", tags=["maintenance"])
logger = logging.getLogger(__name__)


def _fetch_album_backfill_targets(mode: str, limit: int) -> list[Album]:
    count_expr = func.count(Track.id)
    targets: list[Album] = []
    with get_session() as session:
        if mode in {"missing", "both"}:
            missing_stmt = (
                select(Album)
                .outerjoin(Track, Track.album_id == Album.id)
                .where(Album.spotify_id.is_not(None))
                .group_by(Album.id)
                .having(count_expr == 0)
                .order_by(Album.id.asc())
                .limit(limit)
            )
            targets.extend(session.exec(missing_stmt).all())

        if mode in {"incomplete", "both"} and len(targets) < limit:
            remaining = max(0, limit - len(targets))
            incomplete_stmt = (
                select(Album)
                .outerjoin(Track, Track.album_id == Album.id)
                .where(Album.spotify_id.is_not(None))
                .group_by(Album.id)
                .having(
                    (count_expr > 0)
                    & (Album.total_tracks > 0)
                    & (count_expr < Album.total_tracks)
                )
                .order_by(Album.id.asc())
                .limit(remaining)
            )
            targets.extend(session.exec(incomplete_stmt).all())
    return targets


def _schedule_action_task(action_key: str, coro: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> asyncio.Task:
    task = asyncio.create_task(run_with_action_status(action_key, coro, *args, **kwargs))
    register_maintenance_task(task)
    return task


async def _backfill_album_tracks(spotify_id: str, album_id: int, artist_id: int) -> int:
    album_name = spotify_id
    artist_name = str(artist_id)
    with get_session() as session:
        album_row = session.exec(select(Album).where(Album.id == album_id)).first()
        artist_row = session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if album_row and album_row.name:
            album_name = album_row.name
        if artist_row and artist_row.name:
            artist_name = artist_row.name
    try:
        tracks = await spotify_client.get_album_tracks(spotify_id)
    except Exception as exc:
        logger.warning("[maintenance] Spotify album tracks backfill failed for %s: %r", spotify_id, exc, exc_info=True)
        return 0
    logger.info("[backfill] album tracks %s — %s (%s)", artist_name, album_name, len(tracks))
    saved = 0
    for track_data in tracks:
        try:
            save_track(track_data, album_id, artist_id)
            saved += 1
        except Exception as exc:
            logger.warning(
                "[maintenance] Track save failed for album %s (%s): %r",
                spotify_id,
                track_data.get("id"),
                exc,
            )
    return saved


async def _run_album_tracks_backfill(mode: str, limit: int, concurrency: int) -> None:
    if maintenance_stop_requested():
        return
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        logger.warning("[maintenance] album backfill skipped: Spotify credentials missing")
        return
    targets = _fetch_album_backfill_targets(mode, limit)
    if not targets:
        logger.info("[maintenance] album backfill: no targets found")
        return
    logger.info("[maintenance] album backfill: %d targets (mode=%s)", len(targets), mode)
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _worker(album: Album) -> None:
        async with sem:
            if maintenance_stop_requested():
                return
            await _backfill_album_tracks(album.spotify_id, album.id, album.artist_id)

    await asyncio.gather(*[asyncio.create_task(_worker(album)) for album in targets])
    logger.info("[maintenance] album backfill complete")


def _fetch_youtube_backfill_targets(limit: int, retry_failed: bool) -> list[tuple[Track, Artist, Album | None]]:
    with get_session() as session:
        linked_ids = set(
            session.exec(
                select(YouTubeDownload.spotify_track_id)
                .where(YouTubeDownload.youtube_video_id.is_not(None))
                .where(YouTubeDownload.youtube_video_id != "")
            ).all()
        )
        failed_ids = set()
        if not retry_failed:
            failed_ids = set(
                session.exec(
                    select(YouTubeDownload.spotify_track_id)
                    .where(YouTubeDownload.youtube_video_id == "")
                    .where(YouTubeDownload.download_status.in_(("video_not_found", "error")))
                ).all()
            )

        targets: list[tuple[Track, Artist, Album | None]] = []

        # Priority 1: Fetch tracks that are favorites first
        fav_stmt = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .join(UserFavorite, UserFavorite.track_id == Track.id)
            .where(UserFavorite.target_type == FavoriteTargetType.TRACK)
            .where(Track.spotify_id.is_not(None))
            .order_by(UserFavorite.created_at.desc(), Track.popularity.desc(), Track.id.asc())
            .limit(limit)
        )
        fav_rows = session.exec(fav_stmt).all()

        for track, artist, album in fav_rows:
            if not track.spotify_id or not artist.spotify_id:
                continue
            if track.spotify_id in linked_ids or track.spotify_id in failed_ids:
                continue
            targets.append((track, artist, album))

        # Priority 2: Fill remaining slots with popular tracks (not favorites)
        if len(targets) < limit:
            already_have = {t[0].spotify_id for t in targets}
            remaining = limit - len(targets)

            pop_stmt = (
                select(Track, Artist, Album)
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
                .where(Track.spotify_id.is_not(None))
                .where(~Track.spotify_id.in_(already_have))
                .order_by(Track.popularity.desc(), Track.id.asc())
                .limit(remaining * 2)
            )
            pop_rows = session.exec(pop_stmt).all()

            for track, artist, album in pop_rows:
                if not track.spotify_id or not artist.spotify_id:
                    continue
                if track.spotify_id in linked_ids or track.spotify_id in failed_ids:
                    continue
                targets.append((track, artist, album))
                if len(targets) >= limit:
                    break

    return targets


async def _run_youtube_backfill(limit: int, retry_failed: bool) -> None:
    if maintenance_stop_requested():
        return
    try:
        from ..core.youtube import youtube_client
    except Exception as exc:
        logger.warning("[maintenance] youtube backfill skipped: %s", exc)
        return

    targets = _fetch_youtube_backfill_targets(limit, retry_failed)
    if not targets:
        logger.info("[maintenance] youtube backfill: no targets found")
        return
    logger.info("[maintenance] youtube backfill: %d tracks (retry_failed=%s)", len(targets), retry_failed)

    for track, artist, album in targets:
        if maintenance_stop_requested():
            return
        try:
            videos = await youtube_client.search_music_videos(
                artist=artist.name,
                track=track.name,
                album=album.name if album else None,
                max_results=1,
            )
        except Exception as exc:
            logger.warning("[maintenance] YouTube search failed for %s - %s: %r", artist.name, track.name, exc)
            continue

        if videos:
            best = videos[0]
            payload = {
                "spotify_track_id": track.spotify_id,
                "spotify_artist_id": artist.spotify_id,
                "youtube_video_id": best.get("video_id", ""),
                "download_path": "",
                "download_status": "link_found",
                "error_message": None,
            }
        else:
            payload = {
                "spotify_track_id": track.spotify_id,
                "spotify_artist_id": artist.spotify_id,
                "youtube_video_id": "",
                "download_path": "",
                "download_status": "video_not_found",
                "error_message": "YouTube video not found or restricted",
            }
        await asyncio.to_thread(save_youtube_download, payload)

    logger.info("[maintenance] youtube backfill complete")


async def _run_chart_backfill(
    chart_source: str,
    chart_name: str,
    weeks: int,
    force_reset: bool,
) -> None:
    if maintenance_stop_requested():
        return
    latest_chart_date = _align_chart_date(date.today())
    cutoff_date = _chart_start_date(chart_name, latest_chart_date)

    with get_session() as session:
        state = session.exec(
            select(ChartScanState).where(
                (ChartScanState.chart_source == chart_source)
                & (ChartScanState.chart_name == chart_name)
            )
        ).first()
        if not state:
            state = ChartScanState(chart_source=chart_source, chart_name=chart_name)
            session.add(state)
            session.commit()
            session.refresh(state)
        if force_reset:
            state.backfill_complete = False
            state.last_scanned_date = None
            session.add(state)
            session.commit()
            session.refresh(state)

        start_date = state.last_scanned_date or latest_chart_date
        next_last_scanned = state.last_scanned_date
        next_backfill_complete = state.backfill_complete

    dates_to_scan: list[date] = []
    if not next_backfill_complete:
        for offset in range(weeks):
            chart_date = start_date - timedelta(days=7 * offset)
            if chart_date < cutoff_date:
                next_backfill_complete = True
                next_last_scanned = latest_chart_date
                break
            dates_to_scan.append(chart_date)
        if dates_to_scan:
            next_last_scanned = dates_to_scan[-1]
    else:
        for offset in range(1, weeks + 1):
            chart_date = start_date + timedelta(days=7 * offset)
            if chart_date > latest_chart_date:
                break
            dates_to_scan.append(chart_date)
        if dates_to_scan:
            next_last_scanned = dates_to_scan[-1]

    if not dates_to_scan:
        logger.info("[maintenance] chart backfill: no dates to scan for %s/%s", chart_source, chart_name)
        return

    with get_session() as session:
        artists = session.exec(select(Artist.id, Artist.name)).all()
    artist_map = {
        normalize_artist_name(name): artist_id
        for artist_id, name in artists
        if name
    }

    total_raw = 0
    total_updates = 0
    for chart_date in dates_to_scan:
        if maintenance_stop_requested():
            return
        try:
            entries = await asyncio.to_thread(fetch_chart_entries, chart_name, chart_date)
        except Exception as exc:
            logger.warning("[maintenance] chart backfill %s/%s %s failed: %s", chart_source, chart_name, chart_date, exc)
            await asyncio.sleep(settings.CHART_REQUEST_MAX_DELAY_SECONDS)
            continue
        if entries:
            with get_session() as session:
                total_raw += _store_raw_entries(
                    session,
                    entries,
                    chart_source,
                    chart_name,
                    chart_date,
                )
            with get_session() as session:
                total_updates += _apply_chart_entries(
                    session,
                    entries,
                    chart_source,
                    chart_name,
                    chart_date,
                    artist_map,
                )
        delay = random.uniform(
            settings.CHART_REQUEST_MIN_DELAY_SECONDS,
            settings.CHART_REQUEST_MAX_DELAY_SECONDS,
        )
        await asyncio.sleep(delay)

    with get_session() as session:
        target = session.exec(
            select(ChartScanState).where(
                (ChartScanState.chart_source == chart_source)
                & (ChartScanState.chart_name == chart_name)
            )
        ).first()
        if target:
            target.backfill_complete = next_backfill_complete
            target.last_scanned_date = next_last_scanned
            target.updated_at = utc_now()
            session.add(target)
            session.commit()

    logger.info(
        "[maintenance] chart backfill %s/%s stored %d raw rows, updated %d tracks",
        chart_source,
        chart_name,
        total_raw,
        total_updates,
    )


def _run_library_audit(fresh_days: int, as_json: bool) -> None:
    set_action_status('audit', True)
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "audit_library_completeness.py"
    args = [sys.executable, str(script_path), "--fresh-days", str(fresh_days)]
    if as_json:
        args.append("--json")
    logger.info("[audit] Running library audit: %s", " ".join(args))
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root)
        result = subprocess.run(
            args,
            check=False,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                logger.info("[audit] %s", line)
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                logger.warning("[audit] %s", line)
    except Exception as exc:
        logger.error("[audit] Audit failed: %s", exc)
    finally:
        set_action_status('audit', False)


@router.get("/status")
def get_maintenance_status(start: bool = Query(False, description="Start maintenance if not running")) -> dict:
    if start and settings.MAINTENANCE_ENABLED:
        start_maintenance_background(
            delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
            stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
        )
    return {
        "enabled": settings.MAINTENANCE_ENABLED,
        "running": maintenance_status(),
    }


@router.get("/dashboard")
def get_dashboard_stats() -> dict:
    with get_session() as session:
        total_artists = session.exec(select(func.count(Artist.id))).one()
        total_albums = session.exec(select(func.count(Album.id))).one()
        total_tracks = session.exec(select(func.count(Track.id))).one()
        artists_missing_images = session.exec(
            select(func.count(Artist.id)).where(Artist.image_path_id.is_(None))
        ).one()
        albums_without_tracks = session.exec(
            select(func.count(Album.id)).where(
                ~exists(select(1).where(Track.album_id == Album.id))
            )
        ).one()
        youtube_link_exists = exists(
            select(1).where(
                (YouTubeDownload.spotify_track_id == Track.spotify_id)
                & YouTubeDownload.youtube_video_id.is_not(None)
            )
        )
        tracks_without_youtube = session.exec(
            select(func.count(Track.id)).where(~youtube_link_exists)
        ).one()
        youtube_links_total = session.exec(
            select(func.count(func.distinct(YouTubeDownload.spotify_track_id)))
            .where(YouTubeDownload.youtube_video_id.is_not(None))
        ).one()
        youtube_downloads_completed = session.exec(
            select(func.count(YouTubeDownload.id)).where(YouTubeDownload.download_status == "completed")
        ).one()
    return {
        "artists_total": int(total_artists or 0),
        "albums_total": int(total_albums or 0),
        "tracks_total": int(total_tracks or 0),
        "artists_missing_images": int(artists_missing_images or 0),
        "albums_without_tracks": int(albums_without_tracks or 0),
        "tracks_without_youtube": int(tracks_without_youtube or 0),
        "youtube_links_total": int(youtube_links_total or 0),
        "youtube_downloads_completed": int(youtube_downloads_completed or 0),
    }


@router.post("/start")
def start_maintenance() -> dict:
    if not settings.MAINTENANCE_ENABLED:
        return {
            "enabled": False,
            "running": False,
            "message": "Maintenance disabled",
        }
    start_maintenance_background(
        delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
        stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
    )
    return {
        "enabled": True,
        "running": maintenance_status(),
    }


@router.post("/stop")
def stop_maintenance() -> dict:
    request_maintenance_stop()
    return {"stopped": True}


@router.post("/audit")
def audit_library(
    background_tasks: BackgroundTasks,
    fresh_days: int = Query(7, ge=1, le=365),
    as_json: bool = Query(False),
) -> dict:
    set_action_status('audit', True)
    background_tasks.add_task(_run_library_audit, fresh_days, as_json)
    return {"scheduled": True, "fresh_days": fresh_days, "json": as_json}


@router.post("/backfill-album-tracks")
async def backfill_album_tracks(
    mode: str = Query("both", pattern="^(missing|incomplete|both)$"),
    limit: int = Query(200, ge=1, le=2000),
    concurrency: int = Query(2, ge=1, le=6),
) -> dict:
    action_key = "albums_missing" if mode in {"missing", "both"} else "albums_incomplete"
    _schedule_action_task(action_key, _run_album_tracks_backfill, mode, limit, concurrency)
    return {"scheduled": True, "mode": mode, "limit": limit, "concurrency": concurrency}


@router.post("/backfill-youtube-links")
async def backfill_youtube_links(
    limit: int = Query(200, ge=1, le=2000),
    retry_failed: bool = Query(False),
) -> dict:
    _schedule_action_task("youtube_links", _run_youtube_backfill, limit, retry_failed)
    return {"scheduled": True, "limit": limit, "retry_failed": retry_failed}


@router.post("/chart-backfill")
async def backfill_chart(
    chart_source: str = Query("billboard"),
    chart_name: str = Query("hot-100"),
    weeks: int = Query(20, ge=1, le=104),
    force_reset: bool = Query(False),
) -> dict:
    _schedule_action_task("chart_backfill", _run_chart_backfill, chart_source, chart_name, weeks, force_reset)
    return {
        "scheduled": True,
        "chart_source": chart_source,
        "chart_name": chart_name,
        "weeks": weeks,
        "force_reset": force_reset,
    }


@router.get("/logs")
def get_logs(
    since_id: int | None = Query(None, ge=0),
    limit: int = Query(200, ge=1, le=2000),
    scope: str = Query("all", pattern="^(all|maintenance|errors)$"),
) -> dict:
    items, last_id = get_log_entries(since_id, limit)
    if scope == "maintenance":
        tokens = ("[maintenance]", "[discography]", "[audit]", "[youtube_prefetch]", "backfill", "refresh-missing")
        prefixes = (
            "app.core.maintenance",
            "app.api.maintenance",
            "app.services.library_expansion",
            "app.core.data_freshness",
            "app.core.youtube_prefetch",
        )
        filtered = []
        for entry in items:
            logger_name = str(entry.get("logger") or "")
            message = str(entry.get("message") or "")
            if logger_name.startswith(prefixes):
                filtered.append(entry)
                continue
            if any(token in message for token in tokens):
                filtered.append(entry)
        items = filtered
    elif scope == "errors":
        items = [entry for entry in items if str(entry.get("level") or "").upper() in {"ERROR", "WARNING"}]
    return {"items": items, "last_id": last_id}


@router.post("/logs/clear")
def clear_logs() -> dict:
    clear_log_entries()
    return {"cleared": True}


@router.get("/action-status")
def get_maintenance_action_status() -> dict:
    return {"actions": get_action_statuses()}


@router.post("/purge-artist")
def purge_artist(
    spotify_id: str | None = Query(None),
    name: str | None = Query(None),
    confirm: bool = Query(False, description="Set true to confirm destructive delete"),
) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    if not spotify_id and not name:
        raise HTTPException(status_code=400, detail="spotify_id or name required")

    name_filter = (name or "").strip()
    normalized = normalize_name(name_filter) if name_filter else ""

    with get_session() as session:
        filters = []
        if spotify_id:
            filters.append(Artist.spotify_id == spotify_id)
        if name_filter:
            filters.append(Artist.name.ilike(f"%{name_filter}%"))
        if normalized:
            filters.append(Artist.normalized_name == normalized)
        if not filters:
            raise HTTPException(status_code=400, detail="No valid filters")

        artists = session.exec(select(Artist).where(or_(*filters))).all()
        if not artists:
            return {"deleted": False, "artists": [], "albums": 0, "tracks": 0}

        artist_ids = [a.id for a in artists if a.id]
        spotify_artist_ids = [a.spotify_id for a in artists if a.spotify_id]

        album_rows = session.exec(
            select(Album.id).where(Album.artist_id.in_(artist_ids))
        ).all() if artist_ids else []
        album_ids = [row if isinstance(row, int) else row[0] for row in album_rows]

        track_rows = session.exec(
            select(Track.id, Track.spotify_id).where(Track.artist_id.in_(artist_ids))
        ).all() if artist_ids else []
        track_ids = []
        track_spotify_ids = []
        for row in track_rows:
            if isinstance(row, tuple):
                track_id, track_spotify_id = row
            else:
                track_id = row
                track_spotify_id = None
            if track_id:
                track_ids.append(track_id)
            if track_spotify_id:
                track_spotify_ids.append(track_spotify_id)

        if track_ids:
            session.exec(delete(PlaylistTrack).where(PlaylistTrack.track_id.in_(track_ids)))
            session.exec(delete(TrackTag).where(TrackTag.track_id.in_(track_ids)))
            session.exec(delete(PlayHistory).where(PlayHistory.track_id.in_(track_ids)))
            session.exec(delete(TrackChartEntry).where(TrackChartEntry.track_id.in_(track_ids)))
            session.exec(delete(TrackChartStats).where(TrackChartStats.track_id.in_(track_ids)))

        if artist_ids or album_ids or track_ids:
            fav_conditions = []
            if artist_ids:
                fav_conditions.append(UserFavorite.artist_id.in_(artist_ids))
            if album_ids:
                fav_conditions.append(UserFavorite.album_id.in_(album_ids))
            if track_ids:
                fav_conditions.append(UserFavorite.track_id.in_(track_ids))
            if fav_conditions:
                session.exec(delete(UserFavorite).where(or_(*fav_conditions)))

        if spotify_artist_ids or track_spotify_ids:
            dl_conditions = []
            if spotify_artist_ids:
                dl_conditions.append(YouTubeDownload.spotify_artist_id.in_(spotify_artist_ids))
            if track_spotify_ids:
                dl_conditions.append(YouTubeDownload.spotify_track_id.in_(track_spotify_ids))
            if dl_conditions:
                session.exec(delete(YouTubeDownload).where(or_(*dl_conditions)))

        alias_conditions = []
        if artist_ids:
            alias_conditions.append(and_(SearchAlias.entity_type == SearchEntityType.ARTIST, SearchAlias.entity_id.in_(artist_ids)))
        if album_ids:
            alias_conditions.append(and_(SearchAlias.entity_type == SearchEntityType.ALBUM, SearchAlias.entity_id.in_(album_ids)))
        if track_ids:
            alias_conditions.append(and_(SearchAlias.entity_type == SearchEntityType.TRACK, SearchAlias.entity_id.in_(track_ids)))
        if alias_conditions:
            session.exec(delete(SearchAlias).where(or_(*alias_conditions)))

        if track_ids:
            session.exec(delete(Track).where(Track.id.in_(track_ids)))
        if album_ids:
            session.exec(delete(Album).where(Album.id.in_(album_ids)))
        if artist_ids:
            session.exec(delete(UserHiddenArtist).where(UserHiddenArtist.artist_id.in_(artist_ids)))
            session.exec(delete(Artist).where(Artist.id.in_(artist_ids)))

        session.commit()

    return {
        "deleted": True,
        "artists": [{"id": a.id, "name": a.name, "spotify_id": a.spotify_id} for a in artists],
        "albums": len(album_ids),
        "tracks": len(track_ids),
    }
