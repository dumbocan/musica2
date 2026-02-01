"""
YouTube Data API v3 client for music video integration.
Provides methods to search for music videos and get video metadata.
"""

import re
import unicodedata
from difflib import SequenceMatcher
import uuid
import asyncio
import time
import contextlib
from datetime import datetime, timedelta
import logging
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional, Dict, Any
import httpx
import yt_dlp
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)


class YouTubeClient:
    """YouTube Data API v3 client for music-related video operations."""

    def __init__(self):
        self.api_keys = [key for key in (settings.YOUTUBE_API_KEY, settings.YOUTUBE_API_KEY_2) if key]
        self._api_key_index = 0
        self.api_key = self.api_keys[0] if self.api_keys else None
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)
        self._rate_lock = asyncio.Lock()
        self._api_key_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self.min_interval_seconds = 5.0  # Throttle requests to stay under quota
        self._search_cache: "OrderedDict[str, tuple[float, List[Dict[str, Any]]]]" = OrderedDict()
        self._search_cache_ttl_seconds = 60 * 60 * 6
        self._search_cache_max_entries = 2000
        self._request_count = 0
        self._quota_reset_hour = 4
        self._daily_request_limit = 80  # Leave 20 for user browsing
        self._quota_warned_today = False
        self._ytdlp_request_count = 0
        self._ytdlp_request_count_started_at = self._get_last_reset_anchor(datetime.now()).timestamp()
        self._ytdlp_last_request_time = 0.0
        self._ytdlp_daily_limit = settings.YTDLP_DAILY_LIMIT
        self._ytdlp_min_interval_seconds = settings.YTDLP_MIN_INTERVAL_SECONDS
        self._ytdlp_enabled_override: bool | None = None
        now = datetime.now()
        last_reset = self._get_last_reset_anchor(now)
        self._request_count_started_at = last_reset.timestamp()

        if not self.api_key and not self.is_ytdlp_enabled():
            raise ValueError("YouTube API key not configured")
        if not self.api_key and self.is_ytdlp_enabled():
            logger.warning("YouTube API key missing; using yt-dlp fallback only")

        self._noise_tokens = {
            "official",
            "video",
            "music",
            "audio",
            "lyric",
            "lyrics",
            "letra",
            "letras",
            "hd",
            "hq",
            "4k",
            "remastered",
            "live",
            "visualizer",
            "visualiser",
            "feat",
            "ft",
            "featuring",
            "album",
            "full",
            "version",
            "clip",
            "mv",
            "tv",
            "radio",
            "mix",
            "remix",
            "edit",
            "sub",
            "español",
            "spanish",
            "english",
            "officially",
            "topic",
            "records",
            "record",
        }

    def _normalize_text(self, text: str) -> str:
        text = text.lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> List[str]:
        tokens = self._normalize_text(text).split()
        return [t for t in tokens if t and t not in self._noise_tokens]

    def clean_filename(self, text: str) -> str:
        """
        Clean text to create safe filenames.
        Remove/replace problematic characters.
        """
        # Replace problematic characters with safe alternatives
        safe_text = text.replace('/', '-').replace('\\', '-').replace(':', ' -').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '-')
        # Replace multiple spaces/dashes with single ones
        safe_text = re.sub(r'[-\s]+', '-', safe_text.strip())
        # Limit length to avoid filesystem limitations
        return safe_text[:100].strip('-')

    def get_download_path(self, filename: str, format_type: str = "mp3") -> Path:
        """Get the download path for a video file using custom filename."""
        safe_filename = self.clean_filename(filename)
        return self.download_dir / f"{safe_filename}.{format_type}"

    def get_artist_download_path(self, artist_name: str, track_name: str, format_type: str = "mp3") -> Path:
        """Get organized download path: downloads/Artist/Artist - Track.mp3"""
        safe_artist = self.clean_filename(artist_name)
        artist_dir = self.download_dir / safe_artist
        artist_dir.mkdir(exist_ok=True)  # Create artist folder if needed

        full_filename = f"{safe_artist} - {self.clean_filename(track_name)}.{format_type}"
        return artist_dir / full_filename

    def get_album_download_path(
        self,
        artist_name: str,
        album_name: str,
        track_name: str,
        format_type: str = "mp3"
    ) -> Path:
        """Get organized download path: downloads/Artist/Album/Track.ext"""
        safe_artist = self.clean_filename(artist_name)
        safe_album = self.clean_filename(album_name)
        safe_track = self.clean_filename(track_name)
        album_dir = self.download_dir / safe_artist / safe_album
        album_dir.mkdir(parents=True, exist_ok=True)
        return album_dir / f"{safe_track}.{format_type}"

    def get_ydl_opts(self, output_path: Path, format_quality: str = "bestaudio") -> Dict[str, Any]:
        """Get yt-dlp options for audio extraction."""
        return {
            'format': f'{format_quality}/bestaudio',  # Download best audio
            'extractaudio': True,  # Extract audio
            'audioformat': 'mp3',  # Convert to MP3
            'outtmpl': str(output_path.with_suffix('')),  # Output template
            'noplaylist': True,  # Don't download playlists
            'quiet': True,  # Suppress output
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',  # 192 kbps
            }],
        }

    async def _throttle(self):
        """Ensure there's at least `min_interval_seconds` between API requests."""
        async with self._rate_lock:
            now = time.monotonic()
            wait_time = self.min_interval_seconds - (now - self._last_request_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request_time = time.monotonic()

    async def _rotate_api_key(self) -> bool:
        if len(self.api_keys) <= 1:
            return False
        async with self._api_key_lock:
            if len(self.api_keys) <= 1:
                return False
            self._api_key_index = (self._api_key_index + 1) % len(self.api_keys)
            self.api_key = self.api_keys[self._api_key_index]
            logger.warning("YouTube API quota exceeded; rotated API key")
            return True

    async def _api_get(self, endpoint: str, params: Dict[str, Any]) -> httpx.Response:
        # Check daily limit before making requests
        self._maybe_reset_counter()
        if self._request_count >= self._daily_request_limit:
            logger.warning("YouTube API daily limit reached (%d/%d)", self._request_count, self._daily_request_limit)
            return httpx.Response(
                status_code=403,
                json={"error": {"errors": [{"reason": "dailyLimitExceeded", "message": "Daily request limit reached"}]}}
            )

        attempts = max(1, len(self.api_keys))
        for attempt in range(attempts):
            params_with_key = dict(params)
            params_with_key["key"] = self.api_key
            async with httpx.AsyncClient() as client:
                await self._throttle()
                self._maybe_reset_counter()
                self._request_count += 1
                response = await client.get(f"{self.base_url}/{endpoint}", params=params_with_key)

            if response.status_code != 403:
                return response

            reason = None
            try:
                payload = response.json()
                errors = payload.get("error", {}).get("errors") or []
                if errors:
                    reason = errors[0].get("reason")
            except Exception:
                reason = None

            if reason not in ("quotaExceeded", "dailyLimitExceeded"):
                return response

            if attempt >= attempts - 1:
                return response

            rotated = await self._rotate_api_key()
            if not rotated:
                return response

        return response

    def _get_last_reset_anchor(self, now: datetime) -> datetime:
        anchor = now.replace(
            hour=self._quota_reset_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if now < anchor:
            anchor -= timedelta(days=1)
        return anchor

    def _maybe_reset_counter(self) -> None:
        now = datetime.now()
        last_reset = datetime.fromtimestamp(self._request_count_started_at)
        next_reset = last_reset + timedelta(days=1)
        if now < next_reset:
            return
        while now >= next_reset:
            last_reset = next_reset
            next_reset = last_reset + timedelta(days=1)
        self._request_count_started_at = last_reset.timestamp()
        self._request_count = 0

    def _maybe_reset_ytdlp_counter(self) -> None:
        now = datetime.now()
        last_reset = datetime.fromtimestamp(self._ytdlp_request_count_started_at)
        next_reset = last_reset + timedelta(days=1)
        if now < next_reset:
            return
        while now >= next_reset:
            last_reset = next_reset
            next_reset = last_reset + timedelta(days=1)
        self._ytdlp_request_count_started_at = last_reset.timestamp()
        self._ytdlp_request_count = 0

    async def _ytdlp_throttle(self) -> None:
        now = time.monotonic()
        wait_time = self._ytdlp_min_interval_seconds - (now - self._ytdlp_last_request_time)
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._ytdlp_last_request_time = time.monotonic()

    def _ytdlp_can_request(self) -> bool:
        self._maybe_reset_ytdlp_counter()
        return self._ytdlp_request_count < self._ytdlp_daily_limit

    def _ytdlp_search_sync(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "default_search": f"ytsearch{max_results}",
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
        entries = info.get("entries") or []
        results: List[Dict[str, Any]] = []
        for entry in entries:
            video_id = entry.get("id")
            if not video_id:
                continue
            results.append(
                {
                    "video_id": video_id,
                    "title": entry.get("title") or "",
                    "description": entry.get("description") or "",
                    "channel_title": entry.get("uploader") or entry.get("channel") or "",
                    "published_at": entry.get("upload_date"),
                    "thumbnails": entry.get("thumbnails"),
                    "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                    "source": "ytdlp",
                }
            )
        return results

    async def search_music_videos_ytdlp(
        self,
        artist: str,
        track: str,
        album: Optional[str] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        if not self.is_ytdlp_enabled():
            return []
        if not self._ytdlp_can_request():
            logger.warning("yt-dlp daily limit reached (%d/%d)", self._ytdlp_request_count, self._ytdlp_daily_limit)
            return []

        cache_key = self._cache_key(f"ytdlp:{artist}", track, album, max_results)
        cached = self._get_cached_search(cache_key)
        if cached is not None:
            return cached

        queries = []
        if album:
            queries.append(f"{artist} {track} {album} official video")
        queries.append(f"{artist} {track} official video")
        queries.append(f"{artist} {track}")

        fetch_results = max(max_results, 5)
        for query in queries:
            await self._ytdlp_throttle()
            self._maybe_reset_ytdlp_counter()
            self._ytdlp_request_count += 1
            try:
                videos = await asyncio.to_thread(self._ytdlp_search_sync, query, fetch_results)
            except Exception as exc:
                logger.warning("yt-dlp search failed for query %s: %r", query, exc)
                continue

            filtered = self._filter_music_videos(videos, artist, track)
            if filtered:
                trimmed = filtered[:max_results]
                self._set_cached_search(cache_key, trimmed)
                return trimmed

        self._set_cached_search(cache_key, [])
        return []

    def get_usage(self) -> Dict[str, Any]:
        self._maybe_reset_counter()
        last_reset = datetime.fromtimestamp(self._request_count_started_at)
        next_reset = last_reset + timedelta(days=1)
        return {
            "requests_total": self._request_count,
            "requests_limit": self._daily_request_limit,
            "started_at_unix": int(self._request_count_started_at),
            "next_reset_at_unix": int(next_reset.timestamp()),
            "reset_hour_local": self._quota_reset_hour,
            "remaining": max(0, self._daily_request_limit - self._request_count),
        }

    def get_ytdlp_usage(self) -> Dict[str, Any]:
        self._maybe_reset_ytdlp_counter()
        last_reset = datetime.fromtimestamp(self._ytdlp_request_count_started_at)
        next_reset = last_reset + timedelta(days=1)
        return {
            "requests_total": self._ytdlp_request_count,
            "requests_limit": self._ytdlp_daily_limit,
            "started_at_unix": int(self._ytdlp_request_count_started_at),
            "next_reset_at_unix": int(next_reset.timestamp()),
            "remaining": max(0, self._ytdlp_daily_limit - self._ytdlp_request_count),
        }

    def should_stop_for_quota(self) -> bool:
        """Check if we should stop requesting due to daily limit."""
        self._maybe_reset_counter()
        return self._request_count >= self._daily_request_limit

    def _cache_key(self, artist: str, track: str, album: Optional[str], max_results: int) -> str:
        parts = [
            artist.strip().lower(),
            track.strip().lower(),
            (album or "").strip().lower(),
            str(max_results),
        ]
        return "|".join(parts)

    def _get_cached_search(self, key: str) -> Optional[List[Dict[str, Any]]]:
        entry = self._search_cache.get(key)
        if not entry:
            return None
        timestamp, results = entry
        if time.monotonic() - timestamp > self._search_cache_ttl_seconds:
            self._search_cache.pop(key, None)
            return None
        self._search_cache.move_to_end(key)
        return results

    def _set_cached_search(self, key: str, results: List[Dict[str, Any]]) -> None:
        self._search_cache[key] = (time.monotonic(), results)
        self._search_cache.move_to_end(key)
        if len(self._search_cache) > self._search_cache_max_entries:
            self._search_cache.popitem(last=False)

    async def search_videos(
        self,
        query: str,
        max_results: int = 10,
        video_category_id: str = "10"  # Music category
    ) -> List[Dict[str, Any]]:
        """
        Search for music videos by query.

        Args:
            query: Search query (artist, track name, etc.)
            max_results: Maximum number of results to return
            video_category_id: YouTube video category ID (10 = Music)

        Returns:
            List of video information dictionaries
        """
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'videoCategoryId': video_category_id,
            'maxResults': min(max_results, 50),
            'order': 'relevance'
        }

        try:
            response = await self._api_get("search", params)
            response.raise_for_status()
            data = response.json()

            return [
                {
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnails': item['snippet']['thumbnails'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'source': "youtube_api",
                }
                for item in data.get('items', [])
            ]
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"YouTube API error: {str(e)}",
            )

    async def get_video_details(self, video_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            Detailed video information
        """
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': video_id,
        }

        try:
            response = await self._api_get("videos", params)
            response.raise_for_status()
            data = response.json()

            if not data.get('items'):
                raise HTTPException(status_code=404, detail="Video not found")

            item = data['items'][0]

            return {
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'channel_title': item['snippet']['channelTitle'],
                'published_at': item['snippet']['publishedAt'],
                'thumbnails': item['snippet']['thumbnails'],
                'statistics': item.get('statistics', {}),
                'duration': item['contentDetails']['duration'],
                'definition': item['contentDetails']['definition'],
                'caption': item['contentDetails']['caption'],
                'url': f"https://www.youtube.com/watch?v={item['id']}"
            }
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"YouTube API error: {str(e)}",
            )

    async def search_music_videos(
        self,
        artist: str,
        track: str,
        album: Optional[str] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search specifically for music videos by artist and track.

        Args:
            artist: Artist name
            track: Track name
            album: Optional album name
            max_results: Maximum number of results

        Returns:
            List of matching music videos
        """
        cache_key = self._cache_key(artist, track, album, max_results)
        cached = self._get_cached_search(cache_key)
        if cached is not None:
            return cached

        # Minimize calls: prefer a single high-signal query, fall back once for lists.
        queries = []
        if album:
            queries.append(f"{artist} {track} {album} official video")
        queries.append(f"{artist} {track} official video")
        if max_results > 1:
            queries.append(f"{artist} {track}")

        fetch_results = max(max_results, 5)
        if self.api_key and not self.should_stop_for_quota():
            for query in queries:
                try:
                    videos = await self.search_videos(query, fetch_results)
                except Exception as exc:
                    logger.warning("YouTube API search failed for %s - %s: %r", artist, track, exc)
                    break
                if not videos:
                    continue
                filtered = self._filter_music_videos(videos, artist, track)
                if filtered:
                    trimmed = filtered[:max_results]
                    self._set_cached_search(cache_key, trimmed)
                    return trimmed

        if self.is_ytdlp_enabled():
            fallback = await self.search_music_videos_ytdlp(artist, track, album, max_results)
            if fallback:
                logger.info("[ytdlp] fallback used for %s - %s", artist, track)
                self._set_cached_search(cache_key, fallback)
                return fallback

        self._set_cached_search(cache_key, [])
        return []

    def is_ytdlp_enabled(self) -> bool:
        if self._ytdlp_enabled_override is None:
            return settings.YTDLP_FALLBACK_ENABLED
        return self._ytdlp_enabled_override

    def set_ytdlp_enabled(self, enabled: bool) -> None:
        self._ytdlp_enabled_override = bool(enabled)

    def _filter_music_videos(
        self,
        videos: List[Dict[str, Any]],
        artist: str,
        track: str
    ) -> List[Dict[str, Any]]:
        """
        Filter videos to find best matches for the given artist and track.

        Args:
            videos: List of video information
            artist: Target artist name
            track: Target track name

        Returns:
            Filtered list of music videos
        """
        artist_tokens = self._tokenize(artist)
        track_tokens = self._tokenize(track)
        if not track_tokens:
            return []

        def score_video(video: Dict[str, Any]) -> Optional[int]:
            """Score a video based on how well it matches the artist and track."""
            title = video.get("title", "")
            description = video.get("description", "")
            title_norm = self._normalize_text(title)
            title_tokens = set(self._tokenize(title))
            desc_tokens = set(self._tokenize(description))
            score = 0

            track_hits = sum(1 for token in track_tokens if token in title_tokens or token in desc_tokens)
            artist_hits = sum(1 for token in artist_tokens if token in title_tokens or token in desc_tokens)
            track_ratio = track_hits / max(1, len(track_tokens))
            track_phrase = " ".join(track_tokens)
            title_similarity = SequenceMatcher(None, track_phrase, title_norm).ratio() if track_phrase else 0.0

            if track_ratio < 0.6 and title_similarity < 0.6:
                return None

            score += track_hits * 60
            score += artist_hits * 25
            if track_phrase and track_phrase in title_norm:
                score += 30
            if "official" in title_norm:
                score += 10
            if "vevo" in title_norm:
                score += 8

            channel = self._normalize_text(video.get("channel_title", ""))
            if any(token in channel for token in ("vevo", "official", "musica", "music")):
                score += 6

            return score

        # Sort by score and return top results
        scored_videos = []
        for video in videos:
            score = score_video(video)
            if score is None:
                continue
            scored_videos.append((score, video))
        scored_videos.sort(key=lambda x: x[0], reverse=True)

        seen_ids = set()
        results = []
        for score, video in scored_videos:
            video_id = video.get("video_id")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)
            results.append(video)
        return results

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract YouTube video ID from various URL formats.

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if not found
        """
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    async def get_video_duration_seconds(self, video_id: str) -> Optional[int]:
        """
        Get video duration in seconds.

        Args:
            video_id: YouTube video ID

        Returns:
            Duration in seconds or None if not available
        """
        try:
            video_details = await self.get_video_details(video_id)
            duration_str = video_details.get('duration', '')

            # Parse ISO 8601 duration (PT4M13S -> 253 seconds)
            if duration_str.startswith('PT'):
                duration_str = duration_str[2:]  # Remove 'PT'

                seconds = 0
                if 'H' in duration_str:
                    hours = int(duration_str.split('H')[0])
                    seconds += hours * 3600
                    duration_str = duration_str.split('H')[1]

                if 'M' in duration_str:
                    minutes = int(duration_str.split('M')[0])
                    seconds += minutes * 60
                    duration_str = duration_str.split('M')[1]

                if 'S' in duration_str:
                    seconds += int(duration_str.split('S')[0])

                return seconds

        except Exception:
            return None

        return None

    async def download_audio(
        self,
        video_id: str,
        format_quality: str = "bestaudio",
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Download audio from a YouTube video.

        Args:
            video_id: YouTube video ID
            format_quality: Audio quality preference
            output_format: Output audio format (mp3, m4a, etc.)

        Returns:
            Dictionary with download status and file info
        """
        try:
            # Best-effort metadata; do not fail download on quota errors.
            video_details = await self._safe_get_video_details(video_id)

            output_path = self.get_download_path(video_id, output_format)

            # Check if already downloaded
            if output_path.exists():
                file_size = output_path.stat().st_size
                return {
                    'status': 'already_exists',
                    'video_id': video_id,
                    'file_path': str(output_path),
                    'file_size': file_size,
                    'title': video_details['title'] if video_details else video_id,
                    'duration': video_details['duration'] if video_details else None
                }

            # Configure yt-dlp options
            ydl_opts = self.get_ydl_opts(output_path, format_quality)
            ydl_opts['postprocessors'][0]['preferredcodec'] = output_format

            download_id = f"download_{uuid.uuid4().hex}"

            # Download in a thread to keep it async
            loop = asyncio.get_event_loop()

            def download_sync():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                except Exception as e:
                    raise e

            await loop.run_in_executor(None, download_sync)

            # Verify the file was created
            if not output_path.exists():
                raise HTTPException(status_code=500, detail="Download failed - file not created")

            file_size = output_path.stat().st_size

            return {
                'status': 'completed',
                'download_id': download_id,
                'video_id': video_id,
                'file_path': str(output_path),
                'file_size': file_size,
                'title': video_details['title'] if video_details else video_id,
                'duration': video_details['duration'] if video_details else None,
                'format': output_format
            }

        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def download_audio_for_track(
        self,
        video_id: str,
        artist_name: str,
        track_name: str,
        format_quality: str = "bestaudio",
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Download audio from a YouTube video using clean filename (Artist - Track).

        Args:
            video_id: YouTube video ID
            artist_name: Artist name for clean filename
            track_name: Track name for clean filename
            format_quality: Audio quality preference
            output_format: Output audio format (mp3, m4a, etc.)

        Returns:
            Dictionary with download status and file info
        """
        try:
            # Best-effort metadata; do not fail download on quota errors.
            video_details = await self._safe_get_video_details(video_id)

            # Create clean filename: "Artist - Track"
            filename = f"{artist_name} - {track_name}"
            output_path = self.get_download_path(filename, output_format)

            # Check if already downloaded
            if output_path.exists():
                file_size = output_path.stat().st_size
                return {
                    'status': 'already_exists',
                    'video_id': video_id,
                    'file_path': str(output_path),
                    'file_size': file_size,
                    'title': video_details['title'] if video_details else f"{artist_name} - {track_name}",
                    'duration': video_details['duration'] if video_details else None,
                    'artist': artist_name,
                    'track': track_name
                }

            # Configure yt-dlp options
            ydl_opts = self.get_ydl_opts(output_path, format_quality)
            ydl_opts['postprocessors'][0]['preferredcodec'] = output_format

            download_id = f"download_{uuid.uuid4().hex}"

            # Download in a thread to keep it async
            loop = asyncio.get_event_loop()

            def download_sync():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                except Exception as e:
                    raise e

            await loop.run_in_executor(None, download_sync)

            # Verify the file was created
            if not output_path.exists():
                raise HTTPException(status_code=500, detail="Download failed - file not created")

            file_size = output_path.stat().st_size

            return {
                'status': 'completed',
                'download_id': download_id,
                'video_id': video_id,
                'file_path': str(output_path),
                'file_size': file_size,
                'title': video_details['title'] if video_details else f"{artist_name} - {track_name}",
                'duration': video_details['duration'] if video_details else None,
                'artist': artist_name,
                'track': track_name,
                'format': output_format
            }

        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def download_audio_for_organized_track(
        self,
        video_id: str,
        artist_name: str,
        track_name: str,
        format_quality: str = "bestaudio",
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Download audio to organized folder structure: downloads/Artist/Artist - Track.mp3
        """
        try:
            # Best-effort metadata; do not fail download on quota errors.
            video_details = await self._safe_get_video_details(video_id)

            # Use organized path: downloads/Artist/Artist - Track.mp3
            output_path = self.get_artist_download_path(artist_name, track_name, output_format)

            # Check if already downloaded in organized structure
            if output_path.exists():
                file_size = output_path.stat().st_size
                return {
                    'status': 'already_exists',
                    'video_id': video_id,
                    'file_path': str(output_path),
                    'file_size': file_size,
                    'title': video_details['title'] if video_details else f"{artist_name} - {track_name}",
                    'duration': video_details['duration'] if video_details else None,
                    'artist': artist_name,
                    'track': track_name,
                    'organized': True
                }

            # Configure yt-dlp options for organized path
            ydl_opts = self.get_ydl_opts(output_path, format_quality)
            ydl_opts['postprocessors'][0]['preferredcodec'] = output_format

            download_id = f"download_{uuid.uuid4().hex}"

            # Download in a thread to keep it async
            loop = asyncio.get_event_loop()

            def download_sync():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                except Exception as e:
                    raise e

            await loop.run_in_executor(None, download_sync)

            # Verify the file was created
            if not output_path.exists():
                raise HTTPException(status_code=500, detail="Download failed - file not created")

            file_size = output_path.stat().st_size

            return {
                'status': 'completed',
                'download_id': download_id,
                'video_id': video_id,
                'file_path': str(output_path),
                'file_size': file_size,
                'title': video_details['title'] if video_details else f"{artist_name} - {track_name}",
                'duration': video_details['duration'] if video_details else None,
                'artist': artist_name,
                'track': track_name,
                'format': output_format,
                'organized': True
            }

        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def download_audio_for_album_track(
        self,
        video_id: str,
        artist_name: str,
        album_name: str,
        track_name: str,
        format_quality: str = "bestaudio",
        output_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Download audio to organized folder structure: downloads/Artist/Album/Track.ext
        """
        try:
            video_details = await self._safe_get_video_details(video_id)
            output_path = self.get_album_download_path(artist_name, album_name, track_name, output_format)

            if output_path.exists():
                file_size = output_path.stat().st_size
                return {
                    'status': 'already_exists',
                    'video_id': video_id,
                    'file_path': str(output_path),
                    'file_size': file_size,
                    'title': video_details['title'] if video_details else track_name,
                    'duration': video_details['duration'] if video_details else None,
                    'artist': artist_name,
                    'album': album_name,
                    'track': track_name,
                    'organized': True
                }

            ydl_opts = self.get_ydl_opts(output_path, format_quality)
            ydl_opts['postprocessors'][0]['preferredcodec'] = output_format

            download_id = f"download_{uuid.uuid4().hex}"
            loop = asyncio.get_event_loop()

            def download_sync():
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                except Exception as e:
                    raise e

            await loop.run_in_executor(None, download_sync)

            if not output_path.exists():
                raise HTTPException(status_code=500, detail="Download failed - file not created")

            file_size = output_path.stat().st_size
            return {
                'status': 'completed',
                'download_id': download_id,
                'video_id': video_id,
                'file_path': str(output_path),
                'file_size': file_size,
                'title': video_details['title'] if video_details else track_name,
                'duration': video_details['duration'] if video_details else None,
                'artist': artist_name,
                'album': album_name,
                'track': track_name,
                'format': output_format,
                'organized': True
            }
        except yt_dlp.utils.DownloadError as e:
            raise HTTPException(status_code=500, detail=f"YouTube download error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def get_download_status(self, video_id: str, format_type: str = "mp3") -> Dict[str, Any]:
        """
        Check if an audio file exists and return its status.

        Args:
            video_id: YouTube video ID
            format_type: Audio format

        Returns:
            Dictionary with file status
        """
        file_path = self.get_download_path(video_id, format_type)

        if file_path.exists():
            file_size = file_path.stat().st_size
            return {
                'exists': True,
                'video_id': video_id,
                'file_path': str(file_path),
                'file_size': file_size,
                'format': format_type
            }
        else:
            return {
                'exists': False,
                'video_id': video_id,
                'format': format_type
            }

    async def list_downloads(self) -> List[Dict[str, Any]]:
        """
        List all downloaded audio files.

        Returns:
            List of download information
        """
        downloads = []

        if self.download_dir.exists():
            for file_path in self.download_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                if ".partial." in file_path.name:
                    continue
                video_id = file_path.stem
                format_type = file_path.suffix[1:]
                file_size = file_path.stat().st_size
                downloads.append({
                    'video_id': video_id,
                    'file_path': str(file_path),
                    'file_size': file_size,
                    'format': format_type
                })

        return downloads

    async def delete_download(self, video_id: str, format_type: str = "mp3") -> bool:
        """
        Delete a downloaded audio file.

        Args:
            video_id: YouTube video ID
            format_type: Audio format

        Returns:
            True if deleted successfully
        """
        file_path = self.get_download_path(video_id, format_type)

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    async def stream_audio_to_device(
        self,
        video_id: str,
        output_format: str = "m4a",
        format_quality: str = "bestaudio",
        cache: bool = True,
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Stream audio directly to device without storing in backend.
        Returns information and a streaming generator.

        Args:
            video_id: YouTube video ID
            output_format: Output audio format
            format_quality: Audio quality preference

        Returns:
            Dictionary with stream information
        """
        try:
            output_format = output_format.lower()
            if output_format not in ("m4a", "webm"):
                raise HTTPException(status_code=400, detail="Unsupported stream format")

            format_selector = "bestaudio[ext=m4a]/bestaudio" if output_format == "m4a" else "bestaudio[ext=webm]/bestaudio"
            loop = asyncio.get_running_loop()

            def extract_info():
                with yt_dlp.YoutubeDL({
                    "format": format_selector,
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                }) as ydl:
                    return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

            info = await loop.run_in_executor(None, extract_info)
            stream_url = info.get("url")
            if not stream_url:
                raise HTTPException(status_code=500, detail="Unable to resolve audio stream URL")

            ext = (info.get("ext") or output_format).lower()
            media_type = "audio/mp4" if ext == "m4a" else "audio/webm"

            if output_path:
                output_path = output_path.with_suffix(f".{ext}")
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_path = self.get_download_path(video_id, ext)
            if cache and output_path.exists():
                return {
                    "type": "file",
                    "file_path": str(output_path),
                    "media_type": media_type,
                    "title": info.get("title") or video_id,
                    "ext": ext
                }

            temp_path = output_path.with_name(f"{output_path.stem}.partial.{ext}")

            async def stream():
                file_handle = None
                try:
                    if cache:
                        file_handle = open(temp_path, "wb")
                    async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
                        async with client.stream("GET", stream_url) as response:
                            response.raise_for_status()
                            async for chunk in response.aiter_bytes(65536):
                                if file_handle:
                                    file_handle.write(chunk)
                                yield chunk
                    if file_handle:
                        file_handle.flush()
                        file_handle.close()
                        file_handle = None
                        temp_path.replace(output_path)
                except asyncio.CancelledError:
                    if file_handle:
                        file_handle.close()
                    if cache:
                        with contextlib.suppress(FileNotFoundError):
                            temp_path.unlink()
                    raise
                except Exception as exc:
                    if file_handle:
                        file_handle.close()
                    if cache:
                        with contextlib.suppress(FileNotFoundError):
                            temp_path.unlink()
                    logger.warning("Streaming audio failed for %s: %s", video_id, exc)

            return {
                "type": "stream",
                "stream": stream(),
                "media_type": media_type,
                "title": info.get("title") or video_id,
                "ext": ext
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to prepare stream: {str(e)}")

    async def _safe_get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.get_video_details(video_id)
        except HTTPException as exc:
            logger.warning("YouTube metadata lookup failed for %s: %s", video_id, exc.detail)
            return None
        except Exception as exc:
            logger.warning("YouTube metadata lookup failed for %s: %s", video_id, exc)
            return None


# Global YouTube client instance
youtube_client = YouTubeClient()
