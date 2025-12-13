import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import type { SpotifyArtist, SpotifyTrackLite } from '@/types/api';
import { Search, Loader2, Music, Users, Globe } from 'lucide-react';

type ArtistInfo = {
  spotify: SpotifyArtist;
  lastfm?: {
    summary?: string;
    stats?: { listeners?: string | number; playcount?: string | number };
    tags?: Array<{ name?: string }>;
  };
};

export function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SpotifyArtist[]>([]);
  const [relatedResults, setRelatedResults] = useState<SpotifyArtist[]>([]);
  const [trackResults, setTrackResults] = useState<SpotifyTrackLite[]>([]);
  const [mainInfo, setMainInfo] = useState<ArtistInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();

  const stripHtml = (html?: string) => (html ? html.replace(/<[^>]*>/g, '').trim() : '');

  const {
    searchQuery: storedQuery,
    searchResults: storedResults,
    relatedSearchResults: storedRelatedResults,
    searchMainInfo: storedMainInfo,
    trackSearchResults: storedTrackResults,
    setSearchQuery,
    setSearchResults,
    setRelatedSearchResults,
    setTrackSearchResults,
    setSearchMainInfo,
    setSearching
  } = useApiStore();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    if (!value.trim()) {
      setResults([]);
      setRelatedResults([]);
      setTrackResults([]);
      setMainInfo(null);
      setHasSearched(false);
      setSearchResults([]);
      setRelatedSearchResults([]);
      setTrackSearchResults([]);
      setSearchMainInfo(null);
    }
  };

  useEffect(() => {
    if (storedQuery) setQuery(storedQuery);
    if (storedResults?.length) {
      setResults(storedResults as SpotifyArtist[]);
      setHasSearched(true);
    }
    if (storedRelatedResults?.length) {
      setRelatedResults(storedRelatedResults as SpotifyArtist[]);
      setHasSearched(true);
    }
    if (storedMainInfo) {
      setMainInfo(storedMainInfo as ArtistInfo);
      setHasSearched(true);
    }
    if (storedTrackResults?.length) {
      setTrackResults(storedTrackResults as SpotifyTrackLite[]);
      setHasSearched(true);
    }
  }, [storedQuery, storedResults, storedRelatedResults, storedMainInfo, storedTrackResults]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);
    setError('');
    setSearchQuery(query);
    setSearching(true);

    try {
      const response = await audio2Api.searchSpotify(query);
      const baseItems: SpotifyArtist[] = Array.isArray(response.data?.artists)
        ? (response.data.artists as SpotifyArtist[])
        : [];
      const trackItems: SpotifyTrackLite[] = Array.isArray(response.data?.tracks)
        ? (response.data.tracks as SpotifyTrackLite[])
        : [];

      // Primario: búsqueda directa Spotify
      const baseFiltered = baseItems
        .filter((artist) => (artist.followers?.total || 0) >= 1_000_000)
        .map((artist) => ({ ...artist, _source: 'search' } as SpotifyArtist & { _source?: string }))
        .sort((a, b) => (b.popularity ?? 0) - (a.popularity ?? 0));
      const baseIds = new Set(baseFiltered.map((a) => a.id));

      // Secundario: relacionados por Last.fm enriquecidos con Spotify
      let relatedList: (SpotifyArtist & { listeners?: number; tags?: any; _source?: string })[] = [];
      if (baseItems.length > 0) {
        const main = baseItems[0];
        try {
          const relatedRes = await audio2Api.getRelatedArtists(main.id);
          const data = relatedRes?.data || {};
          const top = Array.isArray(data.top) ? data.top : [];

          relatedList = top
            .map((r: any) => {
              const s = r.spotify || {};
              const followers = s.followers || { total: 0 };
              const name = r.name || s.name;
              const id = s.id;
              if (!name || !id) return null;
              return {
                ...s,
                id,
                name,
                followers,
                popularity: s.popularity,
                images: s.images || [],
                _source: 'lastfm',
                listeners: r.listeners,
                tags: r.tags
              } as SpotifyArtist & { listeners?: number; tags?: any; _source?: string };
            })
            .filter(Boolean)
            .filter((artist: SpotifyArtist | null): artist is SpotifyArtist => !!artist)
            .filter((artist: SpotifyArtist) => (artist.followers?.total || 0) >= 1_000_000)
            .filter((artist: SpotifyArtist) => !baseIds.has(artist.id))
            .sort(
              (a: SpotifyArtist & { popularity?: number }, b: SpotifyArtist & { popularity?: number }) =>
                (b.popularity ?? 0) - (a.popularity ?? 0)
            ) as (SpotifyArtist & {
              listeners?: number;
              tags?: any;
              _source?: string;
            })[];

          // Deduplicate related by id
          const seen = new Set<string>();
          relatedList = relatedList.filter((artist) => {
            if (seen.has(artist.id)) return false;
            seen.add(artist.id);
            return true;
          });
        } catch (relErr) {
          console.warn('Related artists failed:', relErr);
        }
      }

      // Elegir artista principal para la tarjeta: prioriza el artista del primer track si existe
      const trackMainId = trackItems[0]?.artists?.[0]?.id;
      const mainIdForCard = trackMainId || baseFiltered[0]?.id;

      if (mainIdForCard) {
        try {
          const infoRes = await audio2Api.getArtistInfo(mainIdForCard);
          const info = infoRes.data as ArtistInfo;
          setMainInfo(info);
          setSearchMainInfo(info);
        } catch (infoErr) {
          console.warn('Artist info failed:', infoErr);
          // fallback con datos mínimos si no hay detalle
          const fallbackArtist = baseFiltered.find((a) => a.id === mainIdForCard);
          if (fallbackArtist) {
            const fallback = { spotify: fallbackArtist } as ArtistInfo;
            setMainInfo(fallback);
            setSearchMainInfo(fallback);
          } else {
            setMainInfo(null);
            setSearchMainInfo(null);
          }
        }
      } else {
        setMainInfo(null);
        setSearchMainInfo(null);
      }

      // Mezcla de directos + relacionados (ambos ya filtrados por 1M y sin duplicados)
      const mainId = mainIdForCard;
      const combined = [...baseFiltered, ...relatedList].filter((artist: SpotifyArtist, idx, arr) => {
        return arr.findIndex((a: SpotifyArtist) => a.id === artist.id) === idx;
      });

      // No repetir en la lista al artista principal que ya está en la tarjeta
      const combinedWithoutMain = combined.filter((a) => a.id !== mainId);

      setResults(combinedWithoutMain);
      setRelatedResults(relatedList);
      setSearchResults(combinedWithoutMain);
      setRelatedSearchResults(relatedList);
      setTrackResults(trackItems || []);
      setTrackSearchResults(trackItems || []);
    } catch (err) {
      console.error('Search failed:', err);
      setError('Error searching artists. Please try again.');
    } finally {
      setIsLoading(false);
      setSearching(false);
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

      {/* Search + Featured artist */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 16,
          alignItems: 'flex-start',
          justifyContent: 'space-between'
        }}
      >
        <div
          className="search-container"
          style={{ flex: '1 1 38%', maxWidth: 520, minWidth: 300 }}
        >
          <form onSubmit={handleSearch} className="search-form">
            <input
              id="q"
              type="text"
              name="q"
              placeholder="Search for artists..."
              value={query}
              onChange={handleInputChange}
              autoComplete="off"
              className="search-input"
            />
            <button type="submit" className="search-button" disabled={isLoading}>
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-6 w-6" />}
            </button>
          </form>
        </div>

        {mainInfo && (
          <div
            className="card"
            style={{
              background: 'var(--panel-2)',
              border: `1px solid var(--border)`,
              borderRadius: 16,
              padding: 16,
              flex: '1 1 58%',
              minWidth: 340,
              maxWidth: 860,
              display: 'flex',
              gap: 16,
              cursor: 'pointer'
            }}
            onClick={() => navigate(`/artists/discography/${mainInfo.spotify.id}`)}
            >
            {mainInfo.spotify.images && mainInfo.spotify.images.length > 0 ? (
              <img
                src={mainInfo.spotify.images[0].url}
                alt={mainInfo.spotify.name}
                style={{ width: 140, height: 140, objectFit: 'cover', borderRadius: 14, flexShrink: 0 }}
              />
            ) : (
              <div
                style={{ width: 140, height: 140, borderRadius: 14, background: 'var(--panel)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <Music className="h-12 w-12 text-muted-foreground" />
              </div>
            )}

            <div className="space-y-2">
              <div>
                <h3 className="text-xl font-semibold">{mainInfo.spotify.name}</h3>
                {mainInfo.spotify.genres?.length > 0 && (
                  <p className="text-sm text-muted-foreground">{mainInfo.spotify.genres.slice(0, 3).join(', ')}</p>
                )}
              </div>

              <div className="flex flex-col gap-1 text-sm text-muted-foreground">
                <span>
                  <Users className="inline h-4 w-4 mr-1" />
                  {mainInfo.spotify.followers?.total?.toLocaleString()} followers (Spotify)
                </span>
                {mainInfo.spotify.popularity !== undefined && (
                  <span>
                    <Globe className="inline h-4 w-4 mr-1" />
                    Popularity: {mainInfo.spotify.popularity}/100
                  </span>
                )}
                {mainInfo.lastfm?.stats && (
                  <span>
                    <Globe className="inline h-4 w-4 mr-1" />
                    {Number(mainInfo.lastfm.stats.listeners || 0).toLocaleString()} listeners (Last.fm)
                  </span>
                )}
                {mainInfo.lastfm?.tags && mainInfo.lastfm.tags.length > 0 && (
                  <span>Tags: {mainInfo.lastfm.tags.slice(0, 4).map((t) => t.name).filter(Boolean).join(', ')}</span>
                )}
              </div>

              <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)' }}>
                {stripHtml(mainInfo.lastfm?.summary) || 'Bio no disponible todavía.'}
              </p>
            </div>
          </div>
        )}
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

      {/* Resultados combinados (Spotify + Related) */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">
            Artists · {results.length}
          </h2>

          <div className="grid-cards" style={{ gap: 18 }}>
            {results.map((artist) => (
              <div
                key={artist.id}
                className="card"
                style={{ background: 'var(--panel-2)', border: `1px solid var(--border)`, borderRadius: 16, padding: 16, minWidth: 262 }}
              >
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
                      {artist.followers.total.toLocaleString()} followers (Spotify)
                    </span>
                  </div>

                  {artist.popularity !== undefined && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Globe className="h-4 w-4" />
                      <span className="text-xs">Popularity (Spotify): {artist.popularity}/100</span>
                    </div>
                  )}

                  {'listeners' in artist && (artist as any).listeners !== undefined && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Globe className="h-4 w-4" />
                      <span className="text-xs">
                        {Number((artist as any).listeners || 0).toLocaleString()} listeners (Last.fm)
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tracks */}
      {trackResults.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Tracks · {trackResults.length}</h2>
          <div className="grid-cards" style={{ gap: 18 }}>
            {trackResults.map((track) => (
              <div
                key={`track-${track.id}`}
                className="card"
                style={{ background: 'var(--panel-2)', border: `1px solid var(--border)`, borderRadius: 16, padding: 16, minWidth: 262 }}
              >
                <div className="flex items-start gap-3">
                  {track.album?.images && track.album.images.length > 0 ? (
                    <img
                      src={track.album.images[0].url}
                      alt={track.album.name}
                      style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 12 }}
                    />
                  ) : (
                    <div style={{ width: 72, height: 72, borderRadius: 12, background: 'var(--panel)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Music className="h-8 w-8 text-muted-foreground" />
                    </div>
                  )}
                  <div className="space-y-1">
                    <div className="font-semibold">{track.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {track.artists?.map((a) => a.name).join(', ')}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {Math.round(track.duration_ms / 1000 / 60)}:{String(Math.round((track.duration_ms / 1000) % 60)).padStart(2, '0')} · Popularity {track.popularity}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && results.length === 0 && relatedResults.length === 0 && query && hasSearched && (
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
