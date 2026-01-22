"""
Advanced search endpoints.
"""

import asyncio
import json
import logging
import time
import ast
import difflib
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from sqlmodel import select, and_
from sqlalchemy import desc, or_, func

from ..core.config import settings
from ..core.db import get_session, SessionDep
from ..core.image_proxy import proxy_image_list
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from ..core.time_utils import utc_now
from ..models.base import (
    Artist,
    Album,
    Track,
    Tag,
    TrackTag,
    SearchAlias,
    SearchEntityType,
    UserFavorite,
    UserHiddenArtist,
)
from ..services.library_expansion import save_artist_discography, schedule_artist_expansion
from ..crud import normalize_name, save_artist, update_artist_bio
from ..core.search_index import normalize_search_text
from sqlmodel.ext.asyncio.session import AsyncSession
from ..core.search_metrics import (
    get_search_metrics as fetch_search_metrics,
    record_external_resolution,
    record_local_resolution,
)
from ..models.base import UserHiddenArtist

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
MAX_CACHE_ENTRIES = 200
ARTIST_REFRESH_DAYS = 7
_orchestrated_cache: dict[str, tuple[float, dict]] = {}
_artist_profile_cache: dict[str, tuple[float, dict]] = {}


def _cache_get(cache: dict[str, tuple[float, dict]], key: str) -> Optional[dict]:
    entry = cache.get(key)
    if not entry:
        return None
    ts, payload = entry
    if time.time() - ts > CACHE_TTL_SECONDS:
        cache.pop(key, None)
        return None
    return payload


def _cache_set(cache: dict[str, tuple[float, dict]], key: str, payload: dict) -> None:
    if len(cache) >= MAX_CACHE_ENTRIES:
        cache.clear()
    cache[key] = (time.time(), payload)


def _format_tracks(tracks: list[dict]) -> list[dict]:
    results = []
    for t in tracks or []:
        album = t.get("album", {}) or {}
        if album.get("images"):
            album["images"] = proxy_image_list(album.get("images", []), size=384)
        results.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "preview_url": t.get("preview_url"),
            "popularity": t.get("popularity"),
            "explicit": t.get("explicit"),
            "duration_ms": t.get("duration_ms"),
            "artists": t.get("artists", []),
            "album": album
        })
    return results


def _parse_images_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        try:
            return ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return []


def _parse_genres_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return [g.strip() for g in raw if isinstance(g, str) and g.strip()]
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return [g.strip() for g in parsed if isinstance(g, str) and g.strip()]
        except (ValueError, SyntaxError):
            return []
    if isinstance(raw, str) and "," in raw:
        return [g.strip() for g in raw.split(",") if g.strip()]
    return []


def _track_to_spotify_lite(track: Track, artist: Artist | None, album: Album | None) -> dict:
    album_payload = None
    if album:
        album_payload = {
            "id": album.spotify_id or str(album.id),
            "name": album.name,
            "images": proxy_image_list(_parse_images_field(album.images), size=384),
        }
    artists_payload = []
    if artist:
        artists_payload.append({
            "id": artist.spotify_id or str(artist.id),
            "name": artist.name,
        })
    entries_to_materialize: list[dict] = []
    if main:
        entries_to_materialize.append({
            "spotify": main.get("spotify"),
            "lastfm": main.get("lastfm") or {},
            "name": main_name,
        })
    entries_to_materialize.extend(similar or [])
    if entries_to_materialize:
        await _materialize_spotify_entries(session, entries_to_materialize, schedule_limit=8)

    payload = {
        "id": track.spotify_id or str(track.id),
        "name": track.name,
        "duration_ms": track.duration_ms,
        "popularity": track.popularity,
        "preview_url": track.preview_url,
        "artists": artists_payload,
    }
    if track.external_url:
        payload["external_urls"] = {"spotify": track.external_url}
    if album_payload:
        payload["album"] = album_payload
    return payload


def _query_tokens(value: str) -> list[str]:
    normalized = normalize_search_text(value)
    return [token for token in normalized.split() if token]


def _track_title_matches(query: str, title: str) -> bool:
    if not query or not title:
        return False
    q_tokens = _query_tokens(query)
    if not q_tokens:
        return False
    title_norm = normalize_search_text(title)
    return all(token in title_norm for token in q_tokens)


async def _persist_spotify_artist_snapshot(
    spotify_artist: dict,
    lastfm_block: dict | None = None,
) -> None:
    """Persist a Spotify artist (and optional Last.fm bio) without blocking the request."""
    if not spotify_artist:
        return
    spotify_id = spotify_artist.get("id")
    if not spotify_id:
        return

    def _save() -> None:
        try:
            artist = save_artist(spotify_artist)
            if artist and lastfm_block:
                summary = (lastfm_block.get("summary") or "").strip()
                content = (lastfm_block.get("content") or "").strip()
                if summary or content:
                    update_artist_bio(artist.id, summary, content)
        except Exception as exc:
            logger.warning(
                "[search] failed to persist artist %s: %s",
                spotify_artist.get("name") or spotify_id,
                exc,
            )

    try:
        await asyncio.to_thread(_save)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "[search] persistence worker failed for %s: %s",
            spotify_artist.get("name") or spotify_id,
            exc,
        )


async def _materialize_spotify_entries(
    session: AsyncSession,
    entries: list[dict],
    schedule_limit: int = 5,
) -> None:
    """Ensure Spotify entries are saved locally and queue refreshing if missing."""
    spotify_entries: list[tuple[str, dict, dict, str | None]] = []
    for entry in entries or []:
        spotify = entry.get("spotify")
        if not spotify:
            continue
        spotify_id = spotify.get("id")
        if not spotify_id:
            continue
        name = entry.get("name") or spotify.get("name")
        lastfm_data = entry.get("lastfm") or {}
        spotify_entries.append((spotify_id, spotify, lastfm_data, name))
    if not spotify_entries:
        return

    unique_ids = {sid for sid, *_ in spotify_entries}
    existing_ids: set[str] = set()
    try:
        rows = await session.exec(
            select(Artist.spotify_id).where(Artist.spotify_id.in_(list(unique_ids)))
        )
        existing_ids = {row for row in rows if row}
    except Exception as exc:
        logger.warning("[search] failed to check existing artists: %s", exc)

    scheduled = 0
    for spotify_id, spotify_obj, lastfm_obj, name in spotify_entries:
        asyncio.create_task(_persist_spotify_artist_snapshot(spotify_obj, lastfm_obj))
        if scheduled >= schedule_limit:
            continue
        if spotify_id in existing_ids:
            continue
        schedule_artist_expansion(
            spotify_artist_id=spotify_id,
            artist_name=name or spotify_obj.get("name") or spotify_id,
            include_youtube_links=True,
        )
        scheduled += 1
        existing_ids.add(spotify_id)


async def _favorite_ids(session: AsyncSession, entity_type: SearchEntityType, user_id: int | None) -> set[int]:
    if not user_id:
        return set()
    if entity_type == SearchEntityType.ARTIST:
        column = UserFavorite.artist_id
    elif entity_type == SearchEntityType.ALBUM:
        column = UserFavorite.album_id
    else:
        column = UserFavorite.track_id
    rows = (await session.exec(
        select(column)
        .where(UserFavorite.user_id == user_id)
        .where(column.is_not(None))
    )).all()
    return {row for row in rows if row is not None}


async def _hidden_artist_ids(session: AsyncSession, user_id: int | None) -> set[int]:
    if not user_id:
        return set()
    rows = (await session.exec(
        select(UserHiddenArtist.artist_id)
        .where(UserHiddenArtist.user_id == user_id)
    )).all()
    return {row for row in rows if row is not None}


def _merge_scores(primary: dict[int, float], secondary: dict[int, float]) -> dict[int, float]:
    merged = dict(primary)
    for key, score in secondary.items():
        merged[key] = max(merged.get(key, 0.0), score)
    return merged


def _apply_boosts(
    entities: list,
    scores: dict[int, float],
    favorite_ids: set[int],
    popularity_attr: str | None = None,
) -> list[tuple]:
    scored = []
    for entity in entities:
        base = scores.get(entity.id, 0.0)
        if entity.id in favorite_ids:
            base += 0.2
        if popularity_attr:
            popularity = getattr(entity, popularity_attr, 0) or 0
            base += (popularity / 100.0) * 0.1
        scored.append((entity, base))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


async def _alias_score_map(
    session: AsyncSession,
    entity_type: SearchEntityType,
    normalized_query: str,
    limit: int,
    min_similarity: float,
) -> dict[int, float]:
    if not normalized_query:
        return {}
    similarity = func.similarity(SearchAlias.normalized_alias, normalized_query)
    trgm_match = SearchAlias.normalized_alias.op("%")(normalized_query)
    score = func.max(similarity)
    stmt = (
        select(SearchAlias.entity_id, score.label("score"))
        .where(SearchAlias.entity_type == entity_type)
        .where(trgm_match)
        .group_by(SearchAlias.entity_id)
        .having(score >= min_similarity)
        .order_by(desc("score"))
        .limit(limit)
    )
    try:
        rows = (await session.exec(stmt)).all()
        return {row[0]: float(row[1] or 0.0) for row in rows}
    except Exception as exc:
        logger.warning("[db_search] alias similarity failed: %s", exc)
        try:
            fallback = (
                select(SearchAlias.entity_id)
                .where(SearchAlias.entity_type == entity_type)
                .where(SearchAlias.normalized_alias.ilike(f"%{normalized_query}%"))
                .limit(limit)
            )
            rows = (await session.exec(fallback)).all()
            return {row: 0.2 for row in rows}
        except Exception as fallback_exc:
            logger.warning("[db_search] alias fallback failed: %s", fallback_exc)
            return {}


async def _artist_name_scores(
    session: AsyncSession,
    query: str,
    limit: int,
    min_similarity: float,
) -> dict[int, float]:
    query_lower = (query or "").lower().strip()
    if not query_lower:
        return {}
    similarity = func.similarity(func.lower(Artist.name), query_lower)
    trgm_match = func.lower(Artist.name).op("%")(query_lower)
    stmt = (
        select(Artist.id, similarity.label("score"))
        .where(or_(Artist.name.ilike(f"%{query_lower}%"), trgm_match, similarity >= min_similarity))
        .order_by(desc("score"))
        .limit(limit)
    )
    try:
        rows = (await session.exec(stmt)).all()
        return {row[0]: float(row[1] or 0.0) for row in rows}
    except Exception as exc:
        logger.warning("[db_search] artist similarity failed: %s", exc)
        fallback = (
            select(Artist.id)
            .where(Artist.name.ilike(f"%{query_lower}%"))
            .limit(limit)
        )
        rows = (await session.exec(fallback)).all()
        return {row: 0.2 for row in rows}


async def _album_name_scores(
    session: AsyncSession,
    query: str,
    limit: int,
    min_similarity: float,
) -> dict[int, float]:
    query_lower = (query or "").lower().strip()
    if not query_lower:
        return {}
    album_similarity = func.similarity(func.lower(Album.name), query_lower)
    artist_similarity = func.similarity(func.lower(Artist.name), query_lower)
    album_trgm = func.lower(Album.name).op("%")(query_lower)
    artist_trgm = func.lower(Artist.name).op("%")(query_lower)
    score = func.greatest(album_similarity, artist_similarity)
    stmt = (
        select(Album.id, score.label("score"))
        .join(Artist, Album.artist_id == Artist.id)
        .where(or_(
            Album.name.ilike(f"%{query_lower}%"),
            Artist.name.ilike(f"%{query_lower}%"),
            album_trgm,
            artist_trgm,
            score >= min_similarity,
        ))
        .order_by(desc("score"))
        .limit(limit)
    )
    try:
        rows = (await session.exec(stmt)).all()
        return {row[0]: float(row[1] or 0.0) for row in rows}
    except Exception as exc:
        logger.warning("[db_search] album similarity failed: %s", exc)
        fallback = (
            select(Album.id)
            .where(Album.name.ilike(f"%{query_lower}%"))
            .limit(limit)
        )
        rows = (await session.exec(fallback)).all()
        return {row: 0.2 for row in rows}


async def _track_name_scores(
    session: AsyncSession,
    query: str,
    limit: int,
    min_similarity: float,
) -> dict[int, float]:
    query_lower = (query or "").lower().strip()
    if not query_lower:
        return {}
    track_similarity = func.similarity(func.lower(Track.name), query_lower)
    track_trgm = func.lower(Track.name).op("%")(query_lower)
    score = track_similarity
    stmt = (
        select(Track.id, score.label("score"))
        .where(or_(
            Track.name.ilike(f"%{query_lower}%"),
            track_trgm,
            score >= min_similarity,
        ))
        .order_by(desc("score"))
        .limit(limit)
    )
    try:
        rows = (await session.exec(stmt)).all()
        return {row[0]: float(row[1] or 0.0) for row in rows}
    except Exception as exc:
        logger.warning("[db_search] track similarity failed: %s", exc)
        fallback = (
            select(Track.id)
            .where(Track.name.ilike(f"%{query_lower}%"))
            .limit(limit)
        )
        rows = (await session.exec(fallback)).all()
        return {row: 0.2 for row in rows}


async def _search_local_artists(
    session: AsyncSession,
    query: str,
    limit: int,
    user_id: int | None = None,
    genre_keys: list[str] | None = None,
) -> list[tuple[Artist, float]]:
    normalized_query = normalize_search_text(query)
    candidate_limit = max(limit * 4, 30)
    scores = await _alias_score_map(
        session,
        SearchEntityType.ARTIST,
        normalized_query,
        candidate_limit,
        min_similarity=0.3,
    )
    if not scores:
        name_scores = await _artist_name_scores(session, query, candidate_limit, min_similarity=0.25)
        scores = _merge_scores(scores, name_scores)

    if genre_keys:
        genre_filters = [Artist.genres.ilike(f"%{key}%") for key in genre_keys]
        if genre_filters:
            genre_rows = (await session.exec(
                select(Artist.id)
                .where(or_(*genre_filters))
                .limit(candidate_limit)
            )).all()
            for artist_id in genre_rows:
                scores[artist_id] = max(scores.get(artist_id, 0.0), 0.25)

    if not scores:
        return []
    hidden_ids = await _hidden_artist_ids(session, user_id)
    stmt = select(Artist).where(Artist.id.in_(scores.keys()))
    if hidden_ids:
        stmt = stmt.where(Artist.id.notin_(hidden_ids))
    artists = (await session.exec(stmt)).all()
    favorite_ids = await _favorite_ids(session, SearchEntityType.ARTIST, user_id)
    return _apply_boosts(artists, scores, favorite_ids, popularity_attr="popularity")


async def _search_local_albums(
    session: AsyncSession,
    query: str,
    limit: int,
    user_id: int | None = None,
) -> list[tuple[Album, float]]:
    normalized_query = normalize_search_text(query)
    candidate_limit = max(limit * 4, 30)
    scores = await _alias_score_map(
        session,
        SearchEntityType.ALBUM,
        normalized_query,
        candidate_limit,
        min_similarity=0.3,
    )
    if not scores:
        name_scores = await _album_name_scores(session, query, candidate_limit, min_similarity=0.25)
        scores = _merge_scores(scores, name_scores)
    if not scores:
        return []
    hidden_ids = await _hidden_artist_ids(session, user_id)
    stmt = select(Album).where(Album.id.in_(scores.keys()))
    if hidden_ids:
        stmt = stmt.where(Album.artist_id.notin_(hidden_ids))
    albums = (await session.exec(stmt)).all()
    favorite_ids = await _favorite_ids(session, SearchEntityType.ALBUM, user_id)
    return _apply_boosts(albums, scores, favorite_ids)


async def _search_local_tracks(
    session: AsyncSession,
    query: str,
    limit: int,
    user_id: int | None = None,
) -> list[tuple[Track, float]]:
    normalized_query = normalize_search_text(query)
    candidate_limit = max(limit * 4, 40)
    scores = await _alias_score_map(
        session,
        SearchEntityType.TRACK,
        normalized_query,
        candidate_limit,
        min_similarity=0.3,
    )
    if not scores:
        name_scores = await _track_name_scores(session, query, candidate_limit, min_similarity=0.25)
        scores = _merge_scores(scores, name_scores)
    if not scores:
        return []
    hidden_ids = await _hidden_artist_ids(session, user_id)
    stmt = select(Track).where(Track.id.in_(scores.keys()))
    if hidden_ids:
        stmt = stmt.where(Track.artist_id.notin_(hidden_ids))
    tracks = (await session.exec(stmt)).all()
    favorite_ids = await _favorite_ids(session, SearchEntityType.TRACK, user_id)
    return _apply_boosts(tracks, scores, favorite_ids, popularity_attr="popularity")


async def _local_similar_artists(
    session: AsyncSession,
    main_artist: Artist | None,
    fallback_name: str,
    limit: int,
    user_id: int | None = None,
) -> list[dict]:
    hidden_ids = await _hidden_artist_ids(session, user_id)
    if main_artist:
        genres = _parse_genres_field(main_artist.genres)
        genre_filters = [Artist.genres.ilike(f"%{genre}%") for genre in genres if genre]
        if genre_filters:
            rows = (await session.exec(
                select(Artist)
                .where(Artist.id != main_artist.id)
                .where(or_(*genre_filters))
                .order_by(desc(Artist.popularity))
                .limit(limit)
            )).all()
            if hidden_ids:
                rows = [artist for artist in rows if artist.id not in hidden_ids]
            return [
                {
                    "name": artist.name,
                    "spotify": _artist_to_spotify_dict(artist, size=384),
                    "lastfm": _artist_to_lastfm_dict(artist),
                }
                for artist in rows
            ]

    hits = await _search_local_artists(session, fallback_name, limit=limit + 5, user_id=user_id)
    results = []
    for artist, _ in hits:
        if main_artist and artist.id == main_artist.id:
            continue
        results.append({
            "name": artist.name,
            "spotify": _artist_to_spotify_dict(artist, size=384),
            "lastfm": _artist_to_lastfm_dict(artist),
        })
        if len(results) >= limit:
            break
    return results

def _artist_to_spotify_dict(artist: Artist, size: int = 512) -> dict:
    images = proxy_image_list(_parse_images_field(artist.images), size=size)
    return {
        "id": artist.spotify_id,
        "name": artist.name,
        "images": images,
        "followers": {"total": artist.followers or 0},
        "popularity": artist.popularity or 0,
        "genres": _parse_genres_field(artist.genres),
    }


def _artist_to_lastfm_dict(artist: Artist) -> dict:
    tags = _parse_genres_field(artist.genres)
    return {
        "summary": artist.bio_summary or "",
        "content": artist.bio_content or "",
        "stats": {},
        "tags": [{"name": tag} for tag in tags] if tags else [],
        "images": [],
    }


def _infer_genre_keywords(query: str) -> list[str]:
    """Lightweight genre inference to filter noisy matches."""
    ql = (query or "").lower()
    if any(k in ql for k in ["hip hop", "hiphop", "rap", "trap"]):
        return ["hip hop", "hip-hop", "rap", "trap", "boom bap", "gangsta"]
    if "rock" in ql:
        return ["rock", "alt", "indie"]
    if "metal" in ql:
        return ["metal", "heavy", "death"]
    if "pop" in ql:
        return ["pop", "dance", "k-pop"]
    return []


def _matches_genre(artist: dict, genre_keys: list[str], extra_tags: Optional[list[str]] = None) -> bool:
    """Mirror the frontend genre filter server-side."""
    if not genre_keys:
        return True
    disallow = ["tamil", "kollywood", "tollywood", "telugu", "k-pop", "kpop"]
    genres = [g.lower() for g in artist.get("genres", []) if isinstance(g, str)]
    tags = [t.lower() for t in extra_tags or [] if isinstance(t, str)]
    pool = genres + tags
    if not pool:
        return False
    if any(any(bad in g for bad in disallow) for g in pool):
        return False
    return any(any(gk in g for g in pool) for gk in genre_keys)


async def _safe_call(coro, default):
    """Run an async call and swallow errors, returning default on failure."""
    try:
        return await coro
    except Exception as exc:
        logger.warning("[search_orchestrated] skipping failed call: %s", exc)
        return default


async def _safe_timed(coro, default, timeout: float):
    """Safe call with a hard timeout to avoid frontend request timeouts."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception as exc:
        logger.warning(
            "[search_orchestrated] timed call failed after %ss: %s",
            timeout,
            exc,
        )
        return default


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _name_matches(target: str, candidate: str) -> bool:
    """Basic fuzzy match to avoid mismapped photos (e.g., Snoop showing Eminem)."""
    t = _normalize_name(target)
    c = _normalize_name(candidate)
    if not t or not c:
        return False
    return t in c or c in t


_SEARCH_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "y",
}


def _token_similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left, right).ratio()


def _filtered_tokens(value: str) -> list[str]:
    tokens = normalize_search_text(value).split()
    return [token for token in tokens if token and token not in _SEARCH_STOPWORDS and len(token) >= 3]


def _is_confident_artist_match(query: str, candidate: str, score: float) -> bool:
    if not query or not candidate:
        return False
    if score < 0.3:
        return False
    query_tokens = _filtered_tokens(query)
    candidate_tokens = _filtered_tokens(candidate)
    if not query_tokens:
        return True
    if not candidate_tokens:
        return False
    matches = 0
    for q_token in query_tokens:
        for c_token in candidate_tokens:
            if q_token == c_token or _token_similarity(q_token, c_token) >= 0.8:
                matches += 1
                break
    if len(query_tokens) == 1:
        return matches >= 1
    if matches >= 2:
        return True
    flat_query = "".join(query_tokens)
    flat_candidate = "".join(candidate_tokens)
    if flat_query and flat_candidate:
        return _token_similarity(flat_query, flat_candidate) >= 0.78
    return False

@router.get("/spotify")
async def search_spotify(
    q: str = Query(..., description="Search query"),
    limit: int = Query(30, description="Number of artists/tracks to return")
):
    """
    Search Spotify for artists and tracks.
    """
    artists = await spotify_client.search_artists(q, limit=limit)
    tracks = await spotify_client.search_tracks(q, limit=limit)
    return {"artists": artists, "tracks": tracks}


@router.get("/lastfm/top-artists")
async def search_lastfm_top_artists(
    tag: str = Query(..., description="Last.fm tag, e.g., hip hop"),
    limit: int = Query(50, description="Number of artists to return")
):
    """Return top artists for a given Last.fm tag."""
    artists = await lastfm_client.get_top_artists_by_tag(tag, limit=limit)
    return {"tag": tag, "artists": artists}


@router.get("/tag-enriched")
async def search_tag_enriched(
    tag: str = Query(..., description="Tag/genre (ej: hip hop, rock)"),
    limit: int = Query(20, description="Max artists to return")
):
    """
    Orquestador: toma artistas de Last.fm por tag y los enriquece con datos de Spotify
    (imagen, followers, popularidad, géneros). Devuelve una sola respuesta lista
    para renderizar.
    """
    from ..core.lastfm import lastfm_client

    artists = await lastfm_client.get_top_artists_by_tag(tag, limit=limit)

    async def enrich(artist: dict):
        try:
            name = artist.get("name", "")
            sp_matches = await spotify_client.search_artists(name, limit=3)
            sp_sorted = sorted(
                sp_matches,
                key=lambda x: x.get("followers", {}).get("total", 0),
                reverse=True
            )
            best = sp_sorted[0] if sp_sorted else None
            return {
                "name": name,
                "url": artist.get("url"),
                "listeners": artist.get("listeners"),
                "image": artist.get("image", []),
                "lastfm": artist,
                "spotify": best
            }
        except Exception:
            return {
                "name": artist.get("name"),
                "url": artist.get("url"),
                "listeners": artist.get("listeners"),
                "image": artist.get("image", []),
                "lastfm": artist,
                "spotify": None
            }

    enriched = await asyncio.gather(*[enrich(a) for a in artists[:limit]])
    return {"tag": tag, "artists": enriched}


@router.get("/orchestrated")
async def orchestrated_search(
    request: Request,
    q: str = Query(..., description="Query o tag principal"),
    limit: int = Query(20, description="Máximo artistas a traer de Spotify (no usado, compatibilidad)"),
    page: int = Query(0, description="Página de resultados (0-index)"),
    lastfm_limit: int = Query(60, description="Máximo artistas por tag Last.fm"),
    related_limit: int = Query(10, description="Límite de similares Last.fm"),
    min_followers: int = Query(300_000, description="Umbral mínimo de followers para mostrar"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Endpoint único que orquesta Spotify + Last.fm y devuelve un payload listo
    para renderizar, evitando múltiples llamadas desde el frontend.
    """
    from ..core.lastfm import lastfm_client
    cache_key = f"{q.lower()}|{max(page, 0)}|{limit}|{lastfm_limit}|{related_limit}|{min_followers}"
    cached = _cache_get(_orchestrated_cache, cache_key)
    if cached:
        return cached

    genre_keys = _infer_genre_keywords(q)
    timeout_spotify = 4.0
    timeout_lastfm = 6.0
    timeout_related = 5.0

    user_id = getattr(request.state, "user_id", None) if request else None

    # DB-first artists + tracks (offline-friendly)
    local_artist_hits = await _search_local_artists(
        session,
        q,
        limit=limit + related_limit,
        user_id=user_id,
        genre_keys=genre_keys,
    )
    local_track_hits = await _search_local_tracks(session, q, limit=5, user_id=user_id)
    confident_artist_hits = [
        hit for hit in local_artist_hits if _is_confident_artist_match(q, hit[0].name, hit[1])
    ]
    confident_track_hits = [
        hit for hit in local_track_hits if _track_title_matches(q, hit[0].name)
    ]
    if confident_artist_hits or confident_track_hits:
        record_local_resolution(user_id)
        artists_for_grid = [
            _artist_to_spotify_dict(hit[0], size=384)
            for hit in confident_artist_hits[:limit]
        ]
        related = [
            _artist_to_spotify_dict(hit[0], size=384)
            for hit in confident_artist_hits[limit:limit + related_limit]
        ]
        tracks = []
        if confident_track_hits:
            track_ids = [hit[0].id for hit in confident_track_hits]
            track_rows = (await session.exec(
                select(Track, Artist, Album)
                .join(Artist, Track.artist_id == Artist.id)
                .outerjoin(Album, Track.album_id == Album.id)
                .where(Track.id.in_(track_ids))
            )).all()
            track_map = {row[0].id: row for row in track_rows}
            for track_id in track_ids:
                row = track_map.get(track_id)
                if not row:
                    continue
                track, artist, album = row
                tracks.append(_track_to_spotify_lite(track, artist, album))
        payload = {
            "query": q,
            "page": max(page, 0),
            "limit": limit,
            "has_more_artists": False,
            "has_more_lastfm": False,
            "main": None,
            "artists": artists_for_grid,
            "related": related,
            "tracks": tracks,
            "lastfm_top": []
        }
        _cache_set(_orchestrated_cache, cache_key, payload)
        return payload

    record_external_resolution(user_id)
    if not settings.LASTFM_API_KEY:
        payload = {
            "query": q,
            "page": max(page, 0),
            "limit": limit,
            "has_more_artists": False,
            "has_more_lastfm": False,
            "main": None,
            "artists": [],
            "related": [],
            "tracks": [],
            "lastfm_top": []
        }
        _cache_set(_orchestrated_cache, cache_key, payload)
        return payload

    tracks_task = asyncio.create_task(
        _safe_timed(spotify_client.search_tracks(q, limit=5), [], timeout_spotify)
    )

    # Si no hay suficientes datos locales, usamos Last.fm + Spotify y persistimos
    lastfm_top_task = asyncio.create_task(
        _safe_timed(lastfm_client.get_top_artists_by_tag(q, limit=lastfm_limit, page=max(page, 0) + 1), [], timeout_lastfm)
    )
    lastfm_top_raw = await lastfm_top_task

    # Enriquecer top Last.fm con Spotify (para imágenes/followers)
    sem_spotify = asyncio.Semaphore(15)

    async def enrich_top_artist(artist: dict):
        name = artist.get("name", "")
        if not name:
            return None
        async with sem_spotify:
            sp_matches = await _safe_timed(spotify_client.search_artists(name, limit=3), [], timeout_spotify)
        if not sp_matches:
            # Retry once with a smaller limit; try to avoid losing key artists
            async with sem_spotify:
                sp_matches = await _safe_timed(spotify_client.search_artists(name, limit=1), [], timeout_spotify)
        sp_sorted = sorted(
            sp_matches,
            key=lambda x: (x.get("followers", {}) or {}).get("total", 0),
            reverse=True
        )
        best = None
        for candidate in sp_sorted:
            if not _matches_genre(candidate, genre_keys):
                continue
            if not _name_matches(name, candidate.get("name", "")):
                continue
            best = candidate
            break
        # Si no hay match por nombre, usar el más popular para no perder foto/datos
        if not best and sp_sorted:
            best = sp_sorted[0]
        if best:
            best["images"] = proxy_image_list(best.get("images", []), size=384)
        return {
            "name": name,
            "url": artist.get("url"),
            "listeners": artist.get("listeners"),
            "image": artist.get("image", []),
            "lastfm": artist,
            "spotify": best
        }

    lastfm_enriched = await asyncio.gather(*[enrich_top_artist(a) for a in (lastfm_top_raw or [])])
    lastfm_enriched = [a for a in lastfm_enriched if a]
    # dedup by Spotify ID or normalized name to avoid repeats
    seen_ids = set()
    seen_names = set()
    unique_enriched = []
    for entry in lastfm_enriched:
        sp = entry.get("spotify") or {}
        sp_id = sp.get("id")
        norm_name = _normalize_name(entry.get("name", ""))
        if sp_id and sp_id in seen_ids:
            continue
        if norm_name and norm_name in seen_names:
            continue
        if sp_id:
            seen_ids.add(sp_id)
        if norm_name:
            seen_names.add(norm_name)
        unique_enriched.append(entry)
    lastfm_enriched = unique_enriched

    # Fallback: si Last.fm trae pocos resultados, completar con Spotify directo
    if len(lastfm_enriched) < 10:
        fallback_sp = await _safe_timed(spotify_client.search_artists(q, limit=20), [], timeout_spotify)
        fallback_sorted = sorted(
            fallback_sp,
            key=lambda x: (x.get("followers", {}) or {}).get("total", 0),
            reverse=True
        )
        for sp in fallback_sorted:
            sp_id = sp.get("id")
            norm_name = _normalize_name(sp.get("name", ""))
            if sp_id and sp_id in seen_ids:
                continue
            if norm_name and norm_name in seen_names:
                continue
            if not _matches_genre(sp, genre_keys):
                continue
            seen_ids.add(sp_id)
            if norm_name:
                seen_names.add(norm_name)
            lastfm_enriched.append({
                "name": sp.get("name"),
                "url": sp.get("external_urls", {}).get("spotify"),
                "listeners": None,
                "image": sp.get("images", []),
                "lastfm": {},
                "spotify": sp
            })
    # Priorizar artistas con más seguidores en Spotify; fallback a listeners de Last.fm
    lastfm_enriched.sort(
        key=lambda x: (
            (x.get("spotify") or {}).get("followers", {}).get("total", 0),
            x.get("listeners", 0)
        ),
        reverse=True
    )

    # El main artist viene del primer resultado Last.fm enriquecido
    main_artist_block = lastfm_enriched[0] if lastfm_enriched else None
    main_name = main_artist_block.get("name") if main_artist_block else None

    # Related usando Last.fm similares enriquecidos con Spotify
    related = []
    if main_name:
        similar = await _safe_timed(lastfm_client.get_similar_artists(main_name, limit=related_limit), [], timeout_related)

        async def enrich_similar(entry: dict):
            name = entry.get("name")
            if not name:
                return None
            spotify_match = None
            async with sem_spotify:
                sp_candidates = await _safe_timed(spotify_client.search_artists(name, limit=1), [], timeout_spotify)
            if sp_candidates:
                candidate = sp_candidates[0]
                if _name_matches(name, candidate.get("name", "")):
                    spotify_match = candidate
                    spotify_match["images"] = proxy_image_list(spotify_match.get("images", []), size=384)
            followers = (spotify_match or {}).get("followers", {}).get("total", 0)
            if followers < max(min_followers, 1_000_000):
                return None

            info = await _safe_timed(lastfm_client.get_artist_info(name), {}, timeout_lastfm) if settings.LASTFM_API_KEY else {}
            tags = info.get("tags", []) or []
            tags_flat = [t.get("name") for t in tags if isinstance(t, dict)]

            if spotify_match and not _matches_genre(spotify_match, genre_keys, tags_flat):
                return None

            return {
                "name": name,
                "listeners": (info.get("stats", {}) or {}).get("listeners"),
                "playcount": (info.get("stats", {}) or {}).get("playcount"),
                "tags": tags,
                "bio": info.get("summary", ""),
                "spotify": spotify_match
            }

        enriched_similar = await asyncio.gather(*[enrich_similar(s) for s in similar])
        seen_ids = set()
        for item in enriched_similar:
            if not item:
                continue
            sp_id = (item.get("spotify") or {}).get("id")
            if sp_id and sp_id in seen_ids:
                continue
            if sp_id:
                seen_ids.add(sp_id)
            related.append(item)

    # Top por tag Last.fm enriquecidos con Spotify
    # Compact response
    main_lastfm = main_artist_block.get("lastfm", {}) if main_artist_block else {}
    main_spotify = main_artist_block.get("spotify") if main_artist_block else None
    main_block = {"spotify": main_spotify, "lastfm": main_lastfm} if main_artist_block else None

    # Lista de artistas para el grid: prioriza el objeto Spotify enriquecido
    artists_for_grid = []
    seen_spotify_ids = set()
    seen_norm_names_grid = set()
    for entry in lastfm_enriched:
        sp = entry.get("spotify")
        if sp:
            sp_id = sp.get("id")
            norm_name = _normalize_name(sp.get("name", ""))
            if sp_id and sp_id in seen_spotify_ids:
                continue
            if norm_name and norm_name in seen_norm_names_grid:
                continue
            if sp_id:
                seen_spotify_ids.add(sp_id)
            if norm_name:
                seen_norm_names_grid.add(norm_name)
            artists_for_grid.append(sp)
        else:
            artists_for_grid.append({"id": entry.get("name"), "name": entry.get("name"), "followers": {"total": entry.get("listeners", 0)}})

    tracks = _format_tracks(await tracks_task)
    if tracks:
        tracks = [t for t in tracks if _track_title_matches(q, t.get("name", ""))]
    if lastfm_enriched:
        await _materialize_spotify_entries(session, lastfm_enriched, schedule_limit=limit)
    payload = {
        "query": q,
        "page": max(page, 0),
        "limit": limit,
        "has_more_artists": len(lastfm_enriched) >= lastfm_limit,
        "has_more_lastfm": len(lastfm_enriched) >= lastfm_limit,
        "main": main_block,
        "artists": artists_for_grid,
        "related": related,
        "tracks": tracks,
        "lastfm_top": lastfm_enriched
    }
    _cache_set(_orchestrated_cache, cache_key, payload)
    return payload


@router.get("/artist-profile")
async def search_artist_profile(
    request: Request,
    q: str = Query(..., description="Nombre del artista/grupo"),
    similar_limit: int = Query(10, description="Número de artistas afines"),
    min_followers: int = Query(200_000, description="Umbral mínimo de followers Spotify para similares"),
    session: AsyncSession = Depends(SessionDep),
):
    """Devuelve ficha del artista (bio Last.fm + datos Spotify) y similares."""
    q = q.strip()
    cache_key = f"{q.lower()}|{similar_limit}|{min_followers}"
    cached = _cache_get(_artist_profile_cache, cache_key)
    if cached:
        return cached
    lastfm_available = bool(settings.LASTFM_API_KEY)
    user_id = getattr(request.state, "user_id", None) if request else None

    local_cache: dict[str, Artist | None] = {}

    async def resolve_best_local(name: str) -> Artist | None:
        hits = await _search_local_artists(session, name, limit=1, user_id=user_id)
        if not hits:
            return None
        artist, score = hits[0]
        return artist if _is_confident_artist_match(name, artist.name, score) else None

    async def get_local_artist(name: str) -> Artist | None:
        normalized = normalize_name(name)
        if not normalized:
            return None
        if normalized in local_cache:
            return local_cache[normalized]
        local = (await session.exec(
            select(Artist)
            .where(
                or_(
                    Artist.normalized_name == normalized,
                    Artist.name.ilike(f"%{name}%"),
                )
            )
            .order_by(desc(Artist.popularity))
            .limit(1)
        )).first()
        if not local:
            local = await resolve_best_local(name)
        local_cache[normalized] = local
        return local

    def is_stale(artist: Artist | None) -> bool:
        if not artist:
            return True
        stale_at = artist.last_refreshed_at
        if not stale_at or (utc_now() - stale_at) > timedelta(days=ARTIST_REFRESH_DAYS):
            return True
        if not artist.spotify_id:
            return True
        images = (artist.images or "").strip()
        if not images or images in {"[]", ""}:
            return True
        return False

    timeout_spotify = 4.0
    timeout_lastfm = 6.0
    sem_spotify = asyncio.Semaphore(10)
    spotify_available = True

    async def safe_spotify(coro, default):
        nonlocal spotify_available
        if not spotify_available:
            if asyncio.iscoroutine(coro):
                coro.close()
            return default
        try:
            return await asyncio.wait_for(coro, timeout=timeout_spotify)
        except Exception as exc:
            spotify_available = False
            logger.warning("[search_artist_profile] spotify call failed: %s", exc)
            return default

    local_main = await resolve_best_local(q)
    if local_main:
        if spotify_available and is_stale(local_main):
            async def _refresh_local_artist(artist: Artist) -> None:
                try:
                    sid = artist.spotify_id
                    if not sid and artist.name:
                        candidates = await safe_spotify(spotify_client.search_artists(artist.name, limit=3), [])
                        match = None
                        for candidate in candidates or []:
                            if _name_matches(artist.name, candidate.get("name", "")):
                                match = candidate
                                break
                        if not match and candidates:
                            match = candidates[0]
                        if match:
                            sid = match.get("id")
                    if sid:
                        logger.info("[artist_profile] refresh queued for %s (%s)", artist.name, sid)
                        await save_artist_discography(sid)
                except Exception as exc:
                    logger.warning(
                        "[artist_profile] refresh failed for %s: %r",
                        artist.name,
                        exc,
                        exc_info=True,
                    )
            asyncio.create_task(_refresh_local_artist(local_main))
        main = {
            "spotify": _artist_to_spotify_dict(local_main),
            "lastfm": _artist_to_lastfm_dict(local_main),
        }
        similars = await _local_similar_artists(session, local_main, local_main.name, similar_limit, user_id)
        local_track_hits = await _search_local_tracks(session, local_main.name, limit=5, user_id=user_id)
        tracks = []
        if local_track_hits:
            track_ids = [hit[0].id for hit in local_track_hits]
            track_rows = (await session.exec(
                select(Track, Artist, Album)
                .join(Artist, Track.artist_id == Artist.id)
                .outerjoin(Album, Track.album_id == Album.id)
                .where(Track.id.in_(track_ids))
            )).all()
            track_map = {row[0].id: row for row in track_rows}
            for track_id in track_ids:
                row = track_map.get(track_id)
                if not row:
                    continue
                track, artist, album = row
                tracks.append(_track_to_spotify_lite(track, artist, album))
        record_local_resolution(user_id)
        payload = {
            "query": q,
            "mode": "artist",
            "main": main,
            "similar": similars,
            "tracks": tracks
        }
        _cache_set(_artist_profile_cache, cache_key, payload)
        return payload

    local_track_hits = await _search_local_tracks(session, q, limit=5, user_id=user_id)
    if local_track_hits:
        track_ids = [hit[0].id for hit in local_track_hits]
        track_rows = (await session.exec(
            select(Track, Artist, Album)
            .join(Artist, Track.artist_id == Artist.id)
            .outerjoin(Album, Track.album_id == Album.id)
            .where(Track.id.in_(track_ids))
        )).all()
        track_map = {row[0].id: row for row in track_rows}
        tracks = []
        main_artist = None
        for track_id in track_ids:
            row = track_map.get(track_id)
            if not row:
                continue
            track, artist, album = row
            if not _track_title_matches(q, track.name):
                continue
            if not main_artist:
                main_artist = artist
            tracks.append(_track_to_spotify_lite(track, artist, album))
        if tracks:
            main = {
                "spotify": _artist_to_spotify_dict(main_artist) if main_artist else None,
                "lastfm": _artist_to_lastfm_dict(main_artist) if main_artist else {},
            }
            similars = await _local_similar_artists(session, main_artist, main_artist.name if main_artist else q, similar_limit, user_id)
            payload = {
                "query": q,
                "mode": "artist",
                "main": main,
                "similar": similars,
                "tracks": tracks
            }
            record_local_resolution(user_id)
            _cache_set(_artist_profile_cache, cache_key, payload)
            return payload

    async def fetch_main():
        local_artist = await get_local_artist(q)
        sp_best = _artist_to_spotify_dict(local_artist) if local_artist else None
        lfm = _artist_to_lastfm_dict(local_artist) if local_artist else {}
        needs_lastfm = not (lfm.get("summary") or lfm.get("content"))
        if needs_lastfm and lastfm_available:
            lfm_remote = await _safe_timed(lastfm_client.get_artist_info(q), {}, timeout_lastfm)
            if local_artist:
                lfm = {
                    "summary": local_artist.bio_summary or lfm_remote.get("summary", ""),
                    "content": local_artist.bio_content or lfm_remote.get("content", ""),
                    "stats": lfm_remote.get("stats", {}),
                    "tags": lfm_remote.get("tags", []) or lfm.get("tags", []),
                    "images": lfm_remote.get("images", []),
                }
            else:
                lfm = lfm_remote
        if not sp_best and spotify_available:
            async with sem_spotify:
                sp_matches = await safe_spotify(spotify_client.search_artists(q, limit=3), [])
            sp_sorted = sorted(
                sp_matches,
                key=lambda x: (x.get("followers", {}) or {}).get("total", 0),
                reverse=True
            )
            for cand in sp_sorted:
                if _name_matches(q, cand.get("name", "")):
                    sp_best = cand
                    break
            if not sp_best and sp_sorted:
                sp_best = sp_sorted[0]
        return {"spotify": sp_best, "lastfm": lfm}

    async def fetch_similars(main_name: str, local_main: Artist | None):
        if not lastfm_available:
            return await _local_similar_artists(session, local_main, main_name, similar_limit, user_id)
        similars = await _safe_timed(
            lastfm_client.get_similar_artists(main_name, limit=similar_limit + 8),
            [],
            timeout_lastfm,
        )
        results = []
        seen_ids = set()
        for entry in similars:
            name = entry.get("name")
            if not name:
                continue
            local_artist = await get_local_artist(name)
            if local_artist:
                sp_best = _artist_to_spotify_dict(local_artist, size=384)
                sp_id = sp_best.get("id")
                if sp_id and sp_id in seen_ids:
                    continue
                if sp_id:
                    seen_ids.add(sp_id)
                results.append({
                    "name": name,
                    "match": entry.get("match"),
                    "url": entry.get("url"),
                    "image": entry.get("image", []),
                    "spotify": sp_best,
                    "lastfm": entry,
                })
                if len(results) >= similar_limit:
                    break
                continue
            if not spotify_available:
                results.append({
                    "name": name,
                    "match": entry.get("match"),
                    "url": entry.get("url"),
                    "image": entry.get("image", []),
                    "spotify": None,
                    "lastfm": entry,
                })
                if len(results) >= similar_limit:
                    break
                continue
            async with sem_spotify:
                sp_candidates = await safe_spotify(spotify_client.search_artists(name, limit=2), [])
            if not spotify_available:
                results.append({
                    "name": name,
                    "match": entry.get("match"),
                    "url": entry.get("url"),
                    "image": entry.get("image", []),
                    "spotify": None,
                    "lastfm": entry,
                })
                if len(results) >= similar_limit:
                    break
                continue
            sp_sorted = sorted(
                sp_candidates,
                key=lambda x: (x.get("followers", {}) or {}).get("total", 0),
                reverse=True
            )
            sp_best = None
            for cand in sp_sorted:
                if not _name_matches(name, cand.get("name", "")):
                    continue
                sp_best = cand
                break
            if not sp_best and sp_sorted:
                sp_best = sp_sorted[0]
            followers = (sp_best or {}).get("followers", {}).get("total", 0)
            if followers < min_followers:
                continue
            sp_id = (sp_best or {}).get("id")
            if sp_id and sp_id in seen_ids:
                continue
            if sp_id:
                seen_ids.add(sp_id)
            results.append({
                "name": name,
                "match": entry.get("match"),
                "url": entry.get("url"),
                "image": entry.get("image", []),
                "spotify": sp_best,
                "lastfm": entry
            })
            if len(results) >= similar_limit:
                break
        return results

    main = await fetch_main()
    spotify_main = (main or {}).get("spotify") or {}
    if not spotify_main:
        normalized = _normalize_name(q)
        local_artist = (await session.exec(
            select(Artist)
            .where(
                (Artist.name.ilike(f"%{q}%")) |
                (Artist.normalized_name == normalized)
            )
            .order_by(desc(Artist.popularity))
            .limit(1)
        )).first()
        if local_artist:
            images = proxy_image_list(_parse_images_field(local_artist.images), size=512)
            spotify_main = {
                "id": local_artist.spotify_id,
                "name": local_artist.name,
                "images": images,
                "followers": {"total": local_artist.followers or 0},
                "popularity": local_artist.popularity or 0,
                "genres": _parse_genres_field(local_artist.genres),
            }
            main["spotify"] = spotify_main
    main_name = spotify_main.get("name") or q
    local_main = await get_local_artist(main_name)

    similars = await fetch_similars(main_name, local_main)

    if spotify_available:
        refresh_ids: list[str] = []
        main_spotify_id = spotify_main.get("id") if isinstance(spotify_main, dict) else None
        scheduled_expansion = False
        if main_spotify_id and (not local_main or is_stale(local_main)):
            schedule_artist_expansion(
                spotify_artist_id=main_spotify_id,
                artist_name=main_name,
                include_youtube_links=True,
            )
            scheduled_expansion = True
        local_main = await get_local_artist(main_name)
        if main_spotify_id and is_stale(local_main) and not scheduled_expansion:
            refresh_ids.append(main_spotify_id)

        for entry in similars:
            sp_id = (entry.get("spotify") or {}).get("id")
            if not sp_id:
                continue
            local_match = (await session.exec(
                select(Artist).where(Artist.spotify_id == sp_id)
            )).first()
            if not local_match:
                local_match = await get_local_artist(entry.get("name") or (entry.get("spotify") or {}).get("name") or "")
            if is_stale(local_match):
                refresh_ids.append(sp_id)

        if refresh_ids:
            unique_ids = []
            for sid in refresh_ids:
                if sid and sid not in unique_ids:
                    unique_ids.append(sid)
            for sid in unique_ids[:6]:
                asyncio.create_task(save_artist_discography(sid))

    tracks = []
    local_track_hits = await _search_local_tracks(session, q, limit=5, user_id=user_id)
    if local_track_hits:
        track_ids = [hit[0].id for hit in local_track_hits]
        track_rows = (await session.exec(
            select(Track, Artist, Album)
            .join(Artist, Track.artist_id == Artist.id)
            .outerjoin(Album, Track.album_id == Album.id)
            .where(Track.id.in_(track_ids))
        )).all()
        track_map = {row[0].id: row for row in track_rows}
        for track_id in track_ids:
            row = track_map.get(track_id)
            if not row:
                continue
            track, artist, album = row
            if _track_title_matches(q, track.name):
                tracks.append(_track_to_spotify_lite(track, artist, album))
    elif spotify_available:
        tracks = _format_tracks(await safe_spotify(spotify_client.search_tracks(q, limit=5), []))
    payload = {
        "query": q,
        "mode": "artist",
        "main": main,
        "similar": similars,
        "tracks": tracks
    }
    record_external_resolution(user_id)
    _cache_set(_artist_profile_cache, cache_key, payload)
    return payload


@router.get("/tracks-quick")
async def search_tracks_quick(
    request: Request,
    q: str = Query(..., description="Nombre de canción"),
    limit: int = Query(10, description="Número de tracks a devolver"),
    session: AsyncSession = Depends(SessionDep),
):
    """Búsqueda rápida de canciones en Spotify con sus artistas y álbum."""
    user_id = getattr(request.state, "user_id", None) if request else None
    local_track_hits = await _search_local_tracks(session, q, limit=limit, user_id=user_id)
    if local_track_hits:
        track_ids = [hit[0].id for hit in local_track_hits]
        track_rows = (await session.exec(
            select(Track, Artist, Album)
            .join(Artist, Track.artist_id == Artist.id)
            .outerjoin(Album, Track.album_id == Album.id)
            .where(Track.id.in_(track_ids))
        )).all()
        track_map = {row[0].id: row for row in track_rows}
        tracks = []
        for track_id in track_ids:
            row = track_map.get(track_id)
            if not row:
                continue
            track, artist, album = row
            tracks.append(_track_to_spotify_lite(track, artist, album))
        record_local_resolution(user_id)
        return {"query": q, "tracks": tracks}
    record_external_resolution(user_id)
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return {"query": q, "tracks": []}
    try:
        tracks = await spotify_client.search_tracks(q, limit=limit)
        artist_entries = []
        for track in tracks or []:
            for artist in track.get("artists", []) or []:
                artist_entries.append({
                    "spotify": artist,
                    "lastfm": {},
                    "name": artist.get("name"),
                })
        if artist_entries:
            await _materialize_spotify_entries(session, artist_entries, schedule_limit=5)
        return {"query": q, "tracks": _format_tracks(tracks)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error searching tracks: {exc}")


@router.get("/metrics")
def search_metrics() -> dict:
    """Search resolution metrics snapshot (local vs external)."""
    return fetch_search_metrics()

@router.get("/advanced")
async def advanced_search(
    request: Request,
    query: str = Query(None, description="Search query"),
    search_in: str = Query("all", description="Search in: artists, albums, tracks, or all"),
    min_rating: int = Query(None, description="Minimum rating (0-5)"),
    is_favorite: bool = Query(None, description="Favorite tracks only"),
    tag: str = Query(None, description="Filter by tag name"),
    limit: int = Query(20, description="Number of results to return"),
    session: AsyncSession = Depends(SessionDep),
):
    """Advanced search across artists, albums, and tracks with filtering."""
    results = {
        "artists": [],
        "albums": [],
        "tracks": []
    }
    user_id = getattr(request.state, "user_id", None) if request else None

    if search_in in ["artists", "all"] and query:
        artist_hits = await _search_local_artists(session, query, limit=limit, user_id=user_id)
        results["artists"] = [artist.dict() for artist, _ in artist_hits[:limit]]

    if search_in in ["albums", "all"] and query:
        album_hits = await _search_local_albums(session, query, limit=limit, user_id=user_id)
        results["albums"] = [album.dict() for album, _ in album_hits[:limit]]

    if search_in in ["tracks", "all"]:
        track_query = select(Track)

        if query:
            track_hits = await _search_local_tracks(session, query, limit=limit * 4, user_id=user_id)
            track_ids = [track.id for track, _ in track_hits]
            if track_ids:
                track_query = track_query.where(Track.id.in_(track_ids))
            else:
                track_query = track_query.where(False)

        if min_rating is not None and min_rating >= 0:
            track_query = track_query.where(Track.user_score >= min_rating)

        if is_favorite is not None:
            track_query = track_query.where(Track.is_favorite == is_favorite)

        if tag:
            tag_obj = (await session.exec(select(Tag).where(Tag.name == tag))).first()
            if tag_obj:
                track_tags = (await session.exec(
                    select(TrackTag).where(TrackTag.tag_id == tag_obj.id)
                )).all()
                track_ids = [tt.track_id for tt in track_tags]
                track_query = track_query.where(Track.id.in_(track_ids))

        track_results = (await session.exec(track_query.limit(limit))).all()
        results["tracks"] = [track.dict() for track in track_results]

    return {
        "query": query,
        "search_in": search_in,
        "filters": {
            "min_rating": min_rating,
            "is_favorite": is_favorite,
            "tag": tag
        },
        "results": results
    }

@router.get("/fuzzy")
def fuzzy_search(
    query: str = Query(..., description="Fuzzy search query"),
    search_in: str = Query("all", description="Search in: artists, albums, tracks, or all"),
    limit: int = Query(10, description="Number of results to return")
):
    """Fuzzy search using ILIKE for case-insensitive partial matching."""
    session = get_session()
    try:
        results = {
            "artists": [],
            "albums": [],
            "tracks": []
        }

        # Fuzzy search in artists
        if search_in in ["artists", "all"]:
            artist_results = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["artists"] = [artist.dict() for artist in artist_results]

        # Fuzzy search in albums
        if search_in in ["albums", "all"]:
            album_results = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["albums"] = [album.dict() for album in album_results]

        # Fuzzy search in tracks
        if search_in in ["tracks", "all"]:
            track_results = session.exec(
                select(Track)
                .where(Track.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["tracks"] = [track.dict() for track in track_results]

        return {
            "query": query,
            "search_in": search_in,
            "results": results
        }
    finally:
        session.close()

@router.get("/by-tags")
def search_by_tags(
    tags: str = Query(..., description="Comma-separated tag names"),
    search_in: str = Query("tracks", description="Search in: tracks only for now"),
    limit: int = Query(20, description="Number of results to return")
):
    """Search by multiple tags (AND logic - tracks must have ALL specified tags)."""
    session = get_session()
    try:
        tag_names = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Get tag objects
        tag_objects = []
        for tag_name in tag_names:
            tag = session.exec(select(Tag).where(Tag.name == tag_name)).first()
            if tag:
                tag_objects.append(tag)

        if not tag_objects:
            return {"tags": tag_names, "results": []}

        # Find tracks that have ALL the specified tags
        # Start with tracks that have the first tag
        first_tag = tag_objects[0]
        track_tags = session.exec(
            select(TrackTag).where(TrackTag.tag_id == first_tag.id)
        ).all()
        track_ids = [tt.track_id for tt in track_tags]

        # For additional tags, filter down the track IDs
        for tag in tag_objects[1:]:
            tag_track_tags = session.exec(
                select(TrackTag).where(TrackTag.tag_id == tag.id)
            ).all()
            tag_track_ids = [tt.track_id for tt in tag_track_tags]
            track_ids = list(set(track_ids) & set(tag_track_ids))  # Intersection

            if not track_ids:
                break

        if not track_ids:
            return {"tags": tag_names, "results": []}

        # Get the tracks
        tracks = session.exec(
            select(Track).where(Track.id.in_(track_ids)).limit(limit)
        ).all()

        return {
            "tags": tag_names,
            "results": [track.dict() for track in tracks]
        }
    finally:
        session.close()

@router.get("/by-rating-range")
def search_by_rating_range(
    min_rating: int = Query(0, description="Minimum rating (0-5)"),
    max_rating: int = Query(5, description="Maximum rating (0-5)"),
    limit: int = Query(20, description="Number of results to return")
):
    """Search tracks by rating range."""
    session = get_session()
    try:
        if min_rating < 0 or min_rating > 5 or max_rating < 0 or max_rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

        if min_rating > max_rating:
            min_rating, max_rating = max_rating, min_rating  # Swap if reversed

        tracks = session.exec(
            select(Track)
            .where(
                and_(
                    Track.user_score >= min_rating,
                    Track.user_score <= max_rating
                )
            )
            .order_by(Track.user_score.desc())
            .limit(limit)
        ).all()

        return {
            "min_rating": min_rating,
            "max_rating": max_rating,
            "results": [track.dict() for track in tracks]
        }
    finally:
        session.close()

@router.get("/combined")
def combined_search(
    query: str = Query(..., description="Search query"),
    include_artists: bool = Query(True, description="Include artists in search"),
    include_albums: bool = Query(True, description="Include albums in search"),
    include_tracks: bool = Query(True, description="Include tracks in search"),
    limit: int = Query(30, description="Total number of results to return")
):
    """Combined search across all content types with single query."""
    session = get_session()
    try:
        combined_results = []

        # Search artists
        if include_artists:
            artists = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for artist in artists:
                combined_results.append({
                    "type": "artist",
                    "data": artist.dict()
                })

        # Search albums
        if include_albums:
            albums = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for album in albums:
                combined_results.append({
                    "type": "album",
                    "data": album.dict()
                })

        # Search tracks
        if include_tracks:
            tracks = session.exec(
                select(Track)
                .where(Track.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for track in tracks:
                combined_results.append({
                    "type": "track",
                    "data": track.dict()
                })

        # Sort by some relevance (simple approach)
        combined_results.sort(key=lambda x: x["data"]["name"].lower().count(query.lower()), reverse=True)

        return {
            "query": query,
            "total_results": len(combined_results),
            "results": combined_results[:limit]
        }
    finally:
        session.close()
