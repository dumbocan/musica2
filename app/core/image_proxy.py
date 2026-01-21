"""Shared helpers for proxying image URLs through the local resizer."""

from urllib.parse import quote_plus, urlparse, parse_qs
from typing import Iterable, List, Union, Dict, Any, Optional

ImageEntry = Union[str, Dict[str, Any]]

_LASTFM_PLACEHOLDER_MARKERS = (
    "2a96cbd8b46e442fc41c2b86b821562f",
    "noimage",
)


def _extract_url(entry: ImageEntry) -> Optional[str]:
    if isinstance(entry, dict):
        url = entry.get("url") or entry.get("#text")
    elif isinstance(entry, str):
        url = entry
    else:
        url = None
    return url if isinstance(url, str) else None


def is_placeholder_image(url: str) -> bool:
    lowered = (url or "").lower()
    if "lastfm" not in lowered:
        return False
    return any(marker in lowered for marker in _LASTFM_PLACEHOLDER_MARKERS)


def has_valid_images(images: Iterable[ImageEntry]) -> bool:
    for img in images or []:
        url = _extract_url(img)
        if url and not is_placeholder_image(url):
            return True
    return False


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
        url = _extract_url(img)
        if not url or is_placeholder_image(url):
            continue
        if _is_proxy_url(url):
            proxied.append({"url": _resize_proxy_url(url, size)})
        else:
            proxied.append({"url": f"/images/proxy?url={quote_plus(url)}&size={size}"})
    return proxied
