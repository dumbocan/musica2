import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { SpotifyArtist } from '@/types/api';
import { Search, Loader2, Music, Users, Globe } from 'lucide-react';

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SpotifyArtist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const {
    searchQuery: storedQuery,
    searchResults: storedResults,
    setSearchQuery,
    setSearchResults,
    setSearching
  } = useApiStore();

  useEffect(() => {
    if (storedQuery) setQuery(storedQuery);
    if (storedResults?.length) setResults(storedResults as SpotifyArtist[]);
  }, [storedQuery, storedResults]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError('');
    setSearchQuery(query);

    try {
      const response = await audio2Api.searchArtists(query);
      const items = response.data || [];
      setResults(items);
      setSearchResults(items);
    } catch (err) {
      console.error('Search failed:', err);
      setError('Error searching artists. Please try again.');
    } finally {
      setIsLoading(false);
      setSearching(false);
    }
  };

  const handleAutoExpansion = async (artistName: string) => {
    setIsLoading(true);
    try {
      const response = await audio2Api.searchArtists(artistName);
      const items = response.data || [];
      setResults(items);
      setSearchResults(items);
      setSearchQuery(artistName);
    } catch (err) {
      console.error('Auto expansion failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Artist Search</h1>
        <p className="text-muted-foreground">
          Search for artists and automatically expand your music library
        </p>
      </div>

      {/* Search Form */}
      <div className="search-container" style={{ width: '40%', minWidth: 300 }}>
        <form onSubmit={handleSearch} className="search-form">
          <input
            id="q"
            type="text"
            name="q"
            placeholder="Search for artists..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="search-input"
          />
          <button type="submit" className="search-button" disabled={isLoading}>
            {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-6 w-6" />}
          </button>
        </form>
      </div>

      <style>
        {`
        input::placeholder {
          color: #ffffff;
          opacity: 0.7;
        }
        `}
      </style>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">
            Found {results.length} artist{results.length !== 1 ? 's' : ''}
          </h2>

          <div className="grid-cards" style={{ gap: 18 }}>
            {results.map((artist, index) => (
              <div
                key={artist.id}
                className="card"
                style={{ background: 'var(--panel-2)', border: `1px solid var(--border)`, borderRadius: 16, padding: 16, minWidth: 262 }}
              >
                {/* Artist Image */}
                {artist.images && artist.images.length > 0 ? (
                  <img
                    src={artist.images[0].url}
                    alt={artist.name}
                    className="mx-auto mb-3"
                    style={{ width: 148, height: 148, objectFit: 'cover', borderRadius: 14, cursor: 'pointer' }}
                    onClick={() => navigate(`/artists/discography/${artist.id}`)}
                  />
                ) : (
                  <div
                    className="mx-auto mb-3"
                    style={{ width: 148, height: 148, borderRadius: 14, background: 'var(--panel)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
                    onClick={() => navigate(`/artists/discography/${artist.id}`)}
                  >
                    <Music className="h-12 w-12 text-muted-foreground" />
                  </div>
                )}

                {/* Artist Info */}
                <h3 className="font-semibold text-center mb-2">{artist.name}</h3>

                <div className="space-y-2 text-sm">
                  {artist.genres && artist.genres.length > 0 && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Music className="h-4 w-4" />
                      <span className="text-xs">
                        {artist.genres.slice(0, 2).join(', ')}
                      </span>
                    </div>
                  )}

                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Users className="h-4 w-4" />
                    <span className="text-xs">
                      {artist.followers.total.toLocaleString()} followers
                    </span>
                  </div>

                  {artist.popularity !== undefined && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Globe className="h-4 w-4" />
                      <span className="text-xs">Popularity: {artist.popularity}/100</span>
                    </div>
                  )}
                </div>

                {/* Discography link on image handled by click */}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && results.length === 0 && query && (
        <div className="text-center py-12">
          <Music className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No artists found</h3>
          <p className="text-muted-foreground">
            Try searching with a different spelling or check your internet connection.
          </p>
        </div>
      )}
    </div>
  );
}
