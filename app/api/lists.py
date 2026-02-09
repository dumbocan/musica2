"""
Curated lists endpoints with caching.
Returns pre-computed lists quickly from cache.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Literal
from app.services.lists_cache import (
    get_cached_list,
    get_all_cached_lists,
    invalidate_cache,
    get_cache_status,
    LIST_CONFIGS
)

router = APIRouter(prefix="/lists", tags=["curated-lists"])


@router.get("/curated")
def get_curated_lists(
    user_id: int = Query(1, description="User ID"),
    list_type: str | None = Query(None, description="Specific list type or all if not provided"),
    force_refresh: bool = Query(False, description="Force regeneration of lists"),
):
    """
    Get curated lists from cache or generate them.
    Returns pre-computed lists for fast response.
    """
    if list_type:
        if list_type not in LIST_CONFIGS:
            raise HTTPException(status_code=400, detail=f"Invalid list_type. Must be one of: {list(list.keys())}")
        result = get_cached_list(list_type, user_id, force_refresh)
        return {
            "list_type": list_type,
            "title": LIST_CONFIGS[list_type]["description"],
            "items": result["items"],
            "total": result["total"],
            "last_updated": result["last_updated"],
            "is_cached": result["is_cached"]
        }
    else:
        # Return all lists
        all_lists = get_all_cached_lists(user_id)
        return {
            "lists": {
                key: {
                    "title": LIST_CONFIGS[key]["description"],
                    "items": value["items"],
                    "total": value["total"],
                    "last_updated": value["last_updated"],
                    "is_cached": value["is_cached"]
                }
                for key, value in all_lists.items()
            }
        }


@router.get("/curated/{list_type}")
def get_single_curated_list(
    list_type: Literal[
        "favorites-with-link",
        "downloaded",
        "discovery",
        "top-year",
        "most-played",
        "genre-suggestions"
    ],
    user_id: int = Query(1, description="User ID"),
    force_refresh: bool = Query(False, description="Force regeneration"),
):
    """Get a single curated list."""
    result = get_cached_list(list_type, user_id, force_refresh)
    return {
        "list_type": list_type,
        "title": LIST_CONFIGS[list_type]["description"],
        "items": result["items"],
        "total": result["total"],
        "last_updated": result["last_updated"],
        "is_cached": result["is_cached"]
    }


@router.post("/curated/refresh")
def refresh_lists(
    list_type: str | None = Query(None, description="Specific list to refresh or all"),
    user_id: int | None = Query(None, description="Specific user or all users"),
):
    """Force refresh of curated lists cache."""
    invalidate_cache(list_type, user_id)

    if list_type and user_id:
        # Refresh specific list for specific user
        result = get_cached_list(list_type, user_id, force_refresh=True)
        return {
            "message": f"Refreshed {list_type} for user {user_id}",
            "total_items": result["total"]
        }
    elif list_type:
        # Refresh specific list for all users
        return {"message": f"Invalidated cache for {list_type}"}
    elif user_id:
        # Refresh all lists for specific user
        results = get_all_cached_lists(user_id)
        return {
            "message": f"Refreshed all lists for user {user_id}",
            "lists_refreshed": len(results)
        }
    else:
        # Refresh all
        return {"message": "Invalidated all curated lists cache"}


@router.get("/curated/status")
def get_lists_cache_status():
    """Get cache status for monitoring."""
    return get_cache_status()


# Spanish aliases for frontend compatibility
@router.get("/overview")
def get_lists_overview(
    user_id: int = Query(1, description="User ID"),
    limit_per_list: int = Query(50, description="Items per list"),
):
    """Legacy endpoint - returns all curated lists."""
    all_lists = get_all_cached_lists(user_id)

    # Format to match expected response
    sections = []
    for key, config in LIST_CONFIGS.items():
        list_data = all_lists.get(key, {})
        items = list_data.get("items", [])[:limit_per_list]

        sections.append({
            "key": key,
            "title": config["description"],
            "description": get_list_description(key),
            "items": items,
            "meta": {
                "count": len(items),
                "total_available": list_data.get("total", 0),
                "is_cached": list_data.get("is_cached", False)
            }
        })

    return {
        "lists": sections,
        "top_genres": [],
        "anchor_artist": None
    }


def get_list_description(list_type: str) -> str:
    """Get description for list type."""
    descriptions = {
        "favorites-with-link": "Tus canciones favoritas que ya tienen enlace de YouTube listo para reproducir.",
        "downloaded": "Canciones con archivo local disponible en tu biblioteca.",
        "discovery": "Canciones que no has escuchado recientemente de tu biblioteca.",
        "top-year": "Ranking personal según tus reproducciones, ratings y recencia en los últimos 365 días.",
        "most-played": "Tus canciones más escuchadas de todos los tiempos.",
        "genre-suggestions": "Tracks de géneros vinculados a tus artistas favoritos.",
    }
    return descriptions.get(list_type, "")
