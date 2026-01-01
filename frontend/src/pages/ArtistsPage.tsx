import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api, API_BASE_URL } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Artist } from '@/types/api';
import { Music, Loader2, RefreshCw } from 'lucide-react';

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

  // Backend stores Python-style lists (single quotes), normalize for JSON.parse
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
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const { isArtistsLoading } = useApiStore();
  const navigate = useNavigate();

  useEffect(() => {
    loadArtists();
  }, []);

  const loadArtists = async () => {
    setIsLoading(true);
    setError('');

    try {
      const res = await audio2Api.getAllArtists();
      const data = res.data || [];
      const limited = data.slice(0, 50);
      setArtists(limited);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const filteredArtists = artists.filter(artist =>
    artist.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Artists Library</h1>
          <p className="text-muted-foreground">
            Browse your saved artists and manage your music collection
          </p>
        </div>
        <Button onClick={loadArtists} disabled={isLoading || isArtistsLoading}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Search */}
      <div className="max-w-sm">
        <Input
          placeholder="Search artists..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Stats */}
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

      {/* Error */}
      {error && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {error}
        </div>
      )}

      {/* Loading */}
      {(isLoading || isArtistsLoading) && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mr-3" />
          Loading artists...
        </div>
      )}

      {!isLoading && !isArtistsLoading && (
        <div className="grid grid-cols-1 gap-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4 sm:gap-5">
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
                  className={`w-full h-full text-left rounded-2xl border bg-card/80 p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    disabled ? 'opacity-70 cursor-not-allowed' : ''
                  }`}
                  disabled={disabled}
                >
                  <div className="flex items-center gap-3">
                    {imageUrl ? (
                      <img
                        src={imageUrl}
                        alt={artist.name}
                        className="w-12 h-12 rounded-xl object-cover"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Music className="h-6 w-6 text-primary" />
                      </div>
                    )}
                    <div className="min-w-0">
                      <p className="font-semibold truncate">{artist.name}</p>
                      <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground mt-1">
                        {artist.popularity > 0 && <span>Pop {artist.popularity}</span>}
                        {genres.length > 0 && <span>{genres.slice(0, 2).join(', ')}</span>}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && artists.length === 0 && (
        <div className="text-center py-12">
          <Music className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No artists yet</h3>
          <p className="text-muted-foreground mb-4">
            Start by searching for artists to build your library.
          </p>
          <Button onClick={() => window.location.href = '/search'}>
            Search Artists
          </Button>
        </div>
      )}
    </div>
  );
}
