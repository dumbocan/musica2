import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import { normalizeImageUrl } from '@/lib/images';
import { useApiStore } from '@/store/useApiStore';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useFavorites } from '@/hooks/useFavorites';
import { AddToPlaylistModal } from '@/components/AddToPlaylistModal';

type Track = {
  id: string;
  spotify_id?: string;
  name: string;
  duration_ms?: number;
  external_urls?: { spotify?: string };
  popularity?: number;
  explicit?: boolean;
  artists?: Array<{ id?: string; name?: string }>;
};
type AlbumImage = { url: string };
type ArtistMini = { id?: string; spotify_id?: string; name: string };
type YouTubeLinkStatus = {
  spotify_track_id: string;
  youtube_video_id?: string;
  youtube_url?: string;
  status?: 'available' | 'missing' | 'error' | 'video_not_found';
  error_message?: string;
};
type ResolvedTrack = {
  spotify_track_id: string;
  track_id: number;
};
type TrackChartStat = {
  track_id: number;
  spotify_track_id?: string | null;
  chart_source?: string | null;
  chart_name?: string | null;
  chart_best_position?: number | null;
  chart_best_position_date?: string | null;
  chart_weeks_at_one?: number | null;
  chart_weeks_top5?: number | null;
  chart_weeks_top10?: number | null;
};
type YoutubeAvailability =
  | { status: 'pending' }
  | { status: 'available'; videoId: string; videoUrl?: string; title?: string }
  | { status: 'missing'; title?: string }
  | { status: 'not_found'; title?: string }
  | { status: 'error'; message?: string; title?: string };
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

const formatChartDate = (value?: string | null) => {
  if (!value) return null;
  const parts = value.split('-');
  if (parts.length !== 3) return value;
  const [year, month, day] = parts;
  if (!day || !month || !year) return value;
  return `${day}-${month}-${year}`;
};

export function AlbumDetailPage() {
  const { token } = useApiStore();
  const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';

  const resolveImageUrl = (url?: string) => {
    if (!url) return undefined;
    // Use local cached image if we have a local album ID
    if (localAlbumId && url.startsWith('http')) {
      return `${API_BASE_URL}/images/entity/album/${localAlbumId}?size=256${tokenParam}`;
    }
    return normalizeImageUrl({ candidate: url, size: 256, token, apiBaseUrl: API_BASE_URL });
  };
  const { spotifyId } = useParams<{ spotifyId: string }>();
  const navigate = useNavigate();
  const [album, setAlbum] = useState<Album | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [favoriteLoading, setFavoriteLoading] = useState(false);
  const [localAlbumId, setLocalAlbumId] = useState<number | null>(null);
  const [trackLocalIds, setTrackLocalIds] = useState<Record<string, number>>({});
  const [trackFavoriteLoading, setTrackFavoriteLoading] = useState<Record<string, boolean>>({});
  const [playlistTrack, setPlaylistTrack] = useState<Track | null>(null);
  const [playlistAlbumOpen, setPlaylistAlbumOpen] = useState(false);
  const [youtubeAvailability, setYoutubeAvailability] = useState<Record<string, YoutubeAvailability>>({});
  const [streamState, setStreamState] = useState<Record<string, StreamUiState>>({});
  const [chartStatsBySpotifyId, setChartStatsBySpotifyId] = useState<Record<string, TrackChartStat>>({});
  const setVideoEmbedId = usePlayerStore((s) => s.setVideoEmbedId);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const setNowPlaying = usePlayerStore((s) => s.setNowPlaying);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const setQueue = usePlayerStore((s) => s.setQueue);
  const setCurrentIndex = usePlayerStore((s) => s.setCurrentIndex);
  const setOnPlayTrack = usePlayerStore((s) => s.setOnPlayTrack);
  const autoSearchOnPlay = true;
  const isMountedRef = useRef(true);
  const userId = useApiStore((s) => s.userId);
  const {
    favoriteIds: favoriteAlbumIds,
    toggleFavorite: toggleAlbumFavorite,
    effectiveUserId: effectiveAlbumUserId
  } = useFavorites('album', userId);
  const {
    favoriteIds: favoriteTrackIds,
    toggleFavorite: toggleTrackFavorite,
    effectiveUserId: effectiveTrackUserId
  } = useFavorites('track', userId);

  const resolveTrackId = useCallback((track: Track) => track.spotify_id || track.id || '', []);
  const handleCloseVideo = useCallback(() => {
    setVideoEmbedId(null);
  }, [setVideoEmbedId]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const getRowKey = useCallback(
    (track: Track, idx?: number) =>
      resolveTrackId(track) ||
      track.external_urls?.spotify ||
      `${track.name}-${album?.id || spotifyId || 'album'}-${idx ?? ''}`,
    [album?.id, spotifyId, resolveTrackId]
  );

  useEffect(() => {
    if (tracks.length === 0) return;
    const trackIds = tracks.map(resolveTrackId).filter(Boolean);
    if (trackIds.length === 0) return;
    let cancelled = false;
    const trackLookup = new Map(tracks.map((track) => [resolveTrackId(track), track]));
    const loadLinks = async () => {
      try {
        const response = await audio2Api.getYoutubeTrackLinks(trackIds);
        if (cancelled) return;
        const items = response.data?.items || [];
        const nextAvailability: Record<string, YoutubeAvailability> = {};
        const nextStreamState: Record<string, StreamUiState> = {};
        items.forEach((item: YouTubeLinkStatus) => {
          const trackId = item.spotify_track_id;
          if (!trackId) return;
          const track = trackLookup.get(trackId);
          if (item.youtube_video_id) {
            nextAvailability[trackId] = {
              status: 'available',
              videoId: item.youtube_video_id,
              videoUrl: item.youtube_url,
              title: track?.name,
            };
          } else if (item.status) {
            nextAvailability[trackId] = {
              status: item.status === 'error' ? 'error' : 'missing',
              message: item.error_message || undefined,
              title: track?.name,
            };
          }
          nextStreamState[trackId] = { status: 'idle' };
        });
        if (Object.keys(nextAvailability).length > 0) {
          setYoutubeAvailability((prev) => ({ ...prev, ...nextAvailability }));
        }
        if (Object.keys(nextStreamState).length > 0) {
          setStreamState((prev) => {
            let changed = false;
            const merged = { ...prev };
            Object.entries(nextStreamState).forEach(([trackId, state]) => {
              if (!(trackId in merged)) {
                merged[trackId] = state;
                changed = true;
              }
            });
            return changed ? merged : prev;
          });
        }
      } catch {
        // best effort
      }
    };
    loadLinks();
    return () => {
      cancelled = true;
    };
  }, [tracks, resolveTrackId]);

  useEffect(() => {
    if (tracks.length === 0) {
      setTrackLocalIds({});
      setChartStatsBySpotifyId({});
      return;
    }
    const spotifyTrackIds = tracks.map(resolveTrackId).filter(Boolean);
    if (spotifyTrackIds.length === 0) {
      setTrackLocalIds({});
      setChartStatsBySpotifyId({});
      return;
    }
    let cancelled = false;
    const loadTrackIds = async () => {
      try {
        const res = await audio2Api.resolveTracks(spotifyTrackIds);
        if (cancelled) return;
        const next: Record<string, number> = {};
        (res.data?.items || []).forEach((item: ResolvedTrack) => {
          if (item?.spotify_track_id && typeof item?.track_id === 'number') {
            next[item.spotify_track_id] = item.track_id;
          }
        });
        setTrackLocalIds(next);
      } catch {
        if (!cancelled) {
          setTrackLocalIds({});
        }
      }
    };
    loadTrackIds();
    return () => {
      cancelled = true;
    };
  }, [resolveTrackId, tracks, localAlbumId]);

  useEffect(() => {
    if (tracks.length === 0) {
      setChartStatsBySpotifyId({});
      return;
    }
    const spotifyTrackIds = tracks.map(resolveTrackId).filter(Boolean);
    if (spotifyTrackIds.length === 0) {
      setChartStatsBySpotifyId({});
      return;
    }
    let cancelled = false;
    const loadChartStats = async () => {
      try {
        const res = await audio2Api.getTrackChartStats(spotifyTrackIds);
        if (cancelled) return;
        const stats: Record<string, TrackChartStat> = {};
        (res.data?.items || []).forEach((item: TrackChartStat) => {
          if (item.spotify_track_id) {
            stats[item.spotify_track_id] = item;
          }
        });
        setChartStatsBySpotifyId(stats);
      } catch {
        if (!cancelled) {
          setChartStatsBySpotifyId({});
        }
      }
    };
    loadChartStats();
    return () => {
      cancelled = true;
    };
  }, [resolveTrackId, tracks]);

  const ensureTrackLocalId = useCallback(
    async (spotifyTrackId: string): Promise<number | null> => {
      const existing = trackLocalIds[spotifyTrackId];
      if (existing) return existing;
      // Try to resolve from existing local tracks
      try {
        const res = await audio2Api.resolveTracks([spotifyTrackId]);
        const items = res.data?.items || [];
        const match = items.find((item: ResolvedTrack) => item.spotify_track_id === spotifyTrackId);
        if (match?.track_id) {
          setTrackLocalIds((prev) => ({ ...prev, [spotifyTrackId]: match.track_id }));
          return match.track_id as number;
        }
      } catch {
        // best effort
      }
      // Track doesn't exist locally - save it from Spotify
      try {
        const saveRes = await audio2Api.saveTrackFromSpotify(spotifyTrackId);
        if (saveRes.data?.track_id) {
          setTrackLocalIds((prev) => ({ ...prev, [spotifyTrackId]: saveRes.data.track_id }));
          return saveRes.data.track_id as number;
        }
      } catch {
        // ignore
      }
      return null;
    },
    [trackLocalIds]
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
        if (data?.local_id) {
          setLocalAlbumId(data.local_id);
        }
        const embeddedTracks = Array.isArray(data?.tracks?.items)
          ? data.tracks.items
          : Array.isArray(data?.tracks)
            ? data.tracks
            : null;
        if (embeddedTracks) {
          setTracks(embeddedTracks);
        } else {
          // Fallback: fetch tracks endpoint
          const tracksRes = await audio2Api.getAlbumTracks(spotifyId);
          if (!isMounted) return;
          setTracks(tracksRes.data || []);
        }
        // DB-first: do not force external save unless explicitly requested
      } catch (err: unknown) {
        if (!isMounted) return;
        const message =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
            ? (err.response.data as { detail: string }).detail
            : err instanceof Error
              ? err.message
              : 'Error cargando álbum';
        setError(message);
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [spotifyId]);


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
        } catch (error: unknown) {
          if (!isMountedRef.current) {
            return null;
          }
          const message =
            error && typeof error === 'object' && 'response' in error && error.response && typeof error.response === 'object' && 'data' in error.response && error.response.data && typeof error.response.data === 'object' && 'detail' in error.response.data
              ? (error.response.data as { detail: string }).detail
              : error instanceof Error
                ? error.message
                : 'Error buscando en YouTube';
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
          if (!autoSearchOnPlay) {
            const next: YoutubeAvailability = { status: 'missing' };
            setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
            return next;
          }
          return refreshFromYoutube();
        }
      } catch (err: unknown) {
        if (!isMountedRef.current) {
          return null;
        }
        const statusCode =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'status' in err.response
            ? (err.response as { status: number }).status
            : undefined;
        if (statusCode === 404) {
          if (!autoSearchOnPlay) {
            const next: YoutubeAvailability = { status: 'not_found' };
            setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
            return next;
          }
          return refreshFromYoutube();
        }
        const detail =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
            ? (err.response.data as { detail: string }).detail
            : err instanceof Error
              ? err.message
              : 'Error consultando YouTube';
        return setError(detail);
      }

      return null;
    },
    [album, autoSearchOnPlay, resolveTrackId]
  );

  useEffect(() => {
    setYoutubeAvailability({});
    setStreamState({});
  }, [spotifyId]);

  const handleStreamTrack = useCallback(async (track: Track, stateKey: string) => {
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

    const cached = youtubeAvailability[stateKey];
    const localTrackId = trackLocalIds[stateKey];
    if (cached?.status === 'available' && cached.videoId) {
      setStream({ status: 'loading', message: 'Abriendo audio...' });
      const nextNowPlaying = {
        title: track.name,
        artist: artistName,
        artistSpotifyId: track.artists?.[0]?.id,
        videoId: cached.videoId,
        spotifyTrackId: stateKey,
        localTrackId,
      };
      setNowPlaying(nextNowPlaying);
      const idx = tracks.findIndex((t) => resolveTrackId(t) === stateKey);
      if (idx >= 0) {
        setCurrentIndex(idx);
      }
      const result = await playByVideoId({
        ...nextNowPlaying,
        durationSec: track.duration_ms ? track.duration_ms / 1000 : undefined,
      });
      if (!result.ok) {
        setStream({ status: 'error', message: 'Pulsa play otra vez para iniciar el audio' });
        return;
      }
      setStream({ status: 'idle' });
      if (playbackMode === 'video') {
        setVideoEmbedId(cached.videoId);
      }
      return;
    }

    const info = await fetchYoutubeForTrack(track, stateKey);
    if (!info || info.status !== 'available') {
      const msg = autoSearchOnPlay ? 'Sin enlace de YouTube' : 'Sin enlace de YouTube (sin buscar)';
      setStream({ status: 'error', message: msg });
      return;
    }

    setStream({ status: 'loading', message: 'Abriendo audio...' });
      const nextNowPlaying = {
        title: track.name,
        artist: artistName,
        artistSpotifyId: track.artists?.[0]?.id,
        videoId: info.videoId,
        spotifyTrackId: stateKey,
        localTrackId,
      };
    setNowPlaying(nextNowPlaying);
    const idx = tracks.findIndex((t) => resolveTrackId(t) === stateKey);
    if (idx >= 0) {
      setCurrentIndex(idx);
    }
    const result = await playByVideoId({
      ...nextNowPlaying,
      durationSec: track.duration_ms ? track.duration_ms / 1000 : undefined,
    });
    if (!result.ok) {
      setStream({ status: 'error', message: 'Pulsa play otra vez para iniciar el audio' });
      return;
    }
    setStream({ status: 'idle' });
    if (playbackMode === 'video') {
      setVideoEmbedId(info.videoId);
    }
  }, [album?.artists, youtubeAvailability, playbackMode, setNowPlaying, tracks, resolveTrackId, setCurrentIndex, playByVideoId, setVideoEmbedId, fetchYoutubeForTrack, autoSearchOnPlay, trackLocalIds]);

  useEffect(() => {
    if (playbackMode !== 'video') {
      handleCloseVideo();
    }
  }, [handleCloseVideo, playbackMode]);

  useEffect(() => {
    if (tracks.length === 0) return;
    const queueItems = tracks
      .map((track) => {
        const spotifyTrackId = resolveTrackId(track);
        if (!spotifyTrackId) return null;
        return {
          localTrackId: trackLocalIds[spotifyTrackId],
          spotifyTrackId,
          title: track.name,
          artist: track.artists?.[0]?.name || album?.artists?.[0]?.name,
          artistSpotifyId: track.artists?.[0]?.id,
          durationMs: track.duration_ms,
          rawTrack: track,
        };
      })
      .filter(Boolean) as Array<{
        localTrackId?: number;
        spotifyTrackId: string;
        title: string;
        artist?: string;
        durationMs?: number;
        rawTrack: Track;
      }>;
    setQueue(queueItems);
    setOnPlayTrack((item) => {
      const rawTrack = item.rawTrack as Track | undefined;
      if (!rawTrack) return;
      void handleStreamTrack(rawTrack, item.spotifyTrackId);
    });
    return () => setOnPlayTrack(null);
  }, [album?.artists, handleStreamTrack, resolveTrackId, setOnPlayTrack, setQueue, tracks, trackLocalIds]);

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
  const isAlbumFavorite = !!(localAlbumId && favoriteAlbumIds.has(localAlbumId));
  const canFavoriteAlbum = !!effectiveAlbumUserId;
  const canFavoriteTrack = !!effectiveTrackUserId;

  if (!spotifyId) return <div className="card">Álbum no especificado.</div>;
  if (loading) return <div className="card">Cargando álbum...</div>;
  if (error) return <div className="card">Error: {error}</div>;
  if (!album) return <div className="card">Sin datos.</div>;

  const coverImageUrl = resolveImageUrl(album.images?.[0]?.url);

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
        <div style={{ position: 'relative', width: '100%', paddingTop: '100%', borderRadius: 12, overflow: 'hidden' }}>
          {coverImageUrl && (
            <img
              src={coverImageUrl}
              alt={album.name}
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'cover',
              }}
            />
          )}
        </div>
        <div>
          <div style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>{album.name}</div>
          <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 10 }}>
            {(album.artists || []).map((a) => a.name).join(', ') || 'Artista desconocido'}
            {album.release_date ? ` · ${album.release_date}` : ''}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 14, lineHeight: 1.5 }}>
            {album.name} — {tracks.length} canciones.{" "}
            {(album.artists || []).map((a) => a.name).join(', ') || 'Este álbum'} salió en {album.release_date || 'fecha no disponible'}.
            Explora los temas, márcalos como favoritos o añádelos a una lista.
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontWeight: 700 }}>Canciones</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="badge"
              style={{ borderRadius: 8 }}
              onClick={() => setPlaylistAlbumOpen(true)}
              title="Añadir álbum entero a una lista"
            >
              ＋ Álbum entero
            </button>
            <button
              className="btn-ghost"
              style={{ borderRadius: 8, fontSize: 18, opacity: favoriteLoading ? 0.6 : 1 }}
              disabled={favoriteLoading || !canFavoriteAlbum || !localAlbumId}
              onClick={async () => {
                if (!canFavoriteAlbum || !localAlbumId) {
                  setError('No se pudo guardar favorito del álbum: inicia sesión de nuevo.');
                  return;
                }
                setFavoriteLoading(true);
                try {
                  await toggleAlbumFavorite(localAlbumId);
                } catch (err) {
                  console.error('Album favorite toggle failed', err);
                  setError('Error guardando favorito del álbum.');
                } finally {
                  setFavoriteLoading(false);
                }
              }}
              aria-pressed={isAlbumFavorite}
              aria-label={isAlbumFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
              title={isAlbumFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
            >
              {isAlbumFavorite ? '❤️' : '🤍'}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          {tracks.map((t, idx) => {
            const rowKey = getRowKey(t, idx);
            const spotifyTrackId = resolveTrackId(t);
            const youtubeInfo = spotifyTrackId ? youtubeAvailability[spotifyTrackId] : undefined;
            const streamInfo = spotifyTrackId ? streamState[spotifyTrackId] : undefined;
            const trackLocalId = spotifyTrackId ? trackLocalIds[spotifyTrackId] : undefined;
            const chartStat = spotifyTrackId ? chartStatsBySpotifyId[spotifyTrackId] : undefined;
            const chartBadge = chartStat?.chart_best_position
              ? `#${chartStat.chart_best_position}`
              : null;
            const chartDate = formatChartDate(chartStat?.chart_best_position_date);
            const isTrackFavorite = !!(trackLocalId && favoriteTrackIds.has(trackLocalId));
            const isTrackFavoriteLoading = !!(spotifyTrackId && trackFavoriteLoading[spotifyTrackId]);
            const streamDisabled = !spotifyTrackId || youtubeInfo?.status === 'pending' || streamInfo?.status === 'loading';
            const streamMessage = streamInfo?.message;
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <button
                    type="button"
                    onClick={() => spotifyTrackId && handleStreamTrack(t, spotifyTrackId)}
                    disabled={streamDisabled}
                    style={{
                      flex: 1,
                      minWidth: 0,
                      textAlign: 'left',
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      margin: 0,
                      font: 'inherit',
                      color: streamDisabled ? 'inherit' : 'var(--accent)',
                      cursor: streamDisabled ? 'default' : 'pointer',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {t.name}
                    {chartBadge ? (
                      <span
                        title={`Billboard ${chartStat?.chart_best_position}${chartDate ? ` · ${chartDate}` : ''}`}
                        style={{
                          marginLeft: 8,
                          fontSize: 12,
                          fontWeight: 700,
                          color: '#facc15',
                          textTransform: 'uppercase',
                        }}
                      >
                        {chartBadge}
                      </span>
                    ) : null}
                    {chartBadge && chartDate ? (
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 11,
                          color: 'var(--muted)',
                        }}
                      >
                        {chartDate}
                      </span>
                    ) : null}
                  </button>
                  {youtubeInfo?.status === 'available' ? (
                    <span
                      title={youtubeInfo.title || 'Disponible para streaming en YouTube'}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 24,
                        height: 24,
                        borderRadius: '50%',
                        border: '2px solid rgba(110, 193, 164, 0.7)',
                        color: 'var(--accent)',
                        fontWeight: 900,
                        fontSize: 16,
                        letterSpacing: 0.5,
                      }}
                    >
                      ✓
                    </span>
                  ) : youtubeInfo?.status === 'error' ? (
                    <span
                      title={youtubeInfo.message || 'Error consultando YouTube'}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 24,
                        height: 24,
                        borderRadius: '50%',
                        border: '2px solid rgba(250, 204, 21, 0.7)',
                        color: '#facc15',
                        fontWeight: 900,
                        fontSize: 16,
                        letterSpacing: 0.5,
                      }}
                    >
                      !
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {t.duration_ms ? `${Math.floor(t.duration_ms / 60000)}:${String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}` : ''}
                  {t.popularity !== undefined ? ` · Pop ${t.popularity}` : ''}
                  {t.explicit ? ' · Explicit' : ''}
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
                  <button
                    className="btn-ghost"
                    style={{ borderRadius: 8, fontSize: 18, opacity: !userId ? 0.4 : 1 }}
                    disabled={!canFavoriteTrack || isTrackFavoriteLoading}
                    onClick={async () => {
                        if (!canFavoriteTrack || !spotifyTrackId) {
                          setError('No se pudo guardar favorito de la canción: inicia sesión de nuevo.');
                          return;
                        }
                        setTrackFavoriteLoading((prev) => ({ ...prev, [spotifyTrackId]: true }));
                      try {
                        const resolvedId = trackLocalId || (await ensureTrackLocalId(spotifyTrackId));
                        if (!resolvedId) return;
                        await toggleTrackFavorite(resolvedId);
                      } catch (err) {
                        console.error('Track favorite toggle failed', err);
                        setError('Error guardando favorito de la canción.');
                      } finally {
                        setTrackFavoriteLoading((prev) => ({ ...prev, [spotifyTrackId]: false }));
                      }
                    }}
                    aria-label={isTrackFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
                    title={isTrackFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
                  >
                    {isTrackFavorite ? '❤️' : '🤍'}
                  </button>
                  <button
                    className="btn-ghost"
                    style={{ borderRadius: 8, fontSize: 12, padding: '6px 10px' }}
                    onClick={() => setPlaylistTrack(t)}
                    title="Añadir a lista"
                  >
                    ＋ Lista
                  </button>
                  {streamMessage && (
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

      <AddToPlaylistModal
        open={!!playlistTrack}
        title="Añadir canción a lista"
        subtitle={
          playlistTrack
            ? `${playlistTrack.name} · ${playlistTrack.artists?.[0]?.name || 'Artista desconocido'}`
            : undefined
        }
        onClose={() => setPlaylistTrack(null)}
        resolveTrackIds={async () => {
          if (!playlistTrack) return [];
          const spotifyTrackId = resolveTrackId(playlistTrack);
          if (!spotifyTrackId) return [];
          const resolvedId = trackLocalIds[spotifyTrackId] || (await ensureTrackLocalId(spotifyTrackId));
          return resolvedId ? [resolvedId] : [];
        }}
      />

      <AddToPlaylistModal
        open={playlistAlbumOpen}
        title="Añadir álbum entero"
        subtitle={`${album.name} · ${tracks.length} pistas`}
        onClose={() => setPlaylistAlbumOpen(false)}
        resolveTrackIds={async () => {
          const ids: number[] = [];
          const seen = new Set<number>();
          for (const track of tracks) {
            const spotifyTrackId = resolveTrackId(track);
            if (!spotifyTrackId) continue;
            const resolvedId = trackLocalIds[spotifyTrackId] || (await ensureTrackLocalId(spotifyTrackId));
            if (!resolvedId || seen.has(resolvedId)) continue;
            seen.add(resolvedId);
            ids.push(resolvedId);
          }
          return ids;
        }}
      />

    </div>
  );
}
