"""
Helpers for deriving artist genres from Last.fm track tags.
"""

from collections import Counter
import re

from .lastfm import lastfm_client


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower()


def _clean_track_name(track_name: str) -> str:
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", "", track_name)
    cleaned = re.sub(r"\s+-\s+.*$", "", cleaned)
    return cleaned.strip()


def _extract_lastfm_tags(raw_tags) -> list[str]:
    if not raw_tags:
        return []
    tags: list[str] = []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, dict):
                name = tag.get("name")
                if isinstance(name, str):
                    tags.append(name)
            elif isinstance(tag, str):
                tags.append(tag)
    elif isinstance(raw_tags, dict):
        name = raw_tags.get("name")
        if isinstance(name, str):
            tags.append(name)
    return tags


def _filter_tag(tag: str, artist_name: str, track_names: list[str]) -> bool:
    normalized = _normalize_tag(tag)
    if not normalized:
        return False
    if normalized in {"seen live", "favorites", "favourite", "favorite", "love"}:
        return False
    if normalized.isdigit() or normalized.endswith("s") and normalized[:-1].isdigit():
        return False
    artist_norm = _normalize_tag(artist_name)
    if artist_norm and artist_norm in normalized:
        return False
    for track in track_names:
        track_norm = _normalize_tag(track)
        if track_norm and track_norm in normalized:
            return False
    return True


async def derive_genres_from_tracks(
    artist_name: str,
    track_names: list[str],
    max_tags: int = 6,
) -> list[str]:
    if not track_names:
        return []
    tag_counts: Counter[str] = Counter()
    for track_name in track_names:
        candidates = [track_name]
        cleaned = _clean_track_name(track_name)
        if cleaned and cleaned != track_name:
            candidates.append(cleaned)
        for candidate in candidates:
            info = await lastfm_client.get_track_info(artist_name, candidate)
            raw_tags = info.get("tags") if isinstance(info, dict) else []
            tags = _extract_lastfm_tags(raw_tags)
            if not tags:
                continue
            for tag in tags:
                if _filter_tag(tag, artist_name, track_names):
                    tag_counts[_normalize_tag(tag)] += 1
            break
    if not tag_counts:
        return []
    return [tag for tag, _ in tag_counts.most_common(max_tags)]
