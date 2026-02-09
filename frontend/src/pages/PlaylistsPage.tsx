import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Play, Plus, Radio, Trash2 } from 'lucide-react';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { normalizeImageUrl } from '@/lib/images';
import { usePlayerStore } from '@/store/usePlayerStore';
import { usePlaylistTrackRemoval } from '@/hooks/usePlaylistTrackRemoval';
import type { CuratedTrackItem, ListsOverviewResponse, Playlist as PlaylistType, PlaylistSection } from '@/types/api';
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

  // User playlists state
  const [userPlaylists, setUserPlaylists] = useState<PlaylistType[]>([]);
  const [userPlaylistsLoading, setUserPlaylistsLoading] = useState(false);
  const [creatingPlaylist, setCreatingPlaylist] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedPlaylist, setExpandedPlaylist] = useState<number | null>(null);
  const [playlistTracks, setPlaylistTracks] = useState<Array<{ id?: number; name?: string; artist?: string }>>([]);
  const [playlistTracksLoading, setPlaylistTracksLoading] = useState(false);
  const [removingTrackId, setRemovingTrackId] = useState<number | null>(null);
  const [deletingPlaylistId, setDeletingPlaylistId] = useState<number | null>(null);

  const setQueue = usePlayerStore((state) => state.setQueue);
  const setOnPlayTrack = usePlayerStore((state) => state.setOnPlayTrack);
  const setCurrentIndex = usePlayerStore((state) => state.setCurrentIndex);
  const setStatusMessage = usePlayerStore((state) => state.setStatusMessage);
  const playByVideoId = usePlayerStore((state) => state.playByVideoId);
  const removeFromQueue = usePlayerStore((state) => state.removeFromQueue);

  // Hook para eliminar tracks de playlists
  const { removeTrackFromPlaylist } = usePlaylistTrackRemoval({
    onSuccess: (message) => setStatusMessage(message),
    onError: (message) => setStatusMessage(message),
  });

  // Fetch curated lists using unified tracks endpoint with smart lists
  // Sequential loading to prevent backend overload
  const fetchLists = useCallback(async (artistName?: string) => {
    setLoadState('loading');
    const lists = [];

    try {
      // Map tracks/overview format to CuratedTrackItem format
      const mapTrackToCurated = (track: any): CuratedTrackItem => ({
        id: track.track_id,
        spotify_id: track.spotify_id,
        name: track.name,
        duration_ms: track.duration_ms,
        popularity: track.popularity,
        is_favorite: track.is_favorite || false,
        download_status: track.download_status,
        download_path: track.download_path,
        videoId: track.videoId,
        album: track.album || null,
        artists: track.artists || [],
      });

      // Load lists sequentially with individual error handling
      // This prevents one slow query from blocking everything

      // 1. Quick lists first (favorites with link)
      try {
        const favoritesWithLinkRes = await audio2Api.getTracksOverview({ 
          list_type: 'favorites-with-link', 
          limit: 12 
        });
        if (favoritesWithLinkRes.data?.items?.length > 0) {
          lists.push({
            key: 'favorites-with-link',
            title: 'Favoritos con enlace',
            description: 'Tus canciones favoritas que ya tienen enlace de YouTube listo para reproducir.',
            items: favoritesWithLinkRes.data.items.map(mapTrackToCurated),
            meta: { count: favoritesWithLinkRes.data.items.length },
          });
        }
      } catch (e) {
        console.warn('Failed to load favorites with link:', e);
      }

      // 2. Downloaded tracks
      try {
        const downloadedRes = await audio2Api.getTracksOverview({ 
          list_type: 'downloaded', 
          limit: 12 
        });
        if (downloadedRes.data?.items?.length > 0) {
          lists.push({
            key: 'downloaded-local',
            title: 'Música descargada',
            description: 'Canciones con archivo local disponible en tu biblioteca.',
            items: downloadedRes.data.items.map(mapTrackToCurated),
            meta: { count: downloadedRes.data.items.length, note: 'Reproducción local' },
          });
        }
      } catch (e) {
        console.warn('Failed to load downloaded tracks:', e);
      }

      // 3. Discovery (random unplayed)
      try {
        const discoveryRes = await audio2Api.getTracksOverview({ 
          list_type: 'discovery', 
          limit: 12 
        });
        if (discoveryRes.data?.items?.length > 0) {
          lists.push({
            key: 'discovery',
            title: 'Descubrimiento',
            description: 'Canciones que no has escuchado recientemente de tu biblioteca.',
            items: discoveryRes.data.items,
            meta: { count: discoveryRes.data.items.length },
          });
        }
      } catch (e) {
        console.warn('Failed to load discovery:', e);
      }

      // 4. Top year (can be slow - lower timeout)
      try {
        const topYearRes = await audio2Api.getTracksOverview({ 
          list_type: 'top-year', 
          limit: 12 
        });
        if (topYearRes.data?.items?.length > 0) {
          lists.push({
            key: 'top-last-year',
            title: 'Mejores del último año',
            description: 'Ranking personal según tus reproducciones, ratings y recencia en los últimos 365 días.',
            items: topYearRes.data.items,
            meta: { count: topYearRes.data.items.length, note: 'DB-first personalizado' },
          });
        }
      } catch (e) {
        console.warn('Failed to load top year:', e);
      }

      // 5. Most played (can be slow)
      try {
        const mostPlayedRes = await audio2Api.getTracksOverview({ 
          list_type: 'most-played', 
          limit: 12 
        });
        if (mostPlayedRes.data?.items?.length > 0) {
          lists.push({
            key: 'most-played',
            title: 'Más reproducidas',
            description: 'Tus canciones más escuchadas de todos los tiempos.',
            items: mostPlayedRes.data.items,
            meta: { count: mostPlayedRes.data.items.length },
          });
        }
      } catch (e) {
        console.warn('Failed to load most played:', e);
      }

      // 6. Genre suggestions (can be slow)
      try {
        const genreSuggestionsRes = await audio2Api.getTracksOverview({ 
          list_type: 'genre-suggestions', 
          limit: 12 
        });
        if (genreSuggestionsRes.data?.items?.length > 0) {
          lists.push({
            key: 'genre-suggestions',
            title: 'Géneros parecidos',
            description: 'Tracks de géneros vinculados a tus artistas favoritos.',
            items: genreSuggestionsRes.data.items,
            meta: { count: genreSuggestionsRes.data.items.length },
          });
        }
      } catch (e) {
        console.warn('Failed to load genre suggestions:', e);
      }

      setSections(lists);
      setTopGenres([]);
      setAnchorArtist(null);
      setLoadState('idle');
    } catch (error) {
      console.error('Error fetching lists:', error);
      setLoadState('error');
    }
  }, []);

  useEffect(() => {
    fetchLists();
  }, [fetchLists]);

  // Load user playlists
  const fetchUserPlaylists = useCallback(() => {
    setUserPlaylistsLoading(true);
    audio2Api
      .getAllPlaylists()
      .then((res) => {
        setUserPlaylists(res.data || []);
      })
      .catch(() => {
        // ignore error
      })
      .finally(() => {
        setUserPlaylistsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchUserPlaylists();
  }, [fetchUserPlaylists]);

  // Escuchar cuando se elimina una playlist desde otros componentes (PlayerFooter)
  useEffect(() => {
    const handlePlaylistDeleted = (event: CustomEvent) => {
      const { playlistId } = event.detail;
      
      // Eliminar de la lista de playlists
      setUserPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
      
      // Si estaba expandida, limpiar
      if (expandedPlaylist === playlistId) {
        setExpandedPlaylist(null);
        setPlaylistTracks([]);
      }
    };

    window.addEventListener('playlist-deleted', handlePlaylistDeleted as EventListener);
    
    // Escuchar cuando se crea una playlist desde otros componentes
    const handlePlaylistCreated = (event: CustomEvent) => {
      const { playlist } = event.detail;
      if (playlist) {
        setUserPlaylists((prev) => {
          // Verificar si ya existe para no duplicar
          if (prev.some((p) => p.id === playlist.id)) return prev;
          return [playlist, ...prev];
        });
      }
    };
    window.addEventListener('playlist-created', handlePlaylistCreated as EventListener);
    
    return () => {
      window.removeEventListener('playlist-deleted', handlePlaylistDeleted as EventListener);
      window.removeEventListener('playlist-created', handlePlaylistCreated as EventListener);
    };
  }, [expandedPlaylist]);

  // Handle create playlist
  const handleCreatePlaylist = useCallback(async () => {
    const name = newPlaylistName.trim();
    if (!name) return;
    setCreatingPlaylist(true);
    try {
      const res = await audio2Api.createPlaylist({ name, user_id: 1 });
      const created = res.data as PlaylistType;
      setUserPlaylists((prev) => [created, ...prev]);
      setNewPlaylistName('');
      setShowCreateForm(false);
      setExpandedPlaylist(created.id);
    } catch {
      setStatusMessage('No se pudo crear la lista');
    } finally {
      setCreatingPlaylist(false);
    }
  }, [newPlaylistName, setStatusMessage]);

  // Handle delete playlist
  const handleDeletePlaylist = useCallback(async (playlistId: number) => {
    if (!confirm('¿Eliminar esta lista?')) return;
    setDeletingPlaylistId(playlistId);
    try {
      // 1. Llamar a la API para eliminar la playlist de la BD
      await audio2Api.deletePlaylist(playlistId);
      
      // 2. Actualizar UI - quitar de la lista local
      setUserPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
      
      // 3. Si estaba expandida, limpiar
      if (expandedPlaylist === playlistId) {
        setExpandedPlaylist(null);
        setPlaylistTracks([]);
      }
      
      // 4. Notificar a otros componentes (PlayerFooter) que la playlist fue eliminada
      window.dispatchEvent(new CustomEvent('playlist-deleted', { 
        detail: { playlistId } 
      }));
      
      setStatusMessage('Lista eliminada correctamente');
    } catch (error: any) {
      console.error('Error eliminando playlist:', error);
      setStatusMessage('No se pudo eliminar la lista: ' + (error.message || 'Error desconocido'));
    } finally {
      setDeletingPlaylistId(null);
    }
  }, [expandedPlaylist, setStatusMessage]);

  // Load playlist tracks when expanded
  useEffect(() => {
    if (!expandedPlaylist) {
      setPlaylistTracks([]);
      return;
    }
    let cancelled = false;
    setPlaylistTracksLoading(true);
    audio2Api
      .getPlaylistTracks(expandedPlaylist)
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res.data) ? res.data : [];
        setPlaylistTracks(
          items.map((item: { id?: number; name?: string; artist?: { name?: string } }) => ({
            id: item.id,
            name: item.name,
            artist: item.artist?.name,
          }))
        );
      })
      .catch(() => {
        if (!cancelled) setPlaylistTracks([]);
      })
      .finally(() => {
        if (!cancelled) setPlaylistTracksLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expandedPlaylist]);

  // Remove track from playlist (usa hook reutilizable)
  const handleRemoveTrack = useCallback(async (trackId: number) => {
    if (!expandedPlaylist) return;
    setRemovingTrackId(trackId);

    const result = await removeTrackFromPlaylist(expandedPlaylist, trackId);

    if (result.tracks) {
      setPlaylistTracks(
        result.tracks.map((item: any) => ({
          id: item.id,
          name: item.name,
          artist: item.artist?.name,
        }))
      );
    }

    setRemovingTrackId(null);
  }, [expandedPlaylist, removeTrackFromPlaylist]);

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
      if (!item) {
        setStatusMessage('Pista inválida');
        return;
      }
      // DB-FIRST: Let playByVideoId handle missing videoId (it will search YouTube)
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
        videoId: item.videoId || '',
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

      {/* User Playlists Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">Mis playlists</p>
            <h2 className="text-xl font-bold">Tus listas guardadas</h2>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
          >
            <Plus className="h-4 w-4" />
            Nueva lista
          </button>
        </div>

        {/* Create Form */}
        {showCreateForm && (
          <div className="mb-4 rounded-xl border border-border bg-panel p-4">
            <div className="flex flex-wrap gap-3 items-end">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground mb-2">
                  Nombre de la lista
                </label>
                <input
                  type="text"
                  value={newPlaylistName}
                  onChange={(e) => setNewPlaylistName(e.target.value)}
                  placeholder="Mi playlist..."
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleCreatePlaylist();
                    if (e.key === 'Escape') setShowCreateForm(false);
                  }}
                />
              </div>
              <button
                type="button"
                onClick={() => void handleCreatePlaylist()}
                disabled={creatingPlaylist || !newPlaylistName.trim()}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-50"
              >
                {creatingPlaylist ? 'Creando...' : 'Crear'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewPlaylistName('');
                }}
                className="rounded-lg border border-border bg-background px-4 py-2 text-sm"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Playlists Grid */}
        {userPlaylistsLoading ? (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Cargando playlists...
          </div>
        ) : userPlaylists.length === 0 ? (
          <div className="rounded-xl border border-border/70 bg-panel-foreground/5 p-6 text-sm text-muted-foreground">
            No tienes playlists creadas. Crea una nueva para añadir tus canciones favoritas.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {userPlaylists.map((playlist) => (
              <div
                key={playlist.id}
                className="group relative rounded-xl border border-border bg-panel overflow-hidden"
              >
                <div className="p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-semibold truncate">{playlist.name}</h3>
                      {playlist.description && (
                        <p className="text-xs text-muted-foreground truncate mt-1">{playlist.description}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleDeletePlaylist(playlist.id!)}
                      disabled={deletingPlaylistId === playlist.id}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                      title="Eliminar lista"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div className="px-4 pb-4">
                  <button
                    type="button"
                    onClick={() => setExpandedPlaylist(expandedPlaylist === playlist.id ? null : playlist.id!)}
                    className="w-full rounded-lg border border-border bg-background py-2 text-sm font-medium transition hover:bg-panel"
                  >
                    {expandedPlaylist === playlist.id ? 'Ocultar' : 'Ver canciones'}
                  </button>
                </div>

                {/* Expanded Track List */}
                {expandedPlaylist === playlist.id && (
                  <div className="border-t border-border bg-panel-foreground/30 p-4 max-h-64 overflow-auto">
                    {playlistTracksLoading ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Cargando...
                      </div>
                    ) : playlistTracks.length > 0 ? (
                      <div className="space-y-2">
                        {playlistTracks.map((track, idx) => (
                          <div
                            key={`${track.id || idx}-${track.name || ''}`}
                            className="flex items-center justify-between gap-2 text-sm py-1.5"
                          >
                            <span className="truncate min-w-0">
                              {track.name || 'Sin título'}
                              {track.artist && (
                                <span className="text-muted-foreground"> · {track.artist}</span>
                              )}
                            </span>
                            {track.id && (
                              <button
                                type="button"
                                onClick={() => void handleRemoveTrack(track.id!)}
                                disabled={removingTrackId === track.id}
                                className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                                title="Eliminar"
                              >
                                {removingTrackId === track.id ? '...' : '×'}
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground py-2">
                        Esta lista está vacía. Añade canciones desde cualquier pista.
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

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
