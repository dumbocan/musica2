"""
Track endpoints: list, etc.
"""

from typing import List
import re
from pathlib import Path as FsPath

from fastapi import APIRouter, Path, HTTPException, Query
from sqlalchemy import func, case, or_, exists, and_

from ..core.db import get_session
from ..models.base import Track, Artist, Album, YouTubeDownload
from ..crud import update_track_lastfm, update_track_spotify_data
from ..core.lastfm import lastfm_client
from ..core.spotify import spotify_client
from sqlmodel import select

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.get("/")
def get_tracks() -> List[Track]:
    """Get all saved tracks from DB."""
    with get_session() as session:
        tracks = session.exec(select(Track)).all()
    return tracks


@router.get("/overview")
def get_tracks_overview(
    verify_files: bool = Query(False, description="Check file existence on disk"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(200, ge=1, le=1000, description="Pagination limit"),
    include_summary: bool = Query(True, description="Include aggregate summary counts"),
    after_id: int | None = Query(None, ge=0, description="Return tracks after this ID"),
    filter: str | None = Query(None, description="Filter: withLink, noLink, hasFile, missingFile"),
    search: str | None = Query(None, description="Search by track, artist, or album"),
) -> dict:
    """
    Return tracks with artist, album, cached YouTube link/status and local file info.
    Useful for the frontend "Tracks" page so users can see what is ready for streaming/downloading.
    """
    def normalize_search(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def normalized_column(column):
        return func.regexp_replace(func.lower(column), "[^a-z0-9]+", " ", "g")

    summary = None
    if filter == "all":
        filter = None
    filter = filter or None
    if filter and filter not in {"withLink", "noLink", "hasFile", "missingFile"}:
        raise HTTPException(status_code=400, detail="Invalid filter value")
    search_term = normalize_search(search) if search else ""
    is_filtered_query = bool(filter or search_term)
    if include_summary:
        with get_session() as session:
            total, with_link, with_file = session.exec(
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
                .outerjoin(YouTubeDownload, YouTubeDownload.spotify_track_id == Track.spotify_id)
            ).one()
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

    with get_session() as session:
        base_query = (
            select(Track, Artist, Album)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .order_by(Track.id.asc())
        )

        if search_term:
            pattern = f"%{search_term}%"
            base_query = base_query.where(
                or_(
                    normalized_column(Track.name).ilike(pattern),
                    normalized_column(Artist.name).ilike(pattern),
                    normalized_column(Album.name).ilike(pattern),
                )
            )

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
            if filter == "withLink":
                base_query = base_query.where(link_exists)
            elif filter == "noLink":
                base_query = base_query.where(~link_exists)
            elif filter == "hasFile":
                base_query = base_query.where(file_exists)
            elif filter == "missingFile":
                base_query = base_query.where(~file_exists)

        if after_id is not None:
            base_query = base_query.where(Track.id > after_id)
        else:
            base_query = base_query.offset(offset)
        rows = session.exec(base_query.limit(limit + 1)).all()

        filtered_total = None
        if is_filtered_query:
            count_query = select(func.count(Track.id)).join(Artist, Artist.id == Track.artist_id).outerjoin(Album, Album.id == Track.album_id)
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
                if filter == "withLink":
                    count_query = count_query.where(link_exists)
                elif filter == "noLink":
                    count_query = count_query.where(~link_exists)
                elif filter == "hasFile":
                    count_query = count_query.where(file_exists)
                elif filter == "missingFile":
                    count_query = count_query.where(~file_exists)
            filtered_total = session.exec(count_query).one()

    raw_rows = rows
    has_more = len(raw_rows) > limit
    track_rows = raw_rows[:limit]
    spotify_ids = [track.spotify_id for track, _, _ in track_rows if track.spotify_id]
    downloads = []
    if spotify_ids:
        with get_session() as session:
            downloads = session.exec(
                select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(spotify_ids))
            ).all()

    download_map: dict[str, YouTubeDownload] = {}
    for download in downloads:
        existing = download_map.get(download.spotify_track_id)
        if not existing:
            download_map[download.spotify_track_id] = download
            continue
        existing_has_video = bool(existing.youtube_video_id)
        new_has_video = bool(download.youtube_video_id)
        if new_has_video and not existing_has_video:
            download_map[download.spotify_track_id] = download
            continue
        if new_has_video == existing_has_video:
            if download.updated_at and existing.updated_at and download.updated_at > existing.updated_at:
                download_map[download.spotify_track_id] = download

    items = []
    for track, artist, album in track_rows:
        download = download_map.get(track.spotify_id) if track.spotify_id else None
        youtube_video_id = (download.youtube_video_id or None) if download else None
        youtube_status = download.download_status if download else None
        youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
        file_path = download.download_path if download else None
        if file_path:
            file_exists = FsPath(file_path).exists() if verify_files else True
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
            "youtube_status": youtube_status,
            "youtube_url": youtube_url,
            "local_file_path": file_path,
            "local_file_exists": file_exists,
        })

    next_after = track_rows[-1][0].id if track_rows else after_id
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
        response["filtered_total"] = int(filtered_total or 0)
    return response


@router.get("/id/{track_id}")
def get_track(track_id: int = Path(..., description="Local track ID")) -> Track:
    """Get single track by local ID."""
    with get_session() as session:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
    return track


@router.post("/enrich/{track_id}")
async def enrich_track_with_lastfm(track_id: int = Path(..., description="Local track ID")):
    """Enrich track with Last.fm playcount/listeners."""
    with get_session() as session:
        # Get track with artist
        track = session.exec(
            select(Track).join(Artist).where(Track.id == track_id)
        ).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        artist_name = track.artist.name
        track_name = track.name

    # Fetch from Last.fm
    lastfm_data = await lastfm_client.get_track_info(artist_name, track_name)
    listeners = lastfm_data['listeners']
    playcount = lastfm_data['playcount']

    # Update DB
    updated_track = update_track_lastfm(track_id, listeners, playcount)
    return {"message": f"Track enriched: playcount={playcount}, listeners={listeners}", "track": updated_track}


@router.post("/bulk-enrich-lastfm")
async def bulk_enrich_tracks_lastfm(limit: int = 50):
    """Bulk enrich tracks without Last.fm data."""
    from app.crud import get_artist_by_spotify_id

    with get_session() as session:
        # Get tracks that don't have Last.fm data yet
        tracks_to_enrich = session.exec(
            select(Track).join(Artist).where(
                (Track.lastfm_listeners.is_(None)) |
                (Track.lastfm_listeners == 0)
            ).limit(limit)
        ).all()

        if not tracks_to_enrich:
            return {"message": "No tracks need enrichment", "processed": 0}

    enriched_count = 0

    for i, track in enumerate(tracks_to_enrich):
        try:
            # Get track with artist
            with get_session() as session:
                track_with_artist = session.exec(
                    select(Track).join(Artist).where(Track.id == track.id)
                ).first()

                if not track_with_artist:
                    continue

                artist_name = track_with_artist.artist.name
                track_name = track_with_artist.name

                # Fetch from Last.fm
                lastfm_data = await lastfm_client.get_track_info(artist_name, track_name)
                listeners = lastfm_data['listeners']
                playcount = lastfm_data['playcount']

                # Update DB
                update_track_lastfm(track.id, listeners, playcount)
                enriched_count += 1

                # Log progress every 10 tracks
                if (i + 1) % 10 == 0:
                    print(f"Enriched {i + 1}/{len(tracks_to_enrich)} tracks...")

        except Exception as e:
            print(f"Error enriching track {track.name}: {e}")
            continue

    return {
        "message": f"Bulk enrichment completed",
        "processed": enriched_count,
        "total_found": len(tracks_to_enrich)
    }


@router.post("/enrich-spotify/{track_id}")
async def enrich_track_with_spotify(track_id: int = Path(..., description="Local track ID")):
    """Enrich track with Spotify popularity and preview_url."""
    from app.crud import update_track_spotify_data

    with get_session() as session:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        if not track.spotify_id:
            raise HTTPException(status_code=400, detail="Track has no Spotify ID")

    # Get fresh Spotify data
    spotify_data = await spotify_client.get_track(track.spotify_id)
    if not spotify_data:
        raise HTTPException(status_code=404, detail="Track not found on Spotify")

    # Update track with Spotify data
    updated_track = update_track_spotify_data(track_id, spotify_data)

    return {
        "message": "Track enriched with Spotify data",
        "track_id": track_id,
        "spotify_popularity": spotify_data.get('popularity'),
        "has_preview": bool(spotify_data.get('preview_url'))
    }


@router.post("/bulk-enrich-spotify")
async def bulk_enrich_tracks_spotify(limit: int = 20):
    """Bulk enrich tracks with missing Spotify data (popularity, preview_url)."""
    from app.crud import update_track_spotify_data

    with get_session() as session:
        # Get tracks with Spotify ID but missing popularity or preview_url
        tracks_to_enrich = session.exec(
            select(Track).where(
                Track.spotify_id.is_not(None),
                Track.spotify_id != '',
                (
                    (Track.popularity.is_(None)) |
                    (Track.popularity == 0) |
                    (Track.preview_url.is_(None)) |
                    (Track.preview_url == '')
                )
            ).limit(limit)
        ).all()

        if not tracks_to_enrich:
            return {"message": "No tracks need Spotify enrichment", "processed": 0}

    enriched_count = 0

    for i, track in enumerate(tracks_to_enrich):
        try:
            # Get fresh Spotify data
            spotify_data = await spotify_client.get_track(track.spotify_id)
            if spotify_data:
                # Update track with Spotify data
                update_track_spotify_data(track.id, spotify_data)
                enriched_count += 1

                # Log progress every 5 tracks
                if (i + 1) % 5 == 0:
                    print(f"Enriched {i + 1}/{len(tracks_to_enrich)} tracks with Spotify data...")

        except Exception as e:
            print(f"Error enriching track {track.name}: {e}")
            continue

    return {
        "message": "Bulk Spotify enrichment completed",
        "processed": enriched_count,
        "total_found": len(tracks_to_enrich)
    }
