"""
Favorites endpoints for artists, albums, tracks (per user).
"""

from fastapi import APIRouter, HTTPException, Path, Query
from typing import Optional
from sqlmodel import select

from ..core.db import get_session
from ..models.base import UserFavorite, FavoriteTargetType, Artist, Album, Track
from ..crud import add_favorite, remove_favorite, list_favorites

router = APIRouter(prefix="/favorites", tags=["favorites"])


def _resolve_target_ids(target_type: FavoriteTargetType, target_id: int):
    """Return a dict to set the proper FK based on type."""
    if target_type == FavoriteTargetType.ARTIST:
        return {"artist_id": target_id}
    if target_type == FavoriteTargetType.ALBUM:
        return {"album_id": target_id}
    if target_type == FavoriteTargetType.TRACK:
        return {"track_id": target_id}
    raise HTTPException(status_code=400, detail="Unsupported favorite type")


@router.post("/{target_type}/{target_id}")
def add_user_favorite(
    target_type: FavoriteTargetType = Path(..., description="artist/album/track"),
    target_id: int = Path(..., description="Local ID of target"),
    user_id: int = Query(..., description="User ID")
):
    """Mark target as favorite for the user."""
    try:
        fav = add_favorite(user_id, target_type, target_id)
        return {"message": "Favorite added", "favorite": fav.dict()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{target_type}/{target_id}")
def delete_user_favorite(
    target_type: FavoriteTargetType = Path(..., description="artist/album/track"),
    target_id: int = Path(..., description="Local ID of target"),
    user_id: int = Query(..., description="User ID")
):
    """Remove favorite mark for the user."""
    removed = remove_favorite(user_id, target_type, target_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"message": "Favorite removed"}


@router.get("/")
def list_user_favorites(
    user_id: int = Query(..., description="User ID"),
    target_type: Optional[FavoriteTargetType] = Query(None, description="Filter by type")
):
    """List favorites for a user, optionally filtered by type."""
    favorites = list_favorites(user_id, target_type)
    return [f.dict() for f in favorites]


@router.get("/full")
def list_user_favorites_full(
    user_id: int = Query(..., description="User ID"),
    target_type: Optional[FavoriteTargetType] = Query(None, description="Filter by type")
):
    """List favorites with hydrated target data."""
    with get_session() as session:
        stmt = select(UserFavorite).where(UserFavorite.user_id == user_id)
        if target_type:
            stmt = stmt.where(UserFavorite.target_type == target_type)
        favs = session.exec(stmt).all()
        results = []
        for fav in favs:
            data = fav.dict()
            if fav.artist_id:
                artist = session.get(Artist, fav.artist_id)
                data["artist"] = artist.dict() if artist else None
            if fav.album_id:
                album = session.get(Album, fav.album_id)
                data["album"] = album.dict() if album else None
            if fav.track_id:
                track = session.get(Track, fav.track_id)
                data["track"] = track.dict() if track else None
            results.append(data)
        return results
