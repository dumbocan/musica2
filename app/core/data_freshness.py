"""
Data Freshness Manager - Ensures music metadata stays fresh and up-to-date.

Key Features:
- Checks database before downloading to avoid duplicates
- Automatically refreshes metadata at configurable intervals
- Detects new songs/albums for existing artists
- Maintains data currency for optimal user experience
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlmodel import select

from .spotify import spotify_client
from .lastfm import lastfm_client
from .db import get_session
from ..models.base import Artist, Album, Track, YouTubeDownload
from ..crud import save_artist, save_album, save_track

logger = logging.getLogger(__name__)


class DataFreshnessManager:
    """Manager for keeping music data fresh and current."""

    def __init__(self):
        # Update intervals (in hours)
        self.artist_update_interval_hours = 24  # Update artist metadata every 24 hours
        self.track_update_interval_hours = 7 * 24  # Update track data every week
        self.album_update_interval_hours = 7 * 24  # Update album data every week

        # Max age for data freshness (soft limits)
        self.max_artist_age_days = 7
        self.max_track_age_days = 30
        self.max_album_age_days = 30

        logger.info("DataFreshnessManager initialized with update intervals")

    async def should_refresh_artist(self, artist: Artist) -> bool:
        """
        Check if artist data needs refreshing.

        Returns True if:
        - No updated_at timestamp (legacy data)
        - Updated more than max_artist_age_days ago
        """
        if not artist.updated_at:
            return True  # Legacy data needs update

        age_hours = (datetime.utcnow() - artist.updated_at).total_seconds() / 3600
        return age_hours > (self.artist_update_interval_hours)

    async def should_refresh_track(self, track: Track) -> bool:
        """
        Check if track data needs refreshing.
        """
        if not track.updated_at:
            return True  # Legacy data needs update

        age_hours = (datetime.utcnow() - track.updated_at).total_seconds() / 3600
        return age_hours > (self.track_update_interval_hours)

    async def should_refresh_album(self, album: Album) -> bool:
        """
        Check if album data needs refreshing.
        """
        if not album.updated_at:
            return True  # Legacy data needs update

        age_hours = (datetime.utcnow() - album.updated_at).total_seconds() / 3600
        return age_hours > (self.album_update_interval_hours)

    async def refresh_artist_data(self, spotify_id: str) -> bool:
        """
        Refresh complete artist data from Spotify and Last.fm.

        Returns True if data was updated.
        """
        try:
            logger.info(f"🔄 Refreshing data for artist {spotify_id}")

            # Get fresh data from Spotify
            artist_data = await spotify_client.get_artist(spotify_id)
            if not artist_data:
                logger.warning(f"Could not fetch artist data for {spotify_id}")
                return False

            # Save/update artist data
            artist = save_artist(artist_data)
            logger.info(f"✅ Artist {artist.name} data updated")

            # Update bio from Last.fm
            try:
                bio_data = await lastfm_client.get_artist_info(artist.name)
                if bio_data:
                    from ..crud import update_artist_bio
                    update_artist_bio(artist.id, bio_data['summary'], bio_data['content'])
                    logger.info(f"✅ Bio updated for {artist.name}")
            except Exception as bio_error:
                logger.warning(f"Could not update bio for {artist.name}: {str(bio_error)}")

            return True

        except Exception as e:
            logger.error(f"Error refreshing artist {spotify_id}: {str(e)}")
            return False

    async def check_for_new_artist_content(self, spotify_id: str) -> Dict[str, int]:
        """
        Check if artist has new albums/tracks not in our database.

        Returns dict with new album and track counts.
        """
        logger.info(f"🔍 Checking for new content from artist {spotify_id}")

        new_albums = 0
        new_tracks = 0

        try:
            # Get all artist albums from Spotify
            spotify_albums = await spotify_client.get_artist_albums(spotify_id)
            logger.info(f"Found {len(spotify_albums)} albums on Spotify")

            # Check each album
            for album_data in spotify_albums:
                album_id = album_data['id']

                # Check if we have this album
                with get_session() as session:
                    existing_album = session.exec(
                        select(Album).where(Album.spotify_id == album_id)
                    ).first()

                if not existing_album:
                    new_albums += 1

                    # Save the new album
                    album = save_album(album_data)
                    logger.info(f"✅ New album saved: {album.name}")

                    # Get tracks for this album and check/save them
                    try:
                        tracks_data = await spotify_client.get_album_tracks(album_id)
                        for track_data in tracks_data:
                            # Check if track exists
                            with get_session() as session:
                                existing_track = session.exec(
                                    select(Track).where(Track.spotify_id == track_data['id'])
                                ).first()

                            if not existing_track:
                                save_track(track_data, album.id, album.artist_id)
                                new_tracks += 1

                    except Exception as track_error:
                        logger.warning(f"Error fetching tracks for album {album_id}: {str(track_error)}")
                        continue

        except Exception as e:
            logger.error(f"Error checking new content for artist {spotify_id}: {str(e)}")

        result = {"new_albums": new_albums, "new_tracks": new_tracks}
        logger.info(f"📊 Artist content check result: {result}")
        return result

    async def is_track_downloaded(self, spotify_track_id: str) -> bool:
        """
        Check if track is already downloaded.

        ALWAYS call this before attempting any download.
        """
        session = get_session()
        try:
            download = session.query(YouTubeDownload).filter(
                YouTubeDownload.spotify_track_id == spotify_track_id,
                YouTubeDownload.download_status == "completed"
            ).first()
            return download is not None
        finally:
            session.close()

    async def get_fresh_artist_tracks(self, spotify_id: str, limit: int = 10) -> List[Track]:
        """
        Get the freshest tracks for an artist, checking for updates first.
        """
        logger.info(f"🎵 Getting fresh tracks for artist {spotify_id}")

        # First refresh artist data if needed
        await self.ensure_artist_data_fresh(spotify_id)

        # Get artist first to get local ID
        session = get_session()
        try:
            artist = session.exec(
                select(Artist).where(Artist.spotify_id == spotify_id)
            ).first()

            if not artist:
                logger.warning(f"Artist {spotify_id} not found in DB")
                return []

            # Get tracks for this artist
            tracks = session.exec(
                select(Track)
                .where(Track.artist_id == artist.id)
                .order_by(Track.popularity.desc(), Track.created_at.desc())
                .limit(limit)
            ).all()

            logger.info(f"📀 Found {len(tracks)} stored tracks for artist")
            return [track for track in tracks]

        finally:
            session.close()

    async def ensure_artist_data_fresh(self, spotify_id: str) -> bool:
        """
        Ensure artist data is fresh, updating if necessary.

        Returns True if data was refreshed.
        """
        session = get_session()
        try:
            artist = session.exec(
                select(Artist).where(Artist.spotify_id == spotify_id)
            ).first()

            if not artist:
                logger.warning(f"Artist {spotify_id} not found locally")
                return False

            if await self.should_refresh_artist(artist):
                logger.info(f"Artist {artist.name} needs refresh, updating...")
                success = await self.refresh_artist_data(spotify_id)
                if success:
                    # Also check for new content
                    new_content = await self.check_for_new_artist_content(spotify_id)
                    if new_content['new_albums'] > 0 or new_content['new_tracks'] > 0:
                        logger.info(f"🎉 Found new content: {new_content}")

                return success
            else:
                logger.info(f"Artist {artist.name} data is still fresh")
                return False

        finally:
            session.close()

    async def bulk_refresh_stale_artists(self, max_artists: int = 10) -> Dict[str, int]:
        """
        Refresh data for artists that haven't been updated recently.

        Useful for background maintenance.
        """
        logger.info(f"🔄 Starting bulk refresh of up to {max_artists} stale artists")

        session = get_session()
        try:
            # Get artists needing refresh
            cutoff_time = datetime.utcnow() - timedelta(days=self.max_artist_age_days)

            stale_artists = session.exec(
                select(Artist).where(
                    (Artist.updated_at.is_(None)) |
                    (Artist.updated_at < cutoff_time)
                ).limit(max_artists)
            ).all()

            logger.info(f"Found {len(stale_artists)} artists needing refresh")

            refreshed = 0
            new_albums = 0
            new_tracks = 0

            for artist in stale_artists:
                if not artist.spotify_id:
                    continue  # Skip artists without Spotify ID

                logger.info(f"Refreshing {artist.name}...")
                success = await self.refresh_artist_data(artist.spotify_id)
                if success:
                    content = await self.check_for_new_artist_content(artist.spotify_id)
                    new_albums += content['new_albums']
                    new_tracks += content['new_tracks']
                    refreshed += 1

                # Small delay to be respectful to APIs
                await asyncio.sleep(0.5)

            result = {
                "artists_refreshed": refreshed,
                "new_albums_discovered": new_albums,
                "new_tracks_discovered": new_tracks
            }

            logger.info(f"✅ Bulk refresh complete: {result}")
            return result

        finally:
            session.close()

    async def expand_user_library_from_artist(
        self,
        main_artist_name: str,
        main_artist_spotify_id: str,
        similar_count: int = 10,
        tracks_per_artist: int = 5
    ) -> Dict[str, any]:
        """
        Automatically expand user library when searching for an artist.

        Adds 10 similar artists + 5 tracks each to create instant music collection.

        Returns complete expansion results.
        """
        logger.info(f"🚀 Starting library expansion for {main_artist_name}")

        # 1. Main artist already processed, ensure fresh
        await self.ensure_artist_data_fresh(main_artist_spotify_id)

        # 2. Get similar artists from Last.fm
        try:
            similar_artists = await lastfm_client.get_similar_artists(main_artist_name, limit=similar_count)
            logger.info(f"Found {len(similar_artists)} similar artists from Last.fm (limit: {similar_count})")
        except Exception as e:
            logger.warning(f"Could not get similar artists from Last.fm: {e}")
            similar_artists = []

        # 3. Process each similar artist and add to library
        expansion_results = []
        total_tracks_added = 0

        for similar_artist in similar_artists[:similar_count]:
            artist_name = similar_artist['name']
            match_score = similar_artist.get('match', 0.0)

            logger.info(f"🔍 Processing similar artist: {artist_name} (match: {match_score:.2f})")

            try:
                # Search artist on Spotify
                spotify_results = await spotify_client.search_artists(artist_name, limit=1)
                if not spotify_results:
                    logger.warning(f"Could not find {artist_name} on Spotify")
                    continue

                artist_data = spotify_results[0]
                artist_spotify_id = artist_data['id']

                # Check if we already have this artist
                session = get_session()
                try:
                    existing_artist = session.exec(
                        select(Artist).where(Artist.spotify_id == artist_spotify_id)
                    ).first()
                finally:
                    session.close()

                if existing_artist:
                    logger.info(f"Artist {artist_name} already exists, ensuring fresh data")
                    await self.ensure_artist_data_fresh(artist_spotify_id)
                else:
                    # Save new artist
                    artist = save_artist(artist_data)
                    logger.info(f"✅ Saved new artist: {artist_name}")

                    # Enrich with Last.fm bio
                    try:
                        bio_data = await lastfm_client.get_artist_info(artist_name)
                        if bio_data:
                            from ..crud import update_artist_bio
                            update_artist_bio(artist.id, bio_data['summary'], bio_data['content'])
                    except Exception:
                        pass

                # Get top tracks for this artist
                try:
                    top_tracks = await spotify_client.get_artist_top_tracks(artist_name, limit=tracks_per_artist)

                    tracks_added = 0
                    for track_data in top_tracks[:tracks_per_artist]:
                        # Check if track exists
                        session = get_session()
                        try:
                            existing_track = session.exec(
                                select(Track).where(Track.spotify_id == track_data['id'])
                            ).first()

                            if not existing_track:
                                # Save new album (mock) and track
                                mock_album_data = {
                                    'id': f"expansion_album_{artist_name.replace(' ', '_')}_{tracks_added}",
                                    'name': f"{artist_name} Top Hits",
                                    'release_date': '2020-01-01',
                                    'total_tracks': tracks_per_artist,
                                    'images': [{"url": ""}],
                                    'artists': [{"id": artist_spotify_id, "name": artist_name}]
                                }

                                # Get or create artist in session
                                session = get_session()
                                try:
                                    album_artist = session.exec(
                                        select(Artist).where(Artist.spotify_id == artist_spotify_id)
                                    ).first()
                                    if album_artist:
                                        album = save_album(mock_album_data)
                                        save_track(track_data, album.id, album_artist.id)
                                        tracks_added += 1
                                finally:
                                    session.close()

                        finally:
                            session.close()

                    total_tracks_added += tracks_added

                    expansion_results.append({
                        "artist_name": artist_name,
                        "spotify_id": artist_spotify_id,
                        "match_score": match_score,
                        "tracks_added": tracks_added,
                        "followers": artist_data.get('followers', {}).get('total', 0)
                    })

                    logger.info(f"✅ Added {tracks_added} tracks for {artist_name}")

                except Exception as track_error:
                    logger.error(f"Error adding tracks for {artist_name}: {track_error}")

            except Exception as artist_error:
                logger.error(f"Error processing similar artist {artist_name}: {artist_error}")
                continue

        # Return complete expansion results
        result = {
            "main_artist": main_artist_name,
            "similar_artists_found": len(expansion_results),
            "total_tracks_added": total_tracks_added,
            "expansion_details": expansion_results,
            "total_library_growth": f"1 + {len(expansion_results)} artists + {total_tracks_added} tracks",
            "expansion_completed": True
        }

        logger.info(f"🎉 Library expansion completed: {result['total_library_growth']}")
        return result

    async def get_data_freshness_report(self) -> Dict[str, any]:
        """
        Generate a report on data freshness across the database.
        """
        session = get_session()
        try:
            now = datetime.utcnow()

            # Artist freshness
            artist_stats = session.exec(
                select(Artist)
            ).all()

            fresh_artists = sum(1 for a in artist_stats if a.updated_at and
                                (now - a.updated_at).days <= self.max_artist_age_days)
            total_artists = len(artist_stats)

            # Download stats
            downloads = session.exec(select(YouTubeDownload)).all()
            completed_downloads = sum(1 for d in downloads if d.is_completed)
            total_downloads = len(downloads)

            return {
                "artists": {
                    "total": total_artists,
                    "fresh": fresh_artists,
                    "stale": total_artists - fresh_artists,
                    "freshness_percentage": (fresh_artists / total_artists * 100) if total_artists > 0 else 0
                },
                "downloads": {
                    "total_attempts": total_downloads,
                    "completed": completed_downloads,
                    "completion_rate": (completed_downloads / total_downloads * 100) if total_downloads > 0 else 0
                },
                "last_updated": now.isoformat()
            }

        finally:
            session.close()


# Global instance
data_freshness_manager = DataFreshnessManager()
