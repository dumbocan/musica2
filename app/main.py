from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
import time
from collections import defaultdict

from .api.routes_health import router as health_router
from .api.artists import artists_router
from .api.albums import router as albums_router
from .api.tracks import tracks_router
from .api.playlists import router as playlists_router
from .api.ratings import router as ratings_router
from .api.tags import router as tags_router
from .api.smart_playlists import router as smart_playlists_router
from .api.search import router as search_router
from .api.charts import router as charts_router
from .api.youtube import youtube_router
from .api.auth import router as auth_router
from .api.favorites import router as favorites_router
from .api.images import router as images_router
from .api.maintenance import maintenance_router
from .api.ai_router import router as ai_router
from .api.lists import router as lists_router
from .core.config import settings
from .core.db import get_session, create_db_and_tables
from .core.maintenance import start_maintenance_background
from .core.security import get_current_user_id_from_token
from .core.log_buffer import install_log_buffer
from .models.base import User
from sqlmodel import select

# Rate limiting storage: {ip: [(timestamp, endpoint)]}
_rate_limit_storage: dict[str, list[tuple[float, str]]] = defaultdict(list)

# Rate limit config: {endpoint: (max_requests, window_seconds)}
RATE_LIMITS = {
    "/auth/login": (5, 60),       # 5 intentos por minuto
    "/auth/register": (3, 60),    # 3 registros por minuto
}


def _is_rate_limited(ip: str, endpoint: str) -> tuple[bool, int]:
    """Check if IP is rate limited. Returns (limited, remaining_seconds)."""
    now = time.time()
    # Clean old entries
    _rate_limit_storage[ip] = [
        (ts, ep) for ts, ep in _rate_limit_storage[ip]
        if now - ts < 60
    ]

    if endpoint in RATE_LIMITS:
        max_requests, window = RATE_LIMITS[endpoint]
        recent = [ts for ts, ep in _rate_limit_storage[ip] if ep == endpoint]
        if len(recent) >= max_requests:
            oldest = min(recent)
            remaining = int(oldest + window - now)
            return True, max(0, remaining)

    return False, 0


def _record_request(ip: str, endpoint: str) -> None:
    """Record a request for rate limiting."""
    _rate_limit_storage[ip].append((time.time(), endpoint))


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting for auth endpoints."""
    path = request.url.path

    # Only rate limit specific auth endpoints
    if path in RATE_LIMITS:
        client_ip = request.client.host if request.client else "unknown"
        limited, remaining = _is_rate_limited(client_ip, path)

        if limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many requests. Try again in {remaining} seconds.",
                    "retry_after": remaining,
                },
                headers={"Retry-After": str(remaining)}
            )

        _record_request(client_ip, path)

    return await call_next(request)


app = FastAPI(title="Audio2 API", description="Personal Music API Backend")
install_log_buffer()
create_db_and_tables()

app.middleware("http")(rate_limit_middleware)

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
    "/ai",  # AI endpoints are public
}
# Endpoints que aceptan token como query param (para HTMLAudioElement y imágenes)
TOKEN_QUERY_PATHS = {
    "/youtube/stream",
    "/youtube/download",
    "/images/entity",
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

    # Check if path accepts token from query param
    accepts_query_token = any(path.startswith(p) for p in TOKEN_QUERY_PATHS)

    # Extract token if provided (even when AUTH_DISABLED)
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token and accepts_query_token:
        token = request.query_params.get("token")

    if settings.AUTH_DISABLED:
        # When AUTH_DISABLED, try to use token first, fallback to first user
        user_id = None
        if token:
            try:
                user_id = get_current_user_id_from_token(token)
            except ValueError:
                pass  # Invalid token, will fallback to first user

        if not user_id:
            with get_session() as session:
                user_id = session.exec(select(User.id)).first()

        if user_id:
            request.state.user_id = user_id
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)
    if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # Token already extracted at the beginning of middleware

    # If no users exist, force registration first
    with get_session() as session:
        user_exists = session.exec(select(User.id)).first()
        if not user_exists:
            response = JSONResponse(status_code=401, content={"detail": "No users found. Register via /auth/register."})
            return _apply_cors_headers(response, request)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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
app.include_router(ai_router)
app.include_router(lists_router)


@app.on_event("startup")
async def _start_maintenance_on_boot():
    if settings.MAINTENANCE_START_ON_FIRST_REQUEST:
        return
    start_maintenance_background(
        delay_seconds=settings.MAINTENANCE_STARTUP_DELAY_SECONDS,
        stagger_seconds=settings.MAINTENANCE_STAGGER_SECONDS,
    )
