"""
Smart playlist generation endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from ..crud import (
    generate_top_rated_playlist, generate_most_played_playlist,
    generate_favorites_playlist, generate_recently_played_playlist,
    generate_by_tag_playlist, generate_discover_weekly_playlist
)

router = APIRouter(prefix="/smart-playlists", tags=["smart-playlists"])


@router.post("/top-rated")
def create_top_rated_playlist(
    user_id: int = Query(1, description="User ID"),
    name: str = Query("Top Rated", description="Playlist name"),
    limit: int = Query(20, description="Number of tracks")
):
    """Generate a playlist of top rated tracks."""
    try:
        playlist = generate_top_rated_playlist(user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail="No rated tracks found")
        return {
            "message": "Top rated playlist generated",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/most-played")
def create_most_played_playlist(
    user_id: int = Query(1, description="User ID"),
    name: str = Query("Most Played", description="Playlist name"),
    limit: int = Query(20, description="Number of tracks")
):
    """Generate a playlist of most played tracks."""
    try:
        playlist = generate_most_played_playlist(user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail="No play history found")
        return {
            "message": "Most played playlist generated",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/favorites")
def create_favorites_playlist(
    user_id: int = Query(1, description="User ID"),
    name: str = Query("Favorites", description="Playlist name"),
    limit: int = Query(50, description="Number of tracks")
):
    """Generate a playlist of favorite tracks."""
    try:
        playlist = generate_favorites_playlist(user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail="No favorite tracks found")
        return {
            "message": "Favorites playlist generated",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recently-played")
def create_recently_played_playlist(
    user_id: int = Query(1, description="User ID"),
    name: str = Query("Recently Played", description="Playlist name"),
    limit: int = Query(20, description="Number of tracks")
):
    """Generate a playlist of recently played tracks."""
    try:
        playlist = generate_recently_played_playlist(user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail="No recent plays found")
        return {
            "message": "Recently played playlist generated",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/by-tag")
def create_by_tag_playlist(
    tag_name: str = Query(..., description="Tag name"),
    user_id: int = Query(1, description="User ID"),
    name: str = Query(None, description="Playlist name (optional)"),
    limit: int = Query(30, description="Number of tracks")
):
    """Generate a playlist of tracks with specific tag."""
    try:
        playlist = generate_by_tag_playlist(tag_name, user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail=f"Tag '{tag_name}' not found or no tracks with this tag")
        return {
            "message": f"Tag playlist generated for '{tag_name}'",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/discover-weekly")
def create_discover_weekly_playlist(
    user_id: int = Query(1, description="User ID"),
    name: str = Query("Discover Weekly", description="Playlist name"),
    limit: int = Query(30, description="Number of tracks")
):
    """Generate a discover weekly style playlist."""
    try:
        playlist = generate_discover_weekly_playlist(user_id, name, limit)
        if not playlist:
            raise HTTPException(status_code=404, detail="Not enough tracks for discover weekly")
        return {
            "message": "Discover weekly playlist generated",
            "playlist": playlist.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
