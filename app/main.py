from fastapi import FastAPI

from .api.routes_health import router as health_router
from .api.artists import router as artists_router
from .api.albums import router as albums_router
from .api.tracks import router as tracks_router

app = FastAPI(title="Audio2 API", description="Personal Music API Backend")

app.include_router(health_router)
app.include_router(artists_router)
app.include_router(albums_router)
app.include_router(tracks_router)
