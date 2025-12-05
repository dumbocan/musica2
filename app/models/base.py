# Base for SQLModel classes

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# Musical Genre enum if needed
# from enum import Enum

# class Genre(Enum):
#     ROCK = "rock"
#     POP = "pop"
#     # etc.

class User(SQLModel, table=True):
    """User model for multiuser (prepared)."""
    id: int = Field(primary_key=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=150, unique=True)
    password_hash: str = Field(max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships (future)
    playlists: Optional[List["Playlist"]] = Relationship(back_populates="user")


class Artist(SQLModel, table=True):
    """Artist from Spotify/Last.fm."""
    id: int = Field(primary_key=True)
    spotify_id: Optional[str] = Field(unique=True, default=None)  # Optional if from other source
    name: str = Field(max_length=200, index=True)
    normalized_name: str = Field(default="", index=True)  # For deduplication
    genres: Optional[str] = None  # JSON list as string
    images: Optional[str] = None  # JSON list of image URLs
    popularity: int = Field(default=0)  # Spotify 0-100
    followers: int = Field(default=0)
    bio_summary: Optional[str] = None  # Last.fm bio summary
    bio_content: Optional[str] = None  # Last.fm full bio
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    albums: Optional[List["Album"]] = Relationship(back_populates="artist")
    tracks: Optional[List["Track"]] = Relationship(back_populates="artist")


class Album(SQLModel, table=True):
    """Album from Spotify."""
    id: int = Field(primary_key=True)
    spotify_id: Optional[str] = Field(unique=True, default=None)
    name: str = Field(max_length=200, index=True)
    artist_id: int = Field(foreign_key="artist.id", ondelete="CASCADE")
    release_date: str  # YYYY-MM-DD
    total_tracks: int = Field(default=0)
    images: Optional[str] = None  # JSON
    label: Optional[str] = Field(max_length=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    artist: Artist = Relationship(back_populates="albums")
    tracks: Optional[List["Track"]] = Relationship(back_populates="album")


class Track(SQLModel, table=True):
    """Track from Spotify, with local data."""
    id: int = Field(primary_key=True)
    spotify_id: Optional[str] = Field(unique=True, default=None)
    name: str = Field(max_length=200, index=True)
    artist_id: int = Field(foreign_key="artist.id", ondelete="CASCADE")
    album_id: Optional[int] = Field(foreign_key="album.id", ondelete="CASCADE")
    duration_ms: int = Field(default=0)
    preview_url: Optional[str] = None  # 30s preview
    external_url: Optional[str] = None  # Spotify full
    popularity: int = Field(default=0)  # Spotify 0-100
    lastfm_listeners: int = Field(default=0)  # Last.fm
    lastfm_playcount: int = Field(default=0)  # Scoring
    lyrics: Optional[str] = None  # From Musixmatch
    magnet_link: Optional[str] = None  # Torrent for local file
    user_score: int = Field(default=0)  # User rating 1-5
    played_at: Optional[datetime] = None  # Last played
    is_favorite: bool = Field(default=False)  # Favorite flag
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    artist: Artist = Relationship(back_populates="tracks")
    album: Optional[Album] = Relationship(back_populates="tracks")


class Playlist(SQLModel, table=True):
    """User playlists."""
    id: int = Field(primary_key=True)
    name: str = Field(max_length=150)
    description: Optional[str] = None
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: User = Relationship(back_populates="playlists")
    tracks: Optional[List["PlaylistTrack"]] = Relationship(back_populates="playlist")


class PlaylistTrack(SQLModel, table=True):
    """Many-to-many for playlists and tracks."""
    id: int = Field(primary_key=True)
    playlist_id: int = Field(foreign_key="playlist.id", ondelete="CASCADE")
    track_id: int = Field(foreign_key="track.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    order: int = Field(default=0)  # Position in playlist

    playlist: Playlist = Relationship(back_populates="tracks")
    track: Track = Relationship()


# Pydantic models for API responses (validation)
class SpotifyArtistResponse(SQLModel):
    id: str
    name: str
    genres: List[str] = []
    images: List[dict] = []  # [{'url': str, 'height': int, ...}]
    popularity: int
    followers: dict = {'total': 0}  # total = followers

class SpotifyTrackResponse(SQLModel):
    id: str
    name: str
    artists: List[SpotifyArtistResponse]
    album: dict  # subset, id, name, etc.
    duration_ms: int
    popularity: int
    preview_url: Optional[str] = None
    external_urls: dict  # spotify url

# Future: schemas for create/update endpoints
