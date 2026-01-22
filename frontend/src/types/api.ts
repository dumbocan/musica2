// TypeScript types for Audio2 API based on models/base.py and API responses

// Database Models
export interface Artist {
  id: number;
  spotify_id: string | null;
  name: string;
  normalized_name: string;
  genres: string | null;
  images: string | null;
  popularity: number;
  followers: number;
  bio_summary: string | null;
  bio_content: string | null;
  created_at: string;
  updated_at: string;
  albums?: Album[];
  tracks?: Track[];
}

export interface Album {
  id: number;
  spotify_id: string | null;
  name: string;
  artist_id: number;
  release_date: string;
  total_tracks: number;
  images: string | null;
  label: string | null;
  created_at: string;
  updated_at: string;
  artist?: Artist;
  tracks?: Track[];
}

export interface Track {
  id: number;
  spotify_id: string | null;
  name: string;
  artist_id: number;
  album_id: number | null;
  duration_ms: number;
  preview_url: string | null;
  external_url: string | null;
  popularity: number;
  lastfm_listeners: number;
  lastfm_playcount: number;
  lyrics: string | null;
  magnet_link: string | null;
  user_score: number;
  played_at: string | null;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
  artist?: Artist;
  album?: Album;
  tags?: TrackTag[];
}

export interface Playlist {
  id: number;
  name: string;
  description: string | null;
  user_id: number;
  created_at: string;
  user?: User;
  tracks?: PlaylistTrack[];
}

export interface PlaylistTrack {
  id: number;
  playlist_id: number;
  track_id: number;
  added_at: string;
  order: number;
  playlist: Playlist;
  track: Track;
}

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  created_at: string;
  tracks?: TrackTag[];
}

export interface TrackTag {
  id: number;
  track_id: number;
  tag_id: number;
  created_at: string;
  track: Track;
  tag: Tag;
}

export interface User {
  id: number;
  name: string;
  username: string;
  email: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountLookupResponse {
  id: number;
  name: string;
  username: string;
  email: string;
}

// API Request/Response Types
export interface SearchArtistsRequest {
  q: string;
  user_id?: number;
  expand_library?: boolean;
}

export interface SearchArtistsResponse {
  query: string;
  user_id: number;
  artists: SpotifyArtist[];
  main_artist_processed?: {
    name: string;
    spotify_id: string;
    followers: number;
  };
  library_expansion?: unknown;
}

export interface DiscographyResponse {
  artist: Artist;
  albums: Array<Album & { tracks: Track[] }>;
}

// Spotify API Types
export interface SpotifyArtist {
  id: string;
  name: string;
  genres: string[];
  images: Array<{
    url: string;
    height: number | null;
    width: number | null;
  }>;
  popularity: number;
  followers: {
    total: number;
  };
  external_urls?: {
    spotify: string;
  };
}

export interface SpotifyTrackLite {
  id: string;
  name: string;
  duration_ms: number;
  popularity: number;
  preview_url: string | null;
  external_urls?: {
    spotify: string;
  };
  album?: {
    id?: string;
    name: string;
    images?: Array<{ url: string; height: number | null; width: number | null }>;
  };
  artists: Array<{
    id: string;
    name: string;
  }>;
}

export interface SpotifyTrack {
  id: string;
  name: string;
  duration_ms: number;
  popularity: number;
  preview_url: string | null;
  external_urls?: {
    spotify: string;
  };
  artists: SpotifyArtist[];
  album: {
    id: string;
    name: string;
    release_date: string;
    images: Array<{
      url: string;
      height: number | null;
      width: number | null;
    }>;
  };
}

export interface CuratedTrackItem {
  id: number;
  spotify_id: string | null;
  name: string;
  duration_ms: number;
  popularity: number;
  is_favorite: boolean;
  download_status: string | null;
  download_path: string | null;
  album: {
    id: number;
    spotify_id: string | null;
    name: string;
    release_date: string;
  } | null;
  artists: Array<{
    id: number;
    name: string;
    spotify_id: string | null;
  }>;
  videoId: string | null;
}

export interface PlaylistSection {
  key: string;
  title: string;
  description: string;
  items: CuratedTrackItem[];
  meta?: {
    count?: number;
    genres?: string[];
    artist?: {
      name: string;
      spotify_id: string | null;
    };
    note?: string;
  };
}

export interface ListsOverviewResponse {
  lists: PlaylistSection[];
  top_genres?: string[];
  anchor_artist?: {
    id: number | null;
    name: string | null;
    spotify_id: string | null;
  } | null;
}

// Utility types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  version?: string;
  database?: string;
}

export interface UserRecommendation {
  artist: Artist;
  reason?: string | null;
  confidence?: number | null;
}

export interface UserRecommendationsResponse {
  user_id: number;
  recommendations: UserRecommendation[];
  based_on_artists: string[];
  recommendation_count: number;
}

// Form types
export interface TrackRatingRequest {
  track_id: number;
  rating: number;
  comment?: string;
}

export interface PlaylistCreateRequest {
  name: string;
  description?: string;
  user_id: number;
}

export interface TagCreateRequest {
  name: string;
  color?: string;
}

// Download types
export interface DownloadStatus {
  id: number;
  spotify_track_id: string;
  youtube_video_id: string;
  download_status: 'pending' | 'downloading' | 'completed' | 'error' | 'failed';
  download_path: string;
  file_size: number | null;
  format_type: string;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface TrackOverview {
  track_id: number;
  track_name: string;
  spotify_track_id?: string | null;
  artist_name?: string | null;
  artist_spotify_id?: string | null;
  album_name?: string | null;
  album_spotify_id?: string | null;
  duration_ms?: number | null;
  popularity?: number | null;
  youtube_video_id?: string | null;
  youtube_status?: string | null;
  youtube_url?: string | null;
  local_file_path?: string | null;
  local_file_exists: boolean;
  chart_source?: string | null;
  chart_name?: string | null;
  chart_best_position?: number | null;
  chart_best_position_date?: string | null;
  chart_weeks_at_one?: number | null;
  chart_weeks_top5?: number | null;
  chart_weeks_top10?: number | null;
}

export interface TrackChartStat {
  track_id: number;
  spotify_track_id?: string | null;
  chart_source?: string | null;
  chart_name?: string | null;
  chart_best_position?: number | null;
  chart_best_position_date?: string | null;
  chart_weeks_at_one?: number | null;
  chart_weeks_top5?: number | null;
  chart_weeks_top10?: number | null;
}

export interface TrackPlaySummary extends TrackOverview {
  play_count: number;
  last_played_at?: string | null;
}

export interface TrackRecentPlay extends TrackOverview {
  played_at?: string | null;
}
