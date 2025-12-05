"""
CRUD operations using SQLModel.
"""

import unicodedata

from typing import Optional
from sqlmodel import Session, select

from .models.base import Artist, Album, Track, User, Playlist, PlaylistTrack
from .core.db import get_session


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
    artist = get_artist_by_spotify_id(spotify_id)
    session = get_session()
    try:
        if artist:
            artist.name = artist_data['name']
            artist.normalized_name = normalize_name(artist_data['name'])
            artist.genres = str(artist_data.get('genres', []))
            artist.images = str(artist_data.get('images', []))
            artist.popularity = artist_data.get('popularity', 0)
            artist.followers = artist_data.get('followers', {}).get('total', 0)
            session.add(artist)
        else:
            normalized = normalize_name(artist_data['name'])
            # Check for existing by normalized name
            statement = select(Artist).where(Artist.normalized_name == normalized)
            existing_artist = session.exec(statement).first()
            if existing_artist:
                # Merge into existing
                existing_artist.spotify_id = existing_artist.spotify_id or spotify_id
                existing_artist.name = artist_data['name']
                existing_artist.normalized_name = normalized
                existing_artist.genres = str(artist_data.get('genres', []))
                existing_artist.images = str(artist_data.get('images', []))
                existing_artist.popularity = artist_data.get('popularity', 0)
                existing_artist.followers = artist_data.get('followers', {}).get('total', 0)
                artist = existing_artist
            else:
                artist = Artist(
                    spotify_id=spotify_id,
                    name=artist_data['name'],
                    normalized_name=normalized,
                    genres=str(artist_data.get('genres', [])),
                    images=str(artist_data.get('images', [])),
                    popularity=artist_data.get('popularity', 0),
                    followers=artist_data.get('followers', {}).get('total', 0)
                )
                session.add(artist)
        session.commit()
        session.refresh(artist)
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
        if album:
            album.name = album_data['name']
            album.release_date = album_data['release_date']
            album.total_tracks = album_data['total_tracks']
            album.images = str(album_data.get('images', []))
            album.label = album_data.get('label')
            session.add(album)
        else:
            # Save artist if not exists
            artist_spotify_id = album_data['artists'][0]['id'] if album_data['artists'] else None
            artist_data = {"id": artist_spotify_id, "name": album_data['artists'][0]['name'], "genres": [], "images": [], "popularity": 0, "followers": {"total": 0}} if artist_spotify_id else None
            artist = get_artist_by_spotify_id(artist_spotify_id) if artist_spotify_id else None
            if not artist and artist_data:
                artist = save_artist(artist_data)  # This opens/closes its own session
            artist_id = artist.id if artist else None
            album = Album(
                spotify_id=spotify_id,
                name=album_data['name'],
                artist_id=artist_id,
                release_date=album_data['release_date'],
                total_tracks=album_data['total_tracks'],
                images=str(album_data.get('images', [])),
                label=album_data.get('label')
            )
            session.add(album)
        session.commit()
        session.refresh(album)
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
        if track:
            track.name = track_data['name']
            track.duration_ms = track_data['duration_ms']
            track.popularity = track_data.get('popularity', 0)
            track.preview_url = track_data.get('preview_url')
            track.external_url = track_data['external_urls']['spotify']
            track.album_id = album_id
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
                external_url=track_data['external_urls']['spotify']
            )
            session.add(track)
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
            session.commit()
        return track
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
            session.delete(artist)  # CASCADE handles albums/tracks
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
