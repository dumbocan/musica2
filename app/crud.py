"""
CRUD operations using SQLModel.
"""

from typing import Optional
from sqlmodel import Session, select

from .models.base import Artist, Album, Track, User, Playlist
from .core.db import get_session


# Artists
def get_artist_by_spotify_id(spotify_id: str) -> Optional[Artist]:
    with get_session() as session:
        statement = select(Artist).where(Artist.spotify_id == spotify_id)
        artist = session.exec(statement).first()
        return artist

def save_artist(artist_data: dict) -> Artist:
    spotify_id = artist_data['id']
    artist = get_artist_by_spotify_id(spotify_id)
    if artist:
        artist.name = artist_data['name']
        artist.genres = str(artist_data.get('genres', []))
        artist.images = str(artist_data.get('images', []))
        artist.popularity = artist_data.get('popularity', 0)
        artist.followers = artist_data.get('followers', {}).get('total', 0)
    else:
        artist = Artist(
            spotify_id=spotify_id,
            name=artist_data['name'],
            genres=str(artist_data.get('genres', [])),
            images=str(artist_data.get('images', [])),
            popularity=artist_data.get('popularity', 0),
            followers=artist_data.get('followers', {}).get('total', 0)
        )
    with get_session() as session:
        session.add(artist)
        session.commit()
        session.refresh(artist)
    return artist


# Albums (similar)
def get_album_by_spotify_id(spotify_id: str) -> Optional[Album]:
    with get_session() as session:
        statement = select(Album).where(Album.spotify_id == spotify_id)
        album = session.exec(statement).first()
        return album

def save_album(album_data: dict) -> Album:
    spotify_id = album_data['id']
    album = get_album_by_spotify_id(spotify_id)
    if album:
        album.name = album_data['name']
        album.release_date = album_data['release_date']
        album.total_tracks = album_data['total_tracks']
        album.images = str(album_data.get('images', []))
        album.label = album_data.get('label')
    else:
        # Assume artist already saved, but for simplicity, save if not
        artist = get_artist_by_spotify_id(album_data['artists'][0]['id']) if album_data['artists'] else None
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
    with get_session() as session:
        session.add(album)
        session.commit()
        session.refresh(album)
    return album


# Tracks
def get_track_by_spotify_id(spotify_id: str) -> Optional[Track]:
    with get_session() as session:
        statement = select(Track).where(Track.spotify_id == spotify_id)
        track = session.exec(statement).first()
        return track

def save_track(track_data: dict, album_id: Optional[int] = None, artist_id: Optional[int] = None) -> Track:
    spotify_id = track_data['id']
    track = get_track_by_spotify_id(spotify_id)
    if track:
        track.name = track_data['name']
        track.duration_ms = track_data['duration_ms']
        track.popularity = track_data['popularity']
        track.preview_url = track_data['preview_url']
        track.external_url = track_data['external_urls']['spotify']
        track.album_id = album_id
    else:
        track = Track(
            spotify_id=spotify_id,
            name=track_data['name'],
            artist_id=artist_id,
            album_id=album_id,
            duration_ms=track_data['duration_ms'],
            popularity=track_data['popularity'],
            preview_url=track_data['preview_url'],
            external_url=track_data['external_urls']['spotify']
        )
    with get_session() as session:
        session.add(track)
        session.commit()
        session.refresh(track)
    return track
