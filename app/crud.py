"""
CRUD operations using SQLModel.
"""

import unicodedata
import json

from typing import Optional, List
from sqlmodel import select
from sqlalchemy.exc import IntegrityError

from .models.base import (
    Artist, Album, Track, User, Playlist, PlaylistTrack, Tag, TrackTag,
    PlayHistory, AlgorithmLearning, UserFavorite, FavoriteTargetType,
    SearchEntityType
)
from .core.db import get_session
from .core.image_proxy import proxy_image_list
from .core.image_cache import schedule_warm_cache_images
from .core.search_index import ensure_entity_aliases
from .core.time_utils import utc_now


def normalize_name(name: str) -> str:
    """Normalize artist/album name: lowercase, remove accents, strip."""
    name = name.lower().strip()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')  # Remove accents
    return name


# Artists
def get_artist_by_spotify_id(spotify_id: str) -> Optional[Artist]:
    session = get_session()
    try:
        statement = select(Artist).where(Artist.spotify_id == spotify_id)
        artist = session.exec(statement).first()
        return artist
    finally:
        session.close()

def save_artist(artist_data: dict) -> Artist:
    spotify_id = artist_data['id']
    session = get_session()
    try:
        now = utc_now()
        images_data = artist_data.get('images', []) or []
        proxied_images = proxy_image_list(images_data, size=384)
        serialized_images = json.dumps(proxied_images)
        needs_warm_cache = False

        normalized = normalize_name(artist_data['name'])
        artist = session.exec(
            select(Artist).where(Artist.spotify_id == spotify_id)
        ).first()
        if not artist and normalized:
            artist = session.exec(
                select(Artist).where(Artist.normalized_name == normalized)
            ).first()

        def _apply_updates(target: Artist) -> None:
            target.spotify_id = target.spotify_id or spotify_id
            target.name = artist_data['name']
            target.normalized_name = normalized
            target.genres = str(artist_data.get('genres', []))
            target.popularity = artist_data.get('popularity', 0)
            target.followers = artist_data.get('followers', {}).get('total', 0)
            target.updated_at = now
            target.last_refreshed_at = now
            nonlocal needs_warm_cache
            if target.images != serialized_images:
                needs_warm_cache = True
            target.images = serialized_images
            session.add(target)

        if artist:
            _apply_updates(artist)
        else:
            needs_warm_cache = True
            artist = Artist(
                spotify_id=spotify_id,
                name=artist_data['name'],
                normalized_name=normalized,
                genres=str(artist_data.get('genres', [])),
                images=serialized_images,
                popularity=artist_data.get('popularity', 0),
                followers=artist_data.get('followers', {}).get('total', 0),
                last_refreshed_at=now
            )
            session.add(artist)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            artist = session.exec(
                select(Artist).where(Artist.spotify_id == spotify_id)
            ).first()
            if not artist and normalized:
                artist = session.exec(
                    select(Artist).where(Artist.normalized_name == normalized)
                ).first()
            if not artist:
                raise
            _apply_updates(artist)
            session.flush()
        ensure_entity_aliases(session, SearchEntityType.ARTIST, artist.id, artist.name)
        session.commit()
        session.refresh(artist)
        if needs_warm_cache and images_data:
            schedule_warm_cache_images(images_data, size=384)
        return artist
    finally:
        session.close()


# Albums (similar)
def get_album_by_spotify_id(spotify_id: str) -> Optional[Album]:
    session = get_session()
    try:
        statement = select(Album).where(Album.spotify_id == spotify_id)
        album = session.exec(statement).first()
        return album
    finally:
        session.close()

def save_album(album_data: dict) -> Album:
    spotify_id = album_data['id']
    album = get_album_by_spotify_id(spotify_id)
    session = get_session()
    try:
        now = utc_now()
        images_data = album_data.get('images', []) or []
        proxied_images = proxy_image_list(images_data, size=384)
        serialized_images = json.dumps(proxied_images)
        needs_warm_cache = False
        if not album:
            album = session.exec(
                select(Album).where(Album.spotify_id == spotify_id)
            ).first()
        if album:
            album.name = album_data['name']
            album.release_date = album_data['release_date']
            album.total_tracks = album_data['total_tracks']
            if album.images != serialized_images:
                needs_warm_cache = True
            album.images = serialized_images
            album.label = album_data.get('label')
            album.updated_at = now
            album.last_refreshed_at = now
            session.add(album)
        else:
            # Save artist if not exists
            artist_spotify_id = album_data['artists'][0]['id'] if album_data['artists'] else None
            artist_data = {"id": artist_spotify_id, "name": album_data['artists'][0]['name'], "genres": [], "images": [], "popularity": 0, "followers": {"total": 0}} if artist_spotify_id else None
            artist = get_artist_by_spotify_id(artist_spotify_id) if artist_spotify_id else None
            if not artist and artist_data:
                artist = save_artist(artist_data)  # This opens/closes its own session
            artist_id = artist.id if artist else None
            needs_warm_cache = True
            album = Album(
                spotify_id=spotify_id,
                name=album_data['name'],
                artist_id=artist_id,
                release_date=album_data['release_date'],
                total_tracks=album_data['total_tracks'],
                images=serialized_images,
                label=album_data.get('label'),
                last_refreshed_at=now
            )
            session.add(album)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            album = session.exec(
                select(Album).where(Album.spotify_id == spotify_id)
            ).first()
            if not album:
                raise
            album.name = album_data['name']
            album.release_date = album_data['release_date']
            album.total_tracks = album_data['total_tracks']
            if album.images != serialized_images:
                needs_warm_cache = True
            album.images = serialized_images
            album.label = album_data.get('label')
            album.updated_at = now
            album.last_refreshed_at = now
            session.add(album)
        ensure_entity_aliases(session, SearchEntityType.ALBUM, album.id, album.name)
        session.commit()
        session.refresh(album)
        if needs_warm_cache and images_data:
            schedule_warm_cache_images(images_data, size=384)
        return album
    finally:
        session.close()


# Tracks
def get_track_by_spotify_id(spotify_id: str) -> Optional[Track]:
    session = get_session()
    try:
        statement = select(Track).where(Track.spotify_id == spotify_id)
        track = session.exec(statement).first()
        return track
    finally:
        session.close()

def save_track(track_data: dict, album_id: Optional[int] = None, artist_id: Optional[int] = None) -> Track:
    spotify_id = track_data['id']
    track = get_track_by_spotify_id(spotify_id)
    session = get_session()
    try:
        now = utc_now()
        if track:
            track.name = track_data['name']
            track.duration_ms = track_data['duration_ms']
            track.popularity = track_data.get('popularity', 0)
            track.preview_url = track_data.get('preview_url')
            track.external_url = track_data['external_urls']['spotify']
            track.album_id = album_id
            track.updated_at = now
            track.last_refreshed_at = now
            session.add(track)
        else:
            track = Track(
                spotify_id=spotify_id,
                name=track_data['name'],
                artist_id=artist_id,
                album_id=album_id,
                duration_ms=track_data['duration_ms'],
                popularity=track_data.get('popularity', 0),
                preview_url=track_data.get('preview_url'),
                external_url=track_data['external_urls']['spotify'],
                last_refreshed_at=now
            )
            session.add(track)
        session.flush()
        ensure_entity_aliases(session, SearchEntityType.TRACK, track.id, track.name)
        session.commit()
        session.refresh(track)
        return track
    finally:
        session.close()


def update_track_lastfm(track_id: int, listeners: int, playcount: int):
    """Update track with Last.fm data."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            track.lastfm_listeners = listeners
            track.lastfm_playcount = playcount
            now = utc_now()
            track.updated_at = now  # Update timestamp
            track.last_refreshed_at = now
            session.commit()
        return track
    finally:
        session.close()

def update_track_spotify_data(track_id: int, spotify_data: dict):
    """Update track with fresh Spotify data."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            # Update with fresh Spotify data
            track.name = spotify_data.get('name', track.name)
            track.duration_ms = spotify_data.get('duration_ms', track.duration_ms)
            track.popularity = spotify_data.get('popularity', track.popularity)
            track.preview_url = spotify_data.get('preview_url', track.preview_url)
            track.external_url = spotify_data.get('external_urls', {}).get('spotify', track.external_url)
            now = utc_now()
            track.updated_at = now  # Update timestamp
            track.last_refreshed_at = now
            session.commit()
        return track
    finally:
        session.close()


# Favorites
def add_favorite(user_id: int, target_type: FavoriteTargetType, target_id: int) -> UserFavorite:
    session = get_session()
    try:
        fav = None
        if target_type == FavoriteTargetType.ARTIST:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.artist_id == target_id
                )
            ).first()
            if not fav:
                fav = UserFavorite(user_id=user_id, target_type=target_type, artist_id=target_id)
        elif target_type == FavoriteTargetType.ALBUM:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.album_id == target_id
                )
            ).first()
            if not fav:
                fav = UserFavorite(user_id=user_id, target_type=target_type, album_id=target_id)
        elif target_type == FavoriteTargetType.TRACK:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.track_id == target_id
                )
            ).first()
            if not fav:
                fav = UserFavorite(user_id=user_id, target_type=target_type, track_id=target_id)
        else:
            raise ValueError("Unsupported favorite type")
        session.add(fav)
        session.commit()
        session.refresh(fav)
        return fav
    finally:
        session.close()


def remove_favorite(user_id: int, target_type: FavoriteTargetType, target_id: int) -> bool:
    session = get_session()
    try:
        fav = None
        if target_type == FavoriteTargetType.ARTIST:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.artist_id == target_id
                )
            ).first()
        elif target_type == FavoriteTargetType.ALBUM:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.album_id == target_id
                )
            ).first()
        elif target_type == FavoriteTargetType.TRACK:
            fav = session.exec(
                select(UserFavorite).where(
                    UserFavorite.user_id == user_id,
                    UserFavorite.target_type == target_type,
                    UserFavorite.track_id == target_id
                )
            ).first()
        if fav:
            session.delete(fav)
            session.commit()
            return True
        return False
    finally:
        session.close()


def list_favorites(user_id: int, target_type: Optional[FavoriteTargetType] = None):
    session = get_session()
    try:
        stmt = select(UserFavorite).where(UserFavorite.user_id == user_id)
        if target_type:
            stmt = stmt.where(UserFavorite.target_type == target_type)
        return session.exec(stmt).all()
    finally:
        session.close()


def hide_artist_for_user(user_id: int, artist_id: int) -> Artist:
    session = get_session()
    try:
        artist = session.get(Artist, artist_id)
        if not artist:
            raise ValueError("Artist not found")
        artist.is_hidden = True
        session.add(artist)
        session.commit()
        session.refresh(artist)
        return artist
    finally:
        session.close()


def unhide_artist_for_user(user_id: int, artist_id: int) -> bool:
    session = get_session()
    try:
        artist = session.get(Artist, artist_id)
        if not artist:
            return False
        artist.is_hidden = False
        session.add(artist)
        session.commit()
        return True
    finally:
        session.close()


def update_album_spotify_data(album_id: int, spotify_data: dict):
    """Update album with fresh Spotify data."""
    session = get_session()
    try:
        album = session.exec(select(Album).where(Album.id == album_id)).first()
        if album:
            album.name = spotify_data.get('name', album.name)
            album.release_date = spotify_data.get('release_date', album.release_date)
            album.total_tracks = spotify_data.get('total_tracks', album.total_tracks)
            album.images = str(spotify_data.get('images', []))
            album.label = spotify_data.get('label', album.label)
            album.updated_at = utc_now()  # Update timestamp
            session.commit()
        return album
    finally:
        session.close()

def toggle_track_favorite(track_id: int) -> Track:
    """Toggle favorite status for a track."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            track.is_favorite = not track.is_favorite
            session.commit()
        return track
    finally:
        session.close()

def set_track_rating(track_id: int, rating: int) -> Track:
    """Set user rating for a track (1-5)."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            if rating < 0 or rating > 5:
                raise ValueError("Rating must be between 0 and 5")
            track.user_score = rating
            session.commit()
        return track
    finally:
        session.close()


def update_artist_bio(artist_id: int, bio_summary: str, bio_content: str, lastfm_listeners: int = 0, lastfm_playcount: int = 0):
    """Update artist with Last.fm bio data."""
    session = get_session()
    try:
        artist = session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if artist:
            artist.bio_summary = bio_summary
            artist.bio_content = bio_content
            now = utc_now()
            artist.updated_at = now  # Update timestamp for fresh data
            artist.last_refreshed_at = now
            # Optionally add lastfm counts if added to model
            session.commit()
        return artist
    finally:
        session.close()


def delete_artist(artist_id: int) -> bool:
    """Delete artist and cascade to albums/tracks."""
    session = get_session()
    try:
        artist = session.exec(select(Artist).where(Artist.id == artist_id)).first()
        if artist:
            # Do not delete if favorited by any user
            fav = session.exec(
                select(UserFavorite).where(UserFavorite.artist_id == artist_id)
            ).first()
            if fav:
                raise ValueError("Artist is favorited by a user and cannot be deleted")
            session.delete(artist)  # CASCADE handles albums/tracks
            session.commit()
            return True
        return False
    finally:
        session.close()


def delete_album(album_id: int) -> bool:
    """Delete album and cascade tracks, unless favorited."""
    session = get_session()
    try:
        album = session.exec(select(Album).where(Album.id == album_id)).first()
        if album:
            fav = session.exec(
                select(UserFavorite).where(UserFavorite.album_id == album_id)
            ).first()
            if fav:
                raise ValueError("Album is favorited by a user and cannot be deleted")
            session.delete(album)
            session.commit()
            return True
        return False
    finally:
        session.close()


def delete_track(track_id: int) -> bool:
    """Delete track unless favorited."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            fav = session.exec(
                select(UserFavorite).where(UserFavorite.track_id == track_id)
            ).first()
            if fav:
                raise ValueError("Track is favorited by a user and cannot be deleted")
            session.delete(track)
            session.commit()
            return True
        return False
    finally:
        session.close()


def rate_track(track_id: int, rating: int) -> Optional["Track"]:
    """Rate a track (1-5)."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            track.user_score = rating
            session.commit()
        return track
    finally:
        session.close()

# YouTube Download Records
def save_youtube_download(youtube_data: dict):
    """Save YouTube download/link record."""
    session = get_session()
    try:
        from .models.base import YouTubeDownload as YT
        status = youtube_data.get("download_status")
        youtube_video_id = youtube_data.get("youtube_video_id")
        if status in ("error", "video_not_found") and not youtube_video_id:
            youtube_data["download_status"] = "missing"

        # Check if exists by track ID
        existing = session.exec(
            select(YT).where(YT.spotify_track_id == youtube_data['spotify_track_id'])
        ).first()

        if existing:
            # Update existing
            existing.youtube_video_id = youtube_data.get('youtube_video_id', existing.youtube_video_id)
            existing.download_status = youtube_data.get('download_status', existing.download_status)
            existing.download_path = youtube_data.get('download_path', existing.download_path)
            existing.file_size = youtube_data.get('file_size', existing.file_size)
            if existing.youtube_video_id:
                existing.error_message = None
            else:
                existing.error_message = youtube_data.get('error_message', existing.error_message)
            existing.updated_at = utc_now()
            session.add(existing)
            result = existing
        else:
            # Create new
            download = YT(
                spotify_track_id=youtube_data['spotify_track_id'],
                spotify_artist_id=youtube_data.get('spotify_artist_id'),
                youtube_video_id=youtube_data.get('youtube_video_id'),
                download_path=youtube_data.get('download_path'),
                download_status=youtube_data.get('download_status', 'video_not_found'),
                error_message=youtube_data.get('error_message')
            )
            session.add(download)
            result = download

        session.commit()
        return result
    finally:
        session.close()

# Playlists
def get_playlist_by_id(playlist_id: int) -> Optional[Playlist]:
    session = get_session()
    try:
        statement = select(Playlist).where(Playlist.id == playlist_id)
        playlist = session.exec(statement).first()
        return playlist
    finally:
        session.close()

def create_playlist(name: str, description: str = "", user_id: int = 1) -> Playlist:
    """Create a new playlist."""
    session = get_session()
    try:
        # Check if user exists, create if not
        user = session.exec(select(User).where(User.id == user_id)).first()
        if not user:
            user = User(
                name="Default User",
                email=f"user{user_id}@example.com",
                password_hash="default_password_hash"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id

        playlist = Playlist(
            name=name,
            description=description,
            user_id=user_id
        )
        session.add(playlist)
        session.commit()
        session.refresh(playlist)
        return playlist
    finally:
        session.close()

def update_playlist(playlist_id: int, name: str = None, description: str = None) -> Optional[Playlist]:
    """Update playlist name and/or description."""
    session = get_session()
    try:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        if playlist:
            if name:
                playlist.name = name
            if description:
                playlist.description = description
            session.commit()
        return playlist
    finally:
        session.close()

def delete_playlist(playlist_id: int) -> bool:
    """Delete playlist and its tracks."""
    session = get_session()
    try:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        if playlist:
            session.delete(playlist)  # CASCADE handles playlist tracks
            session.commit()
            return True
        return False
    finally:
        session.close()

def add_track_to_playlist(playlist_id: int, track_id: int) -> Optional["PlaylistTrack"]:
    """Add track to playlist."""
    from .models.base import PlaylistTrack  # Import here to avoid circular imports
    session = get_session()
    try:
        playlist = session.exec(select(Playlist).where(Playlist.id == playlist_id)).first()
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if playlist and track:
            # Check if track already in playlist
            existing = session.exec(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist_id,
                    PlaylistTrack.track_id == track_id
                )
            ).first()
            if not existing:
                # Get max order for this playlist
                max_order = session.exec(
                    select(PlaylistTrack.order)
                    .where(PlaylistTrack.playlist_id == playlist_id)
                    .order_by(PlaylistTrack.order.desc())
                    .limit(1)
                ).first()
                new_order = (max_order or 0) + 1

                playlist_track = PlaylistTrack(
                    playlist_id=playlist_id,
                    track_id=track_id,
                    order=new_order
                )
                session.add(playlist_track)
                session.commit()
                return playlist_track
        return None
    finally:
        session.close()

def remove_track_from_playlist(playlist_id: int, track_id: int) -> bool:
    """Remove track from playlist."""
    session = get_session()
    try:
        playlist_track = session.exec(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id
            )
        ).first()
        if playlist_track:
            session.delete(playlist_track)
            session.commit()
            return True
        return False
    finally:
        session.close()

# Tags CRUD
def create_tag(name: str, color: str = "#666666") -> Tag:
    """Create a new tag."""
    session = get_session()
    try:
        # Check if tag already exists
        existing_tag = session.exec(select(Tag).where(Tag.name == name)).first()
        if existing_tag:
            return existing_tag

        tag = Tag(name=name, color=color)
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return tag
    finally:
        session.close()

def get_tag_by_id(tag_id: int) -> Optional[Tag]:
    """Get tag by ID."""
    session = get_session()
    try:
        return session.exec(select(Tag).where(Tag.id == tag_id)).first()
    finally:
        session.close()

def get_tag_by_name(name: str) -> Optional[Tag]:
    """Get tag by name."""
    session = get_session()
    try:
        return session.exec(select(Tag).where(Tag.name == name)).first()
    finally:
        session.close()

def get_all_tags() -> List[Tag]:
    """Get all tags."""
    session = get_session()
    try:
        return session.exec(select(Tag)).all()
    finally:
        session.close()

def add_tag_to_track(track_id: int, tag_id: int) -> Optional[TrackTag]:
    """Add tag to track."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        tag = session.exec(select(Tag).where(Tag.id == tag_id)).first()

        if track and tag:
            # Check if already tagged
            existing = session.exec(
                select(TrackTag).where(
                    TrackTag.track_id == track_id,
                    TrackTag.tag_id == tag_id
                )
            ).first()

            if not existing:
                track_tag = TrackTag(track_id=track_id, tag_id=tag_id)
                session.add(track_tag)
                session.commit()
                return track_tag
        return None
    finally:
        session.close()

def remove_tag_from_track(track_id: int, tag_id: int) -> bool:
    """Remove tag from track."""
    session = get_session()
    try:
        track_tag = session.exec(
            select(TrackTag).where(
                TrackTag.track_id == track_id,
                TrackTag.tag_id == tag_id
            )
        ).first()

        if track_tag:
            session.delete(track_tag)
            session.commit()
            return True
        return False
    finally:
        session.close()

def get_track_tags(track_id: int) -> List[Tag]:
    """Get all tags for a track."""
    session = get_session()
    try:
        track_tag_relations = session.exec(
            select(TrackTag).where(TrackTag.track_id == track_id)
        ).all()

        tag_ids = [relation.tag_id for relation in track_tag_relations]
        if tag_ids:
            tags = session.exec(
                select(Tag).where(Tag.id.in_(tag_ids))
            ).all()
            return tags
        return []
    finally:
        session.close()

# Play History CRUD
def record_play(track_id: int, user_id: int = 1) -> Optional[PlayHistory]:
    """Record a track play in history."""
    session = get_session()
    try:
        track = session.exec(select(Track).where(Track.id == track_id)).first()
        if track:
            play_history = PlayHistory(
                track_id=track_id,
                user_id=user_id,
                played_at=utc_now()
            )
            session.add(play_history)
            session.commit()
            session.refresh(play_history)
            return play_history
        return None
    finally:
        session.close()

def get_play_history(track_id: int, limit: int = 10) -> List[PlayHistory]:
    """Get play history for a track."""
    session = get_session()
    try:
        return session.exec(
            select(PlayHistory)
            .where(PlayHistory.track_id == track_id)
            .order_by(PlayHistory.played_at.desc())
            .limit(limit)
        ).all()
    finally:
        session.close()

def get_recent_plays(limit: int = 20) -> List[PlayHistory]:
    """Get most recent plays across all tracks."""
    session = get_session()
    try:
        return session.exec(
            select(PlayHistory)
            .order_by(PlayHistory.played_at.desc())
            .limit(limit)
        ).all()
    finally:
        session.close()

def get_most_played_tracks(limit: int = 10) -> List[dict]:
    """Get most played tracks with play count."""
    session = get_session()
    try:
        # Get play counts per track
        from sqlmodel import func
        results = session.exec(
            select(
                PlayHistory.track_id,
                func.count(PlayHistory.id).label("play_count")
            )
            .group_by(PlayHistory.track_id)
            .order_by(func.count(PlayHistory.id).desc())
            .limit(limit)
        ).all()

        track_ids = [result[0] for result in results]
        tracks = session.exec(
            select(Track).where(Track.id.in_(track_ids))
        ).all()

        # Combine results
        track_play_counts = {result[0]: result[1] for result in results}
        return [
            {
                "track": track.dict(),
                "play_count": track_play_counts[track.id]
            }
            for track in tracks
        ]
    finally:
        session.close()

# Algorithm Learning CRUD
def record_artist_search(user_id: int, artist_name: str):
    """Record when a user searches for an artist to train algorithm."""
    session = get_session()
    try:
        # Check if artist already in user's learned artists
        existing = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .where(AlgorithmLearning.artist_name.ilike(artist_name))
        ).first()

        if existing:
            # Update existing record
            existing.times_searched += 1
            existing.last_searched = utc_now()
            session.add(existing)
        else:
            # Create new learning record
            learning = AlgorithmLearning(
                user_id=user_id,
                artist_name=artist_name,
                times_searched=1,
                first_searched=utc_now(),
                last_searched=utc_now(),
                compatibility_score=0.5  # Default neutral score
            )
            session.add(learning)
        
        session.commit()
        return True
    finally:
        session.close()

def get_user_learned_artists(user_id: int, limit: int = 10):
    """Get artists that user has searched for, sorted by search frequency."""
    session = get_session()
    try:
        learned_artists = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .order_by(AlgorithmLearning.times_searched.desc())
            .limit(limit)
        ).all()
        return learned_artists
    finally:
        session.close()

def update_artist_rating(user_id: int, artist_name: str, rating: int):
    """Update user rating for an artist (1-5 stars)."""
    session = get_session()
    try:
        learning = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .where(AlgorithmLearning.artist_name.ilike(artist_name))
        ).first()

        if learning:
            learning.user_rating = rating
            learning.last_searched = utc_now()
            
            # Update algorithm weights based on rating
            if rating >= 4:
                learning.compatibility_score = min(1.0, learning.compatibility_score + 0.2)
            elif rating <= 2:
                learning.compatibility_score = max(0.0, learning.compatibility_score - 0.2)
            
            session.add(learning)
            session.commit()
            return learning
        else:
            # Create new record with rating
            learning = AlgorithmLearning(
                user_id=user_id,
                artist_name=artist_name,
                user_rating=rating,
                times_searched=1,
                first_searched=utc_now(),
                last_searched=utc_now(),
                compatibility_score=0.7 if rating >= 4 else (0.3 if rating <= 2 else 0.5)
            )
            session.add(learning)
            session.commit()
            return learning
    finally:
        session.close()

def mark_artist_as_favorite(user_id: int, artist_name: str, is_favorite: bool = True):
    """Mark/unmark an artist as favorite for the user."""
    session = get_session()
    try:
        learning = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .where(AlgorithmLearning.artist_name.ilike(artist_name))
        ).first()

        if learning:
            learning.is_favorite = is_favorite
            learning.last_searched = utc_now()
            
            # Boost compatibility score for favorites
            if is_favorite:
                learning.compatibility_score = min(1.0, learning.compatibility_score + 0.3)
            
            session.add(learning)
            session.commit()
            return learning
        else:
            # Create new record
            learning = AlgorithmLearning(
                user_id=user_id,
                artist_name=artist_name,
                is_favorite=is_favorite,
                times_searched=1,
                first_searched=utc_now(),
                last_searched=utc_now(),
                compatibility_score=0.8 if is_favorite else 0.5
            )
            session.add(learning)
            session.commit()
            return learning
    finally:
        session.close()

def get_user_preferred_genres(user_id: int):
    """Extract preferred genres from user's learned artists."""
    session = get_session()
    try:
        # Get user's top artists
        learned_artists = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .order_by(AlgorithmLearning.times_searched.desc())
            .limit(10)
        ).all()

        # Get actual artists from database to extract genres
        artist_names = [la.artist_name for la in learned_artists]
        
        genres = []
        for artist_name in artist_names:
            artist = session.exec(
                select(Artist)
                .where(Artist.name.ilike(f"%{artist_name}%"))
            ).first()
            
            if artist and artist.genres:
                try:
                    artist_genres = eval(artist.genres) if isinstance(artist.genres, str) else artist.genres
                    if isinstance(artist_genres, list):
                        genres.extend(artist_genres)
                except Exception:
                    pass
        
        # Count genre frequencies
        from collections import Counter
        genre_counts = Counter(genres)
        return genre_counts.most_common(5)
    finally:
        session.close()

def get_recommendations_for_user(user_id: int, limit: int = 10):
    """Generate artist recommendations based on user's learned preferences."""
    session = get_session()
    try:
        # Get user's learned artists with high compatibility scores
        user_artists = session.exec(
            select(AlgorithmLearning)
            .where(AlgorithmLearning.user_id == user_id)
            .where(AlgorithmLearning.compatibility_score >= 0.6)
            .order_by(AlgorithmLearning.compatibility_score.desc())
            .limit(5)
        ).all()

        if not user_artists:
            return []

        # For now, return similar artists using existing similar artist logic
        # In a real system, this would use Spotify API or ML model
        recommendations = []
        for learned in user_artists:
            # Find similar artists in database (simple example)
            similar = session.exec(
                select(Artist)
                .where(Artist.genres.ilike(f"%{learned.artist_name.lower()}%"))
                .limit(3)
            ).all()
            
            for artist in similar:
                if artist.name.lower() != learned.artist_name.lower():
                    recommendations.append({
                        "artist": artist.dict(),
                        "reason": f"Similar to {learned.artist_name}",
                        "confidence": learned.compatibility_score
                    })
        
        # Deduplicate
        seen = set()
        unique_recs = []
        for rec in recommendations:
            artist_id = rec["artist"]["id"]
            if artist_id not in seen:
                seen.add(artist_id)
                unique_recs.append(rec)
        
        return unique_recs[:limit]
    finally:
        session.close()


# Smart Playlist Generation
def generate_top_rated_playlist(user_id: int = 1, name: str = "Top Rated", limit: int = 20) -> Optional[Playlist]:
    """Generate a playlist of top rated tracks."""
    session = get_session()
    try:
        # Get top rated tracks
        tracks = session.exec(
            select(Track)
            .where(Track.user_score > 0)
            .order_by(Track.user_score.desc())
            .limit(limit)
        ).all()

        if not tracks:
            return None

        # Create playlist
        playlist = create_playlist(name, "Auto-generated top rated tracks", user_id)

        # Add tracks to playlist
        for track in tracks:
            add_track_to_playlist(playlist.id, track.id)

        return playlist
    finally:
        session.close()

def generate_most_played_playlist(user_id: int = 1, name: str = "Most Played", limit: int = 20) -> Optional[Playlist]:
    """Generate a playlist of most played tracks."""
    session = get_session()
    try:
        # Get most played tracks
        most_played = get_most_played_tracks(limit)
        track_ids = [item['track']['id'] for item in most_played]

        if not track_ids:
            return None

        # Create playlist
        playlist = create_playlist(name, "Auto-generated most played tracks", user_id)

        # Add tracks to playlist
        for track_id in track_ids:
            add_track_to_playlist(playlist.id, track_id)

        return playlist
    finally:
        session.close()

def generate_favorites_playlist(user_id: int = 1, name: str = "Favorites", limit: int = 50) -> Optional[Playlist]:
    """Generate a playlist of favorite tracks."""
    session = get_session()
    try:
        # Get favorite tracks
        tracks = session.exec(
            select(Track)
            .where(Track.is_favorite.is_(True))
            .limit(limit)
        ).all()

        if not tracks:
            return None

        # Create playlist
        playlist = create_playlist(name, "Auto-generated favorite tracks", user_id)

        # Add tracks to playlist
        for track in tracks:
            add_track_to_playlist(playlist.id, track.id)

        return playlist
    finally:
        session.close()

def generate_recently_played_playlist(user_id: int = 1, name: str = "Recently Played", limit: int = 20) -> Optional[Playlist]:
    """Generate a playlist of recently played tracks."""
    session = get_session()
    try:
        # Get recent plays
        recent_plays = get_recent_plays(limit)
        track_ids = [play.track_id for play in recent_plays]

        if not track_ids:
            return None

        # Create playlist
        playlist = create_playlist(name, "Auto-generated recently played tracks", user_id)

        # Add tracks to playlist
        for track_id in track_ids:
            add_track_to_playlist(playlist.id, track_id)

        return playlist
    finally:
        session.close()

def generate_by_tag_playlist(tag_name: str, user_id: int = 1, name: str = None, limit: int = 30) -> Optional[Playlist]:
    """Generate a playlist of tracks with specific tag."""
    session = get_session()
    try:
        # Get tag
        tag = get_tag_by_name(tag_name)
        if not tag:
            return None

        # Get tracks with this tag
        track_tags = session.exec(
            select(TrackTag)
            .where(TrackTag.tag_id == tag.id)
        ).all()

        track_ids = [tt.track_id for tt in track_tags][:limit]

        if not track_ids:
            return None

        # Create playlist name
        if not name:
            name = f"Tag: {tag_name}"

        # Create playlist
        playlist = create_playlist(name, f"Auto-generated tracks with tag '{tag_name}'", user_id)

        # Add tracks to playlist
        for track_id in track_ids:
            add_track_to_playlist(playlist.id, track_id)

        return playlist
    finally:
        session.close()

def generate_discover_weekly_playlist(user_id: int = 1, name: str = "Discover Weekly", limit: int = 30) -> Optional[Playlist]:
    """Generate a discover weekly style playlist with mixed criteria."""
    session = get_session()
    try:
        # Get tracks from multiple criteria
        # 1. Top rated
        top_rated = session.exec(
            select(Track)
            .where(Track.user_score >= 4)
            .order_by(Track.user_score.desc())
            .limit(limit // 3)
        ).all()

        # 2. Most played
        most_played_data = get_most_played_tracks(limit // 3)
        most_played_ids = [item['track']['id'] for item in most_played_data]
        most_played = session.exec(
            select(Track)
            .where(Track.id.in_(most_played_ids))
        ).all()

        # 3. Recent plays
        recent_plays = get_recent_plays(limit // 3)
        recent_track_ids = [play.track_id for play in recent_plays]
        recent_tracks = session.exec(
            select(Track)
            .where(Track.id.in_(recent_track_ids))
        ).all()

        # Combine and deduplicate
        all_tracks = top_rated + most_played + recent_tracks
        unique_tracks = []
        seen_ids = set()
        for track in all_tracks:
            if track.id not in seen_ids:
                seen_ids.add(track.id)
                unique_tracks.append(track)

        # Limit to requested size
        unique_tracks = unique_tracks[:limit]

        if not unique_tracks:
            return None

        # Create playlist
        playlist = create_playlist(name, "Auto-generated discover weekly style playlist", user_id)

        # Add tracks to playlist
        for track in unique_tracks:
            add_track_to_playlist(playlist.id, track.id)

        return playlist
    finally:
        session.close()
