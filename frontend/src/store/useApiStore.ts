import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  Artist,
  Album,
  Track,
  Playlist,
  HealthCheckResponse,
  DownloadStatus,
  SpotifyTrackLite
} from '../types/api';

// API Store interface
interface ApiStore {
  // Health state
  health: HealthCheckResponse | null;
  isHealthLoading: boolean;
  setHealth: (health: HealthCheckResponse | null) => void;
  setHealthLoading: (loading: boolean) => void;
  serviceStatus: {
    spotify?: { status?: string | null; last_error?: string | null };
    lastfm?: { status?: string | null; last_error?: string | null };
  } | null;
  setServiceStatus: (
    status: {
      spotify?: { status?: string | null; last_error?: string | null };
      lastfm?: { status?: string | null; last_error?: string | null };
    } | null
  ) => void;

  // Artists state
  artists: Artist[];
  selectedArtist: Artist | null;
  isArtistsLoading: boolean;
  setArtists: (artists: Artist[]) => void;
  setSelectedArtist: (artist: Artist | null) => void;
  setArtistsLoading: (loading: boolean) => void;
  addArtist: (artist: Artist) => void;
  removeArtist: (artistId: number) => void;

  // Albums state
  albums: Album[];
  selectedAlbum: Album | null;
  isAlbumsLoading: boolean;
  setAlbums: (albums: Album[]) => void;
  setSelectedAlbum: (album: Album | null) => void;
  setAlbumsLoading: (loading: boolean) => void;

  // Tracks state
  tracks: Track[];
  selectedTrack: Track | null;
  isTracksLoading: boolean;
  setTracks: (tracks: Track[]) => void;
  setSelectedTrack: (track: Track | null) => void;
  setTracksLoading: (loading: boolean) => void;

  // Playlists state
  playlists: Playlist[];
  selectedPlaylist: Playlist | null;
  isPlaylistsLoading: boolean;
  setPlaylists: (playlists: Playlist[]) => void;
  setSelectedPlaylist: (playlist: Playlist | null) => void;
  setPlaylistsLoading: (loading: boolean) => void;
  addPlaylist: (playlist: Playlist) => void;
  removePlaylist: (playlistId: number) => void;

  // Download state
  downloads: DownloadStatus[];
  setDownloads: (downloads: DownloadStatus[]) => void;
  addDownload: (download: DownloadStatus) => void;
  updateDownload: (download: DownloadStatus) => void;

  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  // Search state
  searchQuery: string;
  searchResults: Artist[];
  relatedSearchResults: Artist[];
  searchMainInfo: Artist | null;
  trackSearchResults: SpotifyTrackLite[];
  searchTrigger: number;
  isSearching: boolean;
  setSearchQuery: (query: string) => void;
  setSearchResults: (results: Artist[]) => void;
  setRelatedSearchResults: (results: Artist[]) => void;
  setSearchMainInfo: (info: Artist | null) => void;
  setTrackSearchResults: (results: SpotifyTrackLite[]) => void;
  setSearchTrigger: (ts: number) => void;
  setSearching: (searching: boolean) => void;

  // Auth state
  token: string | null;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
  setAuthenticated: (isAuthenticated: boolean) => void;
  logout: () => void;
  userId: number | null;
  setUserId: (id: number | null) => void;
  userEmail: string | null;
  setUserEmail: (email: string | null) => void;
}

// Create store
export const useApiStore = create<ApiStore>()(
  devtools(
    (set) => ({
      // Health
      health: null,
      isHealthLoading: false,
      setHealth: (health) => set({ health }),
      setHealthLoading: (loading) => set({ isHealthLoading: loading }),
      serviceStatus: null,
      setServiceStatus: (serviceStatus) => set({ serviceStatus }),

      // Artists
      artists: [],
      selectedArtist: null,
      isArtistsLoading: false,
      setArtists: (artists) => set({ artists }),
      setSelectedArtist: (selectedArtist) => set({ selectedArtist }),
      setArtistsLoading: (loading) => set({ isArtistsLoading: loading }),
      addArtist: (artist) => set((state) => ({
        artists: [...state.artists, artist]
      })),
      removeArtist: (artistId) => set((state) => ({
        artists: state.artists.filter(a => a.id !== artistId)
      })),

      // Albums
      albums: [],
      selectedAlbum: null,
      isAlbumsLoading: false,
      setAlbums: (albums) => set({ albums }),
      setSelectedAlbum: (selectedAlbum) => set({ selectedAlbum }),
      setAlbumsLoading: (loading) => set({ isAlbumsLoading: loading }),

      // Tracks
      tracks: [],
      selectedTrack: null,
      isTracksLoading: false,
      setTracks: (tracks) => set({ tracks }),
      setSelectedTrack: (selectedTrack) => set({ selectedTrack }),
      setTracksLoading: (loading) => set({ isTracksLoading: loading }),

      // Playlists
      playlists: [],
      selectedPlaylist: null,
      isPlaylistsLoading: false,
      setPlaylists: (playlists) => set({ playlists }),
      setSelectedPlaylist: (selectedPlaylist) => set({ selectedPlaylist }),
      setPlaylistsLoading: (loading) => set({ isPlaylistsLoading: loading }),
      addPlaylist: (playlist) => set((state) => ({
        playlists: [...state.playlists, playlist]
      })),
      removePlaylist: (playlistId) => set((state) => ({
        playlists: state.playlists.filter(p => p.id !== playlistId)
      })),

      // Downloads
      downloads: [],
      setDownloads: (downloads) => set({ downloads }),
      addDownload: (download) => set((state) => ({
        downloads: [...state.downloads, download]
      })),
      updateDownload: (download) => set((state) => ({
        downloads: state.downloads.map(d =>
          d.id === download.id ? download : d
        )
      })),

      // UI
      sidebarOpen: false,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      // Search
      searchQuery: '',
      searchResults: [],
      relatedSearchResults: [],
      searchMainInfo: null,
      trackSearchResults: [],
      searchTrigger: 0,
      isSearching: false,
      setSearchQuery: (query) => set({ searchQuery: query }),
      setSearchResults: (results) => set({ searchResults: results }),
      setRelatedSearchResults: (results) => set({ relatedSearchResults: results }),
      setSearchMainInfo: (info) => set({ searchMainInfo: info }),
      setTrackSearchResults: (results) => set({ trackSearchResults: results }),
      setSearchTrigger: (ts) => set({ searchTrigger: ts }),
      setSearching: (searching) => set({ isSearching: searching }),

      // Auth
      token: localStorage.getItem('token'),
      isAuthenticated: !!localStorage.getItem('token'),
      setToken: (token) => {
        if (token) {
          localStorage.setItem('token', token);
          document.cookie = `token=${token}; path=/; max-age=86400; samesite=strict`;
        } else {
          localStorage.removeItem('token');
          document.cookie = 'token=; path=/; max-age=0; samesite=strict';
        }
        set({ token, isAuthenticated: !!token });
      },
      setAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
      logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('userEmail');
        localStorage.removeItem('userId');
        document.cookie = 'token=; path=/; max-age=0; samesite=strict';
        set({ token: null, isAuthenticated: false, userId: null, userEmail: null });
      },
      userId: localStorage.getItem('userId') ? Number(localStorage.getItem('userId')) : null,
      setUserId: (id) => {
        if (id === null || id === undefined) {
          localStorage.removeItem('userId');
        } else {
          localStorage.setItem('userId', String(id));
        }
        set({ userId: id });
      },
      userEmail: localStorage.getItem('userEmail'),
      setUserEmail: (email) => {
        if (email) {
          localStorage.setItem('userEmail', email);
        } else {
          localStorage.removeItem('userEmail');
        }
        set({ userEmail: email });
      },
    }),
    { name: 'audio2-api-store' }
  )
);
