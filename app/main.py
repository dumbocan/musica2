from fastapi import FastAPI

from .api.routes_health import router

app = FastAPI(title="Audio2 API", description="Personal Music API Backend")

app.include_router(router)
