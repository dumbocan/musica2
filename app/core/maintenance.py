"""
Background maintenance tasks (daily refresh).
"""
import asyncio
import logging
import json
import random
from datetime import date, timedelta

from sqlmodel import select

from .config import settings
from .db import get_session, create_db_and_tables
from ..models.base import UserFavorite
from ..services.library_expansion import save_artist_discography
from ..services.data_quality import collect_artist_quality_report
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from ..core.data_freshness import data_freshness_manager
from ..core.image_proxy import proxy_image_list
from ..core.genre_backfill import (
    derive_genres_from_artist_tags,
    derive_genres_from_tracks,
    extract_genres_from_lastfm_tags,
)
from ..core.time_utils import utc_now
from ..models.base import (
    Artist,
    Track,
    ChartScanState,
    ChartEntryRaw,
    TrackChartEntry,
    TrackChartStats,
)
from ..services.billboard import (
    fetch_chart_entries,
    normalize_artist_name,
    normalize_track_title,
)
from ..crud import save_artist

logger = logging.getLogger(__name__)

_BILLBOARD_CHARTS = (
    ("billboard", "hot-100"),
    ("billboard", "billboard-global-200"),
)
_GLOBAL_200_START_DATE = date(2020, 9, 19)


def _align_chart_date(input_date: date) -> date:
    """Billboard charts use Saturday dates."""
    target_weekday = 5  # Saturday
    days_back = (input_date.weekday() - target_weekday) % 7
    return input_date - timedelta(days=days_back)


def _match_track_id(session, artist_id: int, title_norm: str, track_cache: dict) -> int | None:
    if artist_id not in track_cache:
        tracks = session.exec(
            select(Track.id, Track.name).where(Track.artist_id == artist_id)
        ).all()
        track_cache[artist_id] = {
            normalize_track_title(track_name): track_id
            for track_id, track_name in tracks
            if track_name
        }
    track_map = track_cache[artist_id]
    if title_norm in track_map:
        return track_map[title_norm]
    for name_norm, track_id in track_map.items():
        if name_norm and (name_norm in title_norm or title_norm in name_norm):
            return track_id
    return None


def _chart_start_date(chart_name: str, latest_chart_date: date) -> date:
    if chart_name == "billboard-global-200":
        return _GLOBAL_200_START_DATE
    if settings.CHART_BACKFILL_START_DATE:
        try:
            return date.fromisoformat(settings.CHART_BACKFILL_START_DATE)
        except ValueError:
            return latest_chart_date - timedelta(days=settings.CHART_BACKFILL_YEARS * 365)
    return latest_chart_date - timedelta(days=settings.CHART_BACKFILL_YEARS * 365)


def _store_raw_entries(
    session,
    entries: list[dict],
    chart_source: str,
    chart_name: str,
    chart_date: date,
) -> int:
    saved = 0
    for entry in entries:
        rank_value = int(entry.get("rank", 0) or 0)
        if settings.CHART_MAX_RANK and rank_value > settings.CHART_MAX_RANK:
            continue
        title = (entry.get("title") or "").strip()
        artist = (entry.get("artist") or "").strip()
        if not title or not artist:
            continue
        exists = session.exec(
            select(ChartEntryRaw.id).where(
                (ChartEntryRaw.chart_source == chart_source)
                & (ChartEntryRaw.chart_name == chart_name)
                & (ChartEntryRaw.chart_date == chart_date)
                & (ChartEntryRaw.rank == rank_value)
            )
        ).first()
        if exists:
            continue
        session.add(
            ChartEntryRaw(
                chart_source=chart_source,
                chart_name=chart_name,
                chart_date=chart_date,
                rank=rank_value,
                title=title,
                artist=artist,
            )
        )
        saved += 1
    if saved:
        session.commit()
    return saved


def _apply_chart_entries(
    session,
    entries: list[dict],
    chart_source: str,
    chart_name: str,
    chart_date: date,
    artist_map: dict,
) -> int:
    track_cache: dict[int, dict[str, int]] = {}
    updated = 0
    for entry in entries:
        artist_norm = normalize_artist_name(entry.get("artist", ""))
        if not artist_norm:
            continue
        artist_id = artist_map.get(artist_norm)
        if not artist_id:
            continue
        title_norm = normalize_track_title(entry.get("title", ""))
        if not title_norm:
            continue
        track_id = _match_track_id(session, artist_id, title_norm, track_cache)
        if not track_id:
            continue

        rank_value = int(entry.get("rank", 0) or 0)
        if settings.CHART_MAX_RANK and rank_value > settings.CHART_MAX_RANK:
            continue

        exists = session.exec(
            select(TrackChartEntry.id).where(
                (TrackChartEntry.track_id == track_id)
                & (TrackChartEntry.chart_source == chart_source)
                & (TrackChartEntry.chart_name == chart_name)
                & (TrackChartEntry.chart_date == chart_date)
            )
        ).first()
        if exists:
            continue

        entry_row = TrackChartEntry(
            track_id=track_id,
            chart_source=chart_source,
            chart_name=chart_name,
            chart_date=chart_date,
            rank=rank_value,
        )
        session.add(entry_row)

        stats = session.exec(
            select(TrackChartStats).where(
                (TrackChartStats.track_id == track_id)
                & (TrackChartStats.chart_source == chart_source)
                & (TrackChartStats.chart_name == chart_name)
            )
        ).first()
        if not stats:
            stats = TrackChartStats(
                track_id=track_id,
                chart_source=chart_source,
                chart_name=chart_name,
            )
        rank = entry_row.rank
        if rank > 0:
            stats.best_position = (
                rank if stats.best_position is None else min(stats.best_position, rank)
            )
            stats.weeks_on_chart += 1
            if rank == 1:
                stats.weeks_at_one += 1
            if rank <= 5:
                stats.weeks_top5 += 1
            if rank <= 10:
                stats.weeks_top10 += 1
        stats.first_chart_date = (
            chart_date
            if not stats.first_chart_date
            else min(stats.first_chart_date, chart_date)
        )
        stats.last_chart_date = (
            chart_date
            if not stats.last_chart_date
            else max(stats.last_chart_date, chart_date)
        )
        stats.updated_at = utc_now()
        session.add(stats)
        updated += 1
    if updated:
        session.commit()
    return updated


async def daily_refresh_loop():
    """Daily job: refresh discography for favorited artists."""
    while True:
        try:
            with get_session() as session:
                favs = session.exec(
                    select(UserFavorite).where(UserFavorite.artist_id.is_not(None))
                ).all()
                artist_ids = {f.artist_id for f in favs if f.artist_id}
            logger.info("[maintenance] refreshing %d favorited artists", len(artist_ids))
            tasks = [asyncio.create_task(save_artist_discography(str(aid))) for aid in artist_ids if aid]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            # After refreshing favorites, enrich artists missing metadata
            missing_report = collect_artist_quality_report()
            for entry in missing_report:
                spotify_id = entry["spotify_id"]
                if spotify_id:
                    try:
                        data = await spotify_client.get_artist(spotify_id)
                        if data:
                            save_artist(data)
                    except Exception as exc:
                        logger.warning(
                            "[maintenance] Spotify refresh failed for %s: %r",
                            entry.get("name") or spotify_id,
                            exc,
                            exc_info=True
                        )
                missing_fields = set((entry.get("missing") or "").split(","))
                if ({"bio", "genres", "image"} & missing_fields) and entry.get("name"):
                    try:
                        lastfm = await lastfm_client.get_artist_info(entry["name"])
                        summary = lastfm.get("summary")
                        tags = lastfm.get("tags")
                        images = lastfm.get("images")
                        with get_session() as session:
                            artist = session.exec(select(Artist).where(Artist.id == entry["id"])).first()
                            if artist:
                                needs_commit = False
                                if "bio" in missing_fields and summary:
                                    artist.bio_summary = summary
                                    artist.bio_content = lastfm.get("content", artist.bio_content)
                                    needs_commit = True
                                if "genres" in missing_fields and tags:
                                    genres = extract_genres_from_lastfm_tags(tags, artist_name=entry["name"])
                                    if genres:
                                        artist.genres = json.dumps(genres)
                                        needs_commit = True
                                if "image" in missing_fields and images:
                                    proxied = proxy_image_list(images, size=384)
                                    if proxied:
                                        artist.images = json.dumps(proxied)
                                        needs_commit = True
                                if needs_commit:
                                    now = utc_now()
                                    artist.updated_at = now
                                    artist.last_refreshed_at = now
                                    session.add(artist)
                                    session.commit()
                                    if "genres" in missing_fields and artist.genres:
                                        logger.info(
                                            "[maintenance] genres updated from Last.fm for %s",
                                            entry.get("name")
                                        )
                    except Exception as exc:
                        logger.warning(
                            "[maintenance] Last.fm enrichment failed for %s: %r",
                            entry.get("name"),
                            exc,
                            exc_info=True
                        )
        except Exception as exc:
            logger.error("[maintenance] daily refresh failed: %r", exc, exc_info=True)
        await asyncio.sleep(24 * 60 * 60)


async def genre_backfill_loop():
    """Periodic job: fill missing artist genres using Last.fm track tags."""
    while True:
        if not settings.LASTFM_API_KEY:
            logger.info("[maintenance] genre backfill skipped: LASTFM_API_KEY missing")
            await asyncio.sleep(24 * 60 * 60)
            continue
        try:
            with get_session() as session:
                artists = session.exec(
                    select(Artist)
                    .where(
                        (Artist.genres.is_(None)) |
                        (Artist.genres == "") |
                        (Artist.genres == "[]")
                    )
                    .order_by(Artist.popularity.desc(), Artist.id.asc())
                    .limit(100)
                ).all()
                track_samples = {}
                for artist in artists:
                    track_rows = session.exec(
                        select(Track.name)
                        .where(Track.artist_id == artist.id)
                        .order_by(Track.popularity.desc(), Track.id.asc())
                        .limit(3)
                    ).all()
                    track_samples[artist.id] = [row[0] for row in track_rows if row and row[0]]
        except Exception as exc:
            logger.warning(
                "[maintenance] genre backfill load failed: %r",
                exc,
                exc_info=True
            )
            await asyncio.sleep(2 * 60 * 60)
            continue

        if not artists:
            await asyncio.sleep(2 * 60 * 60)
            continue

        updated = 0
        for artist in artists:
            track_names = track_samples.get(artist.id) or []
            try:
                genres = await derive_genres_from_tracks(artist.name, track_names) if track_names else []
                if not genres:
                    genres = await derive_genres_from_artist_tags(artist.name)
            except Exception as exc:
                logger.warning(
                    "[maintenance] genre backfill failed for %s: %r",
                    artist.name,
                    exc,
                    exc_info=True
                )
                continue
            if not genres:
                continue
            with get_session() as session:
                target = session.exec(select(Artist).where(Artist.id == artist.id)).first()
                if not target:
                    continue
                now = utc_now()
                target.genres = json.dumps(genres)
                target.updated_at = now
                target.last_refreshed_at = now
                session.add(target)
                session.commit()
                updated += 1
        logger.info("[maintenance] genre backfill updated %d artists", updated)
        await asyncio.sleep(2 * 60 * 60)


async def full_library_refresh_loop():
    """Periodic job: refresh artist metadata and detect new albums/tracks."""
    while True:
        try:
            with get_session() as session:
                artists = session.exec(
                    select(Artist)
                    .order_by(Artist.updated_at.asc().nullsfirst(), Artist.popularity.desc())
                    .limit(30)
                ).all()
            refreshed = 0
            new_albums = 0
            new_tracks = 0
            for artist in artists:
                if not artist.spotify_id:
                    continue
                if await data_freshness_manager.should_refresh_artist(artist):
                    if await data_freshness_manager.refresh_artist_data(artist.spotify_id):
                        refreshed += 1
                content = await data_freshness_manager.check_for_new_artist_content(artist.spotify_id)
                new_albums += int(content.get("new_albums", 0) or 0)
                new_tracks += int(content.get("new_tracks", 0) or 0)
            logger.info(
                "[maintenance] library refresh: %d artists, %d new albums, %d new tracks",
                refreshed,
                new_albums,
                new_tracks,
            )
        except Exception as exc:
            logger.error("[maintenance] library refresh failed: %s", exc)
        await asyncio.sleep(6 * 60 * 60)


async def chart_scrape_loop():
    """Periodic job: scrape Billboard charts for tracks in the library."""
    create_db_and_tables()
    while True:
        try:
            latest_chart_date = _align_chart_date(date.today())

            with get_session() as session:
                artists = session.exec(select(Artist.id, Artist.name)).all()
                artist_map = {
                    normalize_artist_name(name): artist_id
                    for artist_id, name in artists
                    if name
                }

            for chart_source, chart_name in _BILLBOARD_CHARTS:
                cutoff_date = _chart_start_date(chart_name, latest_chart_date)
                with get_session() as session:
                    state = session.exec(
                        select(ChartScanState).where(
                            (ChartScanState.chart_source == chart_source)
                            & (ChartScanState.chart_name == chart_name)
                        )
                    ).first()
                    if not state:
                        state = ChartScanState(
                            chart_source=chart_source,
                            chart_name=chart_name,
                        )
                        session.add(state)
                        session.commit()
                        session.refresh(state)

                    dates_to_scan = []
                    next_last_scanned = state.last_scanned_date
                    next_backfill_complete = state.backfill_complete

                    if not state.backfill_complete:
                        start_date = state.last_scanned_date or latest_chart_date
                        for offset in range(settings.CHART_MAX_WEEKS_PER_RUN):
                            chart_date = start_date - timedelta(days=7 * offset)
                            if chart_date < cutoff_date:
                                next_backfill_complete = True
                                next_last_scanned = latest_chart_date
                                break
                            dates_to_scan.append(chart_date)
                        if dates_to_scan:
                            next_last_scanned = dates_to_scan[-1]
                    else:
                        start_date = state.last_scanned_date or latest_chart_date
                        for offset in range(1, settings.CHART_MAX_WEEKS_PER_RUN + 1):
                            chart_date = start_date + timedelta(days=7 * offset)
                            if chart_date > latest_chart_date:
                                break
                            dates_to_scan.append(chart_date)
                        if dates_to_scan:
                            next_last_scanned = dates_to_scan[-1]

                if not dates_to_scan:
                    if next_backfill_complete != state.backfill_complete or (
                        next_last_scanned != state.last_scanned_date
                    ):
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
                    continue

                total_updates = 0
                total_raw = 0
                for chart_date in dates_to_scan:
                    try:
                        entries = await asyncio.to_thread(
                            fetch_chart_entries, chart_name, chart_date
                        )
                    except Exception as exc:
                        logger.warning(
                            "[maintenance] chart scrape %s/%s %s failed: %s",
                            chart_source,
                            chart_name,
                            chart_date,
                            exc,
                        )
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
                    "[maintenance] chart scrape %s/%s stored %d raw rows, updated %d tracks",
                    chart_source,
                    chart_name,
                    total_raw,
                    total_updates,
                )
        except Exception as exc:
            logger.error("[maintenance] chart scrape failed: %s", exc)
        await asyncio.sleep(settings.CHART_REFRESH_INTERVAL_HOURS * 60 * 60)


async def chart_match_loop():
    """Periodic job: apply stored chart rows to current track library."""
    create_db_and_tables()
    while True:
        try:
            with get_session() as session:
                artists = session.exec(select(Artist.id, Artist.name)).all()
                artist_map = {
                    normalize_artist_name(name): artist_id
                    for artist_id, name in artists
                    if name
                }

            total_updates = 0
            total_dates = 0
            for chart_source, chart_name in _BILLBOARD_CHARTS:
                with get_session() as session:
                    raw_rows = session.exec(
                        select(
                            ChartEntryRaw.chart_date,
                            ChartEntryRaw.rank,
                            ChartEntryRaw.title,
                            ChartEntryRaw.artist,
                        )
                        .where(
                            (ChartEntryRaw.chart_source == chart_source)
                            & (ChartEntryRaw.chart_name == chart_name)
                        )
                        .order_by(ChartEntryRaw.chart_date.asc(), ChartEntryRaw.rank.asc())
                    ).all()

                entries_by_date: dict[date, list[dict]] = {}
                for chart_date, rank, title, artist in raw_rows:
                    entries_by_date.setdefault(chart_date, []).append(
                        {"rank": rank, "title": title, "artist": artist}
                    )

                if not entries_by_date:
                    continue

                with get_session() as session:
                    for chart_date, entries in entries_by_date.items():
                        total_updates += _apply_chart_entries(
                            session,
                            entries,
                            chart_source,
                            chart_name,
                            chart_date,
                            artist_map,
                        )
                        total_dates += 1
                        if total_dates % 50 == 0:
                            await asyncio.sleep(0)

            logger.info(
                "[maintenance] chart match refresh updated %d tracks across %d dates",
                total_updates,
                total_dates,
            )
        except Exception as exc:
            logger.error("[maintenance] chart match refresh failed: %s", exc)

        await asyncio.sleep(settings.CHART_MATCH_REFRESH_INTERVAL_HOURS * 60 * 60)
