import { useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Artist } from '@/types/api';
import { Music, Loader2, RefreshCw, ExternalLink } from 'lucide-react';

export function ArtistsPage() {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const { isArtistsLoading } = useApiStore();

  useEffect(() => {
    loadArtists();
  }, []);

  const loadArtists = async () => {
    setIsLoading(true);
    setError('');

    try {
      const res = await audio2Api.getAllArtists();
      const data = res.data || [];
      setArtists(data.slice(0, 50)); // Limit for performance
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

      {/* Artist Grid */}
      {!isLoading && !isArtistsLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredArtists.map((artist) => (
            <div
              key={artist.id}
              className="border rounded-lg p-6 hover:shadow-lg transition-shadow"
            >
              {/* Artist Header */}
              <div className="flex items-center space-x-4 mb-4">
                {artist.images ? (
                  <img
                    src={JSON.parse(artist.images)[0]?.url || ''}
                    alt={artist.name}
                    className="w-16 h-16 rounded-lg object-cover"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                ) : null}

                {!artist.images && (
                  <div className="w-16 h-16 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Music className="h-8 w-8 text-primary" />
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-lg truncate">{artist.name}</h3>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    {artist.popularity > 0 && (
                      <span>Popularity: {artist.popularity}</span>
                    )}
                    {artist.followers && artist.followers > 0 && (
                      <span>{artist.followers.toLocaleString()} followers</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Artist Details */}
              <div className="space-y-2 text-sm">
                {artist.genres && (
                  <div>
                    <span className="font-medium">Genres:</span>{' '}
                    <span className="text-muted-foreground">
                      {[artist.genres].flat().slice(0, 3).join(', ')}
                    </span>
                  </div>
                )}

                {artist.bio_summary && (
                  <div>
                    <span className="font-medium">Bio:</span>{' '}
                    <span className="text-muted-foreground line-clamp-2">
                      {artist.bio_summary}
                    </span>
                  </div>
                )}

                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Added: {formatDate(artist.created_at)}</span>
                  <span>Updated: {formatDate(artist.updated_at)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-4 flex gap-2">
                <Button variant="outline" size="sm" className="flex-1">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Discography
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    // TODO: Implement enrich bio
                  }}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
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
