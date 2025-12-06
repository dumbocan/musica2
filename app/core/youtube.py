"""
YouTube Data API v3 client for music video integration.
Provides methods to search for music videos and get video metadata.
"""

import os
import re
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
import httpx
import yt_dlp
import aiofiles
from fastapi import HTTPException
from app.core.config import settings


class YouTubeClient:
    """YouTube Data API v3 client for music-related video operations."""

    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)

        if not self.api_key:
            raise ValueError("YouTube API key not configured")

    def get_download_path(self, video_id: str, format_type: str = "mp3") -> Path:
        """Get the download path for a video file."""
        return self.download_dir / f"{video_id}.{format_type}"

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
            'key': self.api_key,
            'order': 'relevance'
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/search", params=params)
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
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    }
                    for item in data.get('items', [])
                ]
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, 
                                  detail=f"YouTube API error: {str(e)}")
    
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
            'key': self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/videos", params=params)
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
                raise HTTPException(status_code=e.response.status_code, 
                                  detail=f"YouTube API error: {str(e)}")
    
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
        # Try different search query patterns for better results
        queries = [
            f"{artist} {track} official video",
            f"{artist} {track} music video",
            f"{artist} {track}",
            f"{track} {artist}"
        ]
        
        if album:
            queries.insert(0, f"{artist} {track} {album} official video")
        
        for query in queries:
            videos = await self.search_videos(query, max_results)
            if videos:
                # Filter out non-music videos and return best matches
                return self._filter_music_videos(videos, artist, track)
        
        return []
    
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
        artist_lower = artist.lower()
        track_lower = track.lower()
        
        def score_video(video: Dict[str, Any]) -> int:
            """Score a video based on how well it matches the artist and track."""
            title = video['title'].lower()
            score = 0
            
            # Check for artist name in title
            if artist_lower in title:
                score += 50
            
            # Check for track name in title
            if track_lower in title:
                score += 50
            
            # Bonus for official/vevo keywords
            if any(keyword in title for keyword in ['official', 'vevo', 'music video']):
                score += 20
            
            # Check for high-quality channels
            channel = video['channel_title'].lower()
            if any(ch in channel for ch in ['vevo', 'official', 'musica']):
                score += 10
            
            return score
        
        # Sort by score and return top results
        scored_videos = [(score_video(video), video) for video in videos]
        scored_videos.sort(key=lambda x: x[0], reverse=True)
        
        return [video for score, video in scored_videos if score > 0]
    
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
            # Get video details first
            video_details = await self.get_video_details(video_id)
            if not video_details:
                raise HTTPException(status_code=404, detail="Video not found")

            output_path = self.get_download_path(video_id, output_format)

            # Check if already downloaded
            if output_path.exists():
                file_size = output_path.stat().st_size
                return {
                    'status': 'already_exists',
                    'video_id': video_id,
                    'file_path': str(output_path),
                    'file_size': file_size,
                    'title': video_details['title'],
                    'duration': video_details['duration']
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
                'title': video_details['title'],
                'duration': video_details['duration'],
                'format': output_format
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
            for file_path in self.download_dir.iterdir():
                if file_path.is_file():
                    video_id = file_path.stem  # filename without extension
                    format_type = file_path.suffix[1:]  # extension without dot
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
        output_format: str = "mp3",
        format_quality: str = "bestaudio"
    ) -> Dict[str, Any]:
        """
        Stream audio directly to device without storing in backend.
        Returns information about the download process.

        Args:
            video_id: YouTube video ID
            output_format: Output audio format
            format_quality: Audio quality preference

        Returns:
            Dictionary with stream information
        """
        try:
            # Get video details first
            video_details = await self.get_video_details(video_id)
            if not video_details:
                raise HTTPException(status_code=404, detail="Video not found")

            # Generate a temporary filename for this session
            import uuid
            temp_filename = f"stream_{uuid.uuid4().hex}.{output_format}"

            return {
                'status': 'ready_to_stream',
                'video_id': video_id,
                'title': video_details['title'],
                'duration': video_details['duration'],
                'format': output_format,
                'quality': format_quality,
                'temp_filename': temp_filename,
                'estimated_size_mb': f"~{(video_details['duration'] * 0.0125):.1f} MB" if video_details['duration'] else "Unknown"
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to prepare stream: {str(e)}")


# Global YouTube client instance
youtube_client = YouTubeClient()
