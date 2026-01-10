"""
Lightweight image proxy/resize cache for frontend performance.
"""

import hashlib
import ipaddress
import socket
from pathlib import Path
from typing import Optional
from io import BytesIO
import asyncio
from urllib.parse import urlparse

import httpx
from PIL import Image

CACHE_DIR = Path("cache/images")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    if host in {"localhost"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except ValueError:
        try:
            for addr in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(addr[4][0])
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                ):
                    return False
        except socket.gaierror:
            return False
    return True


async def fetch_and_resize(url: str, size: int = 512) -> Optional[Path]:
    """
    Download image, resize to max dimension `size`, store as WebP in cache.
    Returns path to cached file or None on failure.
    """
    try:
        if not _is_safe_url(url):
            return None
        size = max(32, min(int(size), 2048))
        key = hashlib.sha1(f"{url}-{size}".encode("utf-8")).hexdigest()
        out_path = CACHE_DIR / f"{key}.webp"
        if out_path.exists():
            return out_path

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            if 300 <= resp.status_code < 400:
                return None
            content = resp.content

        def _process():
            im = Image.open(BytesIO(content)).convert("RGB")
            im.thumbnail((size, size))
            im.save(out_path, "WEBP", quality=75, method=6)

        await asyncio.to_thread(_process)
        return out_path
    except Exception:
        return None
