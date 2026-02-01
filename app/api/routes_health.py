from fastapi import APIRouter, status
import asyncio
import base64
import httpx
from ..core.time_utils import utc_now

from ..core.db import get_session
from sqlmodel import select
from ..models.base import Artist

router = APIRouter()

# Global state for offline detection
api_status_cache = {
    'spotify': {
        'last_checked': None,
        'is_online': None,
        'last_error': None,
        'last_success': None
    },
    'lastfm': {
        'last_checked': None,
        'is_online': None,
        'last_error': None,
        'last_success': None
    },
    'database': {
        'last_checked': None,
        'is_online': None,
        'last_error': None
    }
}

RECENT_SUCCESS_SECONDS = 15 * 60


def _is_recent(last_checked, max_age_seconds: int = 60) -> bool:
    if not last_checked:
        return False
    return (utc_now() - last_checked).total_seconds() < max_age_seconds


def _has_recent_success(last_success) -> bool:
    if not last_success:
        return False
    return (utc_now() - last_success).total_seconds() < RECENT_SUCCESS_SECONDS


async def check_spotify_api() -> bool:
    """Check if Spotify API is available; skip if no credentials."""
    from ..core.config import settings
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        api_status_cache['spotify']['is_online'] = None
        api_status_cache['spotify']['last_error'] = "credentials not set"
        api_status_cache['spotify']['last_checked'] = utc_now()
        return False
    if _is_recent(api_status_cache['spotify']['last_checked']):
        cached = api_status_cache['spotify']['is_online']
        if cached is not None:
            return bool(cached)

    try:
        auth_string = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
        response.raise_for_status()
        api_status_cache['spotify']['is_online'] = True
        api_status_cache['spotify']['last_error'] = None
        api_status_cache['spotify']['last_success'] = utc_now()
        return True
    except asyncio.TimeoutError:
        if _has_recent_success(api_status_cache['spotify']['last_success']):
            api_status_cache['spotify']['is_online'] = True
            api_status_cache['spotify']['last_error'] = "timeout (cached)"
            return True
        api_status_cache['spotify']['is_online'] = False
        api_status_cache['spotify']['last_error'] = "timeout"
        return False
    except httpx.TimeoutException:
        if _has_recent_success(api_status_cache['spotify']['last_success']):
            api_status_cache['spotify']['is_online'] = True
            api_status_cache['spotify']['last_error'] = "timeout (cached)"
            return True
        api_status_cache['spotify']['is_online'] = False
        api_status_cache['spotify']['last_error'] = "timeout"
        return False
    except Exception as e:
        if _has_recent_success(api_status_cache['spotify']['last_success']):
            api_status_cache['spotify']['is_online'] = True
            api_status_cache['spotify']['last_error'] = f"cached: {e}"
            return True
        api_status_cache['spotify']['is_online'] = False
        api_status_cache['spotify']['last_error'] = str(e)
        return False
    finally:
        api_status_cache['spotify']['last_checked'] = utc_now()


async def check_lastfm_api() -> bool:
    """Check if Last.fm API is available; skip if no credentials."""
    from ..core.config import settings
    if not settings.LASTFM_API_KEY:
        api_status_cache['lastfm']['is_online'] = None
        api_status_cache['lastfm']['last_error'] = "credentials not set"
        api_status_cache['lastfm']['last_checked'] = utc_now()
        return False
    if _is_recent(api_status_cache['lastfm']['last_checked']):
        cached = api_status_cache['lastfm']['is_online']
        if cached is not None:
            return bool(cached)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "artist.getinfo",
                    "artist": "cher",
                    "api_key": settings.LASTFM_API_KEY,
                    "format": "json",
                },
                timeout=4,
            )
        ok = response.status_code == 200
        error_message = None
        if ok:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            if isinstance(payload, dict) and payload.get("error"):
                ok = False
                error_message = payload.get("message", "Last.fm error")
        api_status_cache['lastfm']['is_online'] = ok
        api_status_cache['lastfm']['last_error'] = None if ok else (error_message or f"HTTP {response.status_code}")
        if ok:
            api_status_cache['lastfm']['last_success'] = utc_now()
        return ok
    except httpx.TimeoutException:
        if _has_recent_success(api_status_cache['lastfm']['last_success']):
            api_status_cache['lastfm']['is_online'] = True
            api_status_cache['lastfm']['last_error'] = "timeout (cached)"
            return True
        api_status_cache['lastfm']['is_online'] = False
        api_status_cache['lastfm']['last_error'] = "timeout"
        return False
    except Exception as e:
        if _has_recent_success(api_status_cache['lastfm']['last_success']):
            api_status_cache['lastfm']['is_online'] = True
            api_status_cache['lastfm']['last_error'] = f"cached: {e}"
            return True
        api_status_cache['lastfm']['is_online'] = False
        api_status_cache['lastfm']['last_error'] = str(e)
        return False
    finally:
        api_status_cache['lastfm']['last_checked'] = utc_now()


def check_database() -> bool:
    """Check if database is available."""
    try:
        with get_session() as session:
            # Simple query to test connectivity
            session.exec(select(Artist).limit(1)).first()
            api_status_cache['database']['is_online'] = True
            api_status_cache['database']['last_error'] = None
            return True
    except Exception as e:
        api_status_cache['database']['is_online'] = False
        api_status_cache['database']['last_error'] = str(e)
        return False
    finally:
        api_status_cache['database']['last_checked'] = utc_now()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health() -> dict:
    """Detailed health check with service status."""
    # Check all services in parallel (fast-fail with timeouts inside checks)
    spotify_task = asyncio.create_task(check_spotify_api())
    lastfm_task = asyncio.create_task(check_lastfm_api())
    db_task = asyncio.to_thread(check_database)
    spotify_ok, lastfm_ok, db_ok = await asyncio.gather(spotify_task, lastfm_task, db_task)

    # Determine overall system status
    system_status = "online"
    if not (spotify_ok and lastfm_ok and db_ok):
        system_status = "degraded" if any([spotify_ok, lastfm_ok, db_ok]) else "offline"

    return {
        "status": system_status,
        "services": {
            "spotify": {
                "status": "online" if spotify_ok else "offline",
                "last_checked": api_status_cache['spotify']['last_checked'].isoformat() if api_status_cache['spotify']['last_checked'] else None,
                "last_error": api_status_cache['spotify']['last_error']
            },
            "lastfm": {
                "status": "online" if lastfm_ok else "offline",
                "last_checked": api_status_cache['lastfm']['last_checked'].isoformat() if api_status_cache['lastfm']['last_checked'] else None,
                "last_error": api_status_cache['lastfm']['last_error']
            },
            "database": {
                "status": "online" if db_ok else "offline",
                "last_checked": api_status_cache['database']['last_checked'].isoformat() if api_status_cache['database']['last_checked'] else None,
                "last_error": api_status_cache['database']['last_error']
            }
        }
    }


@router.get("/api-status", status_code=status.HTTP_200_OK)
async def api_status() -> dict:
    """Get current API status (Spotify, Last.fm)."""
    return {
        "spotify": {
            "status": "online" if api_status_cache['spotify']['is_online'] else "offline",
            "last_checked": api_status_cache['spotify']['last_checked'].isoformat() if api_status_cache['spotify']['last_checked'] else None,
            "last_error": api_status_cache['spotify']['last_error']
        },
        "lastfm": {
            "status": "online" if api_status_cache['lastfm']['is_online'] else "offline",
            "last_checked": api_status_cache['lastfm']['last_checked'].isoformat() if api_status_cache['lastfm']['last_checked'] else None,
            "last_error": api_status_cache['lastfm']['last_error']
        }
    }


@router.get("/db-status", status_code=status.HTTP_200_OK)
def db_status() -> dict:
    """Get current database status."""
    check_database()
    return {
        "status": "online" if api_status_cache['database']['is_online'] else "offline",
        "last_checked": api_status_cache['database']['last_checked'].isoformat() if api_status_cache['database']['last_checked'] else None,
        "last_error": api_status_cache['database']['last_error']
    }


@router.get("/offline-mode", status_code=status.HTTP_200_OK)
def offline_mode() -> dict:
    """Check if system is in offline mode (any service offline)."""
    any_offline = not all([
        api_status_cache['spotify']['is_online'],
        api_status_cache['lastfm']['is_online'],
        api_status_cache['database']['is_online']
    ])

    return {
        "offline_mode": any_offline,
        "services_offline": [
            service for service, data in api_status_cache.items()
            if not data['is_online']
        ]
    }
