import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import type { Artist } from '@/types/api';
import { Music, Loader2 } from 'lucide-react';
import { usePaginatedArtists } from '@/hooks/usePaginatedArtists';

const parseStoredJsonArray = (raw?: string | null) => {
  if (!raw) return [] as any[];
  const trimmed = raw.trim();
  if (!trimmed) return [] as any[];

  const tryParse = (value: string) => {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const firstAttempt = tryParse(trimmed);
  if (firstAttempt.length) return firstAttempt;

  const normalized = trimmed
    .replace(/'/g, '"')
    .replace(/None/g, 'null');
  return tryParse(normalized);
};
const getArtistAssets = (artist: Artist) => {
  const images = parseStoredJsonArray(artist.images);
  const firstImageEntry = images.find((img) => {
    if (typeof img === 'string') return !!img.trim();
    return typeof img?.url === 'string';
  });
  const rawUrl = typeof firstImageEntry === 'string'
    ? firstImageEntry
    : firstImageEntry?.url;
  const genres = parseStoredJsonArray(artist.genres).filter((g) => typeof g === 'string');

  let proxyUrl: string | null = null;
  const candidate = rawUrl || '';
  if (candidate) {
    proxyUrl = candidate.startsWith('/images/proxy')
      ? `${API_BASE_URL}${candidate}`
      : `${API_BASE_URL}/images/proxy?url=${encodeURIComponent(candidate)}&size=256`;
  }

  return {
    imageUrl: proxyUrl ?? null,
    genres,
  };
};

export function ArtistsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOption, setSortOption] = useState<'pop-desc' | 'pop-asc' | 'name-asc'>('pop-desc');
  const [genreFilter, setGenreFilter] = useState('');
  const { artists, isLoading, error, hasMore, loadInitial, loadMore } = usePaginatedArtists({ pageSize: 30, searchTerm, sortOption });
  const { isArtistsLoading } = useApiStore();
  const navigate = useNavigate();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (!hasMore) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore]);

  const genreOptions = useMemo(() => {
    const set = new Set<string>();
    artists.forEach((artist) => {
      parseStoredJsonArray(artist.genres).forEach((genre) => {
        if (typeof genre === 'string' && genre.trim()) set.add(genre.trim());
      });
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [artists]);

  const filteredArtists = useMemo(() => {
    return artists.filter((artist) => {
      const matchesSearch = artist.name.toLowerCase().includes(searchTerm.toLowerCase());
      const genres = parseStoredJsonArray(artist.genres)
        .map((g) => (typeof g === 'string' ? g.toLowerCase() : ''))
        .filter(Boolean);
      const matchesGenre = !genreFilter || genres.includes(genreFilter.toLowerCase());
      return matchesSearch && matchesGenre;
    });
  }, [artists, searchTerm, genreFilter]);

  const displayArtists = filteredArtists;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Artists Library</h1>
        </div>
      </div>

      <div className="filter-card mb-12">
        <div className="filter-panel">
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <div className="filter-stat">
              <p className="text-2xl font-bold" style={{ margin: 0, color: 'var(--accent)' }}>
                {filteredArtists.length}
              </p>
              <h3 className="filter-label uppercase tracking-wide" style={{ margin: 0, color: '#fff' }}>
                Filtered Results
              </h3>
            </div>
          </div>
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <div className="filter-control rounded-full border border-white/10 bg-[#151823] px-4 py-2">
              <label className="filter-label uppercase tracking-wide text-white shrink-0">
                Sort by
              </label>
              <select
                value={sortOption}
                onChange={(e) => setSortOption(e.target.value as typeof sortOption)}
                className="filter-select text-white"
              >
                <option value="pop-desc">Popularity (high → low)</option>
                <option value="pop-asc">Popularity (low → high)</option>
                <option value="name-asc">Name (A → Z)</option>
              </select>
            </div>
          </div>
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <div className="filter-control rounded-full border border-white/10 bg-[#151823] px-4 py-2">
              <label className="filter-label uppercase tracking-wide text-white shrink-0">
                Genre
              </label>
              <select
                value={genreFilter}
                onChange={(e) => setGenreFilter(e.target.value)}
                className="filter-select text-white"
              >
                <option value="">All</option>
                {genreOptions.map((genre) => (
                  <option key={genre} value={genre}>
                    {genre}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {error}
        </div>
      )}

      {(isLoading || isArtistsLoading) && artists.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mr-3" />
          Loading artists...
        </div>
      )}

      {!isLoading && !isArtistsLoading && (
        <div className="space-y-4">
          <div
            className="grid gap-6"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(6, minmax(0, 1fr))',
            }}
          >
            {displayArtists.map((artist) => {
              const { imageUrl, genres } = getArtistAssets(artist);
              const disabled = !artist.spotify_id;

              return (
                <button
                  key={artist.spotify_id || `local-${artist.id}`}
                  onClick={() => {
                    if (artist.spotify_id) {
                      navigate(`/artists/${artist.spotify_id}`);
                    }
                  }}
                  className={`flex flex-col items-center justify-center gap-3 rounded-2xl bg-transparent p-6 text-center text-white transition ${
                    disabled ? 'opacity-40 cursor-not-allowed' : ''
                  }`}
                  disabled={disabled}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '20px',
                    background: 'none',
                    border: 'none',
                  }}
                  type="button"
                >
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={artist.name}
                      style={{
                        width: '200px',
                        height: '200px',
                        borderRadius: '50%',
                        objectFit: 'cover',
                        display: 'block',
                        margin: '0 auto 10px auto',
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        width: '200px',
                        height: '200px',
                        borderRadius: '50%',
                        border: '1px solid var(--border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        margin: '0 auto 10px auto',
                        background: '#0f1320',
                        color: '#fff',
                        fontSize: '18px',
                        letterSpacing: '2px',
                      }}
                    >
                      {artist.name
                        .split(' ')
                        .filter(Boolean)
                        .slice(0, 2)
                        .map((word) => word[0]?.toUpperCase())
                        .join('')
                        .padEnd(2, '•')}
                    </div>
                  )}
                  <div style={{ color: 'white', textAlign: 'center', width: '100%' }}>
                    <p className="text-sm font-semibold truncate">{artist.name}</p>
                    {artist.popularity > 0 && (
                      <p className="text-xs text-white/60">Popularity {artist.popularity}</p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
          {hasMore && (
            <div
              ref={sentinelRef}
              style={{ height: 1 }}
            />
          )}
          {isLoading && artists.length > 0 && (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
              Loading more artists...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
