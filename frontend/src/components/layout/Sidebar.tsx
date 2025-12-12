import { Link, useLocation } from 'react-router-dom';
import { useApiStore } from '@/store/useApiStore';
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
            Audio2 Frontend · v0.1.0
          </div>
        </div>
      </div>
    </>
  );
}
