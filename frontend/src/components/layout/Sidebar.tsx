import { Link, useLocation } from 'react-router-dom';
import { useApiStore } from '@/store/useApiStore';
import { usePlayerStore } from '@/store/usePlayerStore';
import { YouTubeOverlayPlayer } from '@/components/YouTubeOverlayPlayer';
import {
  Home,
  Search,
  Music,
  ListMusic,
  Download,
  Settings,
  X,
  Activity,
  Tag
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Search', href: '/search', icon: Search },
  { name: 'Artists', href: '/artists', icon: Music },
  { name: 'Tracks', href: '/tracks', icon: Music },
  { name: 'Playlists', href: '/playlists', icon: ListMusic },
  { name: 'Tags', href: '/tags', icon: Tag },
  { name: 'Downloads', href: '/downloads', icon: Download },
  { name: 'Health', href: '/health', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarOpen, setSidebarOpen } = useApiStore();
  const videoEmbedId = usePlayerStore((s) => s.videoEmbedId);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const nowPlaying = usePlayerStore((s) => s.nowPlaying);
  const videoDownloadVideoId = usePlayerStore((s) => s.videoDownloadVideoId);
  const videoDownloadStatus = usePlayerStore((s) => s.videoDownloadStatus);
  const audioDownloadVideoId = usePlayerStore((s) => s.audioDownloadVideoId);
  const audioDownloadStatus = usePlayerStore((s) => s.audioDownloadStatus);

  const audioDownloadLabel = (() => {
    if (!nowPlaying?.videoId) return 'pendiente';
    if (audioDownloadVideoId !== nowPlaying.videoId) return 'pendiente';
    if (audioDownloadStatus === 'checking') return 'comprobando';
    if (audioDownloadStatus === 'downloading') return 'descargando';
    if (audioDownloadStatus === 'downloaded') return 'descargado';
    if (audioDownloadStatus === 'error') return 'error';
    return 'pendiente';
  })();
  const audioDownloadActive =
    !!nowPlaying?.videoId &&
    audioDownloadVideoId === nowPlaying.videoId &&
    audioDownloadStatus === 'downloading';

  return (
    <>
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className="sidebar">
        <div className="flex h-full flex-col">
          {/* Header */}
          <div className="sidebar-header">
            <span>Audio2</span>
            {/* Close button solo en móvil cuando sidebar está abierto */}
            {sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-1 rounded-md hover:bg-accent md:hidden"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Navigation */}
          <nav className="sidebar-nav">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                >
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="sidebar-footer">
            {videoEmbedId && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
                  Video en reproduccion
                </div>
                <div
                  style={{
                    position: 'relative',
                    width: '115%',
                    paddingTop: '62%',
                    marginLeft: '-7.5%',
                    borderRadius: 12,
                    overflow: 'hidden',
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(8, 12, 20, 0.7)',
                  }}
                >
                  <YouTubeOverlayPlayer videoId={videoEmbedId} />
                </div>
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background:
                        videoDownloadStatus === 'downloading' && videoDownloadVideoId === videoEmbedId
                          ? '#22c55e'
                          : 'transparent',
                      border: '2px solid #22c55e',
                      display: 'inline-block',
                    }}
                  />
                  <span>
                    Audio:{' '}
                    {videoDownloadVideoId !== videoEmbedId
                      ? 'pendiente'
                      : videoDownloadStatus === 'checking'
                        ? 'comprobando'
                        : videoDownloadStatus === 'downloading'
                          ? 'descargando'
                          : videoDownloadStatus === 'downloaded'
                            ? 'descargado'
                            : videoDownloadStatus === 'error'
                              ? 'error'
                              : 'pendiente'}
                  </span>
                </div>
              </div>
            )}
            {!videoEmbedId && playbackMode === 'audio' && nowPlaying && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
                  Audio en reproduccion
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {nowPlaying.title} · {nowPlaying.artist || ''}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: audioDownloadActive ? '#22c55e' : 'transparent',
                      border: '2px solid #22c55e',
                      display: 'inline-block',
                    }}
                  />
                  <span>Audio: {audioDownloadLabel}</span>
                </div>
              </div>
            )}
            Audio2 Frontend · v0.1.0
          </div>
        </div>
      </div>
    </>
  );
}
