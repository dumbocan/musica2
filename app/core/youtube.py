"""
YouTube Data API v3 client for music video integration.
Provides methods to search for music videos and get video metadata.
"""

import os
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
import httpx
from fastapi import HTTPException
from app.core.config import settings


class YouTubeClient:
    """YouTube Data API v3 client for music-related video operations."""
    
    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3"
        
        if not self.api_key:
            raise ValueError("YouTube API key not configured")
    
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


# Global YouTube client instance
youtube_client = YouTubeClient()
