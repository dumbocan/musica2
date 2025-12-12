import { useState } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { SpotifyArtist, SearchArtistsResponse } from '@/types/api';
import { Search, Loader2, Music, Users, Globe } from 'lucide-react';

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SpotifyArtist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const { setSearchQuery, setSearchResults, setSearching } = useApiStore();

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError('');
    setSearchQuery(query);

    try {
      const response: SearchArtistsResponse = await audio2Api.searchArtistsAutoDownload({
        q: query,
        user_id: 1,
        expand_library: true
      });

      setResults(response.artists || []);
      setSearchResults(response.artists || []);

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
      await audio2Api.searchArtistsAutoDownload({
        q: artistName,
        user_id: 1,
        expand_library: true
      });
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
      <form onSubmit={handleSearch} className="flex gap-4">
        <div className="flex-1">
          <Input
            type="text"
            placeholder="Enter artist name..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="text-lg p-3"
          />
        </div>
        <Button
          type="submit"
          disabled={isLoading}
          className="px-8"
        >
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Search className="h-5 w-5" />
          )}
          <span className="ml-2">Search</span>
        </Button>
      </form>

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

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {results.map((artist, index) => (
              <div
                key={artist.id}
                className="border rounded-lg p-6 hover:shadow-lg transition-shadow"
              >
                {/* Artist Image */}
                {artist.images && artist.images.length > 0 ? (
                  <img
                    src={artist.images[0].url}
                    alt={artist.name}
                    className="w-24 h-24 rounded-lg object-cover mx-auto mb-4"
                  />
                ) : (
                  <div className="w-24 h-24 rounded-lg bg-muted flex items-center justify-center mx-auto mb-4">
                    <Music className="h-12 w-12 text-muted-foreground" />
                  </div>
                )}

                {/* Artist Info */}
                <h3 className="font-semibold text-center mb-2">{artist.name}</h3>

                <div className="space-y-2 text-sm">
                  {index === 0 && (
                    <div className="text-xs bg-primary/10 text-primary px-2 py-1 rounded text-center font-medium">
                      Expanding Library +15 Related Artists
                    </div>
                  )}

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

                {/* Actions */}
                <div className="mt-4 space-y-2">
                  <Button
                    onClick={() => handleAutoExpansion(artist.name)}
                    disabled={isLoading}
                    className="w-full"
                    variant="default"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Music className="h-4 w-4 mr-2" />
                    )}
                    Expand Library
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      // View full discography
                      window.location.href = `/artists/discography/${artist.id}`;
                    }}
                  >
                    View Discography
                  </Button>
                </div>
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
