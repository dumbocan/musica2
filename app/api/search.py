"""
Advanced search endpoints.
"""

import asyncio
import json
import logging
import time
import ast
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlmodel import select, and_
from sqlalchemy import desc, or_

from ..core.config import settings
from ..core.db import get_session, SessionDep
from ..core.image_proxy import proxy_image_list
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from ..core.time_utils import utc_now
from ..models.base import Artist, Album, Track, Tag, TrackTag
from ..services.library_expansion import save_artist_discography
from ..crud import normalize_name
from sqlmodel.ext.asyncio.session import AsyncSession

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
    q: str = Query(..., description="Query o tag principal"),
    limit: int = Query(20, description="Máximo artistas a traer de Spotify (no usado, compatibilidad)"),
    page: int = Query(0, description="Página de resultados (0-index)"),
    lastfm_limit: int = Query(60, description="Máximo artistas por tag Last.fm"),
    related_limit: int = Query(8, description="Límite de similares Last.fm"),
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

    genre_keys = _infer_genre_keywords(q)
    timeout_spotify = 4.0
    timeout_lastfm = 6.0
    timeout_related = 5.0

    tracks_task = asyncio.create_task(
        _safe_timed(spotify_client.search_tracks(q, limit=5), [], timeout_spotify)
    )

    # Primero intentamos desde DB
    db_artists = []
    db_artists = (await session.exec(
        select(Artist).where(Artist.name.ilike(f"%{q}%")).limit(limit)
    )).all()

    if db_artists:
        tracks = _format_tracks(await tracks_task)
        artists_for_grid = []
        for a in db_artists:
            data = a.dict()
            # Rewrite images to proxy
            try:
                import json
                imgs = json.loads(a.images) if a.images else []
            except Exception:
                imgs = []
            data["images"] = proxy_image_list(imgs, size=384)
            artists_for_grid.append(data)
        payload = {
            "query": q,
            "page": max(page, 0),
            "limit": limit,
            "has_more_artists": False,
            "has_more_lastfm": False,
            "main": None,
            "artists": artists_for_grid,
            "related": [],
            "tracks": tracks,
            "lastfm_top": []
        }
        _cache_set(_orchestrated_cache, cache_key, payload)
        return payload

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

    if not settings.LASTFM_API_KEY:
        raise HTTPException(status_code=400, detail="Se requiere LASTFM_API_KEY para este endpoint")

    local_cache: dict[str, Artist | None] = {}

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
        local_cache[normalized] = local
        return local

    def is_stale(artist: Artist | None) -> bool:
        if not artist:
            return True
        stale_at = artist.last_refreshed_at
        return not stale_at or (utc_now() - stale_at) > timedelta(days=ARTIST_REFRESH_DAYS)

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

    async def fetch_main():
        local_artist = await get_local_artist(q)
        sp_best = _artist_to_spotify_dict(local_artist) if local_artist else None
        lfm = _artist_to_lastfm_dict(local_artist) if local_artist else {}
        needs_lastfm = not (lfm.get("summary") or lfm.get("content"))
        if needs_lastfm:
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

    async def fetch_similars(main_name: str):
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

    tracks_task = asyncio.create_task(
        safe_spotify(spotify_client.search_tracks(q, limit=5), [])
    )
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

    similars = await fetch_similars(main_name)

    if spotify_available:
        refresh_ids: list[str] = []
        main_spotify_id = spotify_main.get("id") if isinstance(spotify_main, dict) else None
        local_main = await get_local_artist(main_name)
        if main_spotify_id and is_stale(local_main):
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

    tracks = _format_tracks(await tracks_task)
    payload = {
        "query": q,
        "mode": "artist",
        "main": main,
        "similar": similars,
        "tracks": tracks
    }
    _cache_set(_artist_profile_cache, cache_key, payload)
    return payload


@router.get("/tracks-quick")
async def search_tracks_quick(
    q: str = Query(..., description="Nombre de canción"),
    limit: int = Query(10, description="Número de tracks a devolver")
):
    """Búsqueda rápida de canciones en Spotify con sus artistas y álbum."""
    try:
        tracks = await spotify_client.search_tracks(q, limit=limit)
        return {"query": q, "tracks": _format_tracks(tracks)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error searching tracks: {exc}")

@router.get("/advanced")
def advanced_search(
    query: str = Query(None, description="Search query"),
    search_in: str = Query("all", description="Search in: artists, albums, tracks, or all"),
    min_rating: int = Query(None, description="Minimum rating (0-5)"),
    is_favorite: bool = Query(None, description="Favorite tracks only"),
    tag: str = Query(None, description="Filter by tag name"),
    limit: int = Query(20, description="Number of results to return")
):
    """Advanced search across artists, albums, and tracks with filtering."""
    session = get_session()
    try:
        results = {
            "artists": [],
            "albums": [],
            "tracks": []
        }

        # Search in artists
        if search_in in ["artists", "all"] and query:
            artist_results = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["artists"] = [artist.dict() for artist in artist_results]

        # Search in albums
        if search_in in ["albums", "all"] and query:
            album_results = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["albums"] = [album.dict() for album in album_results]

        # Search in tracks with advanced filtering
        if search_in in ["tracks", "all"]:
            track_query = select(Track)

            # Apply search query if provided
            if query:
                track_query = track_query.where(Track.name.ilike(f"%{query}%"))

            # Apply rating filter
            if min_rating is not None and min_rating >= 0:
                track_query = track_query.where(Track.user_score >= min_rating)

            # Apply favorite filter
            if is_favorite is not None:
                track_query = track_query.where(Track.is_favorite == is_favorite)

            # Apply tag filter
            if tag:
                # Get tag ID first
                tag_obj = session.exec(select(Tag).where(Tag.name == tag)).first()
                if tag_obj:
                    # Get track IDs with this tag
                    track_tags = session.exec(
                        select(TrackTag).where(TrackTag.tag_id == tag_obj.id)
                    ).all()
                    track_ids = [tt.track_id for tt in track_tags]
                    track_query = track_query.where(Track.id.in_(track_ids))

            track_results = session.exec(track_query.limit(limit)).all()
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
    finally:
        session.close()

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
