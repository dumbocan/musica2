// API Client for Audio2 Frontend
import axios from 'axios';
import { useApiStore } from '@/store/useApiStore';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Axios instance with defaults
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // algunas llamadas (discografía completa) tardan más
  headers: {
    'Content-Type': 'application/json',
  },
});

const healthClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const HEALTH_CHECK_COOLDOWN_MS = 120000;
let lastHealthCheckAt = 0;
let healthCheckInFlight: Promise<void> | null = null;

const refreshServiceStatus = () => {
  const token = localStorage.getItem('token');
  if (!token) return;
  const now = Date.now();
  if (healthCheckInFlight || now - lastHealthCheckAt < HEALTH_CHECK_COOLDOWN_MS) return;
  lastHealthCheckAt = now;
  healthCheckInFlight = healthClient
    .get('/health/detailed', { headers: { Authorization: `Bearer ${token}` } })
    .then((res) => {
      useApiStore.getState().setServiceStatus(res.data?.services ?? null);
    })
    .catch(() => {})
    .finally(() => {
      healthCheckInFlight = null;
    });
};

// Attach token if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const store = useApiStore.getState();
    const isTimeout = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT';
    const isNetwork = error.code === 'ERR_NETWORK' || !error.response;
    if (isTimeout || isNetwork || (status && status >= 500)) {
      refreshServiceStatus();
    }
    if (status === 401) {
      if (store.isAuthenticated) {
        store.logout();
      }
    } else if (error.code === 'ERR_NETWORK') {
      console.warn('Network error:', error.config?.url || error.message);
    } else if (status === 500) {
      console.error('Server Error:', error.response.data);
    }
    return Promise.reject(error);
  }
);

export const audio2Api = {
  // Auth
  createFirstUser: (userData: { name: string; email: string; password: string }) =>
    api.post('/auth/create-first-user', userData),
  login: (userData: { email: string; password: string }) =>
    api.post('/auth/login', userData),
  getCurrentUser: () => api.get('/auth/me'),
  accountLookup: (payload: { email: string; recovery_code: string }) =>
    api.post('/auth/account-lookup', payload),
  resetPassword: (payload: { email: string; recovery_code: string; new_password: string }) =>
    api.post('/auth/reset-password', payload),

  // Health
  healthCheck: () => api.get('/health'),
  healthDetailed: () => api.get('/health/detailed'),
  dbStatus: () => api.get('/db-status'),

  // Artists
  getArtistFullDiscography: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/full-discography`),
  getArtistInfo: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/info`),
  getLocalArtistBySpotifyId: (spotifyId: string) =>
    api.get(`/artists/spotify/${spotifyId}/local`),
  getArtistAlbums: (spotifyId: string, params?: { refresh?: boolean }) =>
    api.get(`/artists/${spotifyId}/albums`, { params }),

  searchOrchestrated: (params: { q: string; limit?: number; page?: number; lastfm_limit?: number; related_limit?: number }) =>
    api.get('/search/orchestrated', { params }),
  searchArtistProfile: (params: { q: string; similar_limit?: number; min_followers?: number }) =>
    api.get('/search/artist-profile', { params }),
  searchTracksQuick: (params: { q: string; limit?: number }) =>
    api.get('/search/tracks-quick', { params }),
  getSearchMetrics: () => api.get('/search/metrics'),

  getAllArtists: (params?: { offset?: number; limit?: number; order?: 'pop-desc' | 'pop-asc' | 'name-asc'; user_id?: number }) =>
    api.get('/artists/', { params }),
  getHiddenArtists: (params?: {
    user_id: number;
    offset?: number;
    limit?: number;
    order?: 'pop-desc' | 'pop-asc' | 'name-asc';
    search?: string;
    genre?: string;
  }) => api.get('/artists/management/hidden', { params }),
  hideArtist: (artistId: number, userId: number) =>
    api.post(`/artists/management/id/${artistId}/hide`, null, { params: { user_id: userId } }),
  unhideArtist: (artistId: number, userId: number) =>
    api.delete(`/artists/management/id/${artistId}/hide`, { params: { user_id: userId } }),

  // Albums
  getAllAlbums: () => api.get('/albums/'),
  getAlbumDetail: (spotifyId: string) =>
    api.get(`/albums/spotify/${spotifyId}`),
  saveAlbumToDb: (spotifyId: string) =>
    api.post(`/albums/save/${spotifyId}`),
  getAlbumTracks: (spotifyId: string) =>
    api.get(`/albums/${spotifyId}/tracks`),

  // Tracks
  getAllTracks: () => api.get('/tracks/'),
  resolveTracks: (spotifyTrackIds: string[]) =>
    api.post('/tracks/resolve', { spotify_track_ids: spotifyTrackIds }),
  saveTrackFromSpotify: (spotifyTrackId: string) =>
    api.post('/tracks/save-from-spotify', { spotify_track_id: spotifyTrackId }),
  getRecentlyAddedTracks: (params?: { limit?: number }) =>
    api.get('/tracks/recently-added', { params }),
  getMostPlayedTracks: (params?: { limit?: number }) =>
    api.get('/tracks/most-played', { params }),
  getRecentPlays: (params?: { limit?: number }) =>
    api.get('/tracks/recent-plays', { params }),
  getTrackRecommendations: (params: { seed_tracks?: string[]; seed_artists?: string[]; limit?: number }) =>
    api.get('/tracks/recommendations', {
      params: {
        seed_tracks: params.seed_tracks?.join(','),
        seed_artists: params.seed_artists?.join(','),
        limit: params.limit,
      },
    }),
  getMaintenanceStatus: (params?: { start?: boolean }) => api.get('/maintenance/status', { params }),
  startMaintenance: () => api.post('/maintenance/start'),
  stopMaintenance: () => api.post('/maintenance/stop'),
  toggleMaintenance: (enabled: boolean) => api.post(`/maintenance/toggle?enabled=${enabled}`),
  getDashboardStats: () => api.get('/maintenance/dashboard'),
  auditLibrary: (params?: { fresh_days?: number; json?: boolean }) =>
    api.post('/maintenance/audit', null, { params }),
  backfillAlbumTracks: (params?: { mode?: 'missing' | 'incomplete' | 'both'; limit?: number; concurrency?: number }) =>
    api.post('/maintenance/backfill-album-tracks', null, { params }),
  backfillYoutubeLinks: (params?: { limit?: number; retry_failed?: boolean }) =>
    api.post('/maintenance/backfill-youtube-links', null, { params }),
  backfillImages: (params?: { limit_artists?: number; limit_albums?: number }) =>
    api.post('/maintenance/backfill-images', null, { params }),
  backfillChart: (params?: { chart_source?: string; chart_name?: string; weeks?: number; force_reset?: boolean }) =>
    api.post('/maintenance/chart-backfill', null, { params }),
  refreshMissingArtists: (params?: { limit?: number; use_spotify?: boolean; use_lastfm?: boolean }) =>
    api.post('/artists/refresh-missing', null, { params }),
  getMaintenanceActionStatus: () => api.get('/maintenance/action-status'),
  getMaintenanceLogs: (params?: { since_id?: number; limit?: number; scope?: 'all' | 'maintenance' | 'errors' }) =>
    api.get('/maintenance/logs', { params }),
  clearMaintenanceLogs: () => api.post('/maintenance/logs/clear'),
  repairAlbumImages: (params?: { limit?: number; background?: boolean }) =>
    api.post('/maintenance/repair-album-images', null, { params }),
  getTrackChartStats: (spotifyTrackIds: string[]) =>
    api.get('/tracks/chart-stats', {
      params: { spotify_ids: spotifyTrackIds.join(',') },
    }),
  recordTrackPlay: (trackId: number) => api.post(`/tracks/play/${trackId}`),
  getTrackDownloadInfo: (trackId: number) => api.get(`/tracks/id/${trackId}/download-info`),

  // Charts
  getChartRaw: (params?: {
    chart_source?: string;
    chart_name?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
    include_summary?: boolean;
  }) => api.get('/charts/external/raw', { params }),

  // Playlists
  getAllPlaylists: () => api.get('/playlists/'),
  createPlaylist: (params: { name: string; description?: string; user_id?: number }) =>
    api.post('/playlists/', null, { params }),
  deletePlaylist: (playlistId: number) =>
    api.delete(`/playlists/id/${playlistId}`),
  addTrackToPlaylist: (playlistId: number, trackId: number) =>
    api.post(`/playlists/id/${playlistId}/tracks/${trackId}`),
  removeTrackFromPlaylist: (playlistId: number, trackId: number) =>
    api.delete(`/playlists/id/${playlistId}/tracks/${trackId}`),
  getPlaylistTracks: (playlistId: number) =>
    api.get(`/playlists/id/${playlistId}/tracks`),
  // Unified tracks endpoint - supports both traditional tracks and curated lists
  getTracksOverview: (params?: {
    verify_files?: boolean;
    offset?: number;
    limit?: number;
    include_summary?: boolean;
    after_id?: number;
    filter?: string;
    search?: string;
    list_type?: string;
    artist_id?: number;
    sort?: string;
  }) => api.get('/tracks/overview', { params }),
  // Legacy endpoint - will be deprecated
  getListsOverview: (params?: { limit_per_list?: number; artist_spotify_id?: string; artist_name?: string }) =>
    api.get('/lists/overview', { params, timeout: 60000 }),
  // Cached curated lists - fast response
  getCachedLists: (params?: { user_id?: number; list_type?: string; force_refresh?: boolean }) =>
    api.get('/lists/curated', { params }),
  refreshCachedLists: (params?: { list_type?: string; user_id?: number }) =>
    api.post('/lists/curated/refresh', { params }),

  // Favorites
  addFavorite: (targetType: 'artist' | 'album' | 'track', targetId: number, userId: number) =>
    api.post(`/favorites/${targetType}/${targetId}`, null, { params: { user_id: userId } }),
  removeFavorite: (targetType: 'artist' | 'album' | 'track', targetId: number, userId: number) =>
    api.delete(`/favorites/${targetType}/${targetId}`, { params: { user_id: userId } }),
  listFavorites: (params: { user_id: number; target_type?: 'artist' | 'album' | 'track' }) =>
    api.get('/favorites/', { params }),
  repairArtistImages: (artistId: number, params?: { background?: boolean; limit?: number; download_missing?: boolean }) =>
    api.post(`/images/repair/artist/${artistId}`, null, { params }),

  // User learning
  getUserRecommendations: (userId: number, limit?: number) =>
    api.get(`/user-learning/recommendations/${userId}`, { params: { limit } }),

  // YouTube
  searchYoutubeMusic: (params: { artist: string; track: string; album?: string; max_results?: number }) =>
    api.get('/youtube/search/music', { params }),
  downloadYoutubeAudio: (
    videoId: string,
    params?: { format?: string; quality?: string; to_device?: boolean }
  ) =>
    api.post(`/youtube/download/${videoId}`, null, { params, timeout: 180000 }),
  getYoutubeDownloadStatus: (videoId: string, params?: { format?: string }) =>
    api.get(`/youtube/download/${videoId}/status`, { params }),
  prefetchYoutubeAlbum: (spotifyId: string) =>
    api.post(`/youtube/album/${spotifyId}/prefetch`),
  getYoutubeTrackLink: (spotifyTrackId: string) =>
    api.get(`/youtube/track/${spotifyTrackId}/link`),
  refreshYoutubeTrackLink: (
    spotifyTrackId: string,
    payload: { artist?: string; track?: string; album?: string }
  ) => api.post(`/youtube/track/${spotifyTrackId}/refresh`, payload),
  getYoutubeTrackLinks: (spotifyTrackIds: string[]) =>
    api.post('/youtube/links', { spotify_track_ids: spotifyTrackIds }),
  getYoutubeUsage: () => api.get('/youtube/usage/'),
  getYoutubeFallbackStatus: () => api.get('/youtube/fallback/status'),
  toggleYoutubeFallback: (enabled: boolean) => api.post(`/youtube/fallback/toggle?enabled=${enabled}`),
  getYoutubeFallbackLogs: (params?: { limit?: number }) => api.get('/youtube/fallback/logs', { params }),
};
