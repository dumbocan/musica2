"""
Advanced search endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from ..core.db import get_session
from ..models.base import Artist, Album, Track, Tag, TrackTag
from sqlmodel import select, or_, and_

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/advanced")
def advanced_search(
    query: str = Query(None, description="Search query"),
    search_in: str = Query("all", description="Search in: artists, albums, tracks, or all"),
    min_rating: int = Query(None, description="Minimum rating (0-5)"),
    is_favorite: bool = Query(None, description="Favorite tracks only"),
    tag: str = Query(None, description="Filter by tag name"),
    limit: int = Query(20, description="Number of results to return")
):
    """Advanced search across artists, albums, and tracks with filtering."""
    session = get_session()
    try:
        results = {
            "artists": [],
            "albums": [],
            "tracks": []
        }

        # Search in artists
        if search_in in ["artists", "all"] and query:
            artist_results = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["artists"] = [artist.dict() for artist in artist_results]

        # Search in albums
        if search_in in ["albums", "all"] and query:
            album_results = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["albums"] = [album.dict() for album in album_results]

        # Search in tracks with advanced filtering
        if search_in in ["tracks", "all"]:
            track_query = select(Track)

            # Apply search query if provided
            if query:
                track_query = track_query.where(Track.name.ilike(f"%{query}%"))

            # Apply rating filter
            if min_rating is not None and min_rating >= 0:
                track_query = track_query.where(Track.user_score >= min_rating)

            # Apply favorite filter
            if is_favorite is not None:
                track_query = track_query.where(Track.is_favorite == is_favorite)

            # Apply tag filter
            if tag:
                # Get tag ID first
                tag_obj = session.exec(select(Tag).where(Tag.name == tag)).first()
                if tag_obj:
                    # Get track IDs with this tag
                    track_tags = session.exec(
                        select(TrackTag).where(TrackTag.tag_id == tag_obj.id)
                    ).all()
                    track_ids = [tt.track_id for tt in track_tags]
                    track_query = track_query.where(Track.id.in_(track_ids))

            track_results = session.exec(track_query.limit(limit)).all()
            results["tracks"] = [track.dict() for track in track_results]

        return {
            "query": query,
            "search_in": search_in,
            "filters": {
                "min_rating": min_rating,
                "is_favorite": is_favorite,
                "tag": tag
            },
            "results": results
        }
    finally:
        session.close()

@router.get("/fuzzy")
def fuzzy_search(
    query: str = Query(..., description="Fuzzy search query"),
    search_in: str = Query("all", description="Search in: artists, albums, tracks, or all"),
    limit: int = Query(10, description="Number of results to return")
):
    """Fuzzy search using ILIKE for case-insensitive partial matching."""
    session = get_session()
    try:
        results = {
            "artists": [],
            "albums": [],
            "tracks": []
        }

        # Fuzzy search in artists
        if search_in in ["artists", "all"]:
            artist_results = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["artists"] = [artist.dict() for artist in artist_results]

        # Fuzzy search in albums
        if search_in in ["albums", "all"]:
            album_results = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["albums"] = [album.dict() for album in album_results]

        # Fuzzy search in tracks
        if search_in in ["tracks", "all"]:
            track_results = session.exec(
                select(Track)
                .where(Track.name.ilike(f"%{query}%"))
                .limit(limit)
            ).all()
            results["tracks"] = [track.dict() for track in track_results]

        return {
            "query": query,
            "search_in": search_in,
            "results": results
        }
    finally:
        session.close()

@router.get("/by-tags")
def search_by_tags(
    tags: str = Query(..., description="Comma-separated tag names"),
    search_in: str = Query("tracks", description="Search in: tracks only for now"),
    limit: int = Query(20, description="Number of results to return")
):
    """Search by multiple tags (AND logic - tracks must have ALL specified tags)."""
    session = get_session()
    try:
        tag_names = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Get tag objects
        tag_objects = []
        for tag_name in tag_names:
            tag = session.exec(select(Tag).where(Tag.name == tag_name)).first()
            if tag:
                tag_objects.append(tag)

        if not tag_objects:
            return {"tags": tag_names, "results": []}

        # Find tracks that have ALL the specified tags
        # Start with tracks that have the first tag
        first_tag = tag_objects[0]
        track_tags = session.exec(
            select(TrackTag).where(TrackTag.tag_id == first_tag.id)
        ).all()
        track_ids = [tt.track_id for tt in track_tags]

        # For additional tags, filter down the track IDs
        for tag in tag_objects[1:]:
            tag_track_tags = session.exec(
                select(TrackTag).where(TrackTag.tag_id == tag.id)
            ).all()
            tag_track_ids = [tt.track_id for tt in tag_track_tags]
            track_ids = list(set(track_ids) & set(tag_track_ids))  # Intersection

            if not track_ids:
                break

        if not track_ids:
            return {"tags": tag_names, "results": []}

        # Get the tracks
        tracks = session.exec(
            select(Track).where(Track.id.in_(track_ids)).limit(limit)
        ).all()

        return {
            "tags": tag_names,
            "results": [track.dict() for track in tracks]
        }
    finally:
        session.close()

@router.get("/by-rating-range")
def search_by_rating_range(
    min_rating: int = Query(0, description="Minimum rating (0-5)"),
    max_rating: int = Query(5, description="Maximum rating (0-5)"),
    limit: int = Query(20, description="Number of results to return")
):
    """Search tracks by rating range."""
    session = get_session()
    try:
        if min_rating < 0 or min_rating > 5 or max_rating < 0 or max_rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

        if min_rating > max_rating:
            min_rating, max_rating = max_rating, min_rating  # Swap if reversed

        tracks = session.exec(
            select(Track)
            .where(
                and_(
                    Track.user_score >= min_rating,
                    Track.user_score <= max_rating
                )
            )
            .order_by(Track.user_score.desc())
            .limit(limit)
        ).all()

        return {
            "min_rating": min_rating,
            "max_rating": max_rating,
            "results": [track.dict() for track in tracks]
        }
    finally:
        session.close()

@router.get("/combined")
def combined_search(
    query: str = Query(..., description="Search query"),
    include_artists: bool = Query(True, description="Include artists in search"),
    include_albums: bool = Query(True, description="Include albums in search"),
    include_tracks: bool = Query(True, description="Include tracks in search"),
    limit: int = Query(30, description="Total number of results to return")
):
    """Combined search across all content types with single query."""
    session = get_session()
    try:
        combined_results = []

        # Search artists
        if include_artists:
            artists = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for artist in artists:
                combined_results.append({
                    "type": "artist",
                    "data": artist.dict()
                })

        # Search albums
        if include_albums:
            albums = session.exec(
                select(Album)
                .where(Album.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for album in albums:
                combined_results.append({
                    "type": "album",
                    "data": album.dict()
                })

        # Search tracks
        if include_tracks:
            tracks = session.exec(
                select(Track)
                .where(Track.name.ilike(f"%{query}%"))
                .limit(limit // 3 if limit > 3 else limit)
            ).all()
            for track in tracks:
                combined_results.append({
                    "type": "track",
                    "data": track.dict()
                })

        # Sort by some relevance (simple approach)
        combined_results.sort(key=lambda x: x["data"]["name"].lower().count(query.lower()), reverse=True)

        return {
            "query": query,
            "total_results": len(combined_results),
            "results": combined_results[:limit]
        }
    finally:
        session.close()
