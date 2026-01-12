"""
Billboard chart scraper helpers.
"""

from __future__ import annotations

from datetime import date
from html import unescape
import re
import unicodedata
from urllib import request


_ENTRY_BLOCK_RE = re.compile(
    r'<ul class="o-chart-results-list-row[^"]*"[^>]*>.*?</ul>',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<h3[^>]*class="[^"]*c-title[^"]*"[^>]*>\s*(.*?)\s*</h3>',
    re.DOTALL,
)
_ARTIST_RE = re.compile(
    r'<span[^>]*class="[^"]*a-no-trucate[^"]*"[^>]*>\s*(.*?)\s*</span>',
    re.DOTALL,
)
_RANK_PRIMARY_RE = re.compile(
    r'<span[^>]*class="[^"]*(?:a-font-basic|a-font-primary-bold-l)[^"]*"[^>]*>'
    r'\s*(\d+)\s*</span>',
    re.DOTALL,
)
_RANK_FALLBACK_RE = re.compile(r'<span[^>]*>\s*(\d+)\s*</span>', re.DOTALL)

_SPLIT_ARTIST_RE = re.compile(
    r"\s+(?:feat\.|featuring|with|&|x|/|,|and)\s+",
    re.IGNORECASE,
)

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _clean_text(value: str) -> str:
    cleaned = unescape(value or "")
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_primary_artist(artist: str) -> str:
    parts = _SPLIT_ARTIST_RE.split(artist or "")
    return parts[0].strip() if parts else (artist or "").strip()


def normalize_artist_name(artist: str) -> str:
    return _normalize_text(extract_primary_artist(artist))


def normalize_track_title(title: str) -> str:
    title = re.sub(r"\(.*?\)", "", title or "")
    title = re.sub(r"\[.*?\]", "", title)
    title = re.sub(r"\bfeat\.?\b.*", "", title, flags=re.IGNORECASE)
    return _normalize_text(title)


def fetch_chart_entries(chart_slug: str, chart_date: date) -> list[dict]:
    """Fetch Billboard chart entries for a given chart and date."""
    url = f"https://www.billboard.com/charts/{chart_slug}/{chart_date.isoformat()}/"
    req = request.Request(url, headers=_DEFAULT_HEADERS)
    with request.urlopen(req, timeout=30) as response:
        html_text = response.read().decode("utf-8", errors="ignore")
    return parse_chart_entries(html_text)


def parse_chart_entries(html_text: str) -> list[dict]:
    """Parse chart entries from Billboard HTML."""
    entries = []
    for block in _ENTRY_BLOCK_RE.findall(html_text or ""):
        rank_match = _RANK_PRIMARY_RE.search(block) or _RANK_FALLBACK_RE.search(block)
        title_match = _TITLE_RE.search(block)
        artist_match = _ARTIST_RE.search(block)
        if not rank_match or not title_match or not artist_match:
            continue
        rank = int(rank_match.group(1))
        title = _clean_text(title_match.group(1))
        artist = _clean_text(artist_match.group(1))
        if not title or not artist:
            continue
        entries.append({"rank": rank, "title": title, "artist": artist})
    return entries
