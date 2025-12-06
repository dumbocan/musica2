from fastapi import FastAPI

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
from .core.db import create_db_and_tables

app = FastAPI(title="Audio2 API", description="Personal Music API Backend")

# Create tables if they don't exist
create_db_and_tables()

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
