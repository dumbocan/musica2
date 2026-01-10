from fastapi import APIRouter, status
import httpx
from datetime import datetime

from ..core.db import get_session
from sqlmodel import select
from ..models.base import Artist

router = APIRouter()

# Global state for offline detection
api_status_cache = {
    'spotify': {
        'last_checked': None,
        'is_online': None,
        'last_error': None
    },
    'lastfm': {
        'last_checked': None,
        'is_online': None,
        'last_error': None
    },
    'database': {
        'last_checked': None,
        'is_online': None,
        'last_error': None
    }
}

async def check_spotify_api() -> bool:
    """Check if Spotify API is available; skip if no credentials."""
    from ..core.config import settings
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        api_status_cache['spotify']['is_online'] = None
        api_status_cache['spotify']['last_error'] = "credentials not set"
        api_status_cache['spotify']['last_checked'] = datetime.utcnow()
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.spotify.com/v1", timeout=5)
            api_status_cache['spotify']['is_online'] = response.status_code == 200
            api_status_cache['spotify']['last_error'] = None if response.status_code == 200 else f"HTTP {response.status_code}"
            return response.status_code == 200
    except Exception as e:
        api_status_cache['spotify']['is_online'] = False
        api_status_cache['spotify']['last_error'] = str(e)
        return False
    finally:
        api_status_cache['spotify']['last_checked'] = datetime.utcnow()

async def check_lastfm_api() -> bool:
    """Check if Last.fm API is available; skip if no credentials."""
    from ..core.config import settings
    if not settings.LASTFM_API_KEY:
        api_status_cache['lastfm']['is_online'] = None
        api_status_cache['lastfm']['last_error'] = "credentials not set"
        api_status_cache['lastfm']['last_checked'] = datetime.utcnow()
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist=cher&api_key=test&format=json", timeout=5)
            api_status_cache['lastfm']['is_online'] = response.status_code == 200
            api_status_cache['lastfm']['last_error'] = None if response.status_code == 200 else f"HTTP {response.status_code}"
            return response.status_code == 200
    except Exception as e:
        api_status_cache['lastfm']['is_online'] = False
        api_status_cache['lastfm']['last_error'] = str(e)
        return False
    finally:
        api_status_cache['lastfm']['last_checked'] = datetime.utcnow()

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
        api_status_cache['database']['last_checked'] = datetime.utcnow()

@router.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}

@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health() -> dict:
    """Detailed health check with service status."""
    # Check all services
    spotify_ok = await check_spotify_api()
    lastfm_ok = await check_lastfm_api()
    db_ok = check_database()

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
