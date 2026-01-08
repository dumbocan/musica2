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

  // Health
  healthCheck: () => api.get('/health'),
  healthDetailed: () => api.get('/health/detailed'),

  // Artists
  getArtistFullDiscography: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/full-discography`),
  getArtistInfo: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/info`),
  getLocalArtistBySpotifyId: (spotifyId: string) =>
    api.get(`/artists/spotify/${spotifyId}/local`),
  getArtistAlbums: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/albums`),

  searchOrchestrated: (params: { q: string; limit?: number; page?: number; lastfm_limit?: number; related_limit?: number }) =>
    api.get('/search/orchestrated', { params }),
  searchArtistProfile: (params: { q: string; similar_limit?: number; min_followers?: number }) =>
    api.get('/search/artist-profile', { params }),
  searchTracksQuick: (params: { q: string; limit?: number }) =>
    api.get('/search/tracks-quick', { params }),

  getAllArtists: (params?: { offset?: number; limit?: number; order?: 'pop-desc' | 'pop-asc' | 'name-asc' }) =>
    api.get('/artists/', { params }),
  listHiddenArtists: (params: { user_id: number }) =>
    api.get('/artists/hidden', { params }),
  hideArtist: (artistId: number, userId: number) =>
    api.post(`/artists/id/${artistId}/hide`, null, { params: { user_id: userId } }),
  unhideArtist: (artistId: number, userId: number) =>
    api.delete(`/artists/id/${artistId}/hide`, { params: { user_id: userId } }),

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
  getTracksOverview: (params?: {
    verify_files?: boolean;
    offset?: number;
    limit?: number;
    include_summary?: boolean;
    after_id?: number | null;
    filter?: 'all' | 'favorites' | 'withLink' | 'noLink' | 'hasFile' | 'missingFile';
    search?: string;
  }) =>
    api.get('/tracks/overview', { params, timeout: 60000 }),
  resolveTracks: (spotifyTrackIds: string[]) =>
    api.post('/tracks/resolve', { spotify_track_ids: spotifyTrackIds }),

  // Playlists
  getAllPlaylists: () => api.get('/playlists/'),

  // Favorites
  addFavorite: (targetType: 'artist' | 'album' | 'track', targetId: number, userId: number) =>
    api.post(`/favorites/${targetType}/${targetId}`, null, { params: { user_id: userId } }),
  removeFavorite: (targetType: 'artist' | 'album' | 'track', targetId: number, userId: number) =>
    api.delete(`/favorites/${targetType}/${targetId}`, { params: { user_id: userId } }),
  listFavorites: (params: { user_id: number; target_type?: 'artist' | 'album' | 'track' }) =>
    api.get('/favorites', { params }),

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
  getYoutubeUsage: () => api.get('/youtube/usage'),
};
