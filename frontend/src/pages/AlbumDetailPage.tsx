import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';

type Track = {
  id: string;
  spotify_id?: string;
  name: string;
  duration_ms?: number;
  external_urls?: { spotify?: string };
  popularity?: number;
  explicit?: boolean;
  artists?: ArtistMini[];
};
type AlbumImage = { url: string };
type ArtistMini = { name: string };
type YoutubeAvailability =
  | { status: 'pending' }
  | { status: 'available'; videoId: string; videoUrl: string; title?: string }
  | { status: 'not_found' }
  | { status: 'error'; message?: string };
type DownloadUiState = { status: 'idle' | 'loading' | 'done' | 'error'; message?: string };
type StreamUiState = { status: 'idle' | 'loading' | 'error'; message?: string };
type Album = {
  id: string;
  name: string;
  release_date?: string;
  images?: AlbumImage[];
  artists?: ArtistMini[];
  tracks?: { items: Track[] };
  lastfm?: {
    wiki?: { summary?: string; content?: string; url?: string };
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
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteLoading, setFavoriteLoading] = useState(false);
  const [localAlbumId, setLocalAlbumId] = useState<number | null>(null);
  const [youtubeAvailability, setYoutubeAvailability] = useState<Record<string, YoutubeAvailability>>({});
  const [downloadState, setDownloadState] = useState<Record<string, DownloadUiState>>({});
  const [streamState, setStreamState] = useState<Record<string, StreamUiState>>({});
  const [nowPlaying, setNowPlaying] = useState<{ title: string; artist?: string; videoId: string; embedUrl: string } | null>(null);
  const isMountedRef = useRef(true);
  const userId = useApiStore((s) => s.userId);

  const resolveTrackId = useCallback((track: Track) => track.spotify_id || track.id || '', []);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setYoutubeAvailability({});
    setDownloadState({});
    setStreamState({});
    setNowPlaying(null);
  }, [spotifyId]);

  const getRowKey = useCallback(
    (track: Track, idx?: number) =>
      resolveTrackId(track) ||
      track.external_urls?.spotify ||
      `${track.name}-${album?.id || spotifyId || 'album'}-${idx ?? ''}`,
    [album?.id, spotifyId, resolveTrackId]
  );

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
        // Try to persist album to get local ID for favorites
        try {
          const saveRes = await audio2Api.saveAlbumToDb(spotifyId);
          const albumId = saveRes.data?.album?.id;
          if (albumId && isMounted) {
            setLocalAlbumId(albumId);
          }
        } catch (e) {
          // best effort; ignore
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

  // Check favorite status once we have local album id
  useEffect(() => {
    const checkFavorite = async () => {
      if (!userId || !localAlbumId) return;
      try {
        const res = await audio2Api.listFavorites({ user_id: userId, target_type: 'album' });
        const favs = Array.isArray(res.data) ? res.data : [];
        const found = favs.some((f: any) => f.album_id === localAlbumId);
        setIsFavorite(found);
      } catch (e) {
        // ignore
      }
    };
    checkFavorite();
  }, [userId, localAlbumId]);

  const fetchYoutubeForTrack = useCallback(
    async (track: Track, stateKey: string): Promise<YoutubeAvailability | null> => {
      const spotifyTrackId = resolveTrackId(track);
      if (!spotifyTrackId) return null;

      const setAvailable = (videoId: string, videoUrl?: string) => {
        const next: YoutubeAvailability = {
          status: 'available',
          videoId,
          videoUrl: videoUrl || `https://www.youtube.com/watch?v=${videoId}`,
          title: track.name,
        };
        setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
        setStreamState((prev) => ({ ...prev, [stateKey]: { status: 'idle' } }));
        return next;
      };

      const setError = (message: string) => {
        const next: YoutubeAvailability = { status: 'error', message };
        setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
        return next;
      };

      const refreshFromYoutube = async () => {
        const artistName = track.artists?.[0]?.name || album?.artists?.[0]?.name;
        if (!artistName || !album?.name) {
          const next: YoutubeAvailability = { status: 'not_found' };
          setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
          return next;
        }
        setYoutubeAvailability((prev) => ({
          ...prev,
          [stateKey]: { status: 'pending' },
        }));
        try {
          const response = await audio2Api.refreshYoutubeTrackLink(spotifyTrackId, {
            artist: artistName,
            track: track.name,
            album: album.name,
          });
          if (!isMountedRef.current) {
            return null;
          }
          const linkData = response.data;
          if (linkData?.youtube_video_id) {
            return setAvailable(linkData.youtube_video_id, linkData.youtube_url);
          }
          const next: YoutubeAvailability = { status: 'not_found' };
          setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
          return next;
        } catch (error: any) {
          if (!isMountedRef.current) {
            return null;
          }
          const message = error?.response?.data?.detail || error?.message || 'Error buscando en YouTube';
          return setError(message);
        }
      };

      try {
        const res = await audio2Api.getYoutubeTrackLink(spotifyTrackId);
        if (!isMountedRef.current) {
          return null;
        }
        const linkData = res.data;
        if (linkData?.youtube_video_id) {
          return setAvailable(linkData.youtube_video_id, linkData.youtube_url);
        }
        if (linkData?.status === 'missing' || linkData?.status === 'error' || linkData?.status === 'video_not_found') {
          return refreshFromYoutube();
        }
      } catch (err: any) {
        if (!isMountedRef.current) {
          return null;
        }
        const statusCode = err?.response?.status;
        if (statusCode === 404) {
          return refreshFromYoutube();
        }
        const detail = err?.response?.data?.detail || err?.message || 'Error consultando YouTube';
        return setError(detail);
      }

      return null;
    },
    [album, resolveTrackId]
  );

  const buildEmbedUrl = (videoId: string) =>
    `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;

  const handleStreamTrack = async (track: Track, stateKey: string) => {
    const setStream = (state: StreamUiState) =>
      setStreamState((prev) => ({
        ...prev,
        [stateKey]: state,
      }));

    const artistName = track.artists?.[0]?.name || album?.artists?.[0]?.name;
    if (!artistName) {
      setStream({ status: 'error', message: 'Falta artista para reproducir' });
      return;
    }

    const info = await fetchYoutubeForTrack(track, stateKey);
    if (!info || info.status !== 'available') {
      setStream({ status: 'error', message: 'Sin enlace de YouTube' });
      return;
    }

    setStream({ status: 'loading', message: 'Abriendo YouTube...' });
    try {
      setNowPlaying({
        title: track.name,
        artist: artistName,
        videoId: info.videoId,
        embedUrl: buildEmbedUrl(info.videoId),
      });
      setStream({ status: 'idle' });
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Error al reproducir';
      setStream({ status: 'error', message });
    }
  };

  const handleDownloadTrack = async (track: Track, key: string) => {
    const updateState = (state: DownloadUiState) =>
      setDownloadState((prev) => ({
        ...prev,
        [key]: state,
      }));

    const info = await fetchYoutubeForTrack(track, key);
    if (!info || info.status !== 'available') {
      let message = 'Sin enlace de YouTube';
      if (info?.status === 'not_found') {
        message = 'No se encontró YouTube para esta canción';
      } else if (info?.status === 'error' && info.message) {
        message = info.message;
      }
      updateState({ status: 'error', message });
      return;
    }

    updateState({ status: 'loading', message: 'Descargando...' });
    try {
      await audio2Api.downloadYoutubeAudio(info.videoId);
      updateState({ status: 'done', message: 'Descarga iniciada' });
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Error al descargar';
      updateState({ status: 'error', message });
    }
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

      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontWeight: 700 }}>Reproductor</div>
          {nowPlaying && (
            <button
              className="btn-ghost"
              style={{ borderRadius: 8 }}
              onClick={() => setNowPlaying(null)}
            >
              Detener
            </button>
          )}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 13 }}>
          {nowPlaying ? `Reproduciendo: ${nowPlaying.title} · ${nowPlaying.artist || ''}` : 'Selecciona una canción para reproducir'}
        </div>
        {nowPlaying ? (
          <div style={{ position: 'relative', paddingTop: '56.25%' }}>
            <iframe
              src={nowPlaying.embedUrl}
              title={nowPlaying.title}
              allow="autoplay; encrypted-media"
              allowFullScreen
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                border: 0,
                borderRadius: 12,
              }}
            />
          </div>
        ) : (
          <div style={{ padding: '18px', borderRadius: 12, border: '1px dashed var(--border)', color: 'var(--muted)' }}>
            Sin reproducción activa.
          </div>
        )}
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontWeight: 700 }}>Canciones</div>
          <button
            className="btn-ghost"
            style={{ borderRadius: 8, fontSize: 18, opacity: favoriteLoading ? 0.6 : 1 }}
            disabled={favoriteLoading || !userId || !localAlbumId}
            onClick={async () => {
              if (!userId || !localAlbumId) return;
              setFavoriteLoading(true);
              try {
                if (!isFavorite) {
                  await audio2Api.addFavorite('album', localAlbumId, userId);
                  setIsFavorite(true);
                } else {
                  await audio2Api.removeFavorite('album', localAlbumId, userId);
                  setIsFavorite(false);
                }
              } catch (e) {
                // ignore error for now
              } finally {
                setFavoriteLoading(false);
              }
            }}
            aria-pressed={isFavorite}
            aria-label={isFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
            title={isFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
          >
            {isFavorite ? '❤️' : '🤍'}
          </button>
        </div>
        <div className="space-y-2">
          {tracks.map((t, idx) => {
            const rowKey = getRowKey(t, idx);
            const spotifyTrackId = resolveTrackId(t);
            const youtubeInfo = spotifyTrackId ? youtubeAvailability[spotifyTrackId] : undefined;
            const downloadInfo = spotifyTrackId ? downloadState[spotifyTrackId] : undefined;
            const streamInfo = spotifyTrackId ? streamState[spotifyTrackId] : undefined;
            const streamDisabled = !spotifyTrackId || youtubeInfo?.status === 'pending' || streamInfo?.status === 'loading';
            const downloadDisabled = !spotifyTrackId || downloadInfo?.status === 'loading';
            const downloadMessage = downloadInfo?.message;
            const streamMessage = streamInfo?.message;
            const downloadMessageColor =
              downloadInfo?.status === 'error'
                ? '#f87171'
                : downloadInfo?.status === 'done'
                ? '#4ade80'
                : 'var(--muted)';
            const streamMessageColor = streamInfo?.status === 'error' ? '#f87171' : 'var(--muted)';

            return (
              <div
                key={rowKey}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '40px 1fr 140px 260px',
                  alignItems: 'center',
                  padding: '8px 0',
                  borderBottom: '1px solid var(--border)'
                }}
              >
                <div style={{ color: 'var(--muted)', fontSize: 12 }}>#{idx + 1}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{t.name}</span>
                  {youtubeInfo?.status === 'available' && (
                    <span
                      title={youtubeInfo.title || 'Disponible para streaming en YouTube'}
                      style={{
                        fontSize: 11,
                        padding: '2px 6px',
                        borderRadius: 999,
                        background: 'rgba(255,0,0,0.15)',
                        color: '#ff6666',
                        fontWeight: 600,
                        letterSpacing: 0.5
                      }}
                    >
                      ▶ YT
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {t.duration_ms ? `${Math.floor(t.duration_ms / 60000)}:${String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}` : ''}
                  {t.popularity !== undefined ? ` · Pop ${t.popularity}` : ''}
                  {t.explicit ? ' · Explicit' : ''}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                  <button className="btn-ghost" style={{ borderRadius: 8, fontSize: 18 }}>❤️</button>
                  <button
                    className="btn-ghost"
                    style={{ borderRadius: 8, fontSize: 18, opacity: downloadDisabled ? 0.6 : 1 }}
                    disabled={downloadDisabled}
                    onClick={() => spotifyTrackId && handleDownloadTrack(t, spotifyTrackId)}
                    title="Descargar desde YouTube"
                    aria-label="Descargar desde YouTube"
                  >
                    {downloadInfo?.status === 'loading' ? '⏳' : '⬇️'}
                  </button>
                  <button className="btn-ghost" style={{ borderRadius: 8, fontSize: 18 }}>🏷️</button>
                  <button
                    className="btn-ghost"
                    style={{
                      borderRadius: 8,
                      padding: '6px 12px',
                      background: 'var(--panel-2)',
                      border: 'none',
                      opacity: streamDisabled ? 0.6 : 1,
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
                    onClick={() => spotifyTrackId && handleStreamTrack(t, spotifyTrackId)}
                    disabled={streamDisabled}
                    title={youtubeInfo?.status === 'available' ? 'Escuchar en streaming (YouTube)' : 'Buscar en YouTube y reproducir'}
                    aria-label="Escuchar vía streaming"
                  >
                    {streamDisabled ? (
                      <span style={{ fontSize: 14 }}>⏳</span>
                    ) : (
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
                    )}
                  </button>
                  {downloadMessage && (
                    <span style={{ fontSize: 11, minWidth: 90, textAlign: 'left', color: downloadMessageColor }}>
                      {downloadMessage}
                    </span>
                  )}
                  {streamMessage && !downloadMessage && (
                    <span style={{ fontSize: 11, minWidth: 90, textAlign: 'left', color: streamMessageColor }}>
                      {streamMessage}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
