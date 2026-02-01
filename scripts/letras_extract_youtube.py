#!/usr/bin/env python3
"""
Extract YouTube video ID from a Letras.com song page (static HTML).
Usage:
  /home/micasa/audio2/venv/bin/python scripts/letras_extract_youtube.py "https://www.letras.com/radiohead/63485/"
"""

from __future__ import annotations

import re
import sys
from urllib.parse import parse_qs, urlparse

import httpx


IFRAME_RE = re.compile(r"(https?://[^\"']*iframe_proxy_player_letras_endpoint\.html[^\"']*)", re.IGNORECASE)
VIDEO_ID_RE = re.compile(r"(?:videoId|video_id)[\"'=:\s]+([a-zA-Z0-9_-]{11})")
YOUTUBE_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})")


def _extract_from_iframe_url(url: str) -> str | None:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("videoId", "video_id"):
        if key in params and params[key]:
            return params[key][0]
    return None


def extract_video_id(html: str) -> str | None:
    match = IFRAME_RE.search(html)
    if match:
        iframe_url = match.group(1)
        video_id = _extract_from_iframe_url(iframe_url)
        if video_id:
            return video_id

    match = VIDEO_ID_RE.search(html)
    if match:
        return match.group(1)

    match = YOUTUBE_RE.search(html)
    if match:
        return match.group(1)

    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: letras_extract_youtube.py <letras_url>")
        return 2

    url = sys.argv[1]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Audio2/1.0; +https://example.local)",
        "Accept": "text/html,application/xhtml+xml",
    }
    with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    video_id = extract_video_id(html)
    if not video_id:
        print("No video_id found in static HTML.")
        return 1

    print(video_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
