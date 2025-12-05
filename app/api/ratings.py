"""
Ratings and favorites endpoints.
"""

from typing import List

from fastapi import APIRouter, Path, HTTPException, Query

from ..core.db import get_session
from ..models.base import Track
from ..crud import toggle_track_favorite, set_track_rating
from sqlmodel import select

router = APIRouter(prefix="/ratings", tags=["ratings"])

@router.post("/tracks/{track_id}/favorite")
def toggle_favorite(track_id: int = Path(..., description="Local track ID")):
    """Toggle favorite status for a track."""
    try:
        track = toggle_track_favorite(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        return {
            "message": "Favorite status toggled",
            "track_id": track.id,
            "is_favorite": track.is_favorite
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/tracks/{track_id}/rate")
def rate_track(
    track_id: int = Path(..., description="Local track ID"),
    rating: int = Query(..., description="Rating from 0 to 5")
):
    """Set user rating for a track (0-5)."""
    try:
        if rating < 0 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")
        track = set_track_rating(track_id, rating)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        return {
            "message": "Rating updated",
            "track_id": track.id,
            "rating": track.user_score
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/favorites")
def get_favorite_tracks():
    """Get all favorite tracks."""
    with get_session() as session:
        tracks = session.exec(select(Track).where(Track.is_favorite == True)).all()
        return [track.dict() for track in tracks]

@router.get("/top-rated")
def get_top_rated_tracks(limit: int = Query(10, description="Number of tracks to return")):
    """Get top rated tracks."""
    with get_session() as session:
        tracks = session.exec(
            select(Track)
            .where(Track.user_score > 0)
            .order_by(Track.user_score.desc())
            .limit(limit)
        ).all()
        return [track.dict() for track in tracks]
