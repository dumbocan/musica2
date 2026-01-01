import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Artist } from '@/types/api';
import { Music, Loader2, RefreshCw } from 'lucide-react';
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
  const firstImage = images.find((img) => typeof img?.url === 'string');
  const genres = parseStoredJsonArray(artist.genres).filter((g) => typeof g === 'string');

  const proxyUrl = firstImage?.url
    ? `${API_BASE_URL}/images/proxy?url=${encodeURIComponent(firstImage.url)}&size=256`
    : null;

  return {
    imageUrl: proxyUrl ?? null,
    genres,
  };
};

export function ArtistsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const { artists, isLoading, error, hasMore, loadInitial, loadMore } = usePaginatedArtists({ pageSize: 30, searchTerm });
  const { isArtistsLoading } = useApiStore();
  const navigate = useNavigate();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    if (!hasMore || searchTerm.trim()) return;
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
  }, [hasMore, loadMore, searchTerm]);

  const filteredArtists = artists.filter(artist =>
    artist.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Artists Library</h1>
          <p className="text-muted-foreground">
            Browse your saved artists and manage your music collection
          </p>
        </div>
        <Button onClick={loadInitial} disabled={isLoading || isArtistsLoading}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="max-w-sm">
        <Input
          placeholder="Search artists..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold">Total Artists</h3>
          <p className="text-2xl font-bold text-primary">{artists.length}</p>
        </div>
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold">Filtered Results</h3>
          <p className="text-2xl font-bold text-blue-600">{filteredArtists.length}</p>
        </div>
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold">Average Popularity</h3>
          <p className="text-2xl font-bold text-green-600">-</p>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {error}
        </div>
      )}

      {(isLoading || isArtistsLoading) && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mr-3" />
          Loading artists...
        </div>
      )}

      {!isLoading && !isArtistsLoading && (
        <div className="space-y-4">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">Trending</p>
            <h2 className="text-2xl font-semibold">Hot Artists</h2>
          </div>

          <div
            className="grid gap-6"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(6, minmax(0, 1fr))',
            }}
          >
            {filteredArtists.map((artist) => {
              const { imageUrl, genres } = getArtistAssets(artist);
              const disabled = !artist.spotify_id;

              return (
                <button
                  key={artist.id}
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
                  <img
                    src={imageUrl || ''}
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
        </div>
      )}
    </div>
  );
}
