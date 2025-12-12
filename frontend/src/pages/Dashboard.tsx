import { useEffect } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';

export function Dashboard() {
  const { health, setHealth, setHealthLoading } = useApiStore();

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setHealthLoading(true);
        const response = await audio2Api.healthCheck();
        setHealth(response.data);
      } catch (error) {
        console.error('Health check failed:', error);
      } finally {
        setHealthLoading(false);
      }
    };

    checkHealth();
  }, [setHealth, setHealthLoading]);

  return (
    <div className="space-y-4">
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#1db954' }} />
          <div style={{ fontWeight: 700, fontSize: '18px' }}>Tu música, sin límites</div>
        </div>
        <p style={{ color: 'var(--muted)', marginBottom: 12 }}>
          API y frontend listos. Explora artistas, playlists y descargas desde una interfaz estilo Spotify.
        </p>
        <div style={{ display: 'flex', gap: 12 }}>
          <a className="btn-accent" href="/search">Explorar artistas</a>
          <a className="btn-ghost" href="/downloads">Ver descargas</a>
        </div>
      </div>

      <div className="card" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Estado del backend</div>
          {health ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="badge" style={{ background: 'rgba(29,185,84,0.15)', borderColor: '#1db954', color: '#1db954' }}>
                {String(health.status || '').toUpperCase()}
              </span>
              <span style={{ color: 'var(--muted)', fontSize: 13 }}>http://localhost:8000</span>
            </div>
          ) : (
            <span style={{ color: 'var(--muted)' }}>Comprobando salud de la API…</span>
          )}
        </div>

        <div>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Accesos rápidos</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a className="badge" href="/artists">🎤 Artistas</a>
            <a className="badge" href="/tracks">🎵 Tracks</a>
            <a className="badge" href="/playlists">🎧 Playlists</a>
            <a className="badge" href="/tags">🏷️ Tags</a>
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontWeight: 700 }}>Colecciones destacadas</div>
          <a href="/playlists" className="btn-ghost" style={{ borderRadius: 8 }}>Ver todas</a>
        </div>
        <div className="grid-cards">
          {['Chill Vibes', 'Discover Weekly', 'Top Rated', 'Most Played', 'Recently Added', 'Favorites'].map((name) => (
            <div key={name} className="card" style={{ padding: 12, borderColor: 'rgba(255,255,255,0.05)', background: 'var(--panel-2)' }}>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{name}</div>
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>Lista dinámica basada en tu librería.</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
