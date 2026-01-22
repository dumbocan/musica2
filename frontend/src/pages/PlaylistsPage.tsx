import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { audio2Api } from '@/lib/api';
import { usePlayerStore } from '@/store/usePlayerStore';
import type { CuratedTrackItem, ListsOverviewResponse, PlaylistSection } from '@/types/api';
import type { PlayerQueueItem } from '@/store/usePlayerStore';

type LoadState = 'idle' | 'loading' | 'error';

export function PlaylistsPage() {
  const [sections, setSections] = useState<PlaylistSection[]>([]);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [topGenres, setTopGenres] = useState<string[]>([]);
  const [anchorArtist, setAnchorArtist] = useState<ListsOverviewResponse['anchor_artist']>(null);

  const setQueue = usePlayerStore((state) => state.setQueue);
  const setOnPlayTrack = usePlayerStore((state) => state.setOnPlayTrack);
  const setCurrentIndex = usePlayerStore((state) => state.setCurrentIndex);
  const setStatusMessage = usePlayerStore((state) => state.setStatusMessage);
  const playByVideoId = usePlayerStore((state) => state.playByVideoId);

  useEffect(() => {
    setLoadState('loading');
    audio2Api
      .getListsOverview({ limit_per_list: 12 })
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
      artistSpotifyId: primaryArtist?.spotify_id,
      durationMs: track.duration_ms ?? undefined,
      videoId: track.videoId,
    };
  }, []);

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
    (tracks: CuratedTrackItem[]) => {
      const items = tracks
        .map(createQueueItem)
        .filter((item): item is PlayerQueueItem => Boolean(item));
      if (!items.length) {
        setStatusMessage('No hay pistas con enlaces de YouTube disponibles para esta lista');
        return;
      }
      setQueue(items, 0);
      setCurrentIndex(0);
      setOnPlayTrack(queueHandler);
      setStatusMessage('');
      queueHandler(items[0]);
    },
    [createQueueItem, queueHandler, setCurrentIndex, setOnPlayTrack, setQueue, setStatusMessage]
  );

  const handleSingleTrackPlay = useCallback(
    (track: CuratedTrackItem) => {
      applyQueue([track]);
    },
    [applyQueue]
  );

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
      </header>

      {renderStatus()}

      {sections.map((section) => (
        <section
          key={section.key}
          id={section.key}
          className="space-y-4 rounded-3xl border border-border bg-panel p-6 shadow-sm"
        >
        <div>
          <h2 className="text-xl font-semibold">
            <a
              href={`#${section.key}`}
              className="hover:text-accent transition-colors duration-150"
              aria-label={`Abrir lista ${section.title}`}
            >
              {section.title}
            </a>
          </h2>
          <p className="text-sm text-muted-foreground">{section.description}</p>
          {section.meta?.genres && (
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              {section.meta.genres.join(' · ')}
            </p>
          )}
        </div>
          <ol className="space-y-3">
            {section.items.map((track, index) => {
              const primaryArtist = track.artists?.[0]?.name;
              return (
                <li
                  key={`${section.key}-${track.id}-${track.videoId || 'no-video'}`}
                  className="flex flex-wrap items-center justify-between rounded-2xl border border-border/70 bg-background/70 p-3 text-sm text-foreground"
                >
                  <div className="flex w-full flex-col gap-1 md:w-2/3">
                    <div className="flex items-center gap-3">
                      <span className="text-xs uppercase tracking-[0.3em] text-muted-foreground">{index + 1}</span>
                      <span className="font-semibold">{track.name}</span>
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      {primaryArtist && <span>{primaryArtist}</span>}
                      {track.album?.name && (
                        <span>
                          {track.album.name} · {track.album.release_date}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      disabled={!track.videoId}
                      onClick={() => handleSingleTrackPlay(track)}
                      className="rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {track.videoId ? 'Play' : 'Sin enlace'}
                    </button>
                    <span className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
                      Pop {Math.round((track.popularity || 0) * 10) / 10}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
