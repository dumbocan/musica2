# Base for SQLModel classes

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Musical Genre enum if needed
# from enum import Enum

# class Genre(Enum):
#     ROCK = "rock"
#     POP = "pop"
#     # etc.


class FavoriteTargetType(str, Enum):
    ARTIST = "artist"
    ALBUM = "album"
    TRACK = "track"

class User(SQLModel, table=True):
    """Complete user model for multiuser system."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    username: str = Field(max_length=50, unique=True)
    email: str = Field(max_length=150, unique=True)
    password_hash: str = Field(max_length=200)
    is_active: bool = Field(default=True)
    last_login: Optional[datetime] = None

    # Storage tracking
    storage_used_mb: int = Field(default=0)
    max_storage_mb: int = Field(default=2000)  # 2GB default

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    profile: Optional["UserProfile"] = Relationship(back_populates="user")
    playlists: Optional[List["Playlist"]] = Relationship(back_populates="user")
    play_history: Optional[List["PlayHistory"]] = Relationship(back_populates="user")
    learned_artists: Optional[List["AlgorithmLearning"]] = Relationship(back_populates="user")
    favorites: Optional[List["UserFavorite"]] = Relationship(back_populates="user")


class Artist(SQLModel, table=True):
    """Artist from Spotify/Last.fm."""
    id: Optional[int] = Field(default=None, primary_key=True)
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
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # Last metadata update

    # Relationships
    albums: Optional[List["Album"]] = Relationship(back_populates="artist")
    tracks: Optional[List["Track"]] = Relationship(back_populates="artist")
    favorites: Optional[List["UserFavorite"]] = Relationship(back_populates="artist")


class Album(SQLModel, table=True):
    """Album from Spotify."""
    id: Optional[int] = Field(default=None, primary_key=True)
    spotify_id: Optional[str] = Field(unique=True, default=None)
    name: str = Field(max_length=200, index=True)
    artist_id: int = Field(foreign_key="artist.id", ondelete="CASCADE")
    release_date: str  # YYYY-MM-DD
    total_tracks: int = Field(default=0)
    images: Optional[str] = None  # JSON
    label: Optional[str] = Field(max_length=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # Last metadata update

    # Relationships
    artist: Artist = Relationship(back_populates="albums")
    tracks: Optional[List["Track"]] = Relationship(back_populates="album")
    favorites: Optional[List["UserFavorite"]] = Relationship(back_populates="album")


class Track(SQLModel, table=True):
    """Track from Spotify, with local data."""
    id: Optional[int] = Field(default=None, primary_key=True)
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
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # Last metadata update

    # Relationships
    artist: Artist = Relationship(back_populates="tracks")
    album: Optional[Album] = Relationship(back_populates="tracks")
    tags: Optional[List["TrackTag"]] = Relationship(back_populates="track")
    play_history: Optional[List["PlayHistory"]] = Relationship(back_populates="track")
    favorites: Optional[List["UserFavorite"]] = Relationship(back_populates="track")


class Playlist(SQLModel, table=True):
    """User playlists."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=150)
    description: Optional[str] = None
    user_id: int = Field(foreign_key="user.id")
    external_source: Optional[str] = Field(default=None, max_length=50)  # e.g., 'spotify'
    external_id: Optional[str] = Field(default=None, max_length=120)  # playlist id on source
    imported_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: User = Relationship(back_populates="playlists")
    tracks: Optional[List["PlaylistTrack"]] = Relationship(back_populates="playlist")


class PlaylistTrack(SQLModel, table=True):
    """Many-to-many for playlists and tracks."""
    id: Optional[int] = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="playlist.id", ondelete="CASCADE")
    track_id: int = Field(foreign_key="track.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    order: int = Field(default=0)  # Position in playlist

    playlist: Playlist = Relationship(back_populates="tracks")
    track: Track = Relationship()


class UserFavorite(SQLModel, table=True):
    """User favorites for artists, albums, tracks."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    target_type: FavoriteTargetType = Field(default=FavoriteTargetType.TRACK)
    artist_id: Optional[int] = Field(default=None, foreign_key="artist.id", index=True)
    album_id: Optional[int] = Field(default=None, foreign_key="album.id", index=True)
    track_id: Optional[int] = Field(default=None, foreign_key="track.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="favorites")
    artist: Optional[Artist] = Relationship(back_populates="favorites")
    album: Optional[Album] = Relationship(back_populates="favorites")
    track: Optional[Track] = Relationship(back_populates="favorites")

class YouTubeDownload(SQLModel, table=True):
    """Tracking system for YouTube audio downloads."""
    id: Optional[int] = Field(default=None, primary_key=True)
    spotify_track_id: str = Field(index=True)  # Spotify track ID
    spotify_artist_id: str = Field(index=True)  # Spotify artist ID
    youtube_video_id: str = Field(index=True)
    download_path: str
    download_status: str = Field(default="pending")  # 'pending', 'downloading', 'completed', 'error'
    file_size: Optional[int] = None
    format_type: str = Field(default="mp3")
    duration_seconds: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        return self.download_status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.download_status in ["error", "failed"]

class Tag(SQLModel, table=True):
    """Tag system for tracks."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    color: Optional[str] = Field(max_length=20, default="#666666")  # Hex color code
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    tracks: Optional[List["TrackTag"]] = Relationship(back_populates="tag")

class TrackTag(SQLModel, table=True):
    """Many-to-many relationship between tracks and tags."""
    id: Optional[int] = Field(default=None, primary_key=True)
    track_id: int = Field(foreign_key="track.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    track: Track = Relationship(back_populates="tags")
    tag: Tag = Relationship(back_populates="tracks")

class UserProfile(SQLModel, table=True):
    """Advanced user profiles for personalized recommendations."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")

    # Music preferences
    favorite_genres: Optional[str] = Field(default="")  # JSON array stored as string
    disliked_genres: Optional[str] = Field(default="")

    # Algorithm settings
    learning_rate: float = Field(default=0.1)  # How fast algorithm adapts
    discovery_preference: str = Field(default="balanced")  # 'conservative', 'balanced', 'adventurous'
    auto_download_enabled: bool = Field(default=True)

    # Storage management
    storage_used_mb: int = Field(default=0)
    max_storage_mb: int = Field(default=2000)  # 2GB default
    cleanup_threshold_days: int = Field(default=90)  # 3 months

    # Learning statistics
    total_searches: int = Field(default=0)
    total_downloads: int = Field(default=0)
    algorithm_confidence: float = Field(default=0.5)  # 0-1 how confident algorithm is

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_algorithm_training: Optional[datetime] = None

    # Relationships
    user: User = Relationship(back_populates="profile")


class AlgorithmLearning(SQLModel, table=True):
    """Machine learning data per user - how algorithm improves based on user behavior."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    artist_name: str = Field(max_length=200, index=True)

    # Learning data
    compatibility_score: float = Field(default=0.5)  # Algorithm's predicted compatibility
    user_rating: Optional[int] = Field(default=None)  # 1-5 user feedback
    times_searched: int = Field(default=1)

    # Behavior tracking
    is_favorite: bool = Field(default=False)
    last_downloaded: Optional[datetime] = None
    total_downloaded_tracks: int = Field(default=0)
    average_rating_given: Optional[float] = None

    # Algorithm weights (machine learning)
    genre_weight: float = Field(default=1.0)
    search_frequency_weight: float = Field(default=1.0)
    user_feedback_weight: float = Field(default=1.0)

    # Timestamps
    first_searched: datetime = Field(default_factory=datetime.utcnow)
    last_searched: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: User = Relationship(back_populates="learned_artists")


class PlayHistory(SQLModel, table=True):
    """Track play history with user tracking."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    track_id: int = Field(foreign_key="track.id", ondelete="CASCADE")

    # Play details
    played_at: datetime = Field(default_factory=datetime.utcnow)
    duration_played_seconds: int = Field(default=0)  # How much was actually listened
    platform: str = Field(default="local")  # 'local', 'web', 'mobile'
    device_info: Optional[str] = Field(default=None)  # Browser/OS info

    # User context
    mood_tag: Optional[str] = Field(default=None)  # happy, sad, energetic, etc.
    playlist_context: Optional[str] = Field(default=None)  # From playlist?

    # Algorithm learning
    was_recommended: bool = Field(default=False)  # Was this recommended?
    recommendation_source: Optional[str] = Field(default=None)  # 'layer1', 'layer2', 'layer3'

    # Relationships
    user: User = Relationship(back_populates="play_history")
    track: Track = Relationship(back_populates="play_history")


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
