"""
Personal charts endpoints.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query

from ..core.db import get_session
from ..models.base import Track, Artist, Album, PlayHistory, Tag, TrackTag
from ..crud import get_most_played_tracks
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
            interval_days = 1
        elif interval == "weekly":
            # Weekly trends
            date_trunc = "week"
            interval_days = 7
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
            query = query.join(Track, Track.id == TrackTag.track_id) \
                          .join(PlayHistory, PlayHistory.track_id == Track.id)

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
