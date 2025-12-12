"""
User learning and recommendation endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from ..core.db import get_session
from ..models.base import User, AlgorithmLearning, Artist
from ..crud import (
    record_artist_search,
    get_user_learned_artists,
    update_artist_rating,
    mark_artist_as_favorite,
    get_user_preferred_genres,
    get_recommendations_for_user
)
from sqlmodel import select

router = APIRouter(prefix="/user-learning", tags=["user-learning"])


@router.get("/record-search")
async def record_search(
    user_id: int = Query(..., description="User ID"),
    artist_name: str = Query(..., description="Artist name that was searched")
):
    """Record a user's artist search to train the algorithm."""
    try:
        success = record_artist_search(user_id, artist_name)
        return {
            "success": success,
            "message": f"Recorded search for {artist_name} by user {user_id}",
            "user_id": user_id,
            "artist_name": artist_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording search: {str(e)}")


@router.get("/learned-artists/{user_id}")
async def get_learned_artists(
    user_id: int,
    limit: int = Query(10, description="Number of artists to return")
) -> List[dict]:
    """Get artists that a user has searched for, with algorithm learning data."""
    try:
        learned_artists = get_user_learned_artists(user_id, limit)
        
        # Convert to dict and add some stats
        result = []
        for learned in learned_artists:
            # Get actual artist data if available
            with get_session() as session:
                artist = session.exec(
                    select(Artist).where(Artist.name.ilike(f"%{learned.artist_name}%"))
                ).first()
            
            result.append({
                "artist_name": learned.artist_name,
                "times_searched": learned.times_searched,
                "first_searched": learned.first_searched.isoformat() if learned.first_searched else None,
                "last_searched": learned.last_searched.isoformat() if learned.last_searched else None,
                "compatibility_score": learned.compatibility_score,
                "user_rating": learned.user_rating,
                "is_favorite": learned.is_favorite,
                "total_downloaded_tracks": learned.total_downloaded_tracks,
                "artist_info": artist.dict() if artist else None
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting learned artists: {str(e)}")


@router.post("/rate-artist")
async def rate_artist(
    user_id: int = Query(..., description="User ID"),
    artist_name: str = Query(..., description="Artist name to rate"),
    rating: int = Query(..., description="Rating 1-5", ge=1, le=5)
):
    """Rate an artist (1-5 stars) to improve algorithm recommendations."""
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        updated = update_artist_rating(user_id, artist_name, rating)
        return {
            "success": True,
            "message": f"Rating {rating} for {artist_name} recorded for user {user_id}",
            "artist_name": artist_name,
            "rating": rating,
            "new_compatibility_score": updated.compatibility_score if updated else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rating artist: {str(e)}")


@router.post("/mark-favorite")
async def mark_artist_favorite(
    user_id: int = Query(..., description="User ID"),
    artist_name: str = Query(..., description="Artist name to mark as favorite"),
    is_favorite: bool = Query(True, description="True to mark as favorite, False to unmark")
):
    """Mark or unmark an artist as favorite for a user."""
    try:
        updated = mark_artist_as_favorite(user_id, artist_name, is_favorite)
        return {
            "success": True,
            "message": f"Artist {artist_name} {'marked as favorite' if is_favorite else 'unmarked as favorite'} for user {user_id}",
            "artist_name": artist_name,
            "is_favorite": is_favorite,
            "new_compatibility_score": updated.compatibility_score if updated else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking artist as favorite: {str(e)}")


@router.get("/preferred-genres/{user_id}")
async def get_preferred_genres(user_id: int):
    """Get a user's preferred genres based on their learned artists."""
    try:
        with get_session() as session:
            # Check if user exists
            user = session.exec(select(User).where(User.id == user_id)).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        preferred_genres = get_user_preferred_genres(user_id)
        
        # Format for response
        genres_formatted = [{"genre": genre, "count": count} for genre, count in preferred_genres]
        
        return {
            "user_id": user_id,
            "preferred_genres": genres_formatted,
            "total_genres": len(preferred_genres)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting preferred genres: {str(e)}")


@router.get("/recommendations/{user_id}")
async def get_personalized_recommendations(
    user_id: int,
    limit: int = Query(10, description="Number of recommendations to return")
):
    """Get personalized artist recommendations for a user based on their learned preferences."""
    try:
        with get_session() as session:
            # Check if user exists
            user = session.exec(select(User).where(User.id == user_id)).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        recommendations = get_recommendations_for_user(user_id, limit)
        
        # Get user's learned artists for context
        learned_artists = get_user_learned_artists(user_id, limit=5)
        
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "based_on_artists": [la.artist_name for la in learned_artists],
            "recommendation_count": len(recommendations)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")


@router.get("/stats/{user_id}")
async def get_user_learning_stats(user_id: int):
    """Get statistics about a user's learning algorithm data."""
    try:
        with get_session() as session:
            # Check if user exists
            user = session.exec(select(User).where(User.id == user_id)).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            
            # Get all learned artists for this user
            learned_artists = session.exec(
                select(AlgorithmLearning)
                .where(AlgorithmLearning.user_id == user_id)
            ).all()
            
            total_artists = len(learned_artists)
            total_searches = sum(la.times_searched for la in learned_artists)
            favorites_count = sum(1 for la in learned_artists if la.is_favorite)
            rated_artists = sum(1 for la in learned_artists if la.user_rating is not None)
            
            # Calculate average compatibility score
            if learned_artists:
                avg_compatibility = sum(la.compatibility_score for la in learned_artists) / total_artists
            else:
                avg_compatibility = 0.5  # Default neutral
            
            # Most searched artist
            if learned_artists:
                most_searched = max(learned_artists, key=lambda x: x.times_searched)
                most_searched_name = most_searched.artist_name
                most_searched_count = most_searched.times_searched
            else:
                most_searched_name = None
                most_searched_count = 0
            
            return {
                "user_id": user_id,
                "total_artists_learned": total_artists,
                "total_searches": total_searches,
                "favorites_count": favorites_count,
                "rated_artists_count": rated_artists,
                "average_compatibility_score": round(avg_compatibility, 2),
                "most_searched_artist": {
                    "name": most_searched_name,
                    "count": most_searched_count
                } if most_searched_name else None,
                "algorithm_trained": total_artists > 0
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting user stats: {str(e)}")


@router.post("/reset-learning/{user_id}")
async def reset_user_learning(user_id: int):
    """Reset all algorithm learning data for a user (useful for testing)."""
    try:
        with get_session() as session:
            # Check if user exists
            user = session.exec(select(User).where(User.id == user_id)).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            
            # Delete all learning records for this user
            records = session.exec(
                select(AlgorithmLearning)
                .where(AlgorithmLearning.user_id == user_id)
            ).all()
            
            for record in records:
                session.delete(record)
            
            session.commit()
            
            return {
                "success": True,
                "message": f"Reset algorithm learning data for user {user_id}",
                "deleted_records": len(records)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting learning data: {str(e)}")
