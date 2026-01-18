"""Shared helpers for proxying image URLs through the local resizer."""

from urllib.parse import quote_plus, urlparse, parse_qs
from typing import Iterable, List, Union, Dict, Any

ImageEntry = Union[str, Dict[str, Any]]

def _is_proxy_url(url: str) -> bool:
    return url.startswith("/images/proxy")


def _resize_proxy_url(url: str, size: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    original = query.get("url", [None])[0]
    if not original:
        return url
    return f"/images/proxy?url={quote_plus(original)}&size={size}"


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
        if _is_proxy_url(url):
            proxied.append({"url": _resize_proxy_url(url, size)})
        else:
            proxied.append({"url": f"/images/proxy?url={quote_plus(url)}&size={size}"})
    return proxied
