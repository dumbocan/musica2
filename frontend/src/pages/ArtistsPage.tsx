import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import type { Artist } from '@/types/api';
import { Music, Loader2, Heart, Trash2 } from 'lucide-react';
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
  const { artists, isLoading, error, total } = usePaginatedArtists({ limit: 1000, sortOption });
  const { isArtistsLoading, userId } = useApiStore();
  const navigate = useNavigate();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set());
  const [hiddenIds, setHiddenIds] = useState<Set<number>>(new Set());
  const [visibleCount, setVisibleCount] = useState(20);

  useEffect(() => {
    setVisibleCount(20);
  }, [searchTerm, genreFilter, sortOption]);

  useEffect(() => {
    let aborted = false;
    const loadPreferences = async () => {
      if (!userId) {
        setFavoriteIds(new Set());
        setHiddenIds(new Set());
        return;
      }
      try {
        const [favoriteRes, hiddenRes] = await Promise.all([
          audio2Api.listFavorites({ user_id: userId, target_type: 'artist' }),
          audio2Api.listHiddenArtists({ user_id: userId })
        ]);
        if (aborted) return;
        const favSet = new Set<number>();
        (favoriteRes.data || []).forEach((fav: any) => {
          if (typeof fav?.artist_id === 'number') {
            favSet.add(fav.artist_id);
          }
        });
        const hiddenSet = new Set<number>();
        (hiddenRes.data || []).forEach((entry: any) => {
          if (typeof entry?.artist_id === 'number') {
            hiddenSet.add(entry.artist_id);
          }
        });
        setFavoriteIds(favSet);
        setHiddenIds(hiddenSet);
      } catch (prefErr) {
        console.error('Failed to load artist preferences', prefErr);
      }
    };
    loadPreferences();
    return () => {
      aborted = true;
    };
  }, [userId]);

  const genreOptions = useMemo(() => {
    const set = new Set<string>();
    artists.forEach((artist) => {
      parseStoredJsonArray(artist.genres).forEach((genre) => {
        if (typeof genre === 'string' && genre.trim()) set.add(genre.trim());
      });
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [artists]);

  const visibleArtists = useMemo(
    () => artists.filter((artist) => !hiddenIds.has(artist.id)),
    [artists, hiddenIds]
  );

  const filteredArtists = useMemo(() => {
    return visibleArtists.filter((artist) => {
      const matchesSearch = artist.name.toLowerCase().includes(searchTerm.toLowerCase());
      const genres = parseStoredJsonArray(artist.genres)
        .map((g) => (typeof g === 'string' ? g.toLowerCase() : ''))
        .filter(Boolean);
      const matchesGenre = !genreFilter || genres.includes(genreFilter.toLowerCase());
      return matchesSearch && matchesGenre;
    });
  }, [visibleArtists, searchTerm, genreFilter]);

  const displayArtists = useMemo(() => filteredArtists.slice(0, visibleCount), [filteredArtists, visibleCount]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          setVisibleCount((prev) => Math.min(prev + 20, filteredArtists.length));
        });
      },
      { root: null, rootMargin: '200px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [filteredArtists.length]);

  const disabledActions = !userId;

  const toggleFavorite = async (event: React.MouseEvent, artistId: number) => {
    event.preventDefault();
    event.stopPropagation();
    if (!userId) return;
    try {
      if (favoriteIds.has(artistId)) {
        await audio2Api.removeFavorite('artist', artistId, userId);
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          next.delete(artistId);
          return next;
        });
      } else {
        await audio2Api.addFavorite('artist', artistId, userId);
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          next.add(artistId);
          return next;
        });
      }
    } catch (err) {
      console.error('Failed to toggle favorite', err);
    }
  };

  const hideArtist = async (event: React.MouseEvent, artistId: number) => {
    event.preventDefault();
    event.stopPropagation();
    if (!userId) return;
    try {
      await audio2Api.hideArtist(artistId, userId);
      setHiddenIds((prev) => {
        const next = new Set(prev);
        next.add(artistId);
        return next;
      });
    } catch (err) {
      console.error('Failed to hide artist', err);
    }
  };

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
            <div className="filter-stat" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <p className="text-2xl font-bold" style={{ margin: 0, color: 'var(--accent)' }}>
                {total ?? '...'}
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <h3 className="filter-label uppercase tracking-wide" style={{ margin: 0, color: '#fff' }}>
                  Artists Found
                </h3>
                <span className="text-xs text-white/70">
                  Filtered: {filteredArtists.length}
                </span>
              </div>
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

              const isFavorite = favoriteIds.has(artist.id);
              return (
                <div
                  key={artist.spotify_id || `local-${artist.id}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    if (artist.spotify_id) {
                      navigate(`/artists/${artist.spotify_id}`);
                    }
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && artist.spotify_id) {
                      navigate(`/artists/${artist.spotify_id}`);
                    }
                  }}
                  className={`flex flex-col items-center justify-center gap-3 rounded-2xl bg-transparent p-6 text-center text-white transition ${
                    disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
                  }`}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '20px',
                    background: 'none',
                    border: 'none',
                    outline: 'none'
                  }}
                >
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={artist.name}
                      loading="lazy"
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
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      width: '100%',
                      marginTop: 8,
                      gap: 12
                    }}
                  >
                    <button
                      type="button"
                      onClick={(e) => toggleFavorite(e, artist.id)}
                      disabled={disabledActions}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: isFavorite ? 'rgba(236, 72, 153, 0.15)' : 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: isFavorite ? '#ec4899' : '#fff',
                        opacity: disabledActions ? 0.4 : 1
                      }}
                    >
                      <Heart
                        className="h-4 w-4"
                        style={{ fill: isFavorite ? '#ec4899' : 'none', color: isFavorite ? '#ec4899' : '#fff' }}
                      />
                      <span style={{ fontSize: 12 }}>Favorito</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => hideArtist(e, artist.id)}
                      disabled={disabledActions}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: '#fff',
                        opacity: disabledActions ? 0.4 : 1
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                      <span style={{ fontSize: 12 }}>Ocultar</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <div ref={loadMoreRef} style={{ height: 1 }} />
        </div>
      )}
    </div>
  );
}
