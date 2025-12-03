"""
Track endpoints: list, etc.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException

from ..core.db import get_session
from ..models.base import Track
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
