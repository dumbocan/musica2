"""Artist profile search endpoints."""

import ast
import json
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Query, Depends, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.config import settings
from ...core.db import SessionDep
from ...core.lastfm import lastfm_client
from ...core.spotify import spotify_client
from ...models.base import Artist, Album, Track

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


def _parse_json_list(raw: Any) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return []


def _artist_to_spotify(local_artist: Artist) -> Dict[str, Any]:
    images = _parse_json_list(local_artist.images)
    genres = _parse_json_list(local_artist.genres)
    return {
        "id": local_artist.spotify_id or str(local_artist.id),
        "name": local_artist.name,
        "images": images,
        "followers": {"total": local_artist.followers or 0},
        "popularity": local_artist.popularity or 0,
        "genres": genres,
        "external_urls": {"spotify": f"https://open.spotify.com/artist/{local_artist.spotify_id}"}
        if local_artist.spotify_id
        else {},
    }


def _local_lastfm_block(local_artist: Optional[Artist]) -> Dict[str, Any]:
    if not local_artist:
        return {}
    return {
        "summary": local_artist.bio_summary or "",
        "content": local_artist.bio_content or "",
        "stats": {"listeners": 0, "playcount": 0},
        "tags": [],
        "images": [],
    }


@router.get("")
@router.get("/")
async def search_artist_profile(
    request: Request,
    q: Optional[str] = Query(default=None, min_length=1, max_length=200, description="Artist or track query"),
    artist_name: Optional[str] = Query(default=None, min_length=1, max_length=200, description="Legacy alias for artist query"),
    similar_limit: int = Query(default=10, ge=1, le=30),
    min_followers: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Return profile + related artists + tracks for Search page. BD-first policy."""
    incoming_query = q if q is not None else artist_name
    if not incoming_query:
        return {"query": "", "mode": "artist", "main": None, "similar": [], "tracks": []}
    query = incoming_query.strip()
    if not query:
        return {"query": incoming_query, "mode": "artist", "main": None, "similar": [], "tracks": []}

    # BD-FIRST: First, search for local tracks (in case query is a song title)
    tracks_rows = (await session.exec(
        select(Track, Artist, Album)
        .join(Artist, Track.artist_id == Artist.id)
        .join(Album, Track.album_id == Album.id, isouter=True)
        .where(Track.name.ilike(f"%{query}%"))
        .order_by(Track.popularity.desc(), Track.id.desc())
        .limit(15)
    )).all()

    # Extract the main artist from tracks if tracks are found
    main_artist_from_tracks: Optional[Artist] = None
    if tracks_rows:
        # Count tracks per artist (use most frequent artist as main)
        artist_track_count: Dict[int, int] = {}
        for track, artist, album in tracks_rows:
            if artist.id not in artist_track_count:
                artist_track_count[artist.id] = 0
            artist_track_count[artist.id] += 1
        if artist_track_count:
            # Use artist with most tracks matching the query
            main_artist_id = max(artist_track_count, key=artist_track_count.get)
            main_artist_from_tracks = next(
                (artist for track, artist, album in tracks_rows if artist.id == main_artist_id),
                None
            )

    # main artist from DB (by name match)
    main_artist = (await session.exec(
        select(Artist)
        .where(Artist.name.ilike(f"%{query}%"))
        .order_by(Artist.followers.desc(), Artist.popularity.desc())
        .limit(1)
    )).first()

    # Use artist from tracks if available, otherwise use name-matched artist
    main_artist = main_artist_from_tracks or main_artist

    spotify_main: Optional[Dict[str, Any]] = _artist_to_spotify(main_artist) if main_artist else None
    lastfm_main: Dict[str, Any] = _local_lastfm_block(main_artist)

    # if no DB match, fallback to Spotify search
    if not spotify_main:
        try:
            artists = await spotify_client.search_artists(query, limit=3)
            if artists:
                spotify_main = artists[0]
        except Exception:
            spotify_main = None

    main_name = (spotify_main or {}).get("name") or (main_artist.name if main_artist else query)

    # enrich bio from Last.fm when available
    if settings.LASTFM_API_KEY:
        try:
            lfm = await lastfm_client.get_artist_info(main_name)
            if lfm:
                if not lastfm_main.get("summary"):
                    lastfm_main = lfm
                else:
                    # Keep local summary if present, fill the rest from Last.fm.
                    merged = dict(lfm)
                    merged["summary"] = lastfm_main.get("summary") or lfm.get("summary", "")
                    merged["content"] = lastfm_main.get("content") or lfm.get("content", "")
                    lastfm_main = merged
        except Exception:
            pass

    # Build tracks list from already-fetched local tracks
    tracks: list[dict[str, Any]] = []
    for track, artist, album in tracks_rows:
        tracks.append({
            "id": track.spotify_id or str(track.id),
            "name": track.name,
            "duration_ms": track.duration_ms or 0,
            "popularity": track.popularity or 0,
            "preview_url": track.preview_url,
            "external_urls": {"spotify": f"https://open.spotify.com/track/{track.spotify_id}"} if track.spotify_id else {},
            "artists": [{"id": artist.spotify_id or str(artist.id), "name": artist.name}],
            "album": {
                "id": album.spotify_id if album else None,
                "name": album.name if album else "",
                "images": _parse_json_list(album.images) if album else [],
            },
        })

    if not tracks:
        try:
            tracks = await spotify_client.search_tracks(query, limit=10)
        except Exception:
            tracks = []

    # similar artists
    similar: list[dict[str, Any]] = []
    if settings.LASTFM_API_KEY:
        try:
            lfm_similar = await lastfm_client.get_similar_artists(main_name, limit=similar_limit + 5)
        except Exception:
            lfm_similar = []
        for entry in lfm_similar:
            name = entry.get("name")
            if not name:
                continue
            local = (await session.exec(
                select(Artist).where(Artist.name.ilike(f"%{name}%")).order_by(Artist.followers.desc()).limit(1)
            )).first()
            spotify_obj = _artist_to_spotify(local) if local else None
            if not spotify_obj:
                try:
                    cands = await spotify_client.search_artists(name, limit=2)
                    spotify_obj = cands[0] if cands else None
                except Exception:
                    spotify_obj = None
            followers = ((spotify_obj or {}).get("followers") or {}).get("total", 0)
            if min_followers and followers < min_followers:
                continue
            similar.append({
                "name": name,
                "url": entry.get("url"),
                "image": entry.get("image", []),
                "spotify": spotify_obj,
                "lastfm": entry,
            })
            if len(similar) >= similar_limit:
                break

    # local fallback if no Last.fm similar
    if not similar and main_artist:
        local_similar = (await session.exec(
            select(Artist)
            .where(Artist.id != main_artist.id)
            .where(Artist.name.ilike(f"%{main_artist.name.split(' ')[0]}%"))
            .order_by(Artist.followers.desc(), Artist.popularity.desc())
            .limit(similar_limit)
        )).all()
        similar = [{"name": a.name, "spotify": _artist_to_spotify(a), "lastfm": {}} for a in local_similar]

    main_block = {"spotify": spotify_main, "lastfm": lastfm_main}
    return {"query": query, "mode": "artist", "main": main_block, "similar": similar, "tracks": tracks}


@router.get("/artist/{artist_id}")
async def get_artist_profile_by_id(
    artist_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist profile by local ID."""
    # TODO: Implement get artist profile by ID
    return {"artist": None, "profile": {}, "artist_id": artist_id}


@router.get("/artist/{artist_id}/similar")
async def get_artist_similar(
    artist_id: int,
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get similar artists."""
    # TODO: Implement similar artists
    return {"similar_artists": [], "artist_id": artist_id}


@router.get("/{artist_id}")
async def get_artist_by_id(
    artist_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist profile by ID."""
    # TODO: Implement get_artist_by_id
    return {"artist": None, "profile": {}, "artist_id": artist_id}


@router.get("/{artist_id}/similar")
async def get_artist_similar_v2(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get similar artists."""
    # TODO: Implement similar artists logic
    return {"similar_artists": [], "artist_id": artist_id}
