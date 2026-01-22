"""
Curated lists based on the local library and user behavior.
"""

from __future__ import annotations

import json
import logging
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.db import SessionDep
from ..models.base import (
    Album,
    Artist,
    Track,
    UserFavorite,
    YouTubeDownload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lists", tags=["lists"])


def _parse_genres(raw: str | None) -> list[str]:
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
        return [genre.strip() for genre in cleaned.split(",") if genre.strip()]
    if isinstance(raw, Iterable):
        return [str(item).strip() for item in raw if isinstance(item, str) and item.strip()]
    return []


def _track_payload(track: Track, artist: Artist | None, album: Album | None, download: YouTubeDownload | None) -> dict:
    payload = {
        "id": track.id,
        "spotify_id": track.spotify_id,
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "is_favorite": bool(track.is_favorite),
        "download_status": track.download_status,
        "download_path": track.download_path,
        "artists": [],
        "album": None,
        "videoId": download.youtube_video_id if download else None,
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
    rows = (await session.exec(stmt)).all()
    results: list[dict] = []
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
        seen.add(track.id)
        results.append(_track_payload(track, artist, album, download))
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
            (YouTubeDownload.spotify_track_id == Track.spotify_id) & YouTubeDownload.youtube_video_id.is_not(None)
        )
        .where(Track.is_favorite.is_(True))
        .where(Track.artist_id.is_not(None))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    return await _fetch_tracks(session, stmt, seen, limit)


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
            (YouTubeDownload.spotify_track_id == Track.spotify_id) & YouTubeDownload.youtube_video_id.is_not(None)
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
            (YouTubeDownload.spotify_track_id == Track.spotify_id) & YouTubeDownload.youtube_video_id.is_not(None)
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
            (YouTubeDownload.spotify_track_id == Track.spotify_id) & YouTubeDownload.youtube_video_id.is_not(None)
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
            (YouTubeDownload.spotify_track_id == Track.spotify_id) & YouTubeDownload.youtube_video_id.is_not(None)
        )
        .where(or_(*[Artist.genres.ilike(f"%{genre}%") for genre in genres]))
        .order_by(desc(Track.popularity), desc(YouTubeDownload.updated_at))
    )
    if favorite_artist_ids:
        stmt = stmt.where(Artist.id.notin_(favorite_artist_ids))
    return await _fetch_tracks(session, stmt, seen, limit)


async def _resolve_artist(
    session: AsyncSession,
    user_id: int,
    artist_spotify_id: str | None,
) -> Artist | None:
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


@router.get("/overview")
async def list_overview(
    request: Request,
    limit_per_list: int = Query(12, ge=6, le=36),
    artist_spotify_id: str | None = Query(None, description="Optional artist to anchor discographies and collaborations"),
    session: AsyncSession = Depends(SessionDep),
):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User required to access lists")

    seen_tracks: set[int] = set()
    favorite_ids = await _get_user_favorite_artist_ids(session, user_id)
    top_genres = await _top_genres_for_user(session, user_id, limit=3)
    favorite_tracks = await _get_favorite_tracks(session, user_id, limit_per_list, seen_tracks)
    genre_tracks = await _genre_suggestions(session, top_genres, seen_tracks, limit_per_list)
    selected_artist = await _resolve_artist(session, user_id, artist_spotify_id)
    discography_tracks = []
    collaboration_tracks = []
    if selected_artist:
        discography_tracks = await _artist_discography_tracks(session, selected_artist.id, seen_tracks, limit_per_list)
        collaboration_tracks = await _collaboration_tracks(session, top_genres, seen_tracks, limit_per_list)
    related_tracks = await _related_artist_tracks(session, favorite_ids, top_genres, seen_tracks, limit_per_list)

    lists = []
    if favorite_tracks:
        lists.append({
            "key": "favorites",
            "title": "Favoritos",
            "description": "Tus canciones marcadas como favoritas en la biblioteca local.",
            "items": favorite_tracks,
            "meta": { "count": len(favorite_tracks) },
        })
    if top_genres and genre_tracks:
        lists.append({
            "key": "genre-suggestions",
            "title": "Géneros parecidos",
            "description": f"Tracks de géneros vinculados a tus artistas favoritos ({', '.join(top_genres)}).",
            "items": genre_tracks,
            "meta": { "genres": top_genres, "count": len(genre_tracks) },
        })
    if selected_artist and discography_tracks:
        lists.append({
            "key": "discography",
            "title": f"{selected_artist.name}: discografía completa",
            "description": "Todas las canciones conocidas del artista, ordenadas por popularidad local.",
            "items": discography_tracks,
            "meta": { "artist": { "name": selected_artist.name, "spotify_id": selected_artist.spotify_id } },
        })
    if collaboration_tracks:
        lists.append({
            "key": "collaborations",
            "title": "Colaboraciones y feats",
            "description": "Pistas marcadas como colaboraciones dentro de tus géneros principales.",
            "items": collaboration_tracks,
            "meta": { "count": len(collaboration_tracks) },
        })
    if related_tracks:
        lists.append({
            "key": "related-artists",
            "title": "Artistas afines",
            "description": "Muestras de artistas cercanos a tus favoritos, sin repetir los mismos nombres.",
            "items": related_tracks,
            "meta": { "genres": top_genres, "count": len(related_tracks) },
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
