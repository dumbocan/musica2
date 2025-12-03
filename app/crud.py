"""
CRUD operations using SQLModel.
"""

import unicodedata

from typing import Optional
from sqlmodel import Session, select

from .models.base import Artist, Album, Track, User, Playlist
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
