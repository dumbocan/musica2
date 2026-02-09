import { useCallback, useEffect, useState } from 'react';
import { Loader2, Play, Plus, Radio, Trash2, RefreshCw } from 'lucide-react';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { normalizeImageUrl } from '@/lib/images';
import { usePlayerStore } from '@/store/usePlayerStore';
import { usePlaylistTrackRemoval } from '@/hooks/usePlaylistTrackRemoval';
import type { CuratedTrackItem, Playlist as PlaylistType, PlaylistSection } from '@/types/api';
import type { PlayerQueueItem } from '@/store/usePlayerStore';

type LoadState = 'idle' | 'loading' | 'error';
const CARD_THEMES = [
  'from-amber-200/25 via-orange-200/10 to-rose-300/25',
  'from-cyan-200/25 via-sky-200/10 to-blue-300/25',
  'from-emerald-200/25 via-lime-200/10 to-teal-300/25',
  'from-pink-200/25 via-fuchsia-200/10 to-violet-300/25',
];

const LIST_TITLES: Record<string, string> = {
  'favorites-with-link': 'Favoritos con enlace',
  'downloaded': 'Música descargada',
  'discovery': 'Descubrimiento',
  'top-year': 'Mejores del último año',
  'most-played': 'Más reproducidas',
  'genre-suggestions': 'Géneros parecidos',
};

const LIST_DESCRIPTIONS: Record<string, string> = {
  'favorites-with-link': 'Tus canciones favoritas que ya tienen enlace de YouTube listo para reproducir.',
  'downloaded': 'Canciones con archivo local disponible en tu biblioteca.',
  'discovery': 'Canciones que no has escuchado recientemente de tu biblioteca.',
  'top-year': 'Ranking personal según tus reproducciones en los últimos 365 días.',
  'most-played': 'Tus canciones más escuchadas de todos los tiempos.',
  'genre-suggestions': 'Tracks de géneros vinculados a tus artistas favoritos.',
};

// Map cached list format to CuratedTrackItem
// Handles both flat format (from lists_cache) and nested format (from smart_lists)
const mapCachedTrackToCurated = (track: any): CuratedTrackItem => {
  // Handle nested artists array format (from smart_lists)
  if (track.artists && Array.isArray(track.artists) && track.artists.length > 0) {
    return {
      id: track.id,
      spotify_id: track.spotify_id,
      name: track.name,
      duration_ms: track.duration_ms,
      popularity: track.popularity,
      is_favorite: track.is_favorite || false,
      download_status: track.download_status,
      download_path: track.download_path,
      videoId: track.videoId,
      image_url: track.image_url,
      album: track.album || null,
      artists: track.artists,
    };
  }
  
  // Handle flat format (from lists_cache)
  return {
    id: track.id,
    spotify_id: track.spotify_id,
    name: track.name,
    duration_ms: track.duration_ms,
    popularity: track.popularity,
    is_favorite: track.is_favorite || false,
    download_status: track.download_status,
    download_path: track.download_path,
    videoId: track.videoId,
    image_url: track.image_url,
    album: track.album_name ? {
      id: track.id,
      spotify_id: track.album_spotify_id,
      name: track.album_name,
      release_date: ''
    } : null,
    artists: track.artist_name ? [{
      id: track.id,
      name: track.artist_name,
      spotify_id: track.artist_spotify_id
    }] : [],
  };
};

export function PlaylistsPage() {
  const [sections, setSections] = useState<PlaylistSection[]>([]);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  
  // Filters
  const [selectedGenre, setSelectedGenre] = useState<string>('');
  const [selectedArtist, setSelectedArtist] = useState<string>('');
  const [availableGenres] = useState<string[]>([]);
  const [availableArtists] = useState<Array<{id: number, name: string}>>([]);

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

  const { removeTrackFromPlaylist } = usePlaylistTrackRemoval({
    onSuccess: (message) => setStatusMessage(message),
    onError: (message) => setStatusMessage(message),
  });

  // Fetch curated lists from cache
  const fetchLists = useCallback(async (forceRefresh = false) => {
    setLoadState('loading');
    try {
      const response = await audio2Api.getCachedLists({ 
        user_id: 1,
        force_refresh: forceRefresh 
      });
      
      if (response.data?.lists) {
        const lists: PlaylistSection[] = [];
        let latestUpdate: Date | null = null;
        
        Object.entries(response.data.lists).forEach(([key, listData]: [string, any]) => {
          const items = (listData.items || []).map(mapCachedTrackToCurated);
          
          lists.push({
            key,
            title: LIST_TITLES[key] || listData.title,
            description: LIST_DESCRIPTIONS[key] || listData.description,
            items,
            meta: { 
              count: items.length,
              total_available: listData.total,
              is_cached: listData.is_cached 
            },
          });
          
          // Track latest update time
          if (listData.last_updated) {
            const updateTime = new Date(listData.last_updated);
            if (!latestUpdate || updateTime > latestUpdate) {
              latestUpdate = updateTime;
            }
          }
        });
        
        setSections(lists);
        setLastUpdated(latestUpdate);
      }
      
      setLoadState('idle');
    } catch (error) {
      console.error('Error fetching cached lists:', error);
      setLoadState('error');
    }
  }, []);

  // Refresh lists
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await audio2Api.refreshCachedLists();
      await fetchLists(true);
      setStatusMessage('Listas actualizadas');
    } catch (error) {
      setStatusMessage('Error al actualizar listas');
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchLists, setStatusMessage]);

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
      await audio2Api.deletePlaylist(playlistId);
      setUserPlaylists((prev) => prev.filter((p) => p.id !== playlistId));
      if (expandedPlaylist === playlistId) {
        setExpandedPlaylist(null);
        setPlaylistTracks([]);
      }
      window.dispatchEvent(new CustomEvent('playlist-deleted', { 
        detail: { playlistId } 
      }));
      setStatusMessage('Lista eliminada correctamente');
    } catch (error: any) {
      setStatusMessage('No se pudo eliminar la lista');
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

  // Remove track from playlist
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

  // Queue management
  const createQueueItem = useCallback((track: CuratedTrackItem): PlayerQueueItem | null => {
    if (!track.videoId) return null;
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

  const applyQueue = useCallback(
    async (_sectionKey: string, tracks: CuratedTrackItem[]) => {
      const items = tracks
        .slice(0, 50)
        .map(createQueueItem)
        .filter((item): item is PlayerQueueItem => Boolean(item));
      
      if (!items.length) {
        setStatusMessage('Sin enlaces disponibles');
        return;
      }
      
      setQueue(items, 0);
      setCurrentIndex(0);
      setOnPlayTrack((item: PlayerQueueItem) => {
        if (!item) {
          setStatusMessage('Pista inválida');
          return;
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
      });
      
      // Play first item
      const first = items[0];
      void playByVideoId({
        localTrackId: first.localTrackId,
        spotifyTrackId: first.spotifyTrackId,
        title: first.title,
        artist: first.artist,
        artistSpotifyId: first.artistSpotifyId,
        videoId: first.videoId || '',
        durationSec: first.durationMs ? Math.round(first.durationMs / 1000) : undefined,
      });
    },
    [createQueueItem, playByVideoId, setCurrentIndex, setOnPlayTrack, setQueue, setStatusMessage]
  );

  const handleSingleTrackPlay = useCallback(
    async (track: CuratedTrackItem) => {
      if (!track.videoId) {
        setStatusMessage('Track sin enlace de YouTube');
        return;
      }
      await applyQueue('single', [track]);
    },
    [applyQueue, setStatusMessage]
  );

  const getTrackImage = useCallback((track?: CuratedTrackItem | null) => {
    if (!track?.image_url) return '';
    return normalizeImageUrl({
      candidate: track.image_url,
      size: 256,
      apiBaseUrl: API_BASE_URL,
    });
  }, []);

  return (
    <div className="space-y-8">
      {/* Header with controls */}
      <header className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">Playlists</p>
            <h1 className="text-3xl font-bold">Listas inteligentes</h1>
          </div>
          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-panel px-4 py-2 text-sm font-semibold hover:bg-accent/10 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Actualizando...' : 'Actualizar listas'}
          </button>
        </div>
        
        <p className="text-sm text-muted-foreground">
          {lastUpdated 
            ? `Última actualización: ${lastUpdated.toLocaleString()}` 
            : 'Listas generadas desde tu biblioteca local.'}
        </p>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <select
            value={selectedGenre}
            onChange={(e) => setSelectedGenre(e.target.value)}
            className="min-w-[180px] rounded-xl border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Todos los géneros</option>
            {availableGenres.map((genre) => (
              <option key={genre} value={genre}>{genre}</option>
            ))}
          </select>
          
          <select
            value={selectedArtist}
            onChange={(e) => setSelectedArtist(e.target.value)}
            className="min-w-[180px] rounded-xl border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Todos los artistas</option>
            {availableArtists.map((artist) => (
              <option key={artist.id} value={artist.id}>{artist.name}</option>
            ))}
          </select>
        </div>
      </header>

      {/* Loading/Error states */}
      {loadState === 'loading' && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Cargando listas curatoriales...
        </div>
      )}
      
      {loadState === 'error' && (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          No pudimos obtener las listas. Intenta nuevamente más tarde.
        </div>
      )}

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

      {/* Curated Lists Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {sections.map((section, sectionIndex) => (
          <section
            key={section.key}
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
              
              {/* List image */}
              <div className="mt-4 h-36 overflow-hidden rounded-2xl border border-white/30 bg-black/10">
                {section.items[0]?.image_url ? (
                  <img
                    src={getTrackImage(section.items[0])}
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
            </div>
            
            {/* Track list - scrollable */}
            <div className="max-h-[500px] overflow-y-auto">
              <ol className="space-y-1 p-3">
                {section.items.map((track, index) => {
                  const primaryArtist = track.artists?.[0]?.name;
                  return (
                    <li
                      key={`${section.key}-${track.id ?? index}-${track.videoId ?? 'no-video'}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-background/70 px-3 py-2 text-sm text-foreground hover:bg-accent/5 transition"
                    >
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground w-6">
                          {index + 1}
                        </span>
                        <div className="min-w-0">
                          <button
                            type="button"
                            onClick={() => void handleSingleTrackPlay(track)}
                            className="truncate text-left font-semibold text-accent underline-offset-2 hover:underline"
                          >
                            {track.name}
                          </button>
                          <p className="truncate text-xs text-muted-foreground">
                            {primaryArtist || 'Artista desconocido'}
                          </p>
                        </div>
                      </div>
                      <span className={`text-xs ${track.videoId ? 'text-green-600' : 'text-muted-foreground'}`}>
                        {track.videoId ? 'reproducir' : 'sin enlace'}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
