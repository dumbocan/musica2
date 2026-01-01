import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import { Sidebar } from '@/components/layout/Sidebar';
import { NetworkDebugger } from '@/components/NetworkDebugger';
import { useApiStore } from '@/store/useApiStore';
import { LogOut, User, ChevronDown, Search } from 'lucide-react';
import { useRef, useState } from 'react';
import { AlbumDetailPage } from '@/pages/AlbumDetailPage';

// Pages
import { Dashboard } from '@/pages/Dashboard';
import { SearchPage } from '@/pages/SearchPage';
import { ArtistsPage } from '@/pages/ArtistsPage';
import { TracksPage } from '@/pages/TracksPage';
import { PlaylistsPage } from '@/pages/PlaylistsPage';
import { TagsPage } from '@/pages/TagsPage';
import { DownloadsPage } from '@/pages/DownloadsPage';
import { LoginPage } from '@/pages/LoginPage';
import { HealthPage } from '@/pages/HealthPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { ArtistDiscographyPage } from '@/pages/ArtistDiscographyPage';

function AppShell() {
  const { setSidebarOpen, isAuthenticated, searchQuery, setSearchQuery, setSearchTrigger } = useApiStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenuTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  const openMenu = () => {
    if (closeMenuTimeout.current) clearTimeout(closeMenuTimeout.current);
    setMenuOpen(true);
  };

  const scheduleClose = () => {
    if (closeMenuTimeout.current) clearTimeout(closeMenuTimeout.current);
    closeMenuTimeout.current = setTimeout(() => setMenuOpen(false), 200);
  };

  // Si no está autenticado, mostrar solo la página de login
  if (!isAuthenticated) {
    return (
      <div className="flex h-screen bg-background">
        <main className="flex-1 flex items-center justify-center p-6">
          <LoginPage />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar />

      {/* Main content */}
      <div className="app-main">
        {/* Top bar */}
        <div className="topbar" style={{ width: '100%' }}>
          <div
            className="flex items-center w-full"
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr auto',
              alignItems: 'center',
              columnGap: 24,
              width: '100%'
            }}
          >
            <div className="badge" style={{ whiteSpace: 'nowrap' }}>🎵 Audio2 · Sesión activa</div>

            <div className="flex-1 flex justify-center" style={{ padding: '0 24px' }}>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setSearchTrigger(Date.now());
                  navigate('/search');
                }}
                className="search-form"
                style={{ maxWidth: 560, minWidth: 260, width: '100%' }}
              >
                <input
                  id="q-top"
                  type="text"
                  name="q-top"
                  placeholder="Search artists or tracks..."
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

            <div className="flex items-center gap-3 text-sm" style={{ whiteSpace: 'nowrap' }}>
              <div
                className="relative"
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
                {menuOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '100%',
                      background: 'var(--panel)',
                      border: `1px solid var(--border)`,
                      borderRadius: 10,
                      minWidth: 180,
                      boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                      zIndex: 20
                    }}
                    onMouseEnter={openMenu}
                    onMouseLeave={scheduleClose}
                  >
                    <a href="/settings" className="nav-item" style={{ marginBottom: 0 }}>
                      ⚙️ Settings
                    </a>
                    <a href="/settings" className="nav-item" style={{ marginBottom: 0 }}>
                      👤 Account
                    </a>
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
            <Route path="/tags" element={<TagsPage />} />
            <Route path="/downloads" element={<DownloadsPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>

      {/* Network Debugger - API Monitor */}
      <NetworkDebugger />
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}
