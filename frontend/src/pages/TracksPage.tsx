import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { useFavorites } from '@/hooks/useFavorites';
import { usePlayerStore } from '@/store/usePlayerStore';
import type { TrackOverview } from '@/types/api';

type FilterTab = 'all' | 'favorites' | 'withLink' | 'noLink' | 'hasFile' | 'missingFile';
type LinkUiState = { status: 'idle' | 'loading' | 'error'; message?: string };

const filterLabels: Record<FilterTab, string> = {
  all: 'Todos',
  favorites: 'Favoritos',
  withLink: 'Con link YouTube',
  noLink: 'Sin link aún',
  hasFile: 'Con MP3 local',
  missingFile: 'Sin MP3 local'
};

const formatChartDate = (value?: string | null) => {
  if (!value) return null;
  const parts = value.split('-');
  if (parts.length !== 3) return value;
  const [year, month, day] = parts;
  if (!day || !month || !year) return value;
  return `${day}-${month}-${year}`;
};

export function TracksPage() {
  const [tracks, setTracks] = useState<TrackOverview[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterTab>('all');
  const [summary, setSummary] = useState<{
    total: number;
    with_link: number;
    with_file: number;
    missing_link: number;
    missing_file: number;
  } | null>(null);
  const [favoriteTotal, setFavoriteTotal] = useState<number | null>(null);
  const [filteredTotal, setFilteredTotal] = useState<number | null>(null);
  const [nextAfter, setNextAfter] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [linkState, setLinkState] = useState<Record<string, LinkUiState>>({});
  const limit = 200;
  const { userId } = useApiStore();
  const listRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const requestedAfterIdRef = useRef<number | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(600);
  const [listTop, setListTop] = useState(0);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const playByVideoId = usePlayerStore((s) => s.playByVideoId);
  const setQueue = usePlayerStore((s) => s.setQueue);
  const setOnPlayTrack = usePlayerStore((s) => s.setOnPlayTrack);
  const playbackMode = usePlayerStore((s) => s.playbackMode);
  const lastDownloadedVideo = usePlayerStore((s) => s.lastDownloadedVideo);
  const setVideoEmbedId = usePlayerStore((s) => s.setVideoEmbedId);
  const setStatusMessage = usePlayerStore((s) => s.setStatusMessage);
  const rowHeight = 64;
  const overscan = 8;
  const stickyTop = 84;
  const columnWidths = {
    index: 44,
    track: 391,
    artist: 130,
    album: 192,
    duration: 72,
    youtube: 140,
    mp3: 90,
    actions: 150,
  };
  const resolveTrackKey = useCallback((track: TrackOverview) =>
    track.spotify_track_id || String(track.track_id), []);
  const dedupeTracks = (items: TrackOverview[]) => {
    const seen = new Set<number>();
    return items.filter((track) => {
      if (seen.has(track.track_id)) return false;
      seen.add(track.track_id);
      return true;
    });
  };

  const {
    favoriteIds: favoriteTrackIds,
    setFavoriteIds: setFavoriteTrackIds,
    effectiveUserId: effectiveTrackUserId
  } = useFavorites('track', userId);

  const toggleTrackFavorite = useCallback(
    async (track: TrackOverview) => {
      if (!effectiveTrackUserId) return;
      const isFavorite = favoriteTrackIds.has(track.track_id);
      try {
        if (isFavorite) {
          await audio2Api.removeFavorite('track', track.track_id, effectiveTrackUserId);
          setFavoriteTrackIds((prev) => {
            const next = new Set(prev);
            next.delete(track.track_id);
            return next;
          });
          setFavoriteTotal((prev) =>
            prev === null ? prev : Math.max(prev - 1, 0)
          );
        } else {
          await audio2Api.addFavorite('track', track.track_id, effectiveTrackUserId);
          setFavoriteTrackIds((prev) => {
            const next = new Set(prev);
            next.add(track.track_id);
            return next;
          });
          setFavoriteTotal((prev) =>
            prev === null ? prev : prev + 1
          );
        }
      } catch (err) {
        console.error('Failed to toggle track favorite', err);
      }
    },
    [effectiveTrackUserId, favoriteTrackIds, setFavoriteTrackIds]
  );

  useEffect(() => {
    const activeSearch = search.trim();
    const isFiltered = filter !== 'all' || activeSearch.length > 0;
    const load = async () => {
      setLoading(true);
      setLoadingMore(false);
      loadingMoreRef.current = false;
      requestedAfterIdRef.current = null;
      setError(null);
      try {
        const response = await audio2Api.getTracksOverview({
          verify_files: false,
          offset: 0,
          limit,
          include_summary: false,
          filter: isFiltered && filter !== 'all' ? filter : undefined,
          search: isFiltered ? activeSearch : undefined,
        });
        setTracks(dedupeTracks(response.data.items || []));
        setFilteredTotal(response.data.filtered_total ?? null);
        setHasMore(Boolean(response.data.has_more));
        setNextAfter(response.data.next_after ?? null);
      } catch (err: unknown) {
        const message =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
            ? (err.response.data as { detail: string }).detail
            : err instanceof Error
              ? err.message
              : 'No se pudo cargar el listado de pistas';
        setError(message);
        setHasMore(false);
        setNextAfter(null);
      } finally {
        setLoading(false);
        setHasLoadedOnce(true);
      }
    };
    const timeout = setTimeout(load, activeSearch.length > 0 ? 250 : 0);
    return () => clearTimeout(timeout);
  }, [filter, limit, search]);

  useEffect(() => {
    if (!hasLoadedOnce) return;
    let cancelled = false;
    const loadSummary = async () => {
      try {
        const response = await audio2Api.getTracksOverview({
          verify_files: false,
          offset: 0,
          limit: 1,
          include_summary: true,
        });
        if (cancelled) return;
        setSummary(response.data.summary || null);
      } catch {
        if (cancelled) return;
      }
    };
    const timer = setTimeout(loadSummary, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [hasLoadedOnce]);

  useEffect(() => {
    if (!hasLoadedOnce) return;
    if (!effectiveTrackUserId) return;
    let cancelled = false;
    const loadFavoriteTotal = async () => {
      try {
        const response = await audio2Api.getTracksOverview({
          verify_files: false,
          limit: 1,
          include_summary: false,
          filter: 'favorites',
        });
        if (cancelled) return;
        if (typeof response.data.filtered_total === 'number') {
          setFavoriteTotal(response.data.filtered_total);
        }
      } catch {
        if (cancelled) return;
      }
    };
    const timer = setTimeout(loadFavoriteTotal, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [effectiveTrackUserId, hasLoadedOnce]);

  useEffect(() => {
    if (!lastDownloadedVideo) return;
    const { videoId } = lastDownloadedVideo;
    setTracks((prev) =>
      prev.map((track) => {
        if (track.youtube_video_id !== videoId || track.local_file_exists) return track;
        return {
          ...track,
          local_file_exists: true,
          youtube_status: 'completed',
        };
      })
    );
  }, [lastDownloadedVideo]);

  const handleLoadMore = useCallback(async () => {
    if (loadingMoreRef.current || loadingMore || !hasMore) return;
    const afterId = nextAfter ?? (tracks.length > 0 ? tracks[tracks.length - 1].track_id : null);
    if (afterId === null) return;
    if (requestedAfterIdRef.current === afterId) return;
    loadingMoreRef.current = true;
    requestedAfterIdRef.current = afterId;
    setLoadingMore(true);
    try {
      const activeSearch = search.trim();
      const isFiltered = filter !== 'all' || activeSearch.length > 0;
      const response = await audio2Api.getTracksOverview({
        verify_files: false,
        limit,
        include_summary: false,
        after_id: afterId,
        filter: isFiltered && filter !== 'all' ? filter : undefined,
        search: isFiltered ? activeSearch : undefined,
      });
      const nextItems = response.data.items || [];
      let uniqueCount = 0;
      setTracks((prev) => {
        const seen = new Set(prev.map((track) => track.track_id));
        const unique = nextItems.filter((track: TrackOverview) => !seen.has(track.track_id));
        uniqueCount = unique.length;
        return unique.length > 0 ? [...prev, ...unique] : prev;
      });
      const nextCursor = response.data.next_after ?? null;
      const hasMoreFromServer = Boolean(response.data.has_more);
      const didAdvance = nextCursor !== null && nextCursor !== afterId;
      if (!uniqueCount || !hasMoreFromServer || !didAdvance) {
        setHasMore(false);
        setNextAfter(null);
      } else {
        setHasMore(true);
        setNextAfter(nextCursor);
      }
      if (response.data.filtered_total !== undefined) {
        setFilteredTotal(response.data.filtered_total ?? null);
      }
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? (err.response.data as { detail: string }).detail
          : err instanceof Error
            ? err.message
            : 'No se pudo cargar más pistas';
      setError(message);
      setHasMore(false);
      setNextAfter(null);
      requestedAfterIdRef.current = null;
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [loadingMore, hasMore, search, filter, limit, nextAfter, tracks]);

  const stats = useMemo(() => {
    if (!summary) return null;
    return {
      total: summary.total,
      withLink: summary.with_link,
      withFile: summary.with_file,
      missingLink: summary.missing_link,
      missingFile: summary.missing_file,
    };
  }, [summary]);

  const filteredTracks = useMemo(
    () =>
      [...tracks].sort((a, b) => {
        const artistA = (a.artist_name || '').toLocaleLowerCase();
        const artistB = (b.artist_name || '').toLocaleLowerCase();
        if (artistA !== artistB) {
          return artistA.localeCompare(artistB, 'es', { sensitivity: 'base' });
        }
        const trackA = (a.track_name || '').toLocaleLowerCase();
        const trackB = (b.track_name || '').toLocaleLowerCase();
        return trackA.localeCompare(trackB, 'es', { sensitivity: 'base' });
      }),
    [tracks]
  );
  const buildQueueItems = useCallback(
    (override?: { trackKey: string; videoId: string }) =>
      filteredTracks
        .map((track) => {
          const trackKey = resolveTrackKey(track);
          const localVideoId = track.local_file_exists && track.track_id ? `local:${track.track_id}` : undefined;
          const videoId =
            localVideoId ||
            track.youtube_video_id ||
            (override && override.trackKey === trackKey ? override.videoId : undefined);
          if (!videoId) return null;
          return {
            localTrackId: track.track_id,
            spotifyTrackId: trackKey,
            title: track.track_name || '—',
            artist: track.artist_name || undefined,
            artistSpotifyId: track.artist_spotify_id || undefined,
            durationMs: track.duration_ms || undefined,
            videoId,
            rawTrack: track,
          };
        })
        .filter(Boolean) as Array<{
        localTrackId?: number;
        spotifyTrackId: string;
        title: string;
        artist?: string;
        durationMs?: number;
        videoId?: string;
        rawTrack?: TrackOverview;
      }>,
    [filteredTracks, resolveTrackKey]
  );

  const ensureYoutubeLink = useCallback(
    async (track: TrackOverview) => {
      const trackKey = resolveTrackKey(track);
      if (!trackKey) return null;
      if (track.youtube_video_id) {
        return { videoId: track.youtube_video_id, url: track.youtube_url || undefined };
      }
      if (!track.spotify_track_id) {
        setStatusMessage('Sin enlace de YouTube');
        return null;
      }
      if (linkState[trackKey]?.status === 'loading') {
        return null;
      }
      setLinkState((prev) => ({
        ...prev,
        [trackKey]: { status: 'loading' },
      }));
      try {
        const response = await audio2Api.refreshYoutubeTrackLink(track.spotify_track_id, {
          artist: track.artist_name || undefined,
          track: track.track_name,
          album: track.album_name || undefined,
        });
        const linkData = response.data;
        if (linkData?.youtube_video_id) {
          setTracks((prev) =>
            prev.map((item) =>
              resolveTrackKey(item) === trackKey
                ? {
                    ...item,
                    youtube_video_id: linkData.youtube_video_id,
                    youtube_url: linkData.youtube_url || item.youtube_url,
                    youtube_status: linkData.status || item.youtube_status,
                  }
                : item
            )
          );
          setLinkState((prev) => ({
            ...prev,
            [trackKey]: { status: 'idle' },
          }));
          return { videoId: linkData.youtube_video_id, url: linkData.youtube_url || undefined };
        }
        setLinkState((prev) => ({
          ...prev,
          [trackKey]: { status: 'error', message: 'No se encontró YouTube' },
        }));
        setStatusMessage('No se encontró YouTube para esta canción');
        return null;
      } catch (err: unknown) {
        const message =
          err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
            ? (err.response.data as { detail: string }).detail
            : err instanceof Error
              ? err.message
              : 'Error buscando en YouTube';
        setLinkState((prev) => ({
          ...prev,
          [trackKey]: { status: 'error', message },
        }));
        setStatusMessage(message);
        return null;
      }
    },
    [linkState, resolveTrackKey, setStatusMessage]
  );

  const totalRows = filteredTracks.length;
  const visibleCount = useMemo(
    () => Math.ceil(containerHeight / rowHeight) + overscan * 2,
    [containerHeight]
  );
  const startIndex = Math.max(Math.floor(scrollTop / rowHeight) - overscan, 0);
  const endIndex = Math.min(startIndex + visibleCount, totalRows);
  const visibleTracks = filteredTracks.slice(startIndex, endIndex);
  const topSpacer = startIndex * rowHeight;
  const bottomSpacer = Math.max(totalRows - endIndex, 0) * rowHeight;
  const isSearchActive = search.trim().length > 0;
  const isFilteredView = filter !== 'all' || isSearchActive;
  const filterTotal = useMemo(() => {
    if (isFilteredView) {
      if (filteredTotal !== null) return filteredTotal;
      if (filter === 'favorites' && favoriteTotal !== null) return favoriteTotal;
      if (summary) {
        switch (filter) {
          case 'withLink':
            return summary.with_link;
          case 'noLink':
            return summary.missing_link;
          case 'hasFile':
            return summary.with_file;
          case 'missingFile':
            return summary.missing_file;
          default:
            break;
        }
      }
      return null;
    }
    return summary ? summary.total : null;
  }, [filter, filteredTotal, favoriteTotal, isFilteredView, summary]);
  const totalKnown = filterTotal !== null;
  const displayTotal = totalKnown ? filterTotal : filteredTracks.length;
  const prefetchTarget = useMemo(() => Math.max(80, Math.floor(limit * 0.8)), [limit]);
  const targetFilteredCount = useMemo(() => {
    if (!isFilteredView) return 0;
    if (filterTotal && filterTotal > 0) return Math.min(filterTotal, prefetchTarget);
    return prefetchTarget;
  }, [filterTotal, isFilteredView, prefetchTarget]);
  const progressCount = useMemo(() => {
    const lastVisible = Math.min(
      Math.max(Math.round((scrollTop + containerHeight) / rowHeight), 0),
      filteredTracks.length
    );
    return lastVisible;
  }, [containerHeight, filteredTracks.length, rowHeight, scrollTop]);
  const progressPercent = filterTotal && filterTotal > 0 ? Math.min((progressCount / filterTotal) * 100, 100) : 0;

  const shouldPrefetchMore = useMemo(() => {
    const isFilteredView = filter !== 'all' || search.trim().length > 0;
    if (!isFilteredView) return false;
    if (!hasMore || loading || loadingMore) return false;
    return filteredTracks.length < targetFilteredCount;
  }, [filter, search, filteredTracks.length, hasMore, loading, loadingMore, targetFilteredCount]);

  useEffect(() => {
    if (!shouldPrefetchMore) return;
    handleLoadMore();
  }, [shouldPrefetchMore, handleLoadMore]);

  useEffect(() => {
    const updateMetrics = () => {
      if (!listRef.current) return;
      const rect = listRef.current.getBoundingClientRect();
      setListTop(rect.top + window.scrollY);
      setContainerHeight(window.innerHeight || 600);
    };
    updateMetrics();
    window.addEventListener('resize', updateMetrics);
    return () => window.removeEventListener('resize', updateMetrics);
  }, []);

  useEffect(() => {
    const updateMetrics = () => {
      if (!listRef.current) return;
      const rect = listRef.current.getBoundingClientRect();
      setListTop(rect.top + window.scrollY);
    };
    updateMetrics();
    setScrollTop(0);
  }, [filter, search]);

  useEffect(() => {
    const handleWindowScroll = () => {
      const relativeTop = Math.max(window.scrollY - listTop, 0);
      setScrollTop(relativeTop);
      if (!hasMore || loadingMore || loading) return;
      const currentIndex = Math.floor((relativeTop + containerHeight) / rowHeight);
      const remainingRows = Math.max(totalRows - currentIndex, 0);
      if (remainingRows <= 100) {
        handleLoadMore();
      }
    };
    window.addEventListener('scroll', handleWindowScroll, { passive: true });
    handleWindowScroll();
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, [
    containerHeight,
    filteredTracks.length,
    hasMore,
    isFilteredView,
    listTop,
    loading,
    loadingMore,
    targetFilteredCount,
    totalRows,
    handleLoadMore,
  ]);

  const formatDuration = (ms?: number | null) => {
    if (!ms) return '–';
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };
  const cellStyle = {
    padding: '10px 6px',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
  };
  const nameCellStyle = {
    padding: '10px 6px',
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden' as const,
    textOverflow: 'ellipsis' as const,
  };
  const mp3CellStyle = { ...cellStyle, paddingRight: 4 };
  const actionsCellStyle = { ...cellStyle, paddingLeft: 4 };
  const headerCellStyle = {
    background: 'var(--panel)',
  };
  const renderColGroup = () => (
    <colgroup>
      <col style={{ width: columnWidths.index }} />
      <col style={{ width: columnWidths.track }} />
      <col style={{ width: columnWidths.artist }} />
      <col style={{ width: columnWidths.album }} />
      <col style={{ width: columnWidths.duration }} />
      <col style={{ width: columnWidths.youtube }} />
      <col style={{ width: columnWidths.mp3 }} />
      <col style={{ width: columnWidths.actions }} />
    </colgroup>
  );

  const handlePlayTrack = useCallback(
    async (track: TrackOverview) => {
      const trackKey = resolveTrackKey(track);
      const localVideoId = track.local_file_exists && track.track_id ? `local:${track.track_id}` : null;
      let videoId = localVideoId;
      if (!videoId) {
        const linkInfo = await ensureYoutubeLink(track);
        videoId = linkInfo?.videoId || track.youtube_video_id || null;
      }
      if (!videoId) {
        setStatusMessage('Sin enlace de YouTube');
        return;
      }
      const durationSec = track.duration_ms ? Math.round(track.duration_ms / 1000) : undefined;
      const queueItems = buildQueueItems({ trackKey, videoId });
      const index = queueItems.findIndex((item) => item.spotifyTrackId === trackKey);
      setQueue(queueItems, index >= 0 ? index : 0);
      setOnPlayTrack((item) => {
        if (!item.videoId) {
          setStatusMessage('Sin enlace de YouTube');
          return;
        }
        const state = usePlayerStore.getState();
        const nextDurationSec = item.durationMs ? Math.round(item.durationMs / 1000) : undefined;
        void state.playByVideoId({
          localTrackId: item.localTrackId,
          spotifyTrackId: item.spotifyTrackId,
          title: item.title,
          artist: item.artist,
          artistSpotifyId: item.artistSpotifyId,
          videoId: item.videoId,
          durationSec: nextDurationSec,
        });
        if (state.playbackMode === 'video' && !item.videoId.startsWith('local:')) {
          state.setVideoEmbedId(item.videoId);
        }
      });
      await playByVideoId({
        localTrackId: track.track_id,
        spotifyTrackId: trackKey,
        title: track.track_name || '—',
        artist: track.artist_name || undefined,
        artistSpotifyId: track.artist_spotify_id || undefined,
        videoId,
        durationSec,
      });
      if (playbackMode === 'video') {
        if (videoId.startsWith('local:')) {
          setVideoEmbedId(null);
        } else {
          setVideoEmbedId(videoId);
        }
      }
    },
    [
      buildQueueItems,
      ensureYoutubeLink,
      playByVideoId,
      resolveTrackKey,
      setOnPlayTrack,
      setQueue,
      setStatusMessage,
      playbackMode,
      setVideoEmbedId,
    ]
  );


  if (loading && !hasLoadedOnce && tracks.length === 0) {
    return <div className="card">Cargando pistas...</div>;
  }

  if (error && tracks.length === 0) {
    return <div className="card">Error: {error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <SummaryCard label="Total pistas" value={stats?.total ?? null} />
          <SummaryCard label="Favoritos" value={favoriteTotal ?? null} />
          <SummaryCard label="Con link YouTube" value={stats?.withLink ?? null} accent />
          <SummaryCard label="Con MP3 local" value={stats?.withFile ?? null} accent />
          <SummaryCard label="Pendiente link" value={stats?.missingLink ?? null} muted />
          <SummaryCard label="Pendiente MP3" value={stats?.missingFile ?? null} muted />
        </div>
      </div>

      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            position: 'sticky',
            top: stickyTop,
            zIndex: 9,
            background: 'var(--panel)',
            paddingTop: 8,
            paddingBottom: 12,
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <div className="search-form" style={{ flex: '1 1 260px' }}>
              <input
                type="text"
                placeholder="Buscar por canción, artista o álbum"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="search-input"
              />
            </div>
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              {isFilteredView
                ? totalKnown
                  ? `Mostrando ${filteredTracks.length} de ${displayTotal} pistas (filtrado).`
                  : `Mostrando ${filteredTracks.length} pistas (filtrado).`
                : totalKnown
                  ? `Mostrando ${tracks.length} de ${displayTotal} pistas.`
                  : `Mostrando ${tracks.length} pistas.`}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'var(--muted)' }}>
              <div
                style={{
                  flex: 1,
                  height: 8,
                  borderRadius: 999,
                  background: 'var(--panel-2)',
                  overflow: 'hidden',
                  border: '1px solid var(--border)',
                }}
              >
                <div
                  style={{
                    width: `${progressPercent}%`,
                    height: '100%',
                    background: 'var(--accent)',
                    transition: 'width 120ms ease',
                  }}
                />
              </div>
              <span>
                {progressCount}/{totalKnown ? displayTotal : '—'}
              </span>
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720, tableLayout: 'fixed' }}>
              {renderColGroup()}
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--muted)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.6, borderBottom: '1px solid var(--border)' }}>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>#</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Track</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Artista</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Álbum</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Duración</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Link YouTube</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>MP3 local</th>
                  <th style={{ ...headerCellStyle, padding: '8px 6px' }}>Acciones</th>
                </tr>
              </thead>
            </table>
          </div>
        </div>

        <div
          className="scroll-area"
          ref={listRef}
          style={{ overflowX: 'auto' }}
        >
          {(loading || loadingMore) && (
            <div className="badge" style={{ marginBottom: 8 }}>
              Cargando resultados...
            </div>
          )}
          {error && (
            <div className="badge" style={{ marginBottom: 8, borderColor: '#ef4444', color: '#fecaca' }}>
              Error: {error}
            </div>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720, tableLayout: 'fixed' }}>
            {renderColGroup()}
            <tbody>
              {topSpacer > 0 && (
                <tr>
                  <td colSpan={8} style={{ height: topSpacer }} />
                </tr>
              )}
              {visibleTracks.map((track, index) => (
                (() => {
                  const trackKey = resolveTrackKey(track);
                  const linkLoading = linkState[trackKey]?.status === 'loading';
                  const canPlay = !linkLoading && (track.local_file_exists || !!track.youtube_video_id || !!track.spotify_track_id);
                  const isFavorite = favoriteTrackIds.has(track.track_id);
                  const chartBadge = track.chart_best_position
                    ? `#${track.chart_best_position}`
                    : null;
                  const chartDate = formatChartDate(track.chart_best_position_date);
                  const youtubeStatus = track.youtube_status || '';
                  const hasYoutube = !!track.youtube_video_id;
                  const isYoutubeError = !hasYoutube && ['error', 'failed'].includes(youtubeStatus);

                  return (
                    <tr
                      key={`${track.track_id}-${track.spotify_track_id || track.track_name}`}
                      style={{ height: rowHeight }}
                    >
                      <td style={{ ...cellStyle, width: 44, color: 'var(--muted)' }}>{startIndex + index + 1}</td>
                      <td style={{ ...nameCellStyle, fontWeight: 600, fontSize: 15 }}>
                        <button
                          type="button"
                          onClick={() => void handlePlayTrack(track)}
                          disabled={!canPlay}
                          style={{
                            display: 'block',
                            width: '100%',
                            textAlign: 'left',
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            margin: 0,
                            font: 'inherit',
                            color: canPlay ? 'var(--accent)' : 'inherit',
                            cursor: canPlay ? 'pointer' : 'default',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {track.track_name}
                          {chartBadge ? (
                            <span
                              title={`Billboard ${track.chart_best_position}${chartDate ? ` · ${chartDate}` : ''}`}
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
                      </td>
                  <td style={{ ...cellStyle, fontSize: 14 }}>{track.artist_name || '—'}</td>
                  <td style={{ ...nameCellStyle, fontSize: 14 }}>
                    {track.album_name || '—'}
                  </td>
                  <td style={cellStyle}>{formatDuration(track.duration_ms)}</td>
                  <td style={{ ...cellStyle, textAlign: 'center' }}>
                    {hasYoutube ? (
                      <span
                        title={`Disponible (${track.youtube_status || 'link'})`}
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
                        }}
                      >
                        ✓
                      </span>
                    ) : isYoutubeError ? (
                      <span
                        title="Error consultando YouTube"
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
                        }}
                      >
                        !
                      </span>
                    ) : null}
                  </td>
                  <td style={{ ...mp3CellStyle, textAlign: 'center' }}>
                    {track.local_file_exists ? (
                      <span
                        title="Guardado"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: 24,
                          height: 24,
                          borderRadius: '50%',
                          border: '2px solid rgba(52, 211, 153, 0.7)',
                          color: '#34d399',
                          fontWeight: 900,
                          fontSize: 16,
                        }}
                      >
                        ✓
                      </span>
                    ) : null}
                  </td>
                  <td style={actionsCellStyle}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'nowrap', overflow: 'hidden' }}>
                      <button
                        type="button"
                        onClick={() => toggleTrackFavorite(track)}
                        className="badge"
                        style={{
                          textDecoration: 'none',
                          cursor: effectiveTrackUserId ? 'pointer' : 'not-allowed',
                          border: 'none',
                          background: isFavorite ? 'rgba(63, 255, 208, 0.18)' : 'transparent',
                          color: isFavorite ? 'var(--accent)' : 'inherit',
                        }}
                        disabled={!effectiveTrackUserId}
                        title={isFavorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
                      >
                        {isFavorite ? '❤️' : '🤍'}
                      </button>
                      <button
                        type="button"
                        className="badge"
                        style={{ textDecoration: 'none', cursor: 'not-allowed', border: 'none', opacity: 0.6 }}
                        disabled
                        title="Próximamente: añadir a lista"
                      >
                        ＋ Lista
                      </button>
                    </div>
                  </td>
                    </tr>
                  );
                })()
              ))}
              {filteredTracks.length === 0 && (
                <tr>
                  <td colSpan={8} style={{ padding: 20, textAlign: 'center', color: 'var(--muted)' }}>
                    Sin pistas que coincidan con el filtro actual.
                  </td>
                </tr>
              )}
              {bottomSpacer > 0 && (
                <tr>
                  <td colSpan={8} style={{ height: bottomSpacer }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {loadingMore && (
          <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--muted)', fontSize: 12 }}>
            Cargando más pistas...
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, accent, muted }: { label: string; value: number | null; accent?: boolean; muted?: boolean }) {
  const background = accent ? 'rgba(5, 247, 165, 0.12)' : muted ? 'rgba(255, 255, 255, 0.04)' : 'var(--panel)';
  const borderColor = accent ? 'rgba(5, 247, 165, 0.4)' : 'var(--border)';

  return (
    <div
      style={{
        flex: '1 1 140px',
        minWidth: 140,
        borderRadius: 14,
        padding: '11px 14px',
        background,
        border: `1px solid ${borderColor}`,
        display: 'flex',
        flexDirection: 'column',
        gap: 4
      }}
    >
      <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value ?? '—'}</div>
    </div>
  );
}
