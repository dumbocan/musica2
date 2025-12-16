"""
Lightweight image proxy/resize cache for frontend performance.
"""

import hashlib
from pathlib import Path
from typing import Optional
from io import BytesIO
import asyncio

import httpx
from PIL import Image

CACHE_DIR = Path("cache/images")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_and_resize(url: str, size: int = 512) -> Optional[Path]:
    """
    Download image, resize to max dimension `size`, store as WebP in cache.
    Returns path to cached file or None on failure.
    """
    try:
        key = hashlib.sha1(f"{url}-{size}".encode("utf-8")).hexdigest()
        out_path = CACHE_DIR / f"{key}.webp"
        if out_path.exists():
            return out_path

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content

        def _process():
            im = Image.open(BytesIO(content)).convert("RGB")
            im.thumbnail((size, size))
            im.save(out_path, "WEBP", quality=75, method=6)

        await asyncio.to_thread(_process)
        return out_path
    except Exception:
        return None
