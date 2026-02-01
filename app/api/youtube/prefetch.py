"""
YouTube prefetch endpoints.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from ...core.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prefetch", tags=["youtube"])


@router.post("/album/{spotify_id}")
async def prefetch_album_youtube(
    spotify_id: str,
    background_tasks: BackgroundTasks = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Prefetch YouTube links for entire album."""
    # TODO: Implement album YouTube prefetch
    return {"message": "Album prefetch started", "spotify_id": spotify_id}


@router.get("/status")
async def get_prefetch_status(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get prefetch system status."""
    # TODO: Implement prefetch status
    return {"status": "idle", "queue_size": 0}
