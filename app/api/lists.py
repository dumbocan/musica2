"""
Curated lists based on the local library and user behavior.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, desc, or_
from sqlalchemy.sql import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.db import SessionDep
from ..models.base import (
    Album,
    Artist,
    PlayHistory,
    Track,
    UserFavorite,
    YouTubeDownload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lists", tags=["lists"])


def _is_valid_youtube_video_id(value: str | None) -> bool:
    if not value:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", value))


def _parse_genres(raw: str | None) -> list[str]:
    def _sanitize(token: str) -> str:
        return token.strip().strip('"').strip("'").strip("{} ").strip('"').strip("'")

    if not raw:
        return []
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return []
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(g).strip() for g in parsed if isinstance(g, str) and g.strip()]
        except Exception:
            pass
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]
        return [
            _sanitize(genre)
            for genre in cleaned.split(",")
            if _sanitize(genre)
        ]
    if isinstance(raw, Iterable):
        return [_sanitize(str(item)) for item in raw if isinstance(item, str) and _sanitize(str(item))]
    return []


def _extract_primary_image_url(images: object) -> str | None:
    if not images:
        return None
    parsed = images
    if isinstance(parsed, str):
        text = parsed.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return None
    if not isinstance(parsed, list) or not parsed:
        return None
    first = parsed[0]
    if isinstance(first, dict):
        url = first.get("url")
    else:
        url = first
    return str(url).strip() if isinstance(url, str) and url.strip() else None


def _track_payload(track: Track, artist: Artist | None, album: Album | None, download: YouTubeDownload | None) -> dict:
    image_url = _extract_primary_image_url(album.images if album else None) or _extract_primary_image_url(
        artist.images if artist else None
    )
    valid_video_id = download.youtube_video_id if download and _is_valid_youtube_video_id(download.youtube_video_id) else None
    merged_download_path = track.download_path or (download.download_path if download and download.download_path else None)
    merged_download_status = track.download_status or (download.download_status if download else None)
    if merged_download_path and not merged_download_status:
        merged_download_status = "completed"
    payload = {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "is_favorite": bool(track.is_favorite),
        "download_status": merged_download_status,
        "download_path": merged_download_path,
        "artists": [],
        "album": None,
        "image_url": image_url,
        "videoId": valid_video_id,
    }
    if artist:
        payload["artists"].append({
            "id": artist.id,
            "name": artist.name,
            "spotify_id": artist.spotify_id,
        })
    if album:
        payload["album"] = {
            "id": album.id,
            "spotify_id": album.spotify_id,
            "name": album.name,
            "release_date": album.release_date,
        }
    return payload


async def _fetch_tracks(
    session: AsyncSession,
    stmt,
    seen: set[int],
    limit: int,
) -> list[dict]:
    # Guardrail: never scan the full library for curated cards.
    capped_stmt = stmt.limit(max(limit * 8, limit))
    rows = (await session.exec(capped_stmt)).all()
    ordered_ids: list[int] = []
    payload_by_track_id: dict[int, dict] = {}
    download_by_track_id: dict[int, YouTubeDownload | None] = {}

    def _pick_download(current: YouTubeDownload | None, candidate: YouTubeDownload | None) -> YouTubeDownload | None:
        if current is None:
            return candidate
        if candidate is None:
            return current
        current_has_path = bool(current.download_path)
        candidate_has_path = bool(candidate.download_path)
        if candidate_has_path != current_has_path:
            return candidate if candidate_has_path else current
        current_valid_video = _is_valid_youtube_video_id(current.youtube_video_id)
        candidate_valid_video = _is_valid_youtube_video_id(candidate.youtube_video_id)
        if candidate_valid_video != current_valid_video:
            return candidate if candidate_valid_video else current
        if candidate.updated_at and current.updated_at:
            return candidate if candidate.updated_at > current.updated_at else current
        return current

    for row in rows:
        if not row:
            continue
        if len(row) == 4:
            track, artist, album, download = row
        else:
            track, artist, album = row
            download = None
        if not isinstance(track, Track):
            continue
        if track.id in seen:
            continue
        if track.id not in payload_by_track_id:
            ordered_ids.append(track.id)
            payload_by_track_id[track.id] = {
                "track": track,
                "artist": artist,
                "album": album,
            }
            download_by_track_id[track.id] = download
        else:
            download_by_track_id[track.id] = _pick_download(download_by_track_id.get(track.id), download)

        if len(ordered_ids) >= limit * 2:
            break

    results: list[dict] = []
    for track_id in ordered_ids:
        if track_id in seen:
            continue
        row_data = payload_by_track_id.get(track_id)
        if not row_data:
            continue
        seen.add(track_id)
        results.append(
            _track_payload(
                row_data["track"],
                row_data["artist"],
                row_data["album"],
                download_by_track_id.get(track_id),
            )
        )
        if len(results) >= limit:
            break
    return results


async def _get_favorite_tracks(session: AsyncSession, user_id: int, limit: int, seen: set[int]) -> list[dict]:
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(Track.is_favorite.is_(True))
        .where(Track.artist_id.is_not(None))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


async def _get_user_favorite_tracks_with_link(
    session: AsyncSession,
    user_id: int,
    limit: int,
    seen: set[int],
) -> list[dict]:
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(UserFavorite, and_(UserFavorite.track_id == Track.id, UserFavorite.user_id == user_id))
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .join(
            YouTubeDownload,
            and_(
                YouTubeDownload.spotify_track_id == Track.spotify_id,
                YouTubeDownload.youtube_video_id.is_not(None),
                YouTubeDownload.youtube_video_id != "",
            ),
        )
        .where(UserFavorite.target_type == "track")
        .order_by(desc(YouTubeDownload.updated_at), desc(Track.popularity))
    )
    rows = await _fetch_tracks(session, stmt, seen, limit * 2)
    return [row for row in rows if row.get("videoId")][:limit]


async def _get_user_favorite_artist_ids(session: AsyncSession, user_id: int) -> set[int]:
    rows = (await session.exec(
        select(UserFavorite.artist_id)
        .where(UserFavorite.user_id == user_id)
        .where(UserFavorite.artist_id.is_not(None))
    )).all()
    return {row for row in rows if row}


async def _top_genres_for_user(session: AsyncSession, user_id: int, limit: int = 3) -> list[str]:
    favorite_rows = (await session.exec(
        select(Artist.genres)
        .join(UserFavorite, UserFavorite.artist_id == Artist.id)
        .where(UserFavorite.user_id == user_id)
        .where(Artist.genres.is_not(None))
    )).all()
    genres: list[str] = []
    for raw in favorite_rows:
        genres.extend(_parse_genres(raw))
    normalized = []
    for genre in genres:
        if genre.lower() not in {g.lower() for g in normalized}:
            normalized.append(genre)
        if len(normalized) >= limit:
            break
    return normalized


async def _genre_suggestions(
    session: AsyncSession,
    genres: list[str],
    seen: set[int],
    limit: int,
) -> list[dict]:
    if not genres:
        return []
    genre_filters = [Artist.genres.ilike(f"%{genre}%") for genre in genres]
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(or_(*genre_filters))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


async def _artist_discography_tracks(
    session: AsyncSession,
    artist_id: int,
    seen: set[int],
    limit: int,
) -> list[dict]:
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(Track.artist_id == artist_id)
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


async def _collaboration_tracks(
    session: AsyncSession,
    genres: list[str],
    seen: set[int],
    limit: int,
) -> list[dict]:
    feat_conditions = [
        Track.name.ilike("%feat%"),
        Track.name.ilike("%ft.%"),
        Track.name.ilike("%with%"),
    ]
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(or_(*feat_conditions))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    if genres:
        stmt = stmt.where(or_(*[Artist.genres.ilike(f"%{genre}%") for genre in genres]))
    return await _fetch_tracks(session, stmt, seen, limit)


async def _related_artist_tracks(
    session: AsyncSession,
    favorite_artist_ids: set[int],
    genres: list[str],
    seen: set[int],
    limit: int,
) -> list[dict]:
    if not genres:
        return []
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(or_(*[Artist.genres.ilike(f"%{genre}%") for genre in genres]))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    if favorite_artist_ids:
        stmt = stmt.where(Artist.id.notin_(favorite_artist_ids))
    return await _fetch_tracks(session, stmt, seen, limit)


async def _library_tracks(
    session: AsyncSession,
    seen: set[int],
    limit: int,
) -> list[dict]:
    """Fallback list: tracks available in local DB regardless of YouTube link."""
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .order_by(desc(Track.user_score), desc(Track.popularity), desc(Track.updated_at))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


async def _downloaded_tracks(
    session: AsyncSession,
    seen: set[int],
    limit: int,
) -> list[dict]:
    """Tracks with local downloaded file or completed download status."""
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(
            or_(
                Track.download_path.is_not(None),
                Track.download_status.in_(["completed", "downloaded"]),
            )
        )
        .order_by(desc(Track.updated_at), desc(Track.user_score), desc(Track.popularity))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


async def _resolve_artist(
    session: AsyncSession,
    user_id: int,
    artist_spotify_id: str | None,
    artist_name: str | None,
) -> Artist | None:
    if artist_name:
        name_clean = artist_name.strip()
        if name_clean:
            actor = await session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{name_clean}%"))
                .order_by(desc(Artist.popularity), Artist.name)
                .limit(1)
            )
            artist = actor.first()
            if artist:
                return artist
    if artist_spotify_id:
        actor = await session.exec(select(Artist).where(Artist.spotify_id == artist_spotify_id))
        artist = actor.first()
        if artist:
            return artist
    fav_artist_id = (await session.exec(
        select(UserFavorite.artist_id)
        .where(UserFavorite.user_id == user_id)
        .where(UserFavorite.artist_id.is_not(None))
        .order_by(UserFavorite.id)
        .limit(1)
    )).first()
    if fav_artist_id:
        actor = await session.exec(select(Artist).where(Artist.id == fav_artist_id))
        return actor.first()
    return None


async def _payload_map_for_tracks(session: AsyncSession, track_ids: list[int]) -> dict[int, dict]:
    if not track_ids:
        return {}
    stmt = (
        select(Track, Artist, Album, YouTubeDownload)
        .join(Artist, Track.artist_id == Artist.id)
        .outerjoin(Album, Track.album_id == Album.id)
        .outerjoin(
            YouTubeDownload,
            YouTubeDownload.spotify_track_id == Track.spotify_id,
        )
        .where(Track.id.in_(track_ids))
        .order_by(desc(YouTubeDownload.updated_at))
    )
    rows = (await session.exec(stmt)).all()
    payload_by_track: dict[int, dict] = {}
    for track, artist, album, download in rows:
        if not isinstance(track, Track) or track.id in payload_by_track:
            continue
        payload_by_track[track.id] = _track_payload(track, artist, album, download)
    return payload_by_track


def _rank_score(user_score: int | None, plays: int, popularity: int | None, last_played: datetime | None) -> float:
    rating_component = float(max(user_score or 0, 0)) / 5.0 * 45.0
    plays_component = min(float(max(plays, 0)), 50.0) / 50.0 * 35.0
    popularity_component = float(max(popularity or 0, 0)) / 100.0 * 10.0
    if last_played:
        age_days = max((datetime.utcnow() - last_played).days, 0)
        recency_component = max(0.0, 10.0 * (1.0 - (age_days / 365.0)))
    else:
        recency_component = 0.0
    return rating_component + plays_component + popularity_component + recency_component


async def _top_tracks_last_year(
    session: AsyncSession,
    user_id: int,
    seen: set[int],
    limit: int,
) -> list[dict]:
    async def _query_rows(since: datetime | None):
        query = (
            select(
                Track.id,
                Track.user_score,
                Track.popularity,
                func.count(PlayHistory.id).label("plays"),
                func.max(PlayHistory.played_at).label("last_played"),
            )
            .join(PlayHistory, PlayHistory.track_id == Track.id)
            .where(PlayHistory.user_id == user_id)
        )
        if since:
            query = query.where(PlayHistory.played_at >= since)
        query = query.group_by(Track.id, Track.user_score, Track.popularity)
        return (await session.exec(query)).all()

    rows = await _query_rows(datetime.utcnow() - timedelta(days=365))
    if not rows:
        rows = await _query_rows(None)
    if not rows:
        fallback_tracks = (await session.exec(
            select(Track)
            .where(Track.user_score > 0)
            .order_by(desc(Track.user_score), desc(Track.popularity))
            .limit(limit * 3)
        )).all()
        rows = [
            (track.id, track.user_score, track.popularity, 0, None)
            for track in fallback_tracks
            if track.id is not None
        ]

    ranked_ids = [
        track_id
        for track_id, _, _, _, _ in sorted(
            rows,
            key=lambda row: _rank_score(row[1], row[3], row[2], row[4]),
            reverse=True,
        )
    ]
    if not ranked_ids:
        return []

    payload_map = await _payload_map_for_tracks(session, ranked_ids)
    results: list[dict] = []
    for track_id in ranked_ids:
        if track_id in seen:
            continue
        payload = payload_map.get(track_id)
        if not payload:
            continue
        seen.add(track_id)
        results.append(payload)
        if len(results) >= limit:
            break
    return results


async def _top_tracks_for_artist(
    session: AsyncSession,
    user_id: int,
    artist_id: int,
    seen: set[int],
    limit: int,
) -> list[dict]:
    rows = (await session.exec(
        select(
            Track.id,
            Track.user_score,
            Track.popularity,
            func.count(PlayHistory.id).label("plays"),
            func.max(PlayHistory.played_at).label("last_played"),
        )
        .outerjoin(
            PlayHistory,
            and_(PlayHistory.track_id == Track.id, PlayHistory.user_id == user_id),
        )
        .where(Track.artist_id == artist_id)
        .group_by(Track.id, Track.user_score, Track.popularity)
    )).all()

    ranked_ids = [
        track_id
        for track_id, _, _, _, _ in sorted(
            rows,
            key=lambda row: _rank_score(row[1], row[3], row[2], row[4]),
            reverse=True,
        )
    ]
    if not ranked_ids:
        return []

    payload_map = await _payload_map_for_tracks(session, ranked_ids)
    results: list[dict] = []
    for track_id in ranked_ids:
        if track_id in seen:
            continue
        payload = payload_map.get(track_id)
        if not payload:
            continue
        seen.add(track_id)
        results.append(payload)
        if len(results) >= limit:
            break
    return results


@router.get("/overview")
async def list_overview(
    request: Request,
    limit_per_list: int = Query(12, ge=6, le=36),
    artist_spotify_id: str | None = Query(None, description="Optional artist to anchor discographies and collaborations"),
    artist_name: str | None = Query(None, description="Optional artist name to build top songs list"),
    session: AsyncSession = Depends(SessionDep),
):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User required to access lists")

    seen_tracks: set[int] = set()
    favorite_ids = await _get_user_favorite_artist_ids(session, user_id)
    top_genres = await _top_genres_for_user(session, user_id, limit=3)
    favorite_tracks_with_link = await _get_user_favorite_tracks_with_link(session, user_id, limit_per_list, seen_tracks)
    top_year_tracks = await _top_tracks_last_year(session, user_id, seen_tracks, limit_per_list)
    favorite_tracks = await _get_favorite_tracks(session, user_id, limit_per_list, seen_tracks)
    genre_tracks = await _genre_suggestions(session, top_genres, seen_tracks, limit_per_list)
    downloaded_tracks = await _downloaded_tracks(session, seen_tracks, limit_per_list)
    selected_artist = await _resolve_artist(session, user_id, artist_spotify_id, artist_name)
    discography_tracks = []
    collaboration_tracks = []
    artist_top_tracks = []
    if selected_artist:
        artist_top_tracks = await _top_tracks_for_artist(session, user_id, selected_artist.id, seen_tracks, limit_per_list)
        discography_tracks = await _artist_discography_tracks(session, selected_artist.id, seen_tracks, limit_per_list)
        collaboration_tracks = await _collaboration_tracks(session, top_genres, seen_tracks, limit_per_list)
    related_tracks = await _related_artist_tracks(session, favorite_ids, top_genres, seen_tracks, limit_per_list)
    library_tracks = await _library_tracks(session, seen_tracks, limit_per_list)

    lists = []
    if favorite_tracks_with_link:
        lists.append({
            "key": "favorites-with-link",
            "title": "Favoritos con enlace",
            "description": "Tus canciones favoritas que ya tienen enlace de YouTube listo para reproducir.",
            "items": favorite_tracks_with_link,
            "meta": {"count": len(favorite_tracks_with_link)},
        })
    if top_year_tracks:
        lists.append({
            "key": "top-last-year",
            "title": "Mejores canciones del ultimo ano",
            "description": "Ranking personal segun tus reproducciones, ratings (1-5) y recencia en los ultimos 365 dias.",
            "items": top_year_tracks,
            "meta": {"count": len(top_year_tracks), "note": "DB-first personalizado"},
        })
    if downloaded_tracks:
        lists.append({
            "key": "downloaded-local",
            "title": "Musica descargada",
            "description": "Canciones con archivo local disponible en tu biblioteca.",
            "items": downloaded_tracks,
            "meta": {"count": len(downloaded_tracks), "note": "Reproduccion local"},
        })
    if favorite_tracks:
        lists.append({
            "key": "favorites",
            "title": "Favoritos",
            "description": "Tus canciones marcadas como favoritas en la biblioteca local.",
            "items": favorite_tracks,
            "meta": {"count": len(favorite_tracks)},
        })
    if selected_artist and artist_top_tracks:
        lists.append({
            "key": "top-artist",
            "title": f"Top de {selected_artist.name}",
            "description": "Mejores canciones del artista segun tus ratings, reproducciones e historial.",
            "items": artist_top_tracks,
            "meta": {
                "count": len(artist_top_tracks),
                "artist": {"name": selected_artist.name, "spotify_id": selected_artist.spotify_id},
                "note": "DB-first personalizado",
            },
        })
    if top_genres and genre_tracks:
        lists.append({
            "key": "genre-suggestions",
            "title": "Géneros parecidos",
            "description": f"Tracks de géneros vinculados a tus artistas favoritos ({', '.join(top_genres)}).",
            "items": genre_tracks,
            "meta": {"genres": top_genres, "count": len(genre_tracks)},
        })
    if selected_artist and discography_tracks:
        lists.append({
            "key": "discography",
            "title": f"{selected_artist.name}: discografía completa",
            "description": "Todas las canciones conocidas del artista, ordenadas por popularidad local.",
            "items": discography_tracks,
            "meta": {"artist": {"name": selected_artist.name, "spotify_id": selected_artist.spotify_id}},
        })
    if collaboration_tracks:
        lists.append({
            "key": "collaborations",
            "title": "Colaboraciones y feats",
            "description": "Pistas marcadas como colaboraciones dentro de tus géneros principales.",
            "items": collaboration_tracks,
            "meta": {"count": len(collaboration_tracks)},
        })
    if related_tracks:
        lists.append({
            "key": "related-artists",
            "title": "Artistas afines",
            "description": "Muestras de artistas cercanos a tus favoritos, sin repetir los mismos nombres.",
            "items": related_tracks,
            "meta": {"genres": top_genres, "count": len(related_tracks)},
        })
    if library_tracks:
        lists.append({
            "key": "library-local",
            "title": "Canciones en tu BD",
            "description": "Selección directa desde tu base local (sin depender de enlaces).",
            "items": library_tracks,
            "meta": {"count": len(library_tracks), "note": "DB local"},
        })

    return {
        "lists": lists,
        "top_genres": top_genres,
        "anchor_artist": {
            "id": selected_artist.id if selected_artist else None,
            "name": selected_artist.name if selected_artist else None,
            "spotify_id": selected_artist.spotify_id if selected_artist else None,
        } if selected_artist else None,
    }
