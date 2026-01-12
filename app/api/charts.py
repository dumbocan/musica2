"""
Personal charts endpoints.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query

from ..core.db import get_session
from ..models.base import (
    Track,
    Artist,
    Album,
    PlayHistory,
    Tag,
    TrackTag,
    TrackChartStats,
    ChartEntryRaw,
    ChartScanState,
)
from sqlmodel import select, func, and_

router = APIRouter(prefix="/charts", tags=["charts"])

def get_date_range(days: int = None, start_date: str = None, end_date: str = None) -> tuple:
    """Get date range for chart filtering."""
    end = datetime.utcnow()
    start = end - timedelta(days=days) if days else None

    if start_date:
        start = datetime.fromisoformat(start_date)
    if end_date:
        end = datetime.fromisoformat(end_date)

    return start, end

@router.get("/top-tracks")
def get_top_tracks_chart(
    limit: int = Query(10, description="Number of tracks to return"),
    days: int = Query(None, description="Last N days"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)")
):
    """Get top tracks chart by play count."""
    session = get_session()
    try:
        start, end = get_date_range(days, start_date, end_date)

        # Get play counts per track with date filtering
        query = select(
            PlayHistory.track_id,
            func.count(PlayHistory.id).label("play_count")
        ).group_by(PlayHistory.track_id)

        if start:
            query = query.where(PlayHistory.played_at >= start)
        if end:
            query = query.where(PlayHistory.played_at <= end)

        results = session.exec(
            query
            .order_by(func.count(PlayHistory.id).desc())
            .limit(limit)
        ).all()

        track_ids = [result[0] for result in results]
        tracks = session.exec(
            select(Track).where(Track.id.in_(track_ids))
        ).all()

        # Combine results
        track_play_counts = {result[0]: result[1] for result in results}
        chart_data = [
            {
                "track": track.dict(),
                "play_count": track_play_counts[track.id],
                "rank": i + 1
            }
            for i, track in enumerate(tracks)
        ]

        return {
            "chart_type": "top_tracks",
            "period": {
                "days": days,
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat()
            },
            "results": chart_data
        }
    finally:
        session.close()

@router.get("/top-artists")
def get_top_artists_chart(
    limit: int = Query(10, description="Number of artists to return"),
    days: int = Query(None, description="Last N days"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)")
):
    """Get top artists chart by play count."""
    session = get_session()
    try:
        start, end = get_date_range(days, start_date, end_date)

        # Get play counts per artist with date filtering
        query = select(
            Track.artist_id,
            func.count(PlayHistory.id).label("play_count")
        ).join(PlayHistory, PlayHistory.track_id == Track.id)

        if start:
            query = query.where(PlayHistory.played_at >= start)
        if end:
            query = query.where(PlayHistory.played_at <= end)

        results = session.exec(
            query
            .group_by(Track.artist_id)
            .order_by(func.count(PlayHistory.id).desc())
            .limit(limit)
        ).all()

        artist_ids = [result[0] for result in results]
        artists = session.exec(
            select(Artist).where(Artist.id.in_(artist_ids))
        ).all()

        # Combine results
        artist_play_counts = {result[0]: result[1] for result in results}
        chart_data = [
            {
                "artist": artist.dict(),
                "play_count": artist_play_counts[artist.id],
                "rank": i + 1
            }
            for i, artist in enumerate(artists)
        ]

        return {
            "chart_type": "top_artists",
            "period": {
                "days": days,
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat()
            },
            "results": chart_data
        }
    finally:
        session.close()

@router.get("/top-albums")
def get_top_albums_chart(
    limit: int = Query(10, description="Number of albums to return"),
    days: int = Query(None, description="Last N days"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)")
):
    """Get top albums chart by play count."""
    session = get_session()
    try:
        start, end = get_date_range(days, start_date, end_date)

        # Get play counts per album with date filtering
        query = select(
            Track.album_id,
            func.count(PlayHistory.id).label("play_count")
        ).join(PlayHistory, PlayHistory.track_id == Track.id)

        if start:
            query = query.where(PlayHistory.played_at >= start)
        if end:
            query = query.where(PlayHistory.played_at <= end)

        results = session.exec(
            query
            .group_by(Track.album_id)
            .order_by(func.count(PlayHistory.id).desc())
            .limit(limit)
        ).all()

        album_ids = [result[0] for result in results if result[0] is not None]
        albums = session.exec(
            select(Album).where(Album.id.in_(album_ids))
        ).all()

        # Combine results
        album_play_counts = {result[0]: result[1] for result in results if result[0] is not None}
        chart_data = [
            {
                "album": album.dict(),
                "play_count": album_play_counts[album.id],
                "rank": i + 1
            }
            for i, album in enumerate(albums)
        ]

        return {
            "chart_type": "top_albums",
            "period": {
                "days": days,
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat()
            },
            "results": chart_data
        }
    finally:
        session.close()

@router.get("/top-rated")
def get_top_rated_chart(
    limit: int = Query(10, description="Number of tracks to return"),
    content_type: str = Query("tracks", description="Content type: tracks, artists, or albums")
):
    """Get top rated content chart."""
    session = get_session()
    try:
        if content_type == "tracks":
            items = session.exec(
                select(Track)
                .where(Track.user_score > 0)
                .order_by(Track.user_score.desc())
                .limit(limit)
            ).all()
            key_field = "track"
        elif content_type == "artists":
            items = session.exec(
                select(Artist)
                .order_by(Artist.popularity.desc())
                .limit(limit)
            ).all()
            key_field = "artist"
        elif content_type == "albums":
            items = session.exec(
                select(Album)
                .order_by(Album.popularity.desc())
                .limit(limit)
            ).all()
            key_field = "album"
        else:
            raise HTTPException(status_code=400, detail="Invalid content_type")

        chart_data = [
            {
                key_field: item.dict(),
                "rating": getattr(item, "user_score", getattr(item, "popularity", 0)),
                "rank": i + 1
            }
            for i, item in enumerate(items)
        ]

        return {
            "chart_type": f"top_rated_{content_type}",
            "content_type": content_type,
            "results": chart_data
        }
    finally:
        session.close()

@router.get("/play-trends")
def get_play_trends_chart(
    days: int = Query(30, description="Number of days to analyze"),
    interval: str = Query("daily", description="Interval: daily or weekly")
):
    """Get play trends over time."""
    session = get_session()
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)

        if interval == "daily":
            # Daily trends
            date_trunc = "date"
        elif interval == "weekly":
            # Weekly trends
            date_trunc = "week"
        else:
            raise HTTPException(status_code=400, detail="Invalid interval")

        # Get play counts by date interval
        results = session.exec(
            select(
                func.date_trunc(date_trunc, PlayHistory.played_at).label("period"),
                func.count(PlayHistory.id).label("play_count")
            )
            .where(
                and_(
                    PlayHistory.played_at >= start,
                    PlayHistory.played_at <= end
                )
            )
            .group_by(func.date_trunc(date_trunc, PlayHistory.played_at))
            .order_by(func.date_trunc(date_trunc, PlayHistory.played_at))
        ).all()

        trends_data = [
            {
                "period": result[0].isoformat(),
                "play_count": result[1],
                "period_type": interval
            }
            for result in results
        ]

        return {
            "chart_type": "play_trends",
            "interval": interval,
            "days": days,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "results": trends_data
        }
    finally:
        session.close()

@router.get("/tag-popularity")
def get_tag_popularity_chart(
    limit: int = Query(10, description="Number of tags to return"),
    days: int = Query(None, description="Last N days"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)")
):
    """Get most popular tags chart."""
    session = get_session()
    try:
        start, end = get_date_range(days, start_date, end_date)

        # Get tag counts with date filtering
        query = select(
            TrackTag.tag_id,
            func.count(TrackTag.id).label("usage_count")
        )

        if start or end:
            # Need to join with PlayHistory to filter by date
            query = query.join(
                Track,
                Track.id == TrackTag.track_id
            ).join(
                PlayHistory,
                PlayHistory.track_id == Track.id
            )

            if start:
                query = query.where(PlayHistory.played_at >= start)
            if end:
                query = query.where(PlayHistory.played_at <= end)

        results = session.exec(
            query
            .group_by(TrackTag.tag_id)
            .order_by(func.count(TrackTag.id).desc())
            .limit(limit)
        ).all()

        tag_ids = [result[0] for result in results]
        tags = session.exec(
            select(Tag).where(Tag.id.in_(tag_ids))
        ).all()

        # Combine results
        tag_counts = {result[0]: result[1] for result in results}
        chart_data = [
            {
                "tag": tag.dict(),
                "usage_count": tag_counts[tag.id],
                "rank": i + 1
            }
            for i, tag in enumerate(tags)
        ]

        return {
            "chart_type": "tag_popularity",
            "period": {
                "days": days,
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat()
            },
            "results": chart_data
        }
    finally:
        session.close()


@router.get("/external/tracks")
def get_external_chart_tracks(
    scope: str = Query("auto", description="auto, global, or us"),
    max_rank: int = Query(10, ge=1, le=200, description="Max chart position"),
    limit: int = Query(50, ge=1, le=200, description="Number of tracks to return"),
    sort_by: str = Query("best_position", description="best_position, weeks_at_one, weeks_on_chart"),
):
    """Get Billboard chart stats for library tracks."""
    session = get_session()
    try:
        if scope not in {"auto", "global", "us"}:
            raise HTTPException(status_code=400, detail="Invalid scope")

        chart_source = "billboard"
        global_chart = "billboard-global-200"
        us_chart = "hot-100"

        stats_by_track = {}
        chart_name_by_track = {}

        if scope in {"auto", "global"}:
            stats = session.exec(
                select(TrackChartStats).where(
                    (TrackChartStats.chart_source == chart_source)
                    & (TrackChartStats.chart_name == global_chart)
                )
            ).all()
            for row in stats:
                stats_by_track[row.track_id] = row
                chart_name_by_track[row.track_id] = global_chart

        if scope in {"auto", "us"}:
            stats = session.exec(
                select(TrackChartStats).where(
                    (TrackChartStats.chart_source == chart_source)
                    & (TrackChartStats.chart_name == us_chart)
                )
            ).all()
            for row in stats:
                if row.track_id not in stats_by_track:
                    stats_by_track[row.track_id] = row
                    chart_name_by_track[row.track_id] = us_chart

        filtered_stats = [
            row for row in stats_by_track.values()
            if row.best_position is not None and row.best_position <= max_rank
        ]

        if sort_by == "best_position":
            filtered_stats.sort(key=lambda item: item.best_position or 999)
        elif sort_by == "weeks_at_one":
            filtered_stats.sort(key=lambda item: item.weeks_at_one, reverse=True)
        elif sort_by == "weeks_on_chart":
            filtered_stats.sort(key=lambda item: item.weeks_on_chart, reverse=True)
        else:
            raise HTTPException(status_code=400, detail="Invalid sort_by")

        limited_stats = filtered_stats[:limit]
        track_ids = [row.track_id for row in limited_stats]
        if not track_ids:
            return {"results": []}

        track_rows = session.exec(
            select(Track, Artist.name)
            .join(Artist, Artist.id == Track.artist_id)
            .where(Track.id.in_(track_ids))
        ).all()
        track_map = {track.id: (track, artist_name) for track, artist_name in track_rows}

        results = []
        for rank, stat in enumerate(limited_stats, start=1):
            track, artist_name = track_map.get(stat.track_id, (None, None))
            if not track:
                continue
            results.append(
                {
                    "track": track.dict(),
                    "artist_name": artist_name,
                    "chart_source": chart_source,
                    "chart_name": chart_name_by_track.get(stat.track_id),
                    "best_position": stat.best_position,
                    "weeks_on_chart": stat.weeks_on_chart,
                    "weeks_at_one": stat.weeks_at_one,
                    "weeks_top5": stat.weeks_top5,
                    "weeks_top10": stat.weeks_top10,
                    "first_chart_date": stat.first_chart_date.isoformat()
                    if stat.first_chart_date
                    else None,
                    "last_chart_date": stat.last_chart_date.isoformat()
                    if stat.last_chart_date
                    else None,
                    "rank": rank,
                }
            )

        return {"results": results}
    finally:
        session.close()


@router.get("/external/status")
def get_external_chart_status() -> dict:
    """Get backfill status for external chart scraping."""
    session = get_session()
    try:
        states = session.exec(select(ChartScanState)).all()
        raw_rows = session.exec(
            select(
                ChartEntryRaw.chart_source,
                ChartEntryRaw.chart_name,
                func.count(ChartEntryRaw.id),
                func.max(ChartEntryRaw.chart_date),
            )
            .group_by(ChartEntryRaw.chart_source, ChartEntryRaw.chart_name)
        ).all()
        raw_map = {
            (row[0], row[1]): {
                "raw_count": int(row[2] or 0),
                "latest_chart_date": row[3].isoformat() if row[3] else None,
            }
            for row in raw_rows
        }

        results = []
        for state in states:
            raw = raw_map.get(
                (state.chart_source, state.chart_name),
                {"raw_count": 0, "latest_chart_date": None},
            )
            results.append(
                {
                    "chart_source": state.chart_source,
                    "chart_name": state.chart_name,
                    "last_scanned_date": state.last_scanned_date.isoformat()
                    if state.last_scanned_date
                    else None,
                    "backfill_complete": state.backfill_complete,
                    "raw_count": raw["raw_count"],
                    "latest_chart_date": raw["latest_chart_date"],
                }
            )

        results.sort(key=lambda item: (item["chart_source"], item["chart_name"]))
        return {"results": results}
    finally:
        session.close()


@router.get("/external/raw")
def get_external_chart_raw(
    chart_source: str = Query("billboard", description="Chart source"),
    chart_name: str | None = Query(None, description="Chart name, e.g. hot-100"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(200, ge=1, le=1000, description="Number of rows to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    include_summary: bool = Query(True, description="Include aggregate counts"),
) -> dict:
    """Return raw chart rows stored by the backfill."""
    session = get_session()
    try:
        query = select(ChartEntryRaw).where(ChartEntryRaw.chart_source == chart_source)
        if chart_name:
            query = query.where(ChartEntryRaw.chart_name == chart_name)
        if start_date:
            query = query.where(ChartEntryRaw.chart_date >= datetime.fromisoformat(start_date).date())
        if end_date:
            query = query.where(ChartEntryRaw.chart_date <= datetime.fromisoformat(end_date).date())

        items = session.exec(
            query.order_by(ChartEntryRaw.chart_date.desc(), ChartEntryRaw.rank.asc())
            .offset(offset)
            .limit(limit)
        ).all()

        summary = None
        if include_summary:
            count_query = select(
                func.count(ChartEntryRaw.id),
                func.count(func.distinct(ChartEntryRaw.chart_date)),
                func.count(func.distinct(ChartEntryRaw.title)),
            ).where(ChartEntryRaw.chart_source == chart_source)
            if chart_name:
                count_query = count_query.where(ChartEntryRaw.chart_name == chart_name)
            if start_date:
                count_query = count_query.where(ChartEntryRaw.chart_date >= datetime.fromisoformat(start_date).date())
            if end_date:
                count_query = count_query.where(ChartEntryRaw.chart_date <= datetime.fromisoformat(end_date).date())
            total_rows, distinct_dates, distinct_titles = session.exec(count_query).one()
            summary = {
                "total_rows": int(total_rows or 0),
                "distinct_dates": int(distinct_dates or 0),
                "distinct_titles": int(distinct_titles or 0),
            }

        return {
            "items": [
                {
                    "chart_source": row.chart_source,
                    "chart_name": row.chart_name,
                    "chart_date": row.chart_date.isoformat(),
                    "rank": row.rank,
                    "title": row.title,
                    "artist": row.artist,
                }
                for row in items
            ],
            "offset": offset,
            "limit": limit,
            "summary": summary,
        }
    finally:
        session.close()
