"""
Track endpoints: list, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.db import get_session
from ..models.base import Track, Artist
from ..crud import update_track_lastfm
from ..core.lastfm import lastfm_client
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
