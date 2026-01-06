#!/usr/bin/env python3
"""
Reorganize downloaded audio files into downloads/Artist/Album/Track.ext.

Only moves files when a YouTube video ID can be matched to a Spotify track in DB.
Existing Artist/Album/Track paths are left untouched.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import re
from pathlib import Path

import yt_dlp

from sqlmodel import select

from app.core.db import get_session
from app.core.spotify import spotify_client
from app.crud import save_artist, save_album, save_track
from app.models.base import YouTubeDownload, Track, Album, Artist


def clean_filename(text: str) -> str:
    safe_text = (
        text.replace("/", "-")
        .replace("\\", "-")
        .replace(":", " -")
        .replace("*", "")
        .replace("?", "")
        .replace('"', "")
        .replace("<", "")
        .replace(">", "")
        .replace("|", "-")
    )
    safe_text = re.sub(r"[-\s]+", "-", safe_text.strip())
    return safe_text[:100].strip("-")


def build_target_path(
    downloads_dir: Path,
    artist_name: str,
    album_name: str,
    track_name: str,
    ext: str
) -> Path:
    safe_artist = clean_filename(artist_name)
    safe_album = clean_filename(album_name)
    safe_track = clean_filename(track_name)
    return downloads_dir / safe_artist / safe_album / f"{safe_track}.{ext}"


def resolve_collision(path: Path, suffix: str) -> Path:
    if not path.exists():
        return path
    return path.with_name(f"{path.stem}-{suffix}{path.suffix}")


def is_probable_video_id(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{10,12}", text))


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[\[\(].*?[\]\)]", "", text)
    cleaned = re.sub(
        r"\b(official|video|audio|lyrics|lyric|hd|remaster|remastered|visualizer|explicit)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+feat\.?.*?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_artist_track(title: str) -> tuple[str | None, str | None]:
    for sep in (" - ", " – ", " — "):
        if sep in title:
            left, right = title.split(sep, 1)
            return left.strip(), right.strip()
    return None, None


def to_search_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.strip(" .-_")
    return cleaned or None


def load_track_index():
    with get_session() as session:
        rows = session.exec(
            select(Track, Album, Artist)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
        ).all()
    index = []
    for track, album, artist in rows:
        index.append({
            "track": track,
            "album": album,
            "artist": artist,
            "key": normalize_text(f"{artist.name} - {track.name}"),
            "artist_key": normalize_text(artist.name),
            "track_key": normalize_text(track.name),
            "track_tokens": set(normalize_text(track.name).split())
        })
    return index


def _score_track(track_key: str, candidate_key: str) -> float:
    return difflib.SequenceMatcher(None, track_key, candidate_key).ratio()


def find_match(index, artist_name: str | None, track_name: str | None):
    if not track_name:
        return None
    artist_key = normalize_text(artist_name or "")
    track_key = normalize_text(track_name)
    if artist_key:
        lookup_key = normalize_text(f"{artist_name} - {track_name}")
        for item in index:
            if item["key"] == lookup_key:
                return item
        candidates = [item for item in index if item["artist_key"] == artist_key]
    else:
        candidates = index
    if not candidates:
        return None
    best = None
    best_score = 0.0
    track_tokens = set(track_key.split())
    for item in candidates:
        score = _score_track(track_key, item["track_key"])
        if track_key in item["track_key"] or item["track_key"] in track_key:
            score = max(score, 0.9)
        if track_tokens and item["track_tokens"]:
            overlap = len(track_tokens & item["track_tokens"]) / max(len(track_tokens), len(item["track_tokens"]))
            score = max(score, overlap)
        if score > best_score:
            best_score = score
            best = item
    threshold = 0.72 if artist_key else 0.8
    if best_score >= threshold:
        return best
    return None


def fetch_video_metadata(video_id: str) -> dict | None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "retries": 1,
        "socket_timeout": 5,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception:
        return None


def build_spotify_query(artist_name: str | None, track_name: str | None) -> str:
    parts = []
    if track_name:
        parts.append(f'track:"{track_name}"')
    if artist_name:
        parts.append(f'artist:"{artist_name}"')
    return " ".join(parts) if parts else (track_name or artist_name or "")


def choose_spotify_candidate(results: list[dict], artist_name: str | None, track_name: str | None) -> dict | None:
    requested = normalize_text(f"{artist_name or ''} {track_name or ''}")
    if not requested:
        return None
    best = None
    best_score = 0.0
    for item in results:
        artists = item.get("artists") or []
        candidate_artist = artists[0].get("name") if artists else ""
        candidate_track = item.get("name") or ""
        candidate = normalize_text(f"{candidate_artist} {candidate_track}")
        if not candidate:
            continue
        score = _score_track(requested, candidate)
        if score > best_score:
            best_score = score
            best = item
    return best if best_score >= 0.72 else None


async def _resolve_spotify_match_async(
    track_index,
    track_by_spotify_id,
    artist_name: str | None,
    track_name: str | None,
    limit: int,
    allow_create: bool,
):
    if not track_name:
        return None
    query = build_spotify_query(artist_name, track_name)
    if not query:
        return None
    results = await spotify_client.search_tracks(query, limit=limit)
    if not results:
        fallback = normalize_text(f"{artist_name or ''} {track_name or ''}")
        if fallback and fallback != normalize_text(query):
            results = await spotify_client.search_tracks(fallback, limit=limit)
    for item in results:
        track_id = item.get("id")
        if track_id and track_id in track_by_spotify_id:
            return track_by_spotify_id[track_id], None
    for item in results:
        candidate_track = item.get("name")
        artists = item.get("artists") or []
        candidate_artist = artists[0].get("name") if artists else None
        match = find_match(track_index, candidate_artist, candidate_track)
        if match:
            return match, None
    if allow_create:
        candidate = choose_spotify_candidate(results, artist_name, track_name)
        return None, candidate
    return None, None


def resolve_spotify_match(
    track_index,
    track_by_spotify_id,
    artist_name: str | None,
    track_name: str | None,
    limit: int,
    allow_create: bool,
    cache: dict,
):
    cache_key = (artist_name or "", track_name or "")
    if cache_key in cache:
        return cache[cache_key]
    try:
        match = asyncio.run(
            _resolve_spotify_match_async(
                track_index,
                track_by_spotify_id,
                artist_name,
                track_name,
                limit,
                allow_create,
            )
        )
    except RuntimeError as exc:
        print(f"Spotify lookup failed: {exc}")
        match = (None, None)
    except Exception:
        match = (None, None)
    cache[cache_key] = match
    return match


def add_track_to_index(track_index, track_by_spotify_id, artist: Artist, album: Album | None, track: Track):
    entry = {
        "track": track,
        "album": album,
        "artist": artist,
        "key": normalize_text(f"{artist.name} - {track.name}"),
        "artist_key": normalize_text(artist.name),
        "track_key": normalize_text(track.name),
        "track_tokens": set(normalize_text(track.name).split()),
    }
    track_index.append(entry)
    if track.spotify_id:
        track_by_spotify_id[track.spotify_id] = entry
    return entry


def create_entities_from_spotify(track_item: dict):
    album_data = track_item.get("album") or {}
    artists = track_item.get("artists") or []
    primary_artist = artists[0] if artists else None
    if primary_artist:
        artist = save_artist(primary_artist)
    else:
        artist = None
    album = save_album(album_data) if album_data else None
    artist_id = artist.id if artist else (album.artist_id if album else None)
    album_id = album.id if album else None
    track = save_track(track_item, album_id=album_id, artist_id=artist_id)
    if not artist and album:
        with get_session() as session:
            artist = session.exec(select(Artist).where(Artist.id == album.artist_id)).first()
    return artist, album, track


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize downloads by Artist/Album/Track")
    parser.add_argument("--dry-run", action="store_true", help="Show what would move without touching files")
    parser.add_argument("--resolve-unknown", action="store_true", help="Try to resolve unknown files via YouTube metadata")
    parser.add_argument("--resolve-spotify", action="store_true", help="Try to resolve unknown files via Spotify search")
    parser.add_argument("--spotify-create", action="store_true", help="Create missing Spotify Artist/Album/Track entries")
    parser.add_argument("--spotify-limit", type=int, default=6, help="Spotify search results to check per file")
    args = parser.parse_args()

    downloads_dir = Path("downloads")
    if not downloads_dir.exists():
        print("downloads/ directory not found.")
        return 1

    with get_session() as session:
        rows = session.exec(
            select(YouTubeDownload, Track, Album, Artist)
            .join(Track, Track.spotify_id == YouTubeDownload.spotify_track_id)
            .join(Artist, Artist.id == Track.artist_id)
            .outerjoin(Album, Album.id == Track.album_id)
            .where(YouTubeDownload.youtube_video_id.is_not(None))
        ).all()

    by_video_id = {}
    for download, track, album, artist in rows:
        if not download.youtube_video_id:
            continue
        by_video_id[download.youtube_video_id] = {
            "download": download,
            "track": track,
            "album": album,
            "artist": artist
        }

    moved = 0
    skipped = 0
    not_found = 0
    resolved = 0
    resolved_spotify = 0
    created_spotify = 0
    unresolved = 0

    track_index = load_track_index() if (args.resolve_unknown or args.resolve_spotify) else []
    track_by_spotify_id = {
        item["track"].spotify_id: item
        for item in track_index
        if item["track"].spotify_id
    }
    spotify_cache = {}

    files = [p for p in downloads_dir.rglob("*") if p.is_file() and ".partial." not in p.name]
    for file_path in files:
        rel_parts = file_path.relative_to(downloads_dir).parts
        if len(rel_parts) >= 3:
            skipped += 1
            continue

        video_id = file_path.stem
        meta = by_video_id.get(video_id)
        if not meta and (args.resolve_unknown or args.resolve_spotify):
            artist_name = None
            track_name = None
            if is_probable_video_id(video_id):
                info = fetch_video_metadata(video_id)
                if not info:
                    unresolved += 1
                    continue
                artist_name = info.get("artist") or info.get("uploader")
                track_name = info.get("track")
                if not track_name:
                    title = info.get("title") or ""
                    guess_artist, guess_track = extract_artist_track(title)
                    artist_name = artist_name or guess_artist
                    track_name = track_name or guess_track or title
                artist_name = to_search_text(artist_name)
                track_name = to_search_text(track_name)
            else:
                raw_stem = file_path.stem.replace("_", " ")
                parent_artist = file_path.parent.name if file_path.parent != downloads_dir else None
                guess_artist, guess_track = extract_artist_track(raw_stem)
                artist_name = to_search_text(parent_artist) or to_search_text(guess_artist)
                track_name = to_search_text(guess_track) or to_search_text(raw_stem)

            used_spotify = False
            created_from_spotify = False
            match = find_match(track_index, artist_name, track_name) if args.resolve_unknown else None
            if not match and args.resolve_spotify:
                match, spotify_candidate = resolve_spotify_match(
                    track_index,
                    track_by_spotify_id,
                    artist_name,
                    track_name,
                    args.spotify_limit,
                    args.spotify_create,
                    spotify_cache,
                )
                if match:
                    used_spotify = True
                elif spotify_candidate and args.spotify_create:
                    artist, album, track = create_entities_from_spotify(spotify_candidate)
                    if artist and track:
                        match = add_track_to_index(track_index, track_by_spotify_id, artist, album, track)
                        used_spotify = True
                        created_from_spotify = True
                        spotify_cache[(artist_name or "", track_name or "")] = (match, None)
            if not match:
                unresolved += 1
                continue
            artist = match["artist"]
            track = match["track"]
            album = match["album"]
            album_name = album.name if album else "Singles"
            target_path = build_target_path(
                downloads_dir,
                artist.name,
                album_name,
                track.name,
                file_path.suffix.lstrip(".")
            )
            target_path = resolve_collision(target_path, video_id)
            if args.dry_run:
                print(f"[DRY][RESOLVE] {file_path} -> {target_path}")
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.replace(target_path)
                with get_session() as session:
                    db_row = session.exec(
                        select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == track.spotify_id)
                    ).first()
                    if not db_row:
                        db_row = YouTubeDownload(
                            spotify_track_id=track.spotify_id,
                            spotify_artist_id=artist.spotify_id,
                            youtube_video_id=video_id,
                            download_status="completed",
                            format_type=file_path.suffix.lstrip("."),
                            download_path=str(target_path),
                            file_size=target_path.stat().st_size
                        )
                        session.add(db_row)
                    else:
                        db_row.youtube_video_id = video_id
                        db_row.download_path = str(target_path)
                        db_row.download_status = "completed"
                        db_row.file_size = target_path.stat().st_size
                        session.add(db_row)
                    track_row = session.exec(
                        select(Track).where(Track.spotify_id == track.spotify_id)
                    ).first()
                    if track_row:
                        track_row.download_path = str(target_path)
                        track_row.download_status = "completed"
                        session.add(track_row)
                    session.commit()
            if used_spotify:
                resolved_spotify += 1
                if created_from_spotify:
                    created_spotify += 1
            else:
                resolved += 1
            continue

        if not meta:
            not_found += 1
            continue

        artist = meta["artist"]
        track = meta["track"]
        album = meta["album"]
        if not artist or not track:
            not_found += 1
            continue

        album_name = album.name if album else "Singles"
        target_path = build_target_path(
            downloads_dir,
            artist.name,
            album_name,
            track.name,
            file_path.suffix.lstrip(".")
        )
        target_path = resolve_collision(target_path, video_id)

        if args.dry_run:
            print(f"[DRY] {file_path} -> {target_path}")
            moved += 1
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.replace(target_path)
        moved += 1

        with get_session() as session:
            db_row = session.exec(
                select(YouTubeDownload).where(YouTubeDownload.youtube_video_id == video_id)
            ).first()
            if db_row:
                db_row.download_path = str(target_path)
                db_row.download_status = "completed"
                session.add(db_row)
                track_row = session.exec(
                    select(Track).where(Track.spotify_id == db_row.spotify_track_id)
                ).first()
                if track_row:
                    track_row.download_path = str(target_path)
                    session.add(track_row)
                session.commit()

    print(f"Moved: {moved}")
    print(f"Resolved via metadata: {resolved}")
    print(f"Resolved via Spotify: {resolved_spotify}")
    print(f"Created via Spotify: {created_spotify}")
    print(f"Skipped (already organized): {skipped}")
    print(f"No match in DB: {not_found}")
    print(f"Unresolved (metadata/spotify): {unresolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
