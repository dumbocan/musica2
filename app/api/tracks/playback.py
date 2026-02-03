"""
Track playback and history endpoints.

Handles play tracking, history, and playback-related functionality.
"""

import logging
from typing import Dict, Any
from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import Track, Artist, Album, YouTubeDownload, PlayHistory

logger = logging.getLogger(__name__)
REPO_ROOT = FsPath(__file__).resolve().parents[3]
DOWNLOADS_ROOT = REPO_ROOT / "downloads"


def _select_best_downloads(
    downloads: list,
) -> dict:
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


def _resolve_download_path(raw_path: str | None) -> FsPath | None:
    if not raw_path:
        return None
    candidate = FsPath(raw_path.strip())
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    options = [
        REPO_ROOT / candidate,
        DOWNLOADS_ROOT / candidate,
    ]
    for path in options:
        if path.exists():
            return path
    return None


router = APIRouter(tags=["tracks"])


@router.post("/play/{track_id}")
def record_track_play(
    request: Request,
    track_id: int = Path(..., description="Track ID"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Record a play for a track (counts in play history)."""
    from ...crud import record_play

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    play_history = record_play(track_id, user_id=user_id)
    if not play_history:
        raise HTTPException(status_code=404, detail="Track not found")
    return {
        "message": "Play recorded",
        "play_history": play_history.dict(),
    }


@router.get("/id/{track_id}/download-info")
def get_track_download_info(
    track_id: int = Path(..., description="Local track ID"),
) -> Dict[str, Any]:
    """Get DB-first download info for a track (local file first, then YouTube metadata)."""
    with get_session() as sync_session:
        track_row = sync_session.exec(
            select(Track, Artist)
            .join(Artist, Artist.id == Track.artist_id)
            .where(Track.id == track_id)
        ).first()
        if not track_row:
            raise HTTPException(status_code=404, detail="Track not found")

        track, artist = track_row
        download = None
        if track.spotify_id:
            downloads = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == track.spotify_id)
            ).all()
            best = _select_best_downloads(downloads)
            download = best.get(track.spotify_id) if best else None

        local_path = track.download_path or (download.download_path if download else None)
        local_exists = _resolve_download_path(local_path) is not None
        youtube_video_id = (download.youtube_video_id if download else None)
        youtube_status = (download.download_status if download else None)

        if local_exists:
            youtube_status = "completed"
        elif youtube_video_id and not youtube_status:
            youtube_status = "link_found"

        return {
            "track_id": track.id,
            "track_name": track.name,
            "spotify_track_id": track.spotify_id,
            "artist_name": artist.name if artist else None,
            "youtube_video_id": youtube_video_id,
            "youtube_status": youtube_status,
            "local_file_path": local_path,
            "local_file_exists": local_exists,
        }


@router.get("/most-played")
def get_most_played_tracks(
    request: Request,
    limit: int = Query(20, ge=1, le=50, description="Number of tracks"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get most played tracks for current user."""
    from pathlib import Path as FsPath

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Get play history aggregated
    with get_session() as sync_session:
        rows = sync_session.exec(
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

        # Get track details
        track_ids = [row[0] for row in rows]
        track_rows = sync_session.exec(
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

        # Get YouTube downloads
        downloads = []
        if spotify_ids:
            downloads = sync_session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()

        download_map = _select_best_downloads(downloads)

        items = []
        for track_id, play_count, last_played_at in rows:
            if track_id in track_map:
                track, artist, album = track_map[track_id]
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
                    "play_count": int(play_count),
                    "last_played_at": last_played_at.isoformat() if last_played_at else None,
                    "youtube_video_id": youtube_video_id,
                    "youtube_status": youtube_status,
                    "youtube_url": youtube_url,
                    "local_file_path": file_path,
                    "local_file_exists": file_exists,
                })

    return {"items": items}


@router.get("/recent-plays")
def get_recent_plays(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100, description="Límite de resultados"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get recent play history."""
    from pathlib import Path as FsPath

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    with get_session() as sync_session:
        history_query = (
            select(PlayHistory, Track, Artist, Album)
            .join(Track, Track.id == PlayHistory.track_id)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(PlayHistory.user_id == user_id)
            .order_by(PlayHistory.played_at.desc(), PlayHistory.id.desc())
            .limit(limit)
        )
        rows = sync_session.exec(history_query).all()

        if not rows:
            return {"items": []}

        spotify_ids = [track.spotify_id for _, track, _, _ in rows if track.spotify_id]
        downloads = []
        if spotify_ids:
            downloads = sync_session.exec(
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


@router.get("/chart-stats")
def get_chart_statistics(
    spotify_ids: str | None = Query(None, description="Comma-separated Spotify track IDs"),
    track_ids: str | None = Query(None, description="Comma-separated local track IDs"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get chart statistics for tracks."""
    from ...models.base import TrackChartStats

    spotify_list = [t for t in (spotify_ids or "").split(",") if t]
    track_id_list = [int(t) for t in (track_ids or "").split(",") if t.isdigit()]
    if not spotify_list and not track_id_list:
        raise HTTPException(status_code=400, detail="Missing spotify_ids or track_ids")

    with get_session() as sync_session:
        id_map = {}
        if spotify_list:
            rows = sync_session.exec(
                select(Track.id, Track.spotify_id).where(Track.spotify_id.in_(spotify_list))
            ).all()
            for track_id, spotify_id in rows:
                id_map[track_id] = spotify_id
        if track_id_list:
            rows = sync_session.exec(
                select(Track.id, Track.spotify_id).where(Track.id.in_(track_id_list))
            ).all()
            for track_id, spotify_id in rows:
                id_map.setdefault(track_id, spotify_id)

        if not id_map:
            return {"items": []}

        stats_rows = sync_session.exec(
            select(TrackChartStats).where(TrackChartStats.track_id.in_(list(id_map.keys())))
        ).all()

        priority = {
            "billboard-global-200": 0,
            "hot-100": 1,
        }
        chosen = {}
        for row in stats_rows:
            current = chosen.get(row.track_id)
            if not current:
                chosen[row.track_id] = row
                continue
            current_rank = priority.get(current.chart_name, 99)
            next_rank = priority.get(row.chart_name, 99)
            if next_rank < current_rank:
                chosen[row.track_id] = row

        # TODO: Implement _load_best_position_dates function
        best_date_map = {}

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
