#!/usr/bin/env python3
"""Convert m4a streaming cache to MP3 organized structure."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select
from app.core.db import get_session
from app.models.base import YouTubeDownload, Track, Artist, Album
from app.core.youtube import youtube_client
import asyncio


async def convert_track(yt, track, artist, album):
    """Re-download track as MP3."""
    video_id = yt.youtube_video_id
    artist_name = artist.name if artist else 'Unknown'
    track_name = track.name
    album_name = album.name if album else track_name

    print(f"⬇️  {artist_name} - {track_name}")
    print(f"   Album: {album_name}")

    try:
        result = await youtube_client.download_audio_for_track(
            video_id=video_id,
            artist_name=artist_name,
            track_name=track_name,
            album_name=album_name,
            output_format='mp3'
        )

        if result.get('status') in ('completed', 'already_exists'):
            new_path = result.get('file_path', '')
            new_path_relative = new_path.replace('/home/micasa/audio2/downloads/', '')

            # Update database
            yt.download_path = new_path_relative
            yt.download_status = 'completed'
            yt.format_type = 'mp3'
            yt.file_size = Path(new_path).stat().st_size if Path(new_path).exists() else None

            # Delete old m4a file
            old_path = Path('/home/micasa/audio2/downloads') / yt.download_path.replace('downloads/', '', 1) if yt.download_path.startswith('downloads/') else Path(yt.download_path)
            if old_path.exists() and old_path.suffix == '.m4a':
                old_path.unlink()
                print(f"   🗑️  Borrado: {old_path.name}")

            print(f"   ✅ {Path(new_path).name}")
            return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def main():
    session = get_session()

    # Get all m4a completed downloads
    m4a_downloads = session.exec(
        select(YouTubeDownload).where(
            YouTubeDownload.format_type == 'm4a',
            YouTubeDownload.download_status == 'completed'
        )
    ).all()

    print("=== Convirtiendo .m4a a .mp3 ===\n")

    success = 0
    for yt in m4a_downloads:
        # Get track info
        if not yt.spotify_track_id:
            continue

        track = session.exec(
            select(Track).where(Track.spotify_id == yt.spotify_track_id)
        ).first()

        if not track:
            continue

        artist = None
        album = None

        if track.artist_id:
            artist = session.exec(
                select(Artist).where(Artist.id == track.artist_id)
            ).first()

        if track.album_id:
            album = session.exec(
                select(Album).where(Album.id == track.album_id)
            ).first()

        if await convert_track(yt, track, artist, album):
            success += 1
            session.add(yt)

    session.commit()
    session.close()

    print("\n=== Resumen ===")
    print(f"Convertidos: {success}/{len(m4a_downloads)}")


if __name__ == '__main__':
    asyncio.run(main())
