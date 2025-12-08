"""
Track endpoints: list, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.db import get_session
from ..models.base import Track, Artist
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
