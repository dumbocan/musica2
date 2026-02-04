"""
Track playback and history endpoints.

Handles play tracking, history, and playback-related functionality.
"""

import logging
from typing import Dict, Any
from datetime import date
from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, exists, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import get_session, SessionDep
from ...models.base import (
    Track,
    Artist,
    Album,
    YouTubeDownload,
    PlayHistory,
    TrackChartEntry,
    TrackChartStats,
)

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


router = APIRouter(tags=["tracks"])


class TrackResolveRequest(BaseModel):
    spotify_track_ids: list[str]


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


@router.post("/resolve")
def resolve_tracks(payload: TrackResolveRequest) -> dict:
    """Resolve Spotify track IDs to local track IDs."""
    spotify_ids = [track_id for track_id in payload.spotify_track_ids if track_id]
    if not spotify_ids:
        return {"items": []}

    with get_session() as sync_session:
        rows = sync_session.exec(
            select(Track.id, Track.spotify_id).where(Track.spotify_id.in_(spotify_ids))
        ).all()

    items = [
        {"track_id": track_id, "spotify_track_id": spotify_id}
        for track_id, spotify_id in rows
        if spotify_id
    ]
    return {"items": items}


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

        best_date_map = _load_best_position_dates(sync_session, list(id_map.keys()))

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


@router.get("/recently-added")
async def get_recently_added_tracks(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of tracks to return"),
    verify_files: bool = Query(False, description="Check file existence on disk"),
    session: AsyncSession = Depends(SessionDep),
) -> dict:
    """Return the most recently added tracks."""
    user_id = getattr(request.state, "user_id", None) if request else None

    hidden_exists = None
    if user_id:
        from ...models.base import UserHiddenArtist
        hidden_exists = exists(
            select(1).where(
                and_(
                    UserHiddenArtist.user_id == user_id,
                    UserHiddenArtist.artist_id == Track.artist_id
                )
            )
        )

    statement = (
        select(Track, Artist, Album)
        .join(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .order_by(Track.created_at.desc(), Track.id.desc())
        .limit(limit)
    )

    if hidden_exists is not None:
        statement = statement.where(~hidden_exists)

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


@router.get("/recommendations")
async def get_track_recommendations(
    request: Request,
    seed_tracks: str | None = Query(None, description="Comma-separated Spotify track IDs"),
    seed_artists: str | None = Query(None, description="Comma-separated Spotify artist IDs"),
    limit: int = Query(20, ge=1, le=50, description="Number of recommendations"),
    session: AsyncSession = Depends(SessionDep),
) -> dict:
    """Get track recommendations based on seed tracks/artists."""
    from ...core.config import settings
    from ...core.spotify import spotify_client

    track_ids = [t for t in (seed_tracks or "").split(",") if t]
    artist_ids = [a for a in (seed_artists or "").split(",") if a]

    if not track_ids and not artist_ids:
        raise HTTPException(status_code=400, detail="Missing seed_tracks or seed_artists")

    user_id = getattr(request.state, "user_id", None) if request else None

    # Get local recommendations based on user's favorite artists
    hidden_exists = None
    if user_id:
        from ...models.base import UserHiddenArtist, UserFavorite
        hidden_exists = exists(
            select(1).where(
                and_(
                    UserHiddenArtist.user_id == user_id,
                    UserHiddenArtist.artist_id == Track.artist_id
                )
            )
        )

    # Get favorite artist IDs
    favorite_artist_ids = []
    if user_id:
        fav_artists = (await session.exec(
            select(UserFavorite.artist_id)
            .where(UserFavorite.user_id == user_id)
            .distinct()
        )).all()
        favorite_artist_ids = [a for a in fav_artists if a]

    # Get tracks from favorite artists
    local_tracks = []
    if favorite_artist_ids:
        fav_tracks_query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(Track.artist_id.in_(favorite_artist_ids))
            .where(Track.spotify_id.is_not(None))
            .order_by(Track.popularity.desc())
            .limit(limit * 2)
        )
        if hidden_exists is not None:
            fav_tracks_query = fav_tracks_query.where(~hidden_exists)

        fav_tracks = (await session.exec(fav_tracks_query)).all()

        # Get downloads for these tracks
        spotify_ids = [t.spotify_id for t, _, _ in fav_tracks if t.spotify_id]
        downloads = (await session.exec(
            select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
        )).all()
        download_map = _select_best_downloads(downloads)

        for track, artist, album in fav_tracks:
            download = download_map.get(track.spotify_id) if track.spotify_id else None
            local_tracks.append({
                "track_id": track.id,
                "track_name": track.name,
                "spotify_track_id": track.spotify_id,
                "artist_name": artist.name if artist else None,
                "artist_spotify_id": artist.spotify_id if artist else None,
                "album_name": album.name if album else None,
                "duration_ms": track.duration_ms,
                "popularity": track.popularity,
                "local_file_exists": bool(download.download_path if download else None),
            })

    # If no Spotify credentials, return local tracks
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return {"tracks": local_tracks[:limit], "artists": []}

    # Get Spotify recommendations
    spotify_track_ids = [t for t in track_ids if _is_spotify_id(t)]
    spotify_artist_ids = [a for a in artist_ids if _is_spotify_id(a)]

    # Convert local IDs to Spotify IDs
    if not spotify_track_ids and track_ids:
        local_track_ids = [int(t) for t in track_ids if t.isdigit()]
        if local_track_ids:
            rows = (await session.exec(
                select(Track.spotify_id)
                .where(Track.id.in_(local_track_ids))
                .where(Track.spotify_id.is_not(None))
            )).all()
            spotify_track_ids = [r for r in rows if r]

    if not spotify_artist_ids and artist_ids:
        local_artist_ids = [int(a) for a in artist_ids if a.isdigit()]
        if local_artist_ids:
            rows = (await session.exec(
                select(Artist.spotify_id)
                .where(Artist.id.in_(local_artist_ids))
                .where(Artist.spotify_id.is_not(None))
            )).all()
            spotify_artist_ids = [r for r in rows if r]

    if not spotify_track_ids and not spotify_artist_ids:
        return {"tracks": local_tracks[:limit], "artists": []}

    # Limit seed values
    spotify_track_ids = list(dict.fromkeys(spotify_track_ids))[:5]
    spotify_artist_ids = list(dict.fromkeys(spotify_artist_ids))[:5]

    try:
        import asyncio
        spotify_payload = await asyncio.wait_for(
            spotify_client.get_recommendations(
                seed_tracks=spotify_track_ids or None,
                seed_artists=spotify_artist_ids or None,
                limit=min(50, limit * 2),
            ),
            timeout=8.0,
        )
        spotify_tracks = spotify_payload.get("tracks", [])

        # Combine local and Spotify tracks
        combined = local_tracks[:limit]
        seen_spotify_ids = set(t.get("spotify_track_id") for t in combined if t.get("spotify_track_id"))

        for track in spotify_tracks:
            track_id = track.get("id")
            if track_id and track_id not in seen_spotify_ids:
                artists = track.get("artists", [])
                combined.append({
                    "track_id": 0,
                    "track_name": track.get("name"),
                    "spotify_track_id": track_id,
                    "artist_name": artists[0].get("name") if artists else None,
                    "artist_spotify_id": artists[0].get("id") if artists else None,
                    "album_name": track.get("album", {}).get("name"),
                    "duration_ms": track.get("duration_ms"),
                    "popularity": 50,
                    "local_file_exists": False,
                })
                seen_spotify_ids.add(track_id)

        return {"tracks": combined[:limit], "artists": spotify_payload.get("artists", [])}

    except Exception as exc:
        logger.warning("[tracks/recommendations] Spotify failed: %s", exc)
        return {"tracks": local_tracks[:limit], "artists": []}


def _is_spotify_id(value: str) -> bool:
    """Check if value is a Spotify ID (22 alphanumeric chars)."""
    return bool(value and len(value) == 22 and value.replace("_", "").replace("-", "").isalnum())
