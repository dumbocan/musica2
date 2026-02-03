"""
Enhanced tracks overview endpoint with all features from original implementation.
This replaces the simple placeholder with a fully functional implementation.
"""

import logging
import re
from typing import Dict, Any, Optional

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from sqlalchemy import and_, func, or_, exists
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import (
    Track, Artist, Album, YouTubeDownload, UserFavorite, UserHiddenArtist,
    FavoriteTargetType, TrackChartEntry, TrackChartStats
)

logger = logging.getLogger(__name__)


def _select_best_downloads(downloads: list) -> dict:
    """Select the best download for each Spotify track ID."""
    download_map = {}
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


def _is_valid_youtube_video_id(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", value))


def _load_best_position_dates(session, track_ids: list) -> dict:
    """Load best position dates for chart statistics."""
    if not track_ids:
        return {}
    from sqlalchemy import func
    from sqlmodel import select

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


router = APIRouter(prefix="/overview", tags=["tracks"])


@router.get("/")
async def get_tracks_overview(
    request: Request,
    verify_files: bool = Query(False, description="Check file existence on disk"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(200, ge=1, le=1000, description="Pagination limit"),
    include_summary: bool = Query(True, description="Include aggregate summary counts"),
    after_id: Optional[int] = Query(None, ge=0, description="Return tracks after this ID for efficient pagination"),
    filter: Optional[str] = Query(None, description="Filter: withLink, noLink, hasFile, missingFile, favorites"),
    search: Optional[str] = Query(None, description="Search by track, artist, or album"),
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """
    Return tracks with artist, album, cached YouTube link/status and local file info.

    Enhanced version with:
    - After-ID pagination (more efficient than offset)
    - Summary statistics toggle
    - Multiple filter types
    - Improved search patterns
    - Chart integration
    - Hidden artists filtering
    - File verification
    """
    from sqlmodel import select
    from pathlib import Path as FsPath

    def normalize_search(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def normalized_column(column):
        return func.regexp_replace(func.lower(column), "[^a-z0-9]+", " ", "g")

    # Validate filter
    if filter == "all":
        filter = None
    elif filter and filter not in {"withLink", "noLink", "hasFile", "missingFile", "favorites"}:
        raise HTTPException(status_code=400, detail="Invalid filter value")

    # Get user ID
    if user_id is None:
        user_id = getattr(request.state, "user_id", None)

    # Check for hidden artists
    hidden_exists = None
    if user_id:
        hidden_exists = exists(
            select(1).where(
                and_(
                    UserHiddenArtist.user_id == user_id,
                    UserHiddenArtist.artist_id == Track.artist_id
                )
            )
        )

    # Summary statistics (optional)
    summary = None
    if include_summary:
        with get_session() as sync_session:
            summary_query = (
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
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            )
            if hidden_exists is not None:
                summary_query = summary_query.where(~hidden_exists)
            total, with_link, with_file = sync_session.exec(summary_query).one()
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

    # Main query construction
    search_term = normalize_search(search) if search else ""
    is_filtered_query = bool(filter or search_term)

    with get_session() as sync_session:
        base_query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .order_by(Track.id.asc())
        )

        if hidden_exists is not None:
            base_query = base_query.where(~hidden_exists)

        # Apply search filters
        if search_term:
            pattern = f"%{search_term}%"
            base_query = base_query.where(
                or_(
                    normalized_column(Track.name).ilike(pattern),
                    normalized_column(Artist.name).ilike(pattern),
                    normalized_column(Album.name).ilike(pattern),
                )
            )

        # Apply specific filters
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
                if not user_id:
                    raise HTTPException(status_code=401, detail="User not authenticated")
                favorite_exists = exists(
                    select(1).where(
                        (UserFavorite.user_id == user_id)
                        & (UserFavorite.track_id == Track.id)
                        & (UserFavorite.target_type == FavoriteTargetType.TRACK)
                    )
                )
                base_query = base_query.where(favorite_exists)
            elif filter == "withLink":
                base_query = base_query.where(link_exists)
            elif filter == "noLink":
                base_query = base_query.where(~link_exists)
            elif filter == "hasFile":
                base_query = base_query.where(file_exists)
            elif filter == "missingFile":
                base_query = base_query.where(~file_exists)

        # After-ID pagination (more efficient than offset)
        if after_id is not None:
            base_query = base_query.where(Track.id > after_id)
        else:
            base_query = base_query.offset(offset)

        rows = sync_session.exec(base_query.limit(limit + 1)).all()

        # Get filtered total count
        filtered_total = None
        if is_filtered_query:
            count_query = (
                select(func.count(Track.id))
                .join(Artist, Artist.id == Track.artist_id)
                .outerjoin(Album, Album.id == Track.album_id)
            )
            if hidden_exists is not None:
                count_query = count_query.where(~hidden_exists)

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
                if filter == "favorites":
                    if not user_id:
                        raise HTTPException(status_code=401, detail="User not authenticated")
                    favorite_exists = exists(
                        select(1).where(
                            (UserFavorite.user_id == user_id)
                            & (UserFavorite.track_id == Track.id)
                            & (UserFavorite.target_type == FavoriteTargetType.TRACK)
                        )
                    )
                    count_query = count_query.where(favorite_exists)
                elif filter == "withLink":
                    count_query = count_query.where(link_exists)
                elif filter == "noLink":
                    count_query = count_query.where(~link_exists)
                elif filter == "hasFile":
                    count_query = count_query.where(file_exists)
                elif filter == "missingFile":
                    count_query = count_query.where(~file_exists)

            filtered_total = sync_session.exec(count_query).one()
            filtered_total = int(filtered_total or 0)

        # Process results
        raw_rows = rows
        has_more = len(raw_rows) > limit
        track_rows = raw_rows[:limit]

        # Get YouTube downloads and chart stats efficiently
        track_ids = [track.id for track, _, _ in track_rows]
        spotify_ids = [track.spotify_id for track, _, _ in track_rows if track.spotify_id]

        # Get downloads and chart data
        download_map = {}
        chart_stats_map = {}

        if spotify_ids:
            with get_session() as download_session:
                downloads = download_session.exec(
                    select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
                ).all()
                download_map = _select_best_downloads(downloads)

                # Get chart statistics
                from ...models.base import TrackChartStats
                stats_rows = download_session.exec(
                    select(TrackChartStats).where(TrackChartStats.track_id.in_(track_ids))
                ).all()

                priority = {"billboard-global-200": 0, "hot-100": 1}
                for row in stats_rows:
                    current = chart_stats_map.get(row.track_id)
                    if not current:
                        chart_stats_map[row.track_id] = row
                        continue
                    current_rank = priority.get(current.chart_name, 99)
                    next_rank = priority.get(row.chart_name, 99)
                    if next_rank < current_rank:
                        chart_stats_map[row.track_id] = row

        # Get chart dates efficiently
        best_date_map = {}
        if chart_stats_map:
            with get_session() as chart_session:
                best_date_map = _load_best_position_dates(chart_session, list(chart_stats_map.keys()))

        # Build response items
        items = []
        for track, artist, album in track_rows:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            raw_video_id = (download.youtube_video_id or None) if download else None
            youtube_video_id = raw_video_id if _is_valid_youtube_video_id(raw_video_id) else None
            youtube_status = download.download_status if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None

            if verify_files and file_path:
                file_exists = FsPath(file_path).exists()
            else:
                # DB-first: when not verifying disk, trust persisted download_path.
                file_exists = bool(file_path)

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

        # Determine next_after for pagination
        next_after = track_rows[-1][0].id if track_rows and has_more else after_id

        # Build response
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
            response["filtered_total"] = filtered_total

        return response


@router.get("/metrics")
async def get_tracks_metrics(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get aggregated track metrics."""
    from sqlalchemy import func
    from sqlmodel import select

    with get_session() as sync_session:
        total = sync_session.exec(select(func.count(Track.id))).one()
        with_youtube = sync_session.exec(
            select(func.count(func.distinct(Track.id)))
            .join(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            .where(YouTubeDownload.youtube_video_id.is_not(None))
        ).one()
        with_files = sync_session.exec(
            select(func.count(func.distinct(Track.id)))
            .join(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            .where(YouTubeDownload.download_path.is_not(None))
        ).one()

        return {
            "total_tracks": total,
            "tracks_with_youtube": with_youtube,
            "tracks_with_files": with_files,
            "tracks_missing_youtube": total - with_youtube,
            "tracks_missing_files": total - with_files,
        }


@router.get("/favorites/{user_id}")
async def get_user_favorites(
    user_id: int,
    verify_files: bool = Query(False, description="Check file existence on disk"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Pagination limit"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get user's favorite tracks."""
    from sqlalchemy import func
    from sqlmodel import select
    from pathlib import Path as FsPath

    with get_session() as sync_session:
        base_query = (
            select(Track, Artist, Album)
            .join(UserFavorite, UserFavorite.track_id == Track.id)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(UserFavorite.user_id == user_id)
            .where(UserFavorite.target_type == FavoriteTargetType.TRACK)
            .order_by(UserFavorite.created_at.desc(), Track.id.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = sync_session.exec(base_query).all()

        # Get YouTube info
        spotify_ids = [track.spotify_id for track, _, _ in rows if track.spotify_id]

        download_map = {}
        if spotify_ids:
            downloads = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()
            download_map = _select_best_downloads(downloads)

        items = []
        for track, artist, album in rows:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            youtube_video_id = (download.youtube_video_id or None) if download else None
            youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
            file_path = download.download_path if download else None

            if verify_files and file_path:
                file_exists = FsPath(file_path).exists()
            else:
                file_exists = False

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
                "youtube_url": youtube_url,
                "local_file_path": file_path,
                "local_file_exists": file_exists,
                "favorited_at": None,  # Would need to join UserFavorite to get created_at
            })

        total = sync_session.exec(
            select(func.count(func.distinct(Track.id)))
            .join(UserFavorite, UserFavorite.track_id == Track.id)
            .where(UserFavorite.user_id == user_id)
            .where(UserFavorite.target_type == FavoriteTargetType.TRACK)
        ).one()

        return {
            "items": items,
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": len(rows) == limit,
        }
