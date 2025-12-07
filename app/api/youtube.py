"""
YouTube API endpoints for music video integration.
Provides search functionality and video metadata retrieval.
"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import FileResponse
from app.core.youtube import youtube_client

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/search")
async def search_videos(
    query: str = Query(..., description="Search query for videos"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results (1-50)"),
    category: str = Query("10", description="YouTube category ID (10 = Music)")
):
    """
    Search for videos by query.
    
    - **query**: Search query (artist, track name, etc.)
    - **max_results**: Maximum number of results to return (1-50)
    - **category**: YouTube category ID (default: 10 for Music)
    """
    try:
        videos = await youtube_client.search_videos(
            query=query,
            max_results=max_results,
            video_category_id=category
        )
        return {
            "query": query,
            "total_results": len(videos),
            "videos": videos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching videos: {str(e)}")


@router.get("/search/music")
async def search_music_videos(
    artist: str = Query(..., description="Artist name"),
    track: str = Query(..., description="Track name"),
    album: Optional[str] = Query(None, description="Album name (optional)"),
    max_results: int = Query(5, ge=1, le=20, description="Maximum number of results (1-20)")
):
    """
    Search specifically for music videos by artist and track.
    
    - **artist**: Artist name
    - **track**: Track name
    - **album**: Album name (optional)
    - **max_results**: Maximum number of results (1-20)
    """
    try:
        videos = await youtube_client.search_music_videos(
            artist=artist,
            track=track,
            album=album,
            max_results=max_results
        )
        return {
            "search_criteria": {
                "artist": artist,
                "track": track,
                "album": album
            },
            "total_results": len(videos),
            "videos": videos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching music videos: {str(e)}")


@router.get("/video/{video_id}")
async def get_video_details(video_id: str):
    """
    Get detailed information about a specific video.
    
    - **video_id**: YouTube video ID
    """
    try:
        video_details = await youtube_client.get_video_details(video_id)
        return video_details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting video details: {str(e)}")


@router.get("/video/{video_id}/duration")
async def get_video_duration(video_id: str):
    """
    Get video duration in seconds.
    
    - **video_id**: YouTube video ID
    """
    try:
        duration_seconds = await youtube_client.get_video_duration_seconds(video_id)
        if duration_seconds is None:
            raise HTTPException(status_code=404, detail="Video duration not available")
        
        # Convert seconds to minutes:seconds format
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        duration_formatted = f"{minutes}:{seconds:02d}"
        
        return {
            "video_id": video_id,
            "duration_seconds": duration_seconds,
            "duration_formatted": duration_formatted
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting video duration: {str(e)}")


@router.post("/extract-video-id")
async def extract_video_id(url: str = Query(..., description="YouTube URL")):
    """
    Extract YouTube video ID from various URL formats.
    
    - **url**: YouTube URL (supports various formats)
    """
    try:
        video_id = youtube_client.extract_video_id(url)
        if video_id:
            return {
                "url": url,
                "video_id": video_id,
                "embed_url": f"https://www.youtube.com/embed/{video_id}"
            }
        else:
            raise HTTPException(status_code=400, detail="Could not extract video ID from URL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting video ID: {str(e)}")


@router.get("/track/{track_id}/videos")
async def get_track_videos(
    track_id: int,
    max_results: int = Query(3, ge=1, le=10, description="Maximum number of videos to return")
):
    """
    Get YouTube videos for a track from the local database.
    
    - **track_id**: Track ID from local database
    - **max_results**: Maximum number of videos to return (1-10)
    """
    try:
        from app.core.db import SessionDep
        from sqlmodel import select
        from app.models.base import Track, Artist, Album
        
        # Get track with artist info from database
        track = await Track.get_track_with_details(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        
        artist = track.artist
        album = track.album
        
        # Search for music videos
        videos = await youtube_client.search_music_videos(
            artist=artist.name,
            track=track.title,
            album=album.name if album else None,
            max_results=max_results
        )
        
        return {
            "track_info": {
                "id": track.id,
                "title": track.title,
                "artist": artist.name,
                "album": album.name if album else None
            },
            "total_videos": len(videos),
            "videos": videos
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting track videos: {str(e)}")


@router.get("/artist/{artist_id}/videos")
async def get_artist_videos(
    artist_id: int,
    max_results: int = Query(10, ge=1, le=25, description="Maximum number of videos to return")
):
    """
    Get YouTube videos for an artist's popular tracks from the local database.
    
    - **artist_id**: Artist ID from local database
    - **max_results**: Maximum number of videos to return (1-25)
    """
    try:
        from sqlmodel import select
        from app.models.base import Artist, Track
        
        # Get artist and their tracks
        artist = await Artist.get_artist_with_tracks(artist_id)
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        # Get top tracks by playcount or rating
        tracks = await Track.get_artist_top_tracks(artist_id, limit=min(max_results, 10))
        
        all_videos = []
        
        # Search for videos for each track
        for track in tracks:
            try:
                videos = await youtube_client.search_music_videos(
                    artist=artist.name,
                    track=track.title,
                    max_results=1  # Just get the best match per track
                )
                if videos:
                    video = videos[0]
                    video['track_id'] = track.id
                    video['track_title'] = track.title
                    all_videos.append(video)
            except Exception:
                # Continue if individual track search fails
                continue
        
        return {
            "artist_info": {
                "id": artist.id,
                "name": artist.name
            },
            "total_videos": len(all_videos),
            "videos": all_videos
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting artist videos: {str(e)}")


@router.get("/health")
async def youtube_health_check():
    """
    Health check for YouTube API integration.
    """
    try:
        # Test basic connectivity to YouTube API
        test_videos = await youtube_client.search_videos("test", max_results=1)
        downloads_dir = youtube_client.download_dir.exists()
        return {
            "status": "ok",
            "message": "YouTube API connection successful",
            "api_key_configured": bool(youtube_client.api_key),
            "downloads_directory_exists": downloads_dir
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"YouTube API connection failed: {str(e)}",
            "api_key_configured": bool(youtube_client.api_key)
        }


# Audio Download Endpoints

@router.post("/download/{video_id}")
async def download_audio(
    video_id: str,
    format: str = Query("mp3", description="Audio format (mp3, m4a, etc.)"),
    quality: str = Query("bestaudio", description="Audio quality (bestaudio, best, worst)"),
    to_device: bool = Query(False, description="Stream directly to device instead of storing")
):
    """
    Download audio from a YouTube video.

    - **video_id**: YouTube video ID
    - **format**: Audio format (mp3, m4a, etc.)
    - **quality**: Audio quality preference
    - **to_device**: If true, streams directly to device without storing

    ⚠️ **IMPORTANT**: Downloaded content remains in server storage unless to_device=true.
    """
    try:
        if to_device:
            # Stream directly to device without storing
            return await youtube_client.stream_audio_to_device(
                video_id=video_id,
                output_format=format,
                format_quality=quality
            )
        else:
            # Store in backend for caching/recovery
            result = await youtube_client.download_audio(
                video_id=video_id,
                output_format=format,
                format_quality=quality
            )
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/download/{video_id}/status")
async def check_download_status(
    video_id: str,
    format: str = Query("mp3", description="Audio format")
):
    """
    Check if an audio file exists for a video.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        status = await youtube_client.get_download_status(video_id, format)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking status: {str(e)}")


@router.get("/download/{video_id}/file")
async def get_downloaded_file(
    video_id: str,
    format: str = Query("mp3", description="Audio format")
):
    """
    Serve a downloaded audio file.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        status = await youtube_client.get_download_status(video_id, format)

        if not status['exists']:
            raise HTTPException(status_code=404, detail="Audio file not found for this video")

        file_path = status['file_path']

        # Get video details for filename
        try:
            video_details = await youtube_client.get_video_details(video_id)
            filename = f"{video_details['title']}.{format}"
        except:
            filename = f"{video_id}.{format}"

        # Return file as streaming response
        return FileResponse(
            path=file_path,
            media_type=f"audio/{format}",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")


@router.get("/downloads")
async def list_downloads():
    """
    List all downloaded audio files.
    """
    try:
        downloads = await youtube_client.list_downloads()
        return {
            "total_files": len(downloads),
            "downloads": downloads
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing downloads: {str(e)}")


@router.delete("/download/{video_id}")
async def delete_download(
    video_id: str,
    format: str = Query("mp3", description="Audio format")
):
    """
    Delete a downloaded audio file.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        deleted = await youtube_client.delete_download(video_id, format)

        if deleted:
            return {
                "message": f"Successfully deleted audio file for video {video_id}",
                "video_id": video_id,
                "format": format
            }
        else:
            raise HTTPException(status_code=404, detail="Audio file not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
