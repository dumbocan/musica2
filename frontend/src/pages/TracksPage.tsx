import { useEffect, useMemo, useState } from 'react';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import type { TrackOverview } from '@/types/api';

type FilterTab = 'all' | 'withLink' | 'noLink' | 'hasFile' | 'missingFile';

const filterLabels: Record<FilterTab, string> = {
  all: 'Todos',
  withLink: 'Con link YouTube',
  noLink: 'Sin link aún',
  hasFile: 'Con MP3 local',
  missingFile: 'Sin MP3 local'
};

export function TracksPage() {
  const [tracks, setTracks] = useState<TrackOverview[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterTab>('all');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await audio2Api.getTracksOverview();
        setTracks(response.data.items || []);
      } catch (err: any) {
        setError(err?.response?.data?.detail || err?.message || 'No se pudo cargar el listado de pistas');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const stats = useMemo(() => {
    const total = tracks.length;
    const withLink = tracks.filter((t) => !!t.youtube_video_id).length;
    const withFile = tracks.filter((t) => t.local_file_exists).length;
    const missingLink = total - withLink;
    const missingFile = total - withFile;
    return { total, withLink, withFile, missingLink, missingFile };
  }, [tracks]);

  const filteredTracks = useMemo(() => {
    return tracks.filter((track) => {
      const text = `${track.track_name || ''} ${track.artist_name || ''} ${track.album_name || ''}`.toLowerCase();
      const passesSearch = text.includes(search.toLowerCase());

      const hasLink = !!track.youtube_video_id;
      const hasFile = track.local_file_exists;

      const passesFilter =
        filter === 'all' ||
        (filter === 'withLink' && hasLink) ||
        (filter === 'noLink' && !hasLink) ||
        (filter === 'hasFile' && hasFile) ||
        (filter === 'missingFile' && !hasFile);

      return passesSearch && passesFilter;
    });
  }, [tracks, search, filter]);

  const formatDuration = (ms?: number | null) => {
    if (!ms) return '–';
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return <div className="card">Cargando pistas...</div>;
  }

  if (error) {
    return <div className="card">Error: {error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>Biblioteca · Tracks</div>
          <div style={{ color: 'var(--muted)', fontSize: 13 }}>
            Resumen de todas las canciones guardadas con su estado de streaming/descarga.
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <SummaryCard label="Total pistas" value={stats.total} />
          <SummaryCard label="Con link YouTube" value={stats.withLink} accent />
          <SummaryCard label="Con MP3 local" value={stats.withFile} accent />
          <SummaryCard label="Pendiente link" value={stats.missingLink} muted />
          <SummaryCard label="Pendiente MP3" value={stats.missingFile} muted />
        </div>
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <input
            type="text"
            placeholder="Buscar por canción, artista o álbum"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              flex: '1 1 260px',
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--panel)',
              color: 'inherit'
            }}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {(Object.keys(filterLabels) as FilterTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                style={{
                  padding: '8px 12px',
                  borderRadius: 999,
                  border: '1px solid',
                  borderColor: filter === tab ? 'var(--accent)' : 'var(--border)',
                  background: filter === tab ? 'var(--accent)' : 'transparent',
                  color: filter === tab ? '#0b0b0b' : 'inherit',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 600
                }}
              >
                {filterLabels[tab]}
              </button>
            ))}
          </div>
        </div>

        <div className="scroll-area" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--muted)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.6 }}>
                <th style={{ padding: '8px 6px' }}>Track</th>
                <th style={{ padding: '8px 6px' }}>Artista</th>
                <th style={{ padding: '8px 6px' }}>Álbum</th>
                <th style={{ padding: '8px 6px' }}>Duración</th>
                <th style={{ padding: '8px 6px' }}>Link YouTube</th>
                <th style={{ padding: '8px 6px' }}>MP3 local</th>
                <th style={{ padding: '8px 6px' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filteredTracks.map((track) => (
                <tr key={`${track.track_id}-${track.spotify_track_id || track.track_name}`}>
                  <td style={{ padding: '10px 6px', fontWeight: 600 }}>{track.track_name}</td>
                  <td style={{ padding: '10px 6px' }}>{track.artist_name || '—'}</td>
                  <td style={{ padding: '10px 6px' }}>{track.album_name || '—'}</td>
                  <td style={{ padding: '10px 6px' }}>{formatDuration(track.duration_ms)}</td>
                  <td style={{ padding: '10px 6px' }}>
                    {track.youtube_video_id ? (
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Disponible ({track.youtube_status || 'link'})</span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>Pendiente</span>
                    )}
                  </td>
                  <td style={{ padding: '10px 6px' }}>
                    {track.local_file_exists ? (
                      <span style={{ color: '#34d399', fontWeight: 600 }}>Guardado</span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>No</span>
                    )}
                  </td>
                  <td style={{ padding: '10px 6px' }}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {track.youtube_url && (
                        <a
                          href={track.youtube_url}
                          target="_blank"
                          rel="noreferrer"
                          className="badge"
                          style={{ textDecoration: 'none' }}
                        >
                          ▶ Abrir YouTube
                        </a>
                      )}
                      {track.local_file_exists && track.youtube_video_id && (
                        <a
                          href={`${API_BASE_URL}/youtube/download/${track.youtube_video_id}/file?format=mp3`}
                          target="_blank"
                          rel="noreferrer"
                          className="badge"
                          style={{ textDecoration: 'none' }}
                        >
                          ⬇ Descargar MP3
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filteredTracks.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: 20, textAlign: 'center', color: 'var(--muted)' }}>
                    Sin pistas que coincidan con el filtro actual.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, accent, muted }: { label: string; value: number; accent?: boolean; muted?: boolean }) {
  const background = accent ? 'rgba(5, 247, 165, 0.12)' : muted ? 'rgba(255, 255, 255, 0.04)' : 'var(--panel)';
  const borderColor = accent ? 'rgba(5, 247, 165, 0.4)' : 'var(--border)';

  return (
    <div
      style={{
        flex: '1 1 140px',
        minWidth: 140,
        borderRadius: 14,
        padding: '14px 16px',
        background,
        border: `1px solid ${borderColor}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }}
    >
      <div style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
