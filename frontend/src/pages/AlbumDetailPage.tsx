import { useEffect, useRef, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';

type Track = { id: string; name: string; duration_ms?: number; external_urls?: { spotify?: string }; popularity?: number; explicit?: boolean };
type AlbumImage = { url: string };
type ArtistMini = { name: string };
type Album = {
  id: string;
  name: string;
  release_date?: string;
  images?: AlbumImage[];
  artists?: ArtistMini[];
  tracks?: { items: Track[] };
  lastfm?: {
    wiki?: { summary?: string; content?: string };
    listeners?: string | number;
    playcount?: string | number;
  };
};

export function AlbumDetailPage() {
  const { spotifyId } = useParams<{ spotifyId: string }>();
  const navigate = useNavigate();
  const [album, setAlbum] = useState<Album | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!spotifyId) return;
    let isMounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await audio2Api.getAlbumDetail(spotifyId);
        const data = res.data;
        if (!isMounted) return;
        setAlbum(data);
        // Spotify returns tracks as items inside "tracks"
        if (data?.tracks?.items) {
          setTracks(data.tracks.items);
        } else if (data?.tracks) {
          setTracks(data.tracks);
        } else {
          // Fallback: fetch tracks endpoint
          const tracksRes = await audio2Api.getAlbumTracks(spotifyId);
          if (!isMounted) return;
          setTracks(tracksRes.data || []);
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err?.response?.data?.detail || err?.message || 'Error cargando álbum');
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [spotifyId]);

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const togglePlay = (track: Track) => {
    if (!track.external_urls?.spotify && !track.id) return;
    // Prefer preview_url if available on track (not typed, but may exist)
    // @ts-ignore
    const preview = track.preview_url as string | undefined;
    if (!preview) {
      // No preview available
      return;
    }

    // If the same track is playing, pause
    if (playingId === track.id && audioRef.current) {
      audioRef.current.pause();
      setPlayingId(null);
      return;
    }

    // Stop previous
    if (audioRef.current) {
      audioRef.current.pause();
    }

    const audio = new Audio(preview);
    audioRef.current = audio;
    audio.play().catch(() => {});
    setPlayingId(track.id);

    audio.onended = () => {
      setPlayingId(null);
    };
  };

  const wiki = album?.lastfm?.wiki || {};
  const wikiHtml = wiki.content || wiki.summary || '';
  const wikiParagraphs = useMemo(() => {
    if (!wikiHtml) return [];
    const text = wikiHtml
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n')
      .replace(/<[^>]+>/g, '');
    return text
      .split(/\n\s*\n+/)
      .map((p) => p.trim())
      .filter(Boolean);
  }, [wikiHtml]);
  const wikiToShow = wikiParagraphs.slice(0, 2);

  if (!spotifyId) return <div className="card">Álbum no especificado.</div>;
  if (loading) return <div className="card">Cargando álbum...</div>;
  if (error) return <div className="card">Error: {error}</div>;
  if (!album) return <div className="card">Sin datos.</div>;

  return (
    <div className="space-y-4">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 14px',
            borderRadius: 12,
            background: 'transparent',
            border: '1px solid var(--accent)',
            color: 'var(--accent)',
            cursor: 'pointer'
          }}
        >
          ← Volver
        </button>
      </div>

      <div className="card" style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 16, alignItems: 'flex-start' }}>
        {album.images?.[0]?.url && (
          <img
            src={album.images[0].url}
            alt={album.name}
            style={{ width: '100%', borderRadius: 12 }}
          />
        )}
        <div>
          <div style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>{album.name}</div>
          <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 10 }}>
            {(album.artists || []).map((a) => a.name).join(', ') || 'Artista desconocido'}
            {album.release_date ? ` · ${album.release_date}` : ''}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.5 }}>
            {album.name} — {tracks.length} canciones.{" "}
            {(album.artists || []).map((a) => a.name).join(', ') || 'Este álbum'} salió en {album.release_date || 'fecha no disponible'}.
            Explora los temas, márcalos como favoritos, añade tags o descárgalos.
          </div>
          {wikiToShow.length > 0 && (
            <div
              className="text-sm text-muted-foreground space-y-2"
              style={{ marginTop: 10, padding: '10px 12px', borderRadius: 12, border: '1px solid var(--border)', background: 'var(--panel)' }}
            >
              {wikiToShow.map((p, idx) => (
                <p key={idx} style={{ margin: 0, lineHeight: 1.5 }}>
                  {p}
                </p>
              ))}
              {wikiParagraphs.length > 2 && (
                <a
                  href={wiki?.url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  style={{ display: 'inline-block', marginTop: 6, color: 'var(--accent)', fontWeight: 600 }}
                >
                  Ver historia completa
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, marginBottom: 10 }}>Canciones</div>
        <div className="space-y-2">
          {tracks.map((t, idx) => (
            <div
              key={t.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '40px 1fr 140px 220px',
                alignItems: 'center',
                padding: '8px 0',
                borderBottom: '1px solid var(--border)'
              }}
            >
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>#{idx + 1}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{t.name}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {t.duration_ms ? `${Math.floor(t.duration_ms / 60000)}:${String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}` : ''}
                {t.popularity !== undefined ? ` · Pop ${t.popularity}` : ''}
                {t.explicit ? ' · Explicit' : ''}
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="btn-ghost" style={{ borderRadius: 8, fontSize: 18 }}>❤️</button>
                <button className="btn-ghost" style={{ borderRadius: 8, fontSize: 18 }}>⬇️</button>
                <button className="btn-ghost" style={{ borderRadius: 8, fontSize: 18 }}>🏷️</button>
                <button
                  className="btn-ghost"
                  style={{
                    borderRadius: 8,
                    padding: '6px 12px',
                    background: 'var(--panel-2)',
                    border: 'none',
                    transition: 'transform 120ms ease, background 120ms ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'scale(1.08)';
                    e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'scale(1)';
                    e.currentTarget.style.background = 'var(--panel-2)';
                  }}
                  onClick={() => togglePlay(t)}
                >
                  <svg
                    width="32"
                    height="32"
                    viewBox="0 0 32 32"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinejoin="round"
                    style={{ color: 'var(--accent)' }}
                  >
                    <path d="M10 8 L24 16 L10 24 Z" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
