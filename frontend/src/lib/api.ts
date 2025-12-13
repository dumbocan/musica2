// API Client for Audio2 Frontend
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Axios instance with defaults
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000, // algunas llamadas (discografía completa) tardan más
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 500) {
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

  // Health
  healthCheck: () => api.get('/health'),
  healthDetailed: () => api.get('/health/detailed'),

  // Artists
  searchArtists: (query: string) =>
    api.get('/artists/search', { params: { q: query } }),
  searchArtistsAutoDownload: (params: { q: string; user_id?: number; expand_library?: boolean }) =>
    api.get('/artists/search-auto-download', { params }),
  getRelatedArtists: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/related`),
  getArtistFullDiscography: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/full-discography`),
  getArtistInfo: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/info`),
  getArtistAlbums: (spotifyId: string) =>
    api.get(`/artists/${spotifyId}/albums`),

  // Combined Spotify search (artists + tracks)
  searchSpotify: (query: string) => api.get('/search/spotify', { params: { q: query } }),

  getAllArtists: () => api.get('/artists/'),

  // Albums
  getAllAlbums: () => api.get('/albums/'),
  getAlbumDetail: (spotifyId: string) =>
    api.get(`/albums/spotify/${spotifyId}`),
  getAlbumTracks: (spotifyId: string) =>
    api.get(`/albums/${spotifyId}/tracks`),

  // Tracks
  getAllTracks: () => api.get('/tracks/'),

  // Playlists
  getAllPlaylists: () => api.get('/playlists/'),
};
