import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { normalizeImageUrl } from '@/lib/images';
import { useApiStore } from '@/store/useApiStore';
import type { Artist } from '@/types/api';
import { Loader2, Heart, RotateCcw } from 'lucide-react';
import { getUserIdFromToken, useFavorites } from '@/hooks/useFavorites';
import { usePaginatedHiddenArtists } from '@/hooks/usePaginatedHiddenArtists';

type ParsedJsonEntry = string | { url: string };

const parseStoredJsonArray = (raw?: string | null): ParsedJsonEntry[] => {
  if (!raw) return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];

  const tryParse = (value: string) => {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) {
        return parsed
          .map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
              const candidateUrl =
                typeof (item as { url?: string }).url === 'string'
                  ? (item as { url?: string }).url
                  : typeof (item as { '#text'?: string })['#text'] === 'string'
                    ? (item as { '#text'?: string })['#text']
                    : null;
              if (candidateUrl) {
                return { url: candidateUrl };
              }
            }
            return null;
          })
          .filter((entry): entry is ParsedJsonEntry => entry !== null);
      }
      return [];
    } catch {
      return [];
    }
  };

  const firstAttempt = tryParse(trimmed);
  if (firstAttempt.length) return firstAttempt;

  const normalized = trimmed
    .replace(/'/g, '"')
    .replace(/None/g, 'null')
    .replace(/True/g, 'true')
    .replace(/False/g, 'false');

  // Handle non-standard "{a, b, c}" storage format.
  if (normalized.startsWith('{') && normalized.endsWith('}')) {
    const inner = normalized.slice(1, -1);
    const items = inner.split(',').map((s) => s.trim().replace(/"/g, ''));
    return items.filter((s) => s.length > 0 && !s.includes(':'));
  }

  return tryParse(normalized);
};

const getArtistAssets = (artist: Artist, token: string | null) => {
  const images = parseStoredJsonArray(artist.images);
  const firstImageEntry = images.find((img) => (typeof img === 'string' ? !!img.trim() : !!img?.url));
  const rawUrl = typeof firstImageEntry === 'string' ? firstImageEntry : firstImageEntry?.url;
  const genres = parseStoredJsonArray(artist.genres).filter((g): g is string => typeof g === 'string');
  const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';
  let imageUrl: string | null = null;
  if (artist.image_path_id) {
    imageUrl = `${API_BASE_URL}/images/entity/artist/${artist.id}?size=512${tokenParam}`;
  } else if (rawUrl) {
    imageUrl = normalizeImageUrl({ candidate: rawUrl, size: 512, token, apiBaseUrl: API_BASE_URL });
  }
  return { imageUrl, genres };
};

export function HiddenArtistsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOption, setSortOption] = useState<'pop-desc' | 'pop-asc' | 'name-asc' | 'favorites'>('name-asc');
  const apiSortOption = sortOption === 'favorites' ? 'name-asc' : sortOption;
  const [genreFilter, setGenreFilter] = useState('');
  const { isArtistsLoading, userId, token } = useApiStore();
  const navigate = useNavigate();
  const tokenUserId = getUserIdFromToken();
  const effectiveUserId = tokenUserId ?? userId ?? null;
  const { artists, isLoading, isLoadingMore, error, total, hasMore, loadMore, removeArtist } = usePaginatedHiddenArtists({
    limit: 50,
    sortOption: apiSortOption,
    userId: effectiveUserId,
    searchTerm,
    genreFilter,
  });
  const { favoriteIds, toggleFavorite: toggleFavoriteDb } = useFavorites('artist', effectiveUserId);
  const [visibleCount, setVisibleCount] = useState(20);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setVisibleCount(20);
  }, [searchTerm, genreFilter, apiSortOption]);

  const genreOptions = useMemo(() => {
    const set = new Set<string>();
    artists.forEach((artist) => {
      parseStoredJsonArray(artist.genres).forEach((genre) => {
        if (typeof genre === 'string' && genre.trim()) set.add(genre.trim());
      });
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [artists]);

  const displayArtists = useMemo(() => artists.slice(0, visibleCount), [artists, visibleCount]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          if (isLoading || artists.length === 0) return;
          setVisibleCount((prev) => Math.min(prev + 20, artists.length));
          if (hasMore && !isLoadingMore && artists.length - visibleCount < 40) loadMore();
        });
      },
      { root: null, rootMargin: '200px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [artists.length, hasMore, isLoading, isLoadingMore, loadMore, visibleCount]);

  const toggleFavorite = async (event: React.MouseEvent, artistId: number) => {
    event.preventDefault();
    event.stopPropagation();
    if (!effectiveUserId) return;
    await toggleFavoriteDb(artistId);
  };

  const restoreArtist = async (event: React.MouseEvent, artistId: number) => {
    event.preventDefault();
    event.stopPropagation();
    if (!effectiveUserId) return;
    try {
      await audio2Api.unhideArtist(artistId, effectiveUserId);
      removeArtist(artistId);
    } catch (err) {
      console.error('Failed to restore hidden artist', err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="filter-card mb-12">
        <div className="filter-panel">
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <div className="filter-stat" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <p className="text-2xl font-bold" style={{ margin: 0, color: 'var(--accent)' }}>
                {total ?? '...'}
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <h3 className="filter-label uppercase tracking-wide" style={{ margin: 0, color: '#fff' }}>
                  Hidden Artists
                </h3>
                <span className="text-xs text-white/70">Cargados: {artists.length}</span>
              </div>
            </div>
            <div style={{ marginTop: 16, width: '100%' }}>
              <button className="btn-ghost" style={{ width: '100%' }} onClick={() => navigate('/artists')}>
                Volver a Artists
              </button>
            </div>
          </div>
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar artista oculto..."
              className="search-input"
            />
            <div className="filter-control rounded-full border border-white/10 bg-[#151823] px-4 py-2" style={{ marginTop: 10 }}>
              <label className="filter-label uppercase tracking-wide text-white shrink-0">Sort by</label>
              <select value={sortOption} onChange={(e) => setSortOption(e.target.value as typeof sortOption)} className="filter-select text-white">
                <option value="name-asc">Name (A → Z)</option>
                <option value="pop-desc">Popularity (high → low)</option>
                <option value="pop-asc">Popularity (low → high)</option>
                <option value="favorites">Favoritos</option>
              </select>
            </div>
          </div>
          <div style={{ flexBasis: 'calc(33.33% - 1rem)', flexGrow: 0, flexShrink: 0 }}>
            <div className="filter-control rounded-full border border-white/10 bg-[#151823] px-4 py-2">
              <label className="filter-label uppercase tracking-wide text-white shrink-0">Genre</label>
              <select value={genreFilter} onChange={(e) => setGenreFilter(e.target.value)} className="filter-select text-white">
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

      {error && <div className="p-4 bg-destructive/10 text-destructive rounded-lg">{error}</div>}

      {(isLoading || isArtistsLoading) && artists.length === 0 && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mr-3" />
          Loading hidden artists...
        </div>
      )}

      {!isLoading && !isArtistsLoading && (
        <div className="space-y-4">
          <div className="artists-grid">
            {displayArtists.map((artist) => {
              const { imageUrl, genres } = getArtistAssets(artist, token);
              const isFavorite = favoriteIds.has(artist.id);
              return (
                <div
                  key={artist.spotify_id || `hidden-local-${artist.id}`}
                  className="flex flex-col items-center justify-center gap-3 rounded-2xl bg-transparent p-6 text-center text-white"
                  style={{ height: 'var(--artist-card-height, 360px)' }}
                >
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={artist.name}
                      loading="lazy"
                      style={{ width: 'var(--artist-avatar-size, 200px)', height: 'var(--artist-avatar-size, 200px)', borderRadius: '50%', objectFit: 'cover' }}
                    />
                  ) : (
                    <div
                      style={{
                        width: 'var(--artist-avatar-size, 200px)',
                        height: 'var(--artist-avatar-size, 200px)',
                        borderRadius: '50%',
                        border: '1px solid var(--border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: '#0f1320',
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
                    {genres.length > 0 && (
                      <p className="truncate" style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginTop: 4 }}>
                        {genres.slice(0, 3).join(', ')}
                      </p>
                    )}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginTop: 8, gap: 12 }}>
                    <button
                      type="button"
                      onClick={(e) => void toggleFavorite(e, artist.id)}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: isFavorite ? 'rgba(236, 72, 153, 0.15)' : 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: isFavorite ? '#ec4899' : '#fff',
                      }}
                    >
                      <Heart className="h-4 w-4" style={{ fill: isFavorite ? '#ec4899' : 'none', color: isFavorite ? '#ec4899' : '#fff' }} />
                      <span style={{ fontSize: 12 }}>Favorito</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => void restoreArtist(e, artist.id)}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: '#fff',
                      }}
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span style={{ fontSize: 12 }}>Restaurar</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <div ref={loadMoreRef} style={{ height: 1 }} />
          {isLoadingMore && <div className="text-center text-sm text-white/70">Cargando más artistas...</div>}
          {!isLoadingMore && !hasMore && artists.length > 0 && <div className="text-center text-sm text-white/50">Fin de la lista</div>}
        </div>
      )}
    </div>
  );
}
