import { useEffect, useMemo, useRef, useState } from 'react';
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
  const [filteredTotal, setFilteredTotal] = useState<number | null>(null);
  const [nextAfter, setNextAfter] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const limit = 200;
  const listRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(600);
  const [listTop, setListTop] = useState(0);
  const rowHeight = 64;
  const overscan = 8;
  const dedupeTracks = (items: TrackOverview[]) => {
    const seen = new Set<number>();
    return items.filter((track) => {
      if (seen.has(track.track_id)) return false;
      seen.add(track.track_id);
      return true;
    });
  };

  useEffect(() => {
    const activeSearch = search.trim();
    const isFiltered = filter !== 'all' || activeSearch.length > 0;
    const load = async () => {
      setLoading(true);
      setLoadingMore(false);
      loadingMoreRef.current = false;
      setError(null);
      try {
        const response = await audio2Api.getTracksOverview({
          verify_files: false,
          offset: 0,
          limit,
          include_summary: !isFiltered,
          filter: isFiltered ? filter : undefined,
          search: isFiltered ? activeSearch : undefined,
        });
        setTracks(dedupeTracks(response.data.items || []));
        if (!isFiltered) {
          setSummary(response.data.summary || null);
        }
        setFilteredTotal(response.data.filtered_total ?? null);
        setHasMore(Boolean(response.data.has_more));
        setNextAfter(response.data.next_after ?? null);
      } catch (err: any) {
        setError(err?.response?.data?.detail || err?.message || 'No se pudo cargar el listado de pistas');
      } finally {
        setLoading(false);
      }
    };
    const timeout = setTimeout(load, activeSearch.length > 0 ? 250 : 0);
    return () => clearTimeout(timeout);
  }, [filter, limit, search]);

  const handleLoadMore = async () => {
    if (loadingMoreRef.current || loadingMore || !hasMore) return;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      const activeSearch = search.trim();
      const isFiltered = filter !== 'all' || activeSearch.length > 0;
      const response = await audio2Api.getTracksOverview({
        verify_files: false,
        limit,
        include_summary: false,
        after_id: nextAfter ?? (tracks.length > 0 ? tracks[tracks.length - 1].track_id : null),
        filter: isFiltered ? filter : undefined,
        search: isFiltered ? activeSearch : undefined,
      });
      const nextItems = response.data.items || [];
      setTracks((prev) => {
        const seen = new Set(prev.map((track) => track.track_id));
        const unique = nextItems.filter((track: TrackOverview) => !seen.has(track.track_id));
        return unique.length > 0 ? [...prev, ...unique] : prev;
      });
      setHasMore(Boolean(response.data.has_more));
      setNextAfter(response.data.next_after ?? null);
      if (response.data.filtered_total !== undefined) {
        setFilteredTotal(response.data.filtered_total ?? null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'No se pudo cargar más pistas');
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  };

  const stats = useMemo(() => {
    if (summary) {
      return {
        total: summary.total,
        withLink: summary.with_link,
        withFile: summary.with_file,
        missingLink: summary.missing_link,
        missingFile: summary.missing_file,
      };
    }
    const total = tracks.length;
    const withLink = tracks.filter((t) => !!t.youtube_video_id).length;
    const withFile = tracks.filter((t) => t.local_file_exists).length;
    const missingLink = total - withLink;
    const missingFile = total - withFile;
    return { total, withLink, withFile, missingLink, missingFile };
  }, [tracks, summary]);

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
    if (isFilteredView && filteredTotal !== null) {
      return filteredTotal;
    }
    if (!summary || isSearchActive) return filteredTracks.length;
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
        return summary.total;
    }
  }, [filter, filteredTracks.length, filteredTotal, isFilteredView, isSearchActive, summary]);
  const targetFilteredCount = useMemo(() => {
    if (!isFilteredView) return 0;
    if (filterTotal > 0) return filterTotal;
    return Math.max(80, Math.floor(limit * 0.8));
  }, [filter, filterTotal, isFilteredView, isSearchActive, limit]);
  const progressCount = useMemo(() => {
    const lastVisible = Math.min(
      Math.max(Math.round((scrollTop + containerHeight) / rowHeight), 0),
      filteredTracks.length
    );
    return lastVisible;
  }, [containerHeight, filteredTracks.length, rowHeight, scrollTop]);
  const progressPercent = filterTotal > 0 ? Math.min((progressCount / filterTotal) * 100, 100) : 0;

  const shouldPrefetchMore = useMemo(() => {
    const isFilteredView = filter !== 'all' || search.trim().length > 0;
    if (!isFilteredView) return false;
    if (!hasMore || loading || loadingMore) return false;
    return filteredTracks.length < targetFilteredCount;
  }, [filter, search, filteredTracks.length, hasMore, loading, loadingMore, targetFilteredCount]);

  useEffect(() => {
    if (!shouldPrefetchMore) return;
    handleLoadMore();
  }, [shouldPrefetchMore]);

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
      if (isFilteredView && filteredTracks.length >= targetFilteredCount) return;
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

  if (loading) {
    return <div className="card">Cargando pistas...</div>;
  }

  if (error) {
    return <div className="card">Error: {error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <SummaryCard label="Total pistas" value={stats.total} />
            <SummaryCard label="Con link YouTube" value={stats.withLink} accent />
            <SummaryCard label="Con MP3 local" value={stats.withFile} accent />
            <SummaryCard label="Pendiente link" value={stats.missingLink} muted />
            <SummaryCard label="Pendiente MP3" value={stats.missingFile} muted />
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
            top: 84,
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
                ? `Mostrando ${filteredTracks.length} de ${filterTotal} pistas (filtrado).`
                : `Mostrando ${tracks.length} de ${stats.total} pistas.`}
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
                {progressCount}/{filterTotal}
              </span>
            </div>
          </div>
        </div>

        <div
          className="scroll-area"
          ref={listRef}
          style={{ overflowX: 'auto' }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720, tableLayout: 'fixed' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--muted)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.6 }}>
                <th style={{ padding: '8px 6px', width: 44 }}>#</th>
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
              {topSpacer > 0 && (
                <tr>
                  <td colSpan={8} style={{ height: topSpacer }} />
                </tr>
              )}
              {visibleTracks.map((track, index) => (
                <tr
                  key={`${track.track_id}-${track.spotify_track_id || track.track_name}`}
                  style={{ height: rowHeight }}
                >
                  <td style={{ ...cellStyle, width: 44, color: 'var(--muted)' }}>{startIndex + index + 1}</td>
                  <td style={{ ...cellStyle, fontWeight: 600 }}>{track.track_name}</td>
                  <td style={cellStyle}>{track.artist_name || '—'}</td>
                  <td style={cellStyle}>{track.album_name || '—'}</td>
                  <td style={cellStyle}>{formatDuration(track.duration_ms)}</td>
                  <td style={cellStyle}>
                    {track.youtube_video_id ? (
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Disponible ({track.youtube_status || 'link'})</span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>Pendiente</span>
                    )}
                  </td>
                  <td style={cellStyle}>
                    {track.local_file_exists ? (
                      <span style={{ color: '#34d399', fontWeight: 600 }}>Guardado</span>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>No</span>
                    )}
                  </td>
                  <td style={cellStyle}>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'nowrap', overflow: 'hidden' }}>
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

function SummaryCard({ label, value, accent, muted }: { label: string; value: number; accent?: boolean; muted?: boolean }) {
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
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
