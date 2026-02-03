import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import { PlayerFooter } from '@/components/PlayerFooter';
import { useApiStore } from '@/store/useApiStore';
import { usePlayerStore } from '@/store/usePlayerStore';
import { Activity, LogOut, User, ChevronDown, Search, Menu, Home, Music, ListMusic } from 'lucide-react';
import { useMemo, useRef, useState, type CSSProperties } from 'react';
import { AlbumDetailPage } from '@/pages/AlbumDetailPage';
import { YouTubeOverlayPlayer } from '@/components/YouTubeOverlayPlayer';

// Pages
import { Dashboard } from '@/pages/Dashboard';
import { SearchPage } from '@/pages/SearchPage';
import { ArtistsPage } from '@/pages/ArtistsPage';
import { TracksPage } from '@/pages/TracksPage';
import { PlaylistsPage } from '@/pages/PlaylistsPage';
import { DownloadsPage } from '@/pages/DownloadsPage';
import { LoginPage } from '@/pages/LoginPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { StatusPage } from '@/pages/StatusPage';
import { ArtistDiscographyPage } from '@/pages/ArtistDiscographyPage';
import { HistoricalDbPage } from '@/pages/HistoricalDbPage';
import { AuthWrapper } from '@/components/AuthWrapper';

function ServiceDot({ label, color, status, lastError }: { label: string; color: string; status?: string | null; lastError?: string | null }) {
  const isOnline = status === 'online';
  const state = status ?? 'unknown';
  const title = lastError ? `${label}: ${state} · ${lastError}` : `${label}: ${state}`;
  const style = { '--dot-color': color } as CSSProperties;

  return (
    <div className="service-dot" style={style} title={title}>
      <span className={`service-dot__circle${isOnline ? ' service-dot__circle--online' : ''}`} />
      <span className="service-dot__text">{label}</span>
    </div>
  );
}

function AppShell() {
  const { setSidebarOpen, searchQuery, setSearchQuery, setSearchTrigger } = useApiStore();
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const nowPlaying = usePlayerStore((s) => s.nowPlaying);
  const videoEmbedId = usePlayerStore((s) => s.videoEmbedId);
  const videoDownloadVideoId = usePlayerStore((s) => s.videoDownloadVideoId);
  const videoDownloadStatus = usePlayerStore((s) => s.videoDownloadStatus);
  const audioDownloadVideoId = usePlayerStore((s) => s.audioDownloadVideoId);
  const audioDownloadStatus = usePlayerStore((s) => s.audioDownloadStatus);
  const [menuOpen, setMenuOpen] = useState(false);
  const serviceStatus = useApiStore((s) => s.serviceStatus);
  const closeMenuTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const openMenu = () => {
    if (closeMenuTimeout.current) clearTimeout(closeMenuTimeout.current);
    setMenuOpen(true);
  };

  const scheduleClose = () => {
    if (closeMenuTimeout.current) clearTimeout(closeMenuTimeout.current);
    closeMenuTimeout.current = setTimeout(() => setMenuOpen(false), 200);
  };

  const audioDownloadLabel = useMemo(() => {
    if (!nowPlaying?.videoId) return 'pendiente';
    if (audioDownloadVideoId !== nowPlaying.videoId) return 'pendiente';
    if (audioDownloadStatus === 'checking') return 'comprobando';
    if (audioDownloadStatus === 'downloading') return 'descargando';
    if (audioDownloadStatus === 'downloaded') return 'descargado';
    if (audioDownloadStatus === 'error') return 'error';
    return 'pendiente';
  }, [audioDownloadStatus, audioDownloadVideoId, nowPlaying?.videoId]);
  const audioDownloadActive =
    !!nowPlaying?.videoId &&
    audioDownloadVideoId === nowPlaying.videoId &&
    audioDownloadStatus === 'downloading';
  const videoDownloadLabel = useMemo(() => {
    if (!videoEmbedId) return 'pendiente';
    if (videoDownloadVideoId !== videoEmbedId) return 'pendiente';
    if (videoDownloadStatus === 'checking') return 'comprobando';
    if (videoDownloadVideoId === videoEmbedId && videoDownloadStatus === 'downloading') return 'descargando';
    if (videoDownloadStatus === 'downloaded') return 'descargado';
    if (videoDownloadStatus === 'error') return 'error';
    return 'pendiente';
  }, [videoDownloadStatus, videoDownloadVideoId, videoEmbedId]);
  const videoDownloadActive =
    !!videoEmbedId &&
    videoDownloadVideoId === videoEmbedId &&
    videoDownloadStatus === 'downloading';

  const mobileNavItems = [
    { name: 'Dashboard', href: '/', icon: Home },
    { name: 'Artistas', href: '/artists', icon: Music },
    { name: 'Tracks', href: '/tracks', icon: ListMusic },
    { name: 'Status', href: '/status', icon: Activity },
  ];

  return (
    <div className="app-shell">
      <Sidebar />

      {/* Main content */}
      <div className="app-main">
        {/* Top bar */}
        <div className="topbar" style={{ width: '100%' }}>
          <div className="topbar__layout">
            <div className="topbar__left">
              <button
                className="topbar__menu-btn"
                type="button"
                aria-label="Abrir menu"
                onClick={() => setMenuOpen((v) => !v)}
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="topbar__services">
                <ServiceDot
                  label="Spotify"
                  color="#1DB954"
                  status={serviceStatus?.spotify?.status}
                  lastError={serviceStatus?.spotify?.last_error}
                />
                <ServiceDot
                  label="Last.fm"
                  color="#f59e0b"
                  status={serviceStatus?.lastfm?.status}
                  lastError={serviceStatus?.lastfm?.last_error}
                />
              </div>
            </div>

            <div className="topbar__center">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setSearchTrigger(Date.now());
                  navigate('/search');
                }}
                className="search-form topbar__search"
              >
                <input
                  id="q-top"
                  type="text"
                  name="q-top"
                  placeholder="Buscar artista, álbum, canción o género..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoComplete="off"
                  className="search-input"
                />
                <button
                  type="submit"
                  className="search-button"
                  aria-label="Buscar"
                >
                  <Search className="h-6 w-6" />
                </button>
              </form>
            </div>

            <div className="topbar__right">
              <div
                className="topbar__user"
                onMouseEnter={openMenu}
                onMouseLeave={scheduleClose}
              >
                <button
                  className="btn-ghost"
                  style={{ display: 'flex', alignItems: 'center', gap: 8, borderRadius: 999 }}
                  onMouseEnter={openMenu}
                  onClick={() => setMenuOpen((v) => !v)}
                >
                  <User className="h-4 w-4" />
                  <span>{useApiStore.getState().userEmail || 'Cuenta'}</span>
                  <ChevronDown className="h-4 w-4" />
                </button>
              </div>
              {menuOpen && (
                <div
                  className="topbar__menu"
                  onMouseEnter={openMenu}
                  onMouseLeave={scheduleClose}
                >
                  <Link to="/settings" className="nav-item" style={{ marginBottom: 0 }}>
                    ⚙️ Settings
                  </Link>
                  <Link to="/settings" className="nav-item" style={{ marginBottom: 0 }}>
                    👤 Account
                  </Link>
                  <button
                    className="nav-item"
                    style={{ width: '100%', textAlign: 'left', background: 'transparent', border: 'none', cursor: 'pointer' }}
                    onClick={() => {
                      useApiStore.getState().logout();
                      setSidebarOpen(false);
                    }}
                  >
                    <LogOut className="h-4 w-4" />
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="mobile-now-playing">
          {playbackMode === 'video' && videoEmbedId ? (
            <div>
              <div className="mobile-now-playing__label">Video en reproduccion</div>
              <div className="mobile-now-playing__video">
                <YouTubeOverlayPlayer videoId={videoEmbedId} />
              </div>
              <div className="mobile-now-playing__status">
                <span
                  className={`status-dot ${videoDownloadActive ? 'status-dot--active' : ''}`}
                />
                <span>Audio: {videoDownloadLabel}</span>
              </div>
            </div>
          ) : nowPlaying ? (
            <div>
              <div className="mobile-now-playing__label">Audio en reproduccion</div>
              <div className="mobile-now-playing__title">
                {nowPlaying.title} · {nowPlaying.artist || ''}
              </div>
              <div className="mobile-now-playing__status">
                <span
                  className={`status-dot ${audioDownloadActive ? 'status-dot--active' : ''}`}
                />
                <span>Audio: {audioDownloadLabel}</span>
              </div>
            </div>
          ) : null}
        </div>

        {/* Main content area */}
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/artists/discography/:spotifyId" element={<ArtistDiscographyPage />} />
            <Route path="/artists/:spotifyId" element={<ArtistDiscographyPage />} />
            <Route path="/albums/:spotifyId" element={<AlbumDetailPage />} />
            <Route path="/artists" element={<ArtistsPage />} />
            <Route path="/tracks" element={<TracksPage />} />
            <Route path="/playlists" element={<PlaylistsPage />} />
            <Route path="/downloads" element={<DownloadsPage />} />
            <Route path="/bd-historico" element={<HistoricalDbPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/status" element={<StatusPage />} />
          </Routes>
        </main>

        <nav className="mobile-bottom-nav">
          {mobileNavItems.map((item) => {
            const isActive = location.pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`mobile-bottom-nav__item ${isActive ? 'is-active' : ''}`}
              >
                <Icon className="mobile-bottom-nav__icon" />
                <span className="mobile-bottom-nav__label">{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <PlayerFooter />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AuthWrapper>
        <AppShell />
      </AuthWrapper>
    </Router>
  );
}
