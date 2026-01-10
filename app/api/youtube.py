"""
YouTube API endpoints for music video integration.
Provides search functionality and video metadata retrieval.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.core.youtube import youtube_client
from app.core.spotify import spotify_client
from app.core.db import get_session, SessionDep
from app.crud import save_youtube_download
from app.models.base import Album, Artist, Track, YouTubeDownload

router = APIRouter(prefix="/youtube", tags=["youtube"])
logger = logging.getLogger(__name__)
prefetch_tasks: Dict[str, asyncio.Task] = {}


class YoutubeLinkBatchRequest(BaseModel):
    spotify_track_ids: List[str]


class YoutubeTrackRefreshRequest(BaseModel):
    artist: Optional[str] = None
    track: Optional[str] = None
    album: Optional[str] = None


def _fetch_existing_download_ids(track_ids: List[str]) -> set[str]:
    with get_session() as session:
        rows = session.exec(
            select(YouTubeDownload.spotify_track_id).where(YouTubeDownload.spotify_track_id.in_(track_ids))
        ).all()
    return {row[0] for row in rows if row[0]}


async def _resolve_track_metadata(
    video_id: str,
    session: AsyncSession,
) -> Tuple[Optional[YouTubeDownload], Optional[Track], Optional[Album], Optional[Artist]]:
    row = (await session.exec(
        select(YouTubeDownload, Track, Album, Artist)
        .join(Track, Track.spotify_id == YouTubeDownload.spotify_track_id)
        .join(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(YouTubeDownload.youtube_video_id == video_id)
    )).first()
    if not row:
        return None, None, None, None
    download, track, album, artist = row
    return download, track, album, artist


async def _prefetch_album_links(spotify_album_id: str):
    """Background coroutine that fetches YouTube links for every track in an album."""
    try:
        album_info = await spotify_client.get_album(spotify_album_id)
        album_name = album_info.get("name")
        tracks = await spotify_client.get_album_tracks(spotify_album_id)
        default_artist = (album_info.get("artists") or [{}])[0]
        default_artist_name = default_artist.get("name", "")
        default_artist_id = default_artist.get("id")

        existing_downloads = set()
        track_ids = [track.get("id") for track in tracks if track.get("id")]
        if track_ids:
            existing_downloads = await asyncio.to_thread(_fetch_existing_download_ids, track_ids)

        for index, track in enumerate(tracks):
            artist_info = (track.get("artists") or [{}])[0]
            artist_name = artist_info.get("name") or default_artist_name
            artist_id = artist_info.get("id") or default_artist_id
            spotify_track_id = track.get("id")

            if not spotify_track_id or not artist_name:
                continue

            if spotify_track_id in existing_downloads:
                continue

            try:
                videos = await youtube_client.search_music_videos(
                    artist=artist_name,
                    track=track.get("name"),
                    album=album_name,
                    max_results=1
                )
                if videos:
                    best = videos[0]
                    await asyncio.to_thread(save_youtube_download, {
                        "spotify_track_id": spotify_track_id,
                        "spotify_artist_id": artist_id,
                        "youtube_video_id": best["video_id"],
                        "download_path": "",
                        "download_status": "link_found",
                        "error_message": None
                    })
                else:
                    await asyncio.to_thread(save_youtube_download, {
                        "spotify_track_id": spotify_track_id,
                        "spotify_artist_id": artist_id,
                        "youtube_video_id": "",
                        "download_path": "",
                        "download_status": "video_not_found",
                        "error_message": "Video not found"
                    })
            except HTTPException as exc:
                await asyncio.to_thread(save_youtube_download, {
                    "spotify_track_id": spotify_track_id,
                    "spotify_artist_id": artist_id,
                    "youtube_video_id": "",
                    "download_path": "",
                    "download_status": "error",
                    "error_message": exc.detail
                })
                if exc.status_code in (403, 429):
                    logger.warning("Stopping YouTube prefetch for %s due to API error %s", spotify_album_id, exc.status_code)
                    break
            except Exception as err:
                logger.warning("Failed to cache YouTube link for %s: %s", spotify_track_id, err)
                await asyncio.to_thread(save_youtube_download, {
                    "spotify_track_id": spotify_track_id,
                    "spotify_artist_id": artist_id,
                    "youtube_video_id": "",
                    "download_path": "",
                    "download_status": "error",
                    "error_message": str(err)
                })

            await asyncio.sleep(youtube_client.min_interval_seconds)
    finally:
        prefetch_tasks.pop(spotify_album_id, None)


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
    except HTTPException:
        raise
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching music videos: {str(e)}")


@router.post("/album/{spotify_id}/prefetch")
async def prefetch_album_youtube_links(
    spotify_id: str,
    session: AsyncSession = Depends(SessionDep),
):
    """
    Schedule a background job to fetch YouTube links for every track in an album.
    """
    album = (await session.exec(
        select(Album).where(Album.spotify_id == spotify_id)
    )).first()
    if album:
        existing = (await session.exec(
            select(YouTubeDownload.spotify_track_id)
            .join(Track, Track.spotify_id == YouTubeDownload.spotify_track_id)
            .where(Track.album_id == album.id)
            .limit(1)
        )).first()
        if existing:
            return {"status": "cached", "message": "Links already cached for this album"}

    if spotify_id in prefetch_tasks and not prefetch_tasks[spotify_id].done():
        return {"status": "running", "message": "Prefetch already in progress"}

    task = asyncio.create_task(_prefetch_album_links(spotify_id))
    prefetch_tasks[spotify_id] = task
    return {"status": "scheduled"}


@router.get("/track/{spotify_track_id}/link")
def get_track_youtube_link(spotify_track_id: str):
    """
    Retrieve cached YouTube link info for a Spotify track.
    """
    with get_session() as session:
        record = session.exec(
            select(YouTubeDownload).where(YouTubeDownload.spotify_track_id == spotify_track_id)
        ).first()

        if not record:
            raise HTTPException(status_code=404, detail="Link not ready")

        if record.download_status in ("error", "video_not_found") and not record.youtube_video_id:
            record.download_status = "missing"
            session.add(record)
            session.commit()

        status = record.download_status
        if record.youtube_video_id and status in ("missing", "error", "video_not_found"):
            status = "link_found"

        return {
            "spotify_track_id": record.spotify_track_id,
            "status": status,
            "youtube_video_id": record.youtube_video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={record.youtube_video_id}" if record.youtube_video_id else None,
            "error_message": record.error_message,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        }


@router.post("/links")
def get_track_youtube_links(payload: YoutubeLinkBatchRequest):
    track_ids = [track_id for track_id in payload.spotify_track_ids if track_id]
    if not track_ids:
        return {"items": []}

    with get_session() as session:
        records = session.exec(
            select(YouTubeDownload).where(YouTubeDownload.spotify_track_id.in_(track_ids))
        ).all()
        to_update = []
        for record in records:
            if record.download_status in ("error", "video_not_found") and not record.youtube_video_id:
                record.download_status = "missing"
                to_update.append(record)
        if to_update:
            session.add_all(to_update)
            session.commit()

    records_by_id = {record.spotify_track_id: record for record in records}
    items = []
    for track_id in track_ids:
        record = records_by_id.get(track_id)
        if not record:
            items.append({
                "spotify_track_id": track_id,
                "status": "missing",
                "youtube_video_id": None,
                "youtube_url": None,
                "error_message": None,
                "updated_at": None
            })
            continue

        status = record.download_status
        if record.youtube_video_id and status in ("missing", "error", "video_not_found"):
            status = "link_found"

        items.append({
            "spotify_track_id": record.spotify_track_id,
            "status": status,
            "youtube_video_id": record.youtube_video_id,
            "youtube_url": f"https://www.youtube.com/watch?v={record.youtube_video_id}" if record.youtube_video_id else None,
            "error_message": record.error_message,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        })

    return {"items": items}


@router.post("/track/{spotify_track_id}/refresh")
async def refresh_track_youtube_link(
    spotify_track_id: str,
    payload: YoutubeTrackRefreshRequest,
    session: AsyncSession = Depends(SessionDep),
):
    """
    Search YouTube for a track and persist the link. Intended for user-triggered play.
    """
    artist_name = payload.artist
    track_name = payload.track
    album_name = payload.album
    spotify_artist_id = None

    row = (await session.exec(
        select(Track, Artist, Album)
        .join(Artist, Artist.id == Track.artist_id)
        .outerjoin(Album, Album.id == Track.album_id)
        .where(Track.spotify_id == spotify_track_id)
    )).first()

    if row:
        track, artist, album = row
        artist_name = artist.name or artist_name
        track_name = track.name or track_name
        album_name = album.name if album else album_name
        spotify_artist_id = artist.spotify_id

    if not artist_name or not track_name:
        raise HTTPException(status_code=400, detail="Artist and track are required to search YouTube")

    try:
        videos = await youtube_client.search_music_videos(
            artist=artist_name,
            track=track_name,
            album=album_name,
            max_results=1
        )
        if videos:
            best = videos[0]
            await asyncio.to_thread(save_youtube_download, {
                "spotify_track_id": spotify_track_id,
                "spotify_artist_id": spotify_artist_id,
                "youtube_video_id": best["video_id"],
                "download_path": "",
                "download_status": "link_found",
                "error_message": None
            })
            return {
                "spotify_track_id": spotify_track_id,
                "status": "link_found",
                "youtube_video_id": best["video_id"],
                "youtube_url": best["url"],
                "error_message": None
            }
        await asyncio.to_thread(save_youtube_download, {
            "spotify_track_id": spotify_track_id,
            "spotify_artist_id": spotify_artist_id,
            "youtube_video_id": "",
            "download_path": "",
            "download_status": "missing",
            "error_message": "Video not found"
        })
        return {
            "spotify_track_id": spotify_track_id,
            "status": "missing",
            "youtube_video_id": None,
            "youtube_url": None,
            "error_message": "Video not found"
        }
    except HTTPException as exc:
        await asyncio.to_thread(save_youtube_download, {
            "spotify_track_id": spotify_track_id,
            "spotify_artist_id": spotify_artist_id,
            "youtube_video_id": "",
            "download_path": "",
            "download_status": "missing",
            "error_message": str(exc.detail) if hasattr(exc, "detail") else str(exc)
        })
        raise


@router.get("/usage")
async def youtube_usage():
    """
    Return in-memory count of YouTube API requests since server start.
    """
    return youtube_client.get_usage()


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
        await youtube_client.search_videos("test", max_results=1)
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
    to_device: bool = Query(False, description="Stream directly to device instead of storing"),
    session: AsyncSession = Depends(SessionDep),
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
            download, track, album, artist = await _resolve_track_metadata(video_id, session)
            if track and artist and album:
                result = await youtube_client.download_audio_for_album_track(
                    video_id=video_id,
                    artist_name=artist.name,
                    album_name=album.name,
                    track_name=track.name,
                    output_format=format,
                    format_quality=quality
                )
            elif track and artist:
                result = await youtube_client.download_audio_for_organized_track(
                    video_id=video_id,
                    artist_name=artist.name,
                    track_name=track.name,
                    output_format=format,
                    format_quality=quality
                )
            else:
                result = await youtube_client.download_audio(
                    video_id=video_id,
                    output_format=format,
                    format_quality=quality
                )

            if download and result.get("file_path"):
                status = result.get("status") or "completed"
                await asyncio.to_thread(save_youtube_download, {
                    "spotify_track_id": download.spotify_track_id,
                    "spotify_artist_id": download.spotify_artist_id,
                    "youtube_video_id": video_id,
                    "download_path": result.get("file_path"),
                    "file_size": result.get("file_size"),
                    "download_status": "completed" if status in ("completed", "already_exists") else status
                })
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/download/{video_id}/status")
async def check_download_status(
    video_id: str,
    format: str = Query("mp3", description="Audio format"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Check if an audio file exists for a video.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        download, _, _, _ = await _resolve_track_metadata(video_id, session)
        if download and download.download_path:
            path = Path(download.download_path)
            if path.exists():
                return {
                    "exists": True,
                    "video_id": video_id,
                    "file_path": str(path),
                    "file_size": path.stat().st_size,
                    "format": path.suffix[1:]
                }
        status = await youtube_client.get_download_status(video_id, format)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking status: {str(e)}")


@router.get("/download/{video_id}/file")
async def get_downloaded_file(
    video_id: str,
    format: str = Query("mp3", description="Audio format"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Serve a downloaded audio file.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        download, track, _, _ = await _resolve_track_metadata(video_id, session)
        if download and download.download_path:
            path = Path(download.download_path)
            if path.exists():
                ext = path.suffix[1:]
                filename = path.name
                if track:
                    filename = f"{track.name}.{ext}"
                media_type = "audio/mp4" if ext in ("m4a", "mp4") else "audio/mpeg"
                return FileResponse(
                    path=path,
                    media_type=media_type,
                    filename=filename,
                    content_disposition_type="inline"
                )

        status = await youtube_client.get_download_status(video_id, format)
        if not status['exists']:
            raise HTTPException(status_code=404, detail="Audio file not found for this video")

        file_path = status['file_path']
        try:
            video_details = await youtube_client.get_video_details(video_id)
            filename = f"{video_details['title']}.{format}"
        except Exception:
            filename = f"{video_id}.{format}"

        media_type = "audio/mp4" if format in ("m4a", "mp4") else "audio/mpeg"
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="inline"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")


@router.get("/stream/{video_id}")
async def stream_audio(
    video_id: str,
    format: str = Query("m4a", description="Stream format (m4a, webm)"),
    cache: bool = Query(True, description="Cache streamed audio in downloads"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Stream audio directly while downloading it from YouTube.

    - **video_id**: YouTube video ID
    - **format**: Stream format (m4a, webm)
    - **cache**: Cache the stream to disk for later playback
    """
    try:
        output_path = None
        download, track, album, artist = await _resolve_track_metadata(video_id, session)
        if track and artist and album:
            output_path = youtube_client.get_album_download_path(
                artist.name,
                album.name,
                track.name,
                format
            )
        elif track and artist:
            output_path = youtube_client.get_artist_download_path(
                artist.name,
                track.name,
                format
            )

        result = await youtube_client.stream_audio_to_device(
            video_id=video_id,
            output_format=format,
            cache=cache,
            output_path=output_path
        )
        if cache and download and output_path:
            ext = result.get("ext") or format
            await asyncio.to_thread(save_youtube_download, {
                "spotify_track_id": download.spotify_track_id,
                "spotify_artist_id": download.spotify_artist_id,
                "youtube_video_id": video_id,
                "download_path": str(output_path.with_suffix(f".{ext}")),
                "download_status": download.download_status or "completed"
            })
        ext = result.get("ext") or format
        if result.get("type") == "file":
            return FileResponse(
                path=result["file_path"],
                media_type=result["media_type"],
                filename=f"{result.get('title', video_id)}.{ext}",
                content_disposition_type="inline"
            )

        return StreamingResponse(
            result["stream"],
            media_type=result["media_type"],
            headers={"Content-Disposition": f"inline; filename=\"{result.get('title', video_id)}.{ext}\""}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")


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
    format: str = Query("mp3", description="Audio format"),
    session: AsyncSession = Depends(SessionDep),
):
    """
    Delete a downloaded audio file.

    - **video_id**: YouTube video ID
    - **format**: Audio format
    """
    try:
        download, _, _, _ = await _resolve_track_metadata(video_id, session)
        if download and download.download_path:
            path = Path(download.download_path)
            if path.exists():
                path.unlink()
                return {
                    "message": f"Successfully deleted audio file for video {video_id}",
                    "video_id": video_id,
                    "format": path.suffix[1:]
                }

        deleted = await youtube_client.delete_download(video_id, format)
        if deleted:
            return {
                "message": f"Successfully deleted audio file for video {video_id}",
                "video_id": video_id,
                "format": format
            }
        raise HTTPException(status_code=404, detail="Audio file not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
