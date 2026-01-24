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
from .api.maintenance import router as maintenance_router
from .api.lists import router as lists_router
from .core.config import settings
from .core.db import get_session, create_db_and_tables
from .core.maintenance import start_maintenance_background
from .core.security import get_current_user_id_from_token
from .core.log_buffer import install_log_buffer
from .models.base import User
from sqlmodel import select

app = FastAPI(title="Audio2 API", description="Personal Music API Backend")
install_log_buffer()
create_db_and_tables()

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

    response = await call_next(request)
    if settings.MAINTENANCE_START_ON_FIRST_REQUEST:
        start_maintenance_background(
            delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
            stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
        )
    return response

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
app.include_router(maintenance_router)
app.include_router(lists_router)


@app.on_event("startup")
async def _start_maintenance_on_boot():
    if settings.MAINTENANCE_START_ON_FIRST_REQUEST:
        return
    start_maintenance_background(
        delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
        stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
    )
