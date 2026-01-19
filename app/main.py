from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .api.routes_health import router as health_router
from .api.artists import router as artists_router
from .api.albums import router as albums_router
from .api.tracks import router as tracks_router
from .api.playlists import router as playlists_router
from .api.ratings import router as ratings_router
from .api.tags import router as tags_router
from .api.smart_playlists import router as smart_playlists_router
from .api.search import router as search_router
from .api.charts import router as charts_router
from .api.youtube import router as youtube_router
from .api.auth import router as auth_router
from .api.favorites import router as favorites_router
from .api.images import router as images_router
from .core.config import settings
from .core.db import get_session
from .core.maintenance import (
    daily_refresh_loop,
    genre_backfill_loop,
    full_library_refresh_loop,
    chart_scrape_loop,
    chart_match_loop,
)
from .core.security import get_current_user_id_from_token
from .models.base import User
from sqlmodel import select
import asyncio

app = FastAPI(title="Audio2 API", description="Personal Music API Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth guard: block everything if no users exist or no token provided
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/login",
    "/auth/register",
    "/auth/create-first-user",
    "/auth/account-lookup",
    "/auth/reset-password",
    "/db-status",
    "/images/proxy",
}
PUBLIC_PREFIXES = (
    "/static",
    "/favicon",
    "/youtube/stream",  # Audio streaming uses <audio> without auth headers.
    "/youtube/download",  # <audio> fetches file URLs without auth headers.
)

def _apply_cors_headers(response: Response, request: Request) -> Response:
    origin = request.headers.get("origin")
    if not origin:
        return response
    if origin in settings.CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        if settings.CORS_ALLOW_CREDENTIALS:
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


@app.middleware("http")
async def require_authenticated_user(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS":
        return await call_next(request)
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # If no users exist, force registration first
    with get_session() as session:
        user_exists = session.exec(select(User.id)).first()
        if not user_exists:
            response = JSONResponse(status_code=401, content={"detail": "No users found. Register via /auth/register."})
            return _apply_cors_headers(response, request)

        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            response = JSONResponse(status_code=401, content={"detail": "Authorization bearer token required"})
            return _apply_cors_headers(response, request)

        try:
            user_id = get_current_user_id_from_token(token)
        except ValueError as exc:
            response = JSONResponse(status_code=401, content={"detail": str(exc)})
            return _apply_cors_headers(response, request)

        user_in_db = session.exec(select(User.id).where(User.id == user_id)).first()
        if not user_in_db:
            response = JSONResponse(status_code=401, content={"detail": "User not found"})
            return _apply_cors_headers(response, request)

        request.state.user_id = user_id

    return await call_next(request)

app.include_router(health_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)
app.include_router(playlists_router)
app.include_router(ratings_router)
app.include_router(tags_router)
app.include_router(smart_playlists_router)
app.include_router(search_router)
app.include_router(charts_router)
app.include_router(youtube_router)
app.include_router(auth_router)
app.include_router(favorites_router)
app.include_router(images_router)


@app.on_event("startup")
async def _start_maintenance():
    asyncio.create_task(daily_refresh_loop())
    asyncio.create_task(genre_backfill_loop())
    asyncio.create_task(full_library_refresh_loop())
    asyncio.create_task(chart_scrape_loop())
    asyncio.create_task(chart_match_loop())
