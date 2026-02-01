"""
Tags and play history endpoints.
"""

from fastapi import APIRouter, Path, HTTPException, Query

from ..crud import (
    create_tag, get_tag_by_id, get_all_tags,
    add_tag_to_track, remove_tag_from_track, get_track_tags,
    record_play, get_play_history, get_recent_plays, get_most_played_tracks
)

router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("/create")
def create_new_tag(name: str = Query(..., description="Tag name"), color: str = Query("#666666", description="Tag color")):
    """Create a new tag."""
    try:
        tag = create_tag(name, color)
        return {
            "message": "Tag created",
            "tag": tag.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/")
def list_tags():
    """List all tags."""
    tags = get_all_tags()
    return [tag.dict() for tag in tags]


@router.get("/{tag_id}")
def get_tag(tag_id: int = Path(..., description="Tag ID")):
    """Get tag by ID."""
    tag = get_tag_by_id(tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag.dict()


@router.post("/tracks/{track_id}/add")
def add_tag_to_track_endpoint(
    track_id: int = Path(..., description="Track ID"),
    tag_id: int = Query(..., description="Tag ID")
):
    """Add tag to track."""
    try:
        track_tag = add_tag_to_track(track_id, tag_id)
        if not track_tag:
            raise HTTPException(status_code=404, detail="Track or tag not found")
        return {
            "message": "Tag added to track",
            "track_tag": track_tag.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tracks/{track_id}/remove")
def remove_tag_from_track_endpoint(
    track_id: int = Path(..., description="Track ID"),
    tag_id: int = Query(..., description="Tag ID")
):
    """Remove tag from track."""
    try:
        success = remove_tag_from_track(track_id, tag_id)
        if not success:
            raise HTTPException(status_code=404, detail="Track tag relationship not found")
        return {
            "message": "Tag removed from track"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracks/{track_id}")
def get_track_tags_endpoint(track_id: int = Path(..., description="Track ID")):
    """Get all tags for a track."""
    tags = get_track_tags(track_id)
    return [tag.dict() for tag in tags]

# Play History Endpoints


@router.post("/play/{track_id}")
def record_play_endpoint(track_id: int = Path(..., description="Track ID")):
    """Record a track play."""
    try:
        play_history = record_play(track_id)
        if not play_history:
            raise HTTPException(status_code=404, detail="Track not found")
        return {
            "message": "Play recorded",
            "play_history": play_history.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{track_id}")
def get_track_play_history(track_id: int = Path(..., description="Track ID"), limit: int = Query(10, description="Limit")):
    """Get play history for a track."""
    history = get_play_history(track_id, limit)
    return [play.dict() for play in history]


@router.get("/recent")
def get_recent_plays_endpoint(limit: int = Query(20, description="Limit")):
    """Get most recent plays."""
    plays = get_recent_plays(limit)
    return [play.dict() for play in plays]


@router.get("/most-played")
def get_most_played_tracks_endpoint(limit: int = Query(10, description="Limit")):
    """Get most played tracks."""
    tracks = get_most_played_tracks(limit)
    return tracks
