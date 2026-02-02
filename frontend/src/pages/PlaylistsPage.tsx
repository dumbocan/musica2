import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Play, Radio } from 'lucide-react';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { normalizeImageUrl } from '@/lib/images';
import { usePlayerStore } from '@/store/usePlayerStore';
import type { CuratedTrackItem, ListsOverviewResponse, PlaylistSection } from '@/types/api';
import type { PlayerQueueItem } from '@/store/usePlayerStore';

type LoadState = 'idle' | 'loading' | 'error';
const CARD_THEMES = [
  'from-amber-200/25 via-orange-200/10 to-rose-300/25',
  'from-cyan-200/25 via-sky-200/10 to-blue-300/25',
  'from-emerald-200/25 via-lime-200/10 to-teal-300/25',
  'from-pink-200/25 via-fuchsia-200/10 to-violet-300/25',
];

export function PlaylistsPage() {
  const [sections, setSections] = useState<PlaylistSection[]>([]);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [topGenres, setTopGenres] = useState<string[]>([]);
  const [anchorArtist, setAnchorArtist] = useState<ListsOverviewResponse['anchor_artist']>(null);
  const [artistQuery, setArtistQuery] = useState('');
  const [appliedArtist, setAppliedArtist] = useState('');

  const setQueue = usePlayerStore((state) => state.setQueue);
  const setOnPlayTrack = usePlayerStore((state) => state.setOnPlayTrack);
  const setCurrentIndex = usePlayerStore((state) => state.setCurrentIndex);
  const setStatusMessage = usePlayerStore((state) => state.setStatusMessage);
  const playByVideoId = usePlayerStore((state) => state.playByVideoId);

  const fetchLists = useCallback((artistName?: string) => {
    setLoadState('loading');
    audio2Api
      .getListsOverview({ limit_per_list: 12, artist_name: artistName || undefined })
      .then((response) => {
        setSections(response.data.lists ?? []);
        setTopGenres(response.data.top_genres ?? []);
        setAnchorArtist(response.data.anchor_artist ?? null);
        setLoadState('idle');
      })
      .catch(() => {
        setLoadState('error');
      });
  }, []);

  useEffect(() => {
    fetchLists();
  }, [fetchLists]);

  const handleApplyArtist = useCallback(() => {
    const value = artistQuery.trim();
    setAppliedArtist(value);
    fetchLists(value);
  }, [artistQuery, fetchLists]);

  const handleClearArtist = useCallback(() => {
    setArtistQuery('');
    setAppliedArtist('');
    fetchLists();
  }, [fetchLists]);

  const heroCopy = useMemo(() => {
    if (anchorArtist?.name) {
      return `Explora la discografía de ${anchorArtist.name} y listas relacionadas basadas en tus favoritos.`;
    }
    if (topGenres.length) {
      return `Listas animadas por tus géneros preferidos: ${topGenres.join(', ')}.`;
    }
    return 'Playlists inteligentes generadas desde tu biblioteca local.';
  }, [anchorArtist, topGenres]);

  const createQueueItem = useCallback((track: CuratedTrackItem): PlayerQueueItem | null => {
    if (!track.videoId) {
      return null;
    }
    const primaryArtist = track.artists?.[0];
    return {
      localTrackId: track.id,
      spotifyTrackId: track.spotify_id || `local-${track.id}`,
      title: track.name,
      artist: primaryArtist?.name,
      artistSpotifyId: primaryArtist?.spotify_id ?? undefined,
      durationMs: track.duration_ms ?? undefined,
      videoId: track.videoId,
    };
  }, []);

  const patchTrackVideoId = useCallback((sectionKey: string, trackId: number, videoId: string) => {
    setSections((prev) =>
      prev.map((section) =>
        section.key !== sectionKey
          ? section
          : {
              ...section,
              items: section.items.map((item) => (item.id === trackId ? { ...item, videoId } : item)),
            }
      )
    );
  }, []);

  const resolveYoutubeIfNeeded = useCallback(
    async (sectionKey: string, track: CuratedTrackItem): Promise<CuratedTrackItem | null> => {
      if (track.videoId) return track;
      // DB-first policy: if we already have local file in DB, do not hit YouTube.
      if (track.download_path) return null;
      if (!track.spotify_id) return null;
      try {
        const response = await audio2Api.refreshYoutubeTrackLink(track.spotify_id, {
          artist: track.artists?.[0]?.name,
          track: track.name,
          album: track.album?.name || undefined,
        });
        const videoId = response.data?.youtube_video_id;
        if (!videoId) return null;
        patchTrackVideoId(sectionKey, track.id, videoId);
        return { ...track, videoId };
      } catch {
        return null;
      }
    },
    [patchTrackVideoId]
  );

  const queueHandler = useCallback(
    (item: PlayerQueueItem) => {
      if (!item || !item.videoId) {
        setStatusMessage('La pista necesita un enlace de YouTube para reproducirse');
        return;
      }
      const currentQueue = usePlayerStore.getState().queue;
      const idx = currentQueue.findIndex((entry) => entry.videoId === item.videoId);
      if (idx >= 0) {
        setCurrentIndex(idx);
      }
      setStatusMessage('');
      void playByVideoId({
        localTrackId: item.localTrackId,
        spotifyTrackId: item.spotifyTrackId,
        title: item.title,
        artist: item.artist,
        artistSpotifyId: item.artistSpotifyId,
        videoId: item.videoId,
        durationSec: item.durationMs ? Math.round(item.durationMs / 1000) : undefined,
      });
    },
    [playByVideoId, setCurrentIndex, setStatusMessage]
  );

  const applyQueue = useCallback(
    async (sectionKey: string, tracks: CuratedTrackItem[]) => {
      const resolved: CuratedTrackItem[] = [];
      for (const track of tracks.slice(0, 12)) {
        if (track.videoId) {
          resolved.push(track);
          continue;
        }
        const withLink = await resolveYoutubeIfNeeded(sectionKey, track);
        if (withLink?.videoId) {
          resolved.push(withLink);
        }
      }
      const items = resolved.map(createQueueItem).filter((item): item is PlayerQueueItem => Boolean(item));
      if (!items.length) {
        setStatusMessage('Sin enlaces listos; solo se busco en YouTube para tracks sin archivo local');
        return;
      }
      setQueue(items, 0);
      setCurrentIndex(0);
      setOnPlayTrack(queueHandler);
      setStatusMessage('');
      queueHandler(items[0]);
    },
    [
      createQueueItem,
      queueHandler,
      resolveYoutubeIfNeeded,
      setCurrentIndex,
      setOnPlayTrack,
      setQueue,
      setStatusMessage,
    ]
  );

  const handleSingleTrackPlay = useCallback(
    async (sectionKey: string, track: CuratedTrackItem) => {
      if (track.videoId) {
        await applyQueue(sectionKey, [track]);
        return;
      }
      if (track.download_path) {
        setStatusMessage('Archivo local en BD: no se consulta YouTube para esta cancion');
        return;
      }
      const withLink = await resolveYoutubeIfNeeded(sectionKey, track);
      if (!withLink?.videoId) {
        setStatusMessage('No se encontro enlace en YouTube');
        return;
      }
      await applyQueue(sectionKey, [withLink]);
    },
    [applyQueue, resolveYoutubeIfNeeded, setStatusMessage]
  );

  const getTrackImage = useCallback((track?: CuratedTrackItem | null) => {
    if (!track?.image_url) return '';
    return normalizeImageUrl({
      candidate: track.image_url,
      size: 256,
      apiBaseUrl: API_BASE_URL,
    });
  }, []);

  const renderStatus = () => {
    if (loadState === 'loading') {
      return (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Cargando listas curatoriales…
        </div>
      );
    }
    if (loadState === 'error') {
      return (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          No pudimos obtener las listas. Intenta nuevamente más tarde.
        </div>
      );
    }
    if (loadState === 'idle' && !sections.length) {
      return (
        <div className="rounded-2xl border border-border/70 bg-panel-foreground/5 p-6 text-sm text-muted-foreground">
          Aún no hay listas generadas para tu biblioteca. Marca favoritos o reproduce canciones para activar las sugerencias.
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">Playlists</p>
        <h1 className="text-3xl font-bold">Listas inteligentes</h1>
        <p className="text-sm text-muted-foreground">{heroCopy}</p>
        <div className="flex flex-wrap items-center gap-2 pt-2">
          <input
            type="text"
            value={artistQuery}
            onChange={(e) => setArtistQuery(e.target.value)}
            placeholder="Artista para top personalizado (ej: Eminem)"
            className="min-w-[280px] rounded-xl border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={handleApplyArtist}
            className="rounded-xl border border-border bg-panel px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em]"
          >
            Aplicar artista
          </button>
          <button
            type="button"
            onClick={handleClearArtist}
            className="rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em]"
          >
            Limpiar
          </button>
          {appliedArtist && (
            <span className="rounded-xl border border-border/70 bg-panel px-3 py-2 text-xs text-muted-foreground">
              Top artista activo: {appliedArtist}
            </span>
          )}
        </div>
      </header>

      {renderStatus()}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {sections.map((section, sectionIndex) => (
          <section
            key={section.key}
            id={section.key}
            className="overflow-hidden rounded-3xl border border-border/80 bg-panel shadow-sm"
          >
            <div
              className={`relative border-b border-border/70 bg-gradient-to-br ${
                CARD_THEMES[sectionIndex % CARD_THEMES.length]
              } p-5`}
            >
              <div className="mb-3 flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => void applyQueue(section.key, section.items)}
                    className="inline-flex items-center gap-2 text-left text-xl font-bold transition hover:text-accent"
                    aria-label={`Reproducir lista ${section.title}`}
                  >
                    <Play className="h-5 w-5" />
                    {section.title}
                  </button>
                  <p className="text-sm text-foreground/80">{section.description}</p>
                </div>
                <div className="rounded-xl border border-foreground/15 bg-white/30 px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em]">
                  {section.items.length} tracks
                </div>
              </div>
              {section.meta?.genres && (
                <p className="text-xs uppercase tracking-[0.2em] text-foreground/70">
                  {section.meta.genres.join(' · ')}
                </p>
              )}
              {(() => {
                const sectionImage = getTrackImage(section.items[0]);
                return (
                  <div className="mt-4 h-36 overflow-hidden rounded-2xl border border-white/30 bg-black/10">
                    {sectionImage ? (
                  <img
                    src={sectionImage}
                    alt={section.title}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-lg text-white/80">
                    <Radio className="h-6 w-6" />
                  </div>
                )}
                  </div>
                );
              })()}
            </div>
            <ol className="space-y-2 p-4">
              {section.items.map((track, index) => {
                const primaryArtist = track.artists?.[0]?.name;
                return (
                  <li
                    key={`${section.key}-${track.id}-${track.videoId || 'no-video'}`}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-background/70 px-3 py-2 text-sm text-foreground"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => void handleSingleTrackPlay(section.key, track)}
                          className="truncate text-left font-semibold text-accent underline-offset-2 hover:underline"
                        >
                          {track.name}
                        </button>
                        <p className="truncate text-xs text-muted-foreground">
                          {primaryArtist || 'Artista desconocido'}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">{track.videoId ? 'reproducir' : 'sin enlace'}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
