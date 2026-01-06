import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { usePlayerStore } from '@/store/usePlayerStore';
import { useFavorites } from '@/hooks/useFavorites';

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

const resolveImageUrl = (url?: string) => {
  if (!url) return undefined;
  return url.startsWith('/') ? `${API_BASE_URL}${url}` : url;
};

export function AlbumDetailPage() {
  const resolveImageUrl = (url?: string) => {
    if (!url) return undefined;
    return url.startsWith('/') ? `${API_BASE_URL}${url}` : url;
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
  const [youtubeAvailability, setYoutubeAvailability] = useState<Record<string, YoutubeAvailability>>({});
  const [streamState, setStreamState] = useState<Record<string, StreamUiState>>({});
  const nowPlaying = usePlayerStore((s) => s.nowPlaying);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const volume = usePlayerStore((s) => s.volume);
  const setNowPlaying = usePlayerStore((s) => s.setNowPlaying);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const setQueue = usePlayerStore((s) => s.setQueue);
  const setCurrentIndex = usePlayerStore((s) => s.setCurrentIndex);
  const setOnPlayTrack = usePlayerStore((s) => s.setOnPlayTrack);
  const setVideoControls = usePlayerStore((s) => s.setVideoControls);
  const setIsPlaying = usePlayerStore((s) => s.setIsPlaying);
  const setCurrentTime = usePlayerStore((s) => s.setCurrentTime);
  const setDuration = usePlayerStore((s) => s.setDuration);
  const [ytReady, setYtReady] = useState(false);
  const [playerReady, setPlayerReady] = useState(false);
  const autoSearchOnPlay = true;
  const playerContainerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<any>(null);
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

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if ((window as any).YT?.Player) {
      setYtReady(true);
      return;
    }
    const existing = document.getElementById('yt-iframe-api');
    if (!existing) {
      const script = document.createElement('script');
      script.id = 'yt-iframe-api';
      script.src = 'https://www.youtube.com/iframe_api';
      document.body.appendChild(script);
    }
    const interval = window.setInterval(() => {
      if ((window as any).YT?.Player) {
        setYtReady(true);
        window.clearInterval(interval);
      }
    }, 200);
    return () => {
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    setVideoControls({
      play: () => playerRef.current?.playVideo?.(),
      pause: () => playerRef.current?.pauseVideo?.(),
      stop: () => playerRef.current?.stopVideo?.(),
      seek: (value) => playerRef.current?.seekTo?.(value, true),
    });
    return () => setVideoControls(null);
  }, [setVideoControls]);


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
        items.forEach((item: any) => {
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
      return;
    }
    const spotifyTrackIds = tracks.map(resolveTrackId).filter(Boolean);
    if (spotifyTrackIds.length === 0) {
      setTrackLocalIds({});
      return;
    }
    let cancelled = false;
    const loadTrackIds = async () => {
      try {
        const res = await audio2Api.resolveTracks(spotifyTrackIds);
        if (cancelled) return;
        const next: Record<string, number> = {};
        (res.data?.items || []).forEach((item: any) => {
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

  const ensureTrackLocalId = useCallback(
    async (spotifyTrackId: string): Promise<number | null> => {
      const existing = trackLocalIds[spotifyTrackId];
      if (existing) return existing;
      try {
        const res = await audio2Api.resolveTracks([spotifyTrackId]);
        const items = res.data?.items || [];
        const match = items.find((item: any) => item.spotify_track_id === spotifyTrackId);
        if (match?.track_id) {
          setTrackLocalIds((prev) => ({ ...prev, [spotifyTrackId]: match.track_id }));
          return match.track_id as number;
        }
      } catch {
        // best effort
      }
      if (!spotifyId) return null;
      try {
        await audio2Api.saveAlbumToDb(spotifyId);
        const res = await audio2Api.resolveTracks([spotifyTrackId]);
        const items = res.data?.items || [];
        const match = items.find((item: any) => item.spotify_track_id === spotifyTrackId);
        if (match?.track_id) {
          setTrackLocalIds((prev) => ({ ...prev, [spotifyTrackId]: match.track_id }));
          return match.track_id as number;
        }
      } catch {
        // ignore
      }
      return null;
    },
    [spotifyId, trackLocalIds]
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
          if (!autoSearchOnPlay) {
            const next: YoutubeAvailability = { status: 'missing' };
            setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
            return next;
          }
          return refreshFromYoutube();
        }
      } catch (err: any) {
        if (!isMountedRef.current) {
          return null;
        }
        const statusCode = err?.response?.status;
        if (statusCode === 404) {
          if (!autoSearchOnPlay) {
            const next: YoutubeAvailability = { status: 'missing' };
            setYoutubeAvailability((prev) => ({ ...prev, [stateKey]: next }));
            return next;
          }
          return refreshFromYoutube();
        }
        const detail = err?.response?.data?.detail || err?.message || 'Error consultando YouTube';
        return setError(detail);
      }

      return null;
    },
    [album, resolveTrackId]
  );

  useEffect(() => {
    setYoutubeAvailability({});
    setStreamState({});
  }, [spotifyId]);

  useEffect(() => {
    if (playbackMode !== 'video') return;
    if (!ytReady || !nowPlaying || !playerContainerRef.current) return;
    const YT = (window as any).YT;
    const hasPlayerMethods =
      playerRef.current &&
      typeof playerRef.current.loadVideoById === 'function' &&
      typeof playerRef.current.playVideo === 'function';
    if (!hasPlayerMethods) {
      if (playerRef.current?.destroy) {
        playerRef.current.destroy();
      }
      playerRef.current = null;
    }
    if (!playerRef.current) {
      playerRef.current = new YT.Player(playerContainerRef.current, {
        videoId: nowPlaying.videoId,
        playerVars: {
          autoplay: 1,
          controls: 0,
          disablekb: 1,
          fs: 0,
          iv_load_policy: 3,
          modestbranding: 1,
          rel: 0,
          playsinline: 1,
          vq: 'small',
          origin: typeof window !== 'undefined' ? window.location.origin : undefined,
        },
        events: {
          onReady: (event: any) => {
            setDuration(event.target.getDuration() || 0);
            event.target.setVolume?.(volume);
            event.target.setPlaybackQuality?.('tiny');
            event.target.playVideo();
            setPlayerReady(true);
          },
          onStateChange: (event: any) => {
            const state = event.data;
            if (state === YT.PlayerState.PLAYING) {
              setIsPlaying(true);
              event.target.setPlaybackQuality?.('tiny');
              setPlayerReady(true);
            } else if (state === YT.PlayerState.PAUSED) {
              setIsPlaying(false);
              setPlayerReady(true);
            } else if (state === YT.PlayerState.BUFFERING) {
              setPlayerReady(true);
            } else if (state === YT.PlayerState.ENDED) {
              setIsPlaying(false);
            }
          },
        },
      });
      return;
    }
    if (typeof playerRef.current.loadVideoById === 'function') {
      playerRef.current.loadVideoById(nowPlaying.videoId);
    }
  }, [nowPlaying, ytReady, playbackMode]);

  useEffect(() => {
    if (!nowPlaying && playerRef.current) {
      playerRef.current.stopVideo();
      setIsPlaying(false);
      setCurrentTime(0);
      setDuration(0);
    }
  }, [nowPlaying]);

  useEffect(() => {
    setPlayerReady(false);
  }, [nowPlaying?.videoId, playbackMode]);

  useEffect(() => {
    if (playbackMode === 'audio') {
      playerRef.current?.stopVideo?.();
      setIsPlaying(false);
    }
  }, [playbackMode]);

  useEffect(() => {
    if (playbackMode !== 'audio') return;
    if (playerRef.current?.destroy) {
      playerRef.current.destroy();
    }
    playerRef.current = null;
  }, [playbackMode]);

  useEffect(() => {
    if (playbackMode !== 'video') return;
    if (!nowPlaying || !playerRef.current) return;
    const interval = window.setInterval(() => {
      try {
        const current = playerRef.current?.getCurrentTime?.();
        const total = playerRef.current?.getDuration?.();
        if (Number.isFinite(current)) {
          setCurrentTime(current);
        }
        if (Number.isFinite(total) && total > 0) {
          setDuration(total);
        }
      } catch {
        // ignore player polling errors
      }
    }, 1000);
    return () => {
      window.clearInterval(interval);
    };
  }, [nowPlaying, playbackMode]);

  useEffect(() => {
    if (playbackMode === 'video') {
      playerRef.current?.setVolume?.(volume);
    }
  }, [volume, playbackMode]);

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

    const cached = youtubeAvailability[stateKey];
    if (cached?.status === 'available' && cached.videoId) {
      setStream({ status: 'loading', message: playbackMode === 'audio' ? 'Abriendo audio...' : 'Abriendo YouTube...' });
      const nextNowPlaying = {
        title: track.name,
        artist: artistName,
        videoId: cached.videoId,
        spotifyTrackId: stateKey,
      };
      setNowPlaying(nextNowPlaying);
      const idx = tracks.findIndex((t) => resolveTrackId(t) === stateKey);
      if (idx >= 0) {
        setCurrentIndex(idx);
      }
      if (playbackMode === 'audio') {
        const result = await playByVideoId({
          ...nextNowPlaying,
          durationSec: track.duration_ms ? track.duration_ms / 1000 : undefined,
        });
        if (!result.ok) {
          setStream({ status: 'error', message: 'Pulsa play otra vez para iniciar el audio' });
          return;
        }
        setStream({ status: 'idle' });
      } else {
        setStream({ status: 'idle' });
      }
      return;
    }

    const info = await fetchYoutubeForTrack(track, stateKey);
    if (!info || info.status !== 'available') {
      const msg = autoSearchOnPlay ? 'Sin enlace de YouTube' : 'Sin enlace de YouTube (sin buscar)';
      setStream({ status: 'error', message: msg });
      return;
    }

    setStream({ status: 'loading', message: playbackMode === 'audio' ? 'Abriendo audio...' : 'Abriendo YouTube...' });
    const nextNowPlaying = {
      title: track.name,
      artist: artistName,
      videoId: info.videoId,
      spotifyTrackId: stateKey,
    };
    setNowPlaying(nextNowPlaying);
    const idx = tracks.findIndex((t) => resolveTrackId(t) === stateKey);
    if (idx >= 0) {
      setCurrentIndex(idx);
    }
    if (playbackMode === 'audio') {
      const result = await playByVideoId({
        ...nextNowPlaying,
        durationSec: track.duration_ms ? track.duration_ms / 1000 : undefined,
      });
      if (!result.ok) {
        setStream({ status: 'error', message: 'Pulsa play otra vez para iniciar el audio' });
        return;
      }
      setStream({ status: 'idle' });
    } else {
      setStream({ status: 'idle' });
    }
  };

  useEffect(() => {
    if (tracks.length === 0) return;
    const queueItems = tracks
      .map((track) => {
        const spotifyTrackId = resolveTrackId(track);
        if (!spotifyTrackId) return null;
        return {
          spotifyTrackId,
          title: track.name,
          artist: track.artists?.[0]?.name || album?.artists?.[0]?.name,
          durationMs: track.duration_ms,
          rawTrack: track,
        };
      })
      .filter(Boolean) as Array<{
        spotifyTrackId: string;
        title: string;
        artist?: string;
        durationMs?: number;
        rawTrack: Track;
      }>;
    setQueue(queueItems);
    setOnPlayTrack((item) => {
      if (!item.rawTrack) return;
      void handleStreamTrack(item.rawTrack, item.spotifyTrackId);
    });
    return () => setOnPlayTrack(null);
  }, [album?.artists, handleStreamTrack, resolveTrackId, setOnPlayTrack, setQueue, tracks]);

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
  const hasToken = typeof window !== 'undefined' && !!localStorage.getItem('token');
  const canFavorite = !!(effectiveTrackUserId || effectiveAlbumUserId || hasToken);

  if (!spotifyId) return <div className="card">Álbum no especificado.</div>;
  if (loading) return <div className="card">Cargando álbum...</div>;
  if (error) return <div className="card">Error: {error}</div>;
  if (!album) return <div className="card">Sin datos.</div>;

  const coverImageUrl = resolveImageUrl(album?.images?.[0]?.url);

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
          {playerReady && nowPlaying && playbackMode === 'video' && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: 12,
                boxShadow: '0 0 24px rgba(63, 255, 208, 0.15)',
              }}
            />
          )}
          <div
            ref={playerContainerRef}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              opacity: nowPlaying && playbackMode === 'video' && playerReady ? 1 : 0,
              pointerEvents: nowPlaying && playbackMode === 'video' && playerReady ? 'auto' : 'none',
              transition: 'opacity 200ms ease',
            }}
          />
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
                opacity: nowPlaying && playbackMode === 'video' && playerReady ? 0 : 1,
                transition: 'opacity 200ms ease',
              }}
            />
          )}
          {nowPlaying && playbackMode === 'video' && !playerReady && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--muted)',
                fontSize: 12,
                background: 'rgba(10, 14, 20, 0.35)',
              }}
            >
              Cargando video...
            </div>
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
          <button
            className="btn-ghost"
            style={{ borderRadius: 8, fontSize: 18, opacity: favoriteLoading ? 0.6 : 1 }}
            disabled={favoriteLoading || !canFavorite || !localAlbumId}
            onClick={async () => {
              if (!canFavorite || !localAlbumId) return;
              setFavoriteLoading(true);
              try {
                await toggleAlbumFavorite(localAlbumId);
              } catch (e) {
                // ignore error for now
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
        <div className="space-y-2">
          {tracks.map((t, idx) => {
            const rowKey = getRowKey(t, idx);
            const spotifyTrackId = resolveTrackId(t);
            const youtubeInfo = spotifyTrackId ? youtubeAvailability[spotifyTrackId] : undefined;
            const streamInfo = spotifyTrackId ? streamState[spotifyTrackId] : undefined;
            const trackLocalId = spotifyTrackId ? trackLocalIds[spotifyTrackId] : undefined;
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
                  </button>
                  {youtubeInfo?.status === 'available' && (
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
                  )}
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
                    disabled={!canFavorite || isTrackFavoriteLoading}
                    onClick={async () => {
                      if (!canFavorite || !spotifyTrackId) return;
                      setTrackFavoriteLoading((prev) => ({ ...prev, [spotifyTrackId]: true }));
                      try {
                        const resolvedId = trackLocalId || (await ensureTrackLocalId(spotifyTrackId));
                        if (!resolvedId) return;
                        await toggleTrackFavorite(resolvedId);
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
                    style={{ borderRadius: 8, fontSize: 12, padding: '6px 10px', opacity: 0.6 }}
                    disabled
                    title="Próximamente: añadir a lista"
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

    </div>
  );
}
