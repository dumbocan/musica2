"""Shared helpers for proxying image URLs through the local resizer."""

from urllib.parse import quote_plus
from typing import Iterable, List, Union, Dict, Any

ImageEntry = Union[str, Dict[str, Any]]


def proxy_image_list(images: Iterable[ImageEntry], size: int = 512) -> List[dict]:
    """Return list of dicts with proxied URLs ready for frontend consumption."""
    proxied: List[dict] = []
    for img in images or []:
        url = None
        if isinstance(img, dict):
            url = img.get("url") or img.get("#text")
        elif isinstance(img, str):
            url = img
        if not url:
            continue
        proxied.append({"url": f"/images/proxy?url={quote_plus(url)}&size={size}"})
    return proxied
