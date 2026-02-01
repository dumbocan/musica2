#!/usr/bin/env python3
"""
Extract YouTube video ID from a Letras.com song page using Playwright (headless).
Usage:
  /home/micasa/audio2/venv/bin/python scripts/letras_extract_youtube_headless.py "https://www.letras.com/radiohead/63485/"
"""

from __future__ import annotations

import re
import sys
import os
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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


def _extract_from_html(html: str) -> str | None:
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
        print("Usage: letras_extract_youtube_headless.py <letras_url>")
        return 2

    url = sys.argv[1]
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    debug_log_path = os.environ.get("DEBUG_LOG", "/tmp/letras_network.log")

    def _maybe_log(line: str) -> None:
        if not debug:
            return
        with open(debug_log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
            viewport={"width": 1280, "height": 720},
        )
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """
        )
        page = context.new_page()
        found_video_id: str | None = None

        def _scan_url(url: str) -> None:
            nonlocal found_video_id
            if found_video_id:
                return
            if "iframe_proxy_player_letras_endpoint.html" in url:
                video_id = _extract_from_iframe_url(url)
                if video_id:
                    found_video_id = video_id
            if debug and any(token in url for token in ("iframe_proxy", "player", "youtube", "video")):
                _maybe_log(url)

        def _log_req(req) -> None:
            _scan_url(req.url)
            if debug:
                if req.resource_type in ("xhr", "fetch"):
                    _maybe_log(f"[{req.resource_type}] {req.url}")
                elif any(token in req.url for token in ("letras.com", "sscdn.co")):
                    _maybe_log(f"[req] {req.url}")

        def _log_resp(resp) -> None:
            _scan_url(resp.url)
            if debug and any(token in resp.url for token in ("letras.com", "sscdn.co")):
                _maybe_log(f"[resp] {resp.url} {resp.status}")

        page.on("request", _log_req)
        page.on("response", _log_resp)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if debug:
                _maybe_log(f"[page] title={page.title()}")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_selector("iframe", timeout=10000)
            except PlaywrightTimeoutError:
                pass
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                pass
            if not found_video_id:
                for label in ("Aceptar", "Accept", "I agree", "Estoy de acuerdo"):
                    try:
                        page.get_by_role("button", name=label).click(timeout=1500)
                        break
                    except Exception:
                        continue
            if not found_video_id:
                for selector in (
                    "button[aria-label*='play' i]",
                    "button[title*='play' i]",
                    ".player .btn-play",
                    ".player-play",
                    ".js-player-play",
                    ".js-play",
                ):
                    try:
                        page.locator(selector).first.click(timeout=1500)
                        break
                    except Exception:
                        continue
            if not found_video_id and debug:
                try:
                    iframe_srcs = page.locator("iframe").evaluate_all(
                        "els => els.map(e => e.getAttribute('src') || '')"
                    )
                    _maybe_log(f"[debug] iframes={len(iframe_srcs)}")
                    for src in iframe_srcs[:10]:
                        _maybe_log(f"[debug] iframe src={src}")
                except Exception:
                    pass
                try:
                    nodes = page.locator("[id*=player],[class*=player]").evaluate_all(
                        "els => els.slice(0,5).map(e => e.outerHTML.slice(0,500))"
                    )
                    for node in nodes:
                        _maybe_log(f"[debug] node={node}")
                except Exception:
                    pass
            if not found_video_id:
                try:
                    page.keyboard.press("Space")
                except Exception:
                    pass
            if not found_video_id:
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    pass
            html = page.content()
        finally:
            context.close()
            browser.close()

    video_id = found_video_id or _extract_from_html(html)
    if not video_id:
        print("No video_id found in rendered HTML.")
        return 1

    print(video_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
