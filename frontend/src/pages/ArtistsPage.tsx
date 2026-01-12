import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL, audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { useFavorites } from '@/hooks/useFavorites';
import type { Artist } from '@/types/api';
import { Loader2, Heart, Trash2 } from 'lucide-react';
import { usePaginatedArtists } from '@/hooks/usePaginatedArtists';

const parseStoredJsonArray = (raw?: string | null): unknown[] => {
  if (!raw) return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];

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

type HiddenArtistEntry = { artist_id: number };

export function ArtistsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOption, setSortOption] = useState<'pop-desc' | 'pop-asc' | 'name-asc' | 'favorites'>('pop-desc');
  const apiSortOption = sortOption === 'favorites' ? 'pop-desc' : sortOption;
  const [genreFilter, setGenreFilter] = useState('');
  const { artists, isLoading, error, total } = usePaginatedArtists({ limit: 1000, sortOption: apiSortOption });
  const { isArtistsLoading, userId } = useApiStore();
  const navigate = useNavigate();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const {
    favoriteIds,
    toggleFavorite: toggleArtistFavorite,
    effectiveUserId: effectiveArtistUserId
  } = useFavorites('artist', userId);
  const [hiddenIds, setHiddenIds] = useState<Set<number>>(new Set());
  const [visibleCount, setVisibleCount] = useState(20);

  useEffect(() => {

  }, [searchTerm, genreFilter, sortOption]);

  useEffect(() => {
    let aborted = false;
    const loadPreferences = async () => {
      if (!userId) {
        setHiddenIds(new Set());
        return;
      }
      try {
        const hiddenRes = await audio2Api.listHiddenArtists({ user_id: userId });
        if (aborted) return;
        const hiddenSet = new Set<number>();
        (hiddenRes.data || []).forEach((entry: HiddenArtistEntry) => {
          if (typeof entry?.artist_id === 'number') {
            hiddenSet.add(entry.artist_id);
          }
        });
        setHiddenIds(hiddenSet);
      } catch (prefErr) {
        console.error('Failed to load hidden artists', prefErr);
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
      if (sortOption === 'favorites' && !favoriteIds.has(artist.id)) return false;
      const matchesSearch = artist.name.toLowerCase().includes(searchTerm.toLowerCase());
      const genres = parseStoredJsonArray(artist.genres)
        .map((g) => (typeof g === 'string' ? g.toLowerCase() : ''))
        .filter(Boolean);
      const matchesGenre = !genreFilter || genres.includes(genreFilter.toLowerCase());
      return matchesSearch && matchesGenre;
    });
  }, [visibleArtists, searchTerm, genreFilter, sortOption, favoriteIds]);

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

  const canFavorite = !!effectiveArtistUserId;
  const canHide = !!userId;

  const toggleFavorite = async (event: React.MouseEvent, artistId: number) => {
    event.preventDefault();
    event.stopPropagation();
    if (!effectiveArtistUserId) return;
    await toggleArtistFavorite(artistId);
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
            <div style={{ marginTop: 16, width: '100%' }}>
              <label className="filter-label uppercase tracking-wide text-white block mb-1">
                Search
              </label>
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Buscar artista..."
                style={{
                  width: '100%',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: 999,
                  padding: '10px 14px',
                  background: 'rgba(0,0,0,0.2)',
                  color: '#fff'
                }}
              />
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
                <option value="favorites">Favoritos</option>
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
          <div className="artists-grid">
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
                    outline: 'none',
                    height: 'var(--artist-card-height, 360px)'
                  }}
                >
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={artist.name}
                      loading="lazy"
                      style={{
                        width: 'var(--artist-avatar-size, 200px)',
                        height: 'var(--artist-avatar-size, 200px)',
                        borderRadius: '50%',
                        objectFit: 'cover',
                        display: 'block',
                        margin: '0 auto 10px auto',
                      }}
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
                    {genres.length > 0 && (
                      <p
                        className="truncate"
                        style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', marginTop: 4 }}
                      >
                        {genres.slice(0, 3).join(', ')}
                      </p>
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
                        disabled={!canFavorite}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: isFavorite ? 'rgba(236, 72, 153, 0.15)' : 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: isFavorite ? '#ec4899' : '#fff',
                        opacity: canFavorite ? 1 : 0.4
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
                        disabled={!canHide}
                      style={{
                        border: '1px solid var(--border)',
                        borderRadius: 999,
                        padding: '6px 10px',
                        background: 'rgba(255,255,255,0.08)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        color: '#fff',
                        opacity: canHide ? 1 : 0.4
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
