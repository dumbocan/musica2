import { useEffect, useRef, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import type { SpotifyArtist, SpotifyTrackLite } from '@/types/api';
import { Music } from 'lucide-react';

type ArtistInfo = {
  spotify: SpotifyArtist;
  lastfm?: {
    summary?: string;
    stats?: { listeners?: string | number; playcount?: string | number };
    tags?: Array<{ name?: string }>;
  };
};

type SearchMode = 'tag' | 'artist';

export function SearchPage() {
  const [lastfmEnriched, setLastfmEnriched] = useState<any[]>([]);
  const [lastfmArtists, setLastfmArtists] = useState<any[]>([]);
  const [page, setPage] = useState(0);
  const [hasMoreLastfm, setHasMoreLastfm] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const [visibleCount, setVisibleCount] = useState(20);
  const [searchMode, setSearchMode] = useState<SearchMode>('tag');
  const [artistProfile, setArtistProfile] = useState<any | null>(null);
  const [artistSimilar, setArtistSimilar] = useState<any[]>([]);
  const [trackResults, setTrackResults] = useState<any[]>([]);

  const {
    searchMainInfo,
    searchQuery,
    searchTrigger,
    setSearchQuery,
    setSearchResults,
    setRelatedSearchResults,
    setTrackSearchResults,
    setSearchMainInfo,
    setSearching
  } = useApiStore();
  const lastTriggerRef = useRef<number>(0);
  const navigate = useNavigate();

  const genreKeywords = useMemo(
    () => [
      'hip hop', 'hip-hop', 'rap', 'trap', 'boom bap', 'gangsta',
      'rock', 'metal', 'grunge', 'punk', 'indie', 'alt',
      'pop', 'k-pop',
      'reggaeton',
      'edm', 'electronic', 'house', 'techno', 'trance', 'dnb', 'drum and bass',
      'folk', 'country', 'jazz', 'blues', 'soul', 'r&b', 'rb'
    ],
    []
  );

  const inferMode = (query: string): SearchMode => {
    const ql = query.toLowerCase();
    if (genreKeywords.some((g) => ql.includes(g))) return 'tag';
    return 'artist';
  };

  const performSearch = async (queryToUse: string, pageToLoad: number = 0, append = false) => {
    if (!queryToUse.trim()) return;
    const mode = inferMode(queryToUse);
    setSearchMode(mode);
    setSearchQuery(queryToUse);
    setSearching(true);
    setIsLoading(!append);
    setIsLoadingMore(append);
    try {
      if (mode === 'tag') {
        const limit = 20;
        const lastfmLimit = 60;
        const response = await audio2Api.searchOrchestrated({
          q: queryToUse,
          limit,
          page: pageToLoad,
          lastfm_limit: lastfmLimit,
          related_limit: 6
        });
        const data = response.data || {};
        const artists: SpotifyArtist[] = Array.isArray(data.artists) ? data.artists : [];
        const relatedList: any[] = Array.isArray(data.related) ? data.related : [];
        const relatedFlattened = relatedList
          .map((r) => (r && r.spotify ? r.spotify : r))
          .filter(Boolean) as SpotifyArtist[];
        const tracks: SpotifyTrackLite[] = Array.isArray(data.tracks) ? data.tracks : [];
        const main = data.main as ArtistInfo | null;
        const lastfmTop: any[] = Array.isArray(data.lastfm_top) ? data.lastfm_top : [];

        if (!append) {
          setSearchMainInfo(main);
          setSearchResults(artists);
          setRelatedSearchResults(relatedFlattened);
          setTrackSearchResults(tracks || []);
          setLastfmArtists(lastfmTop);
          setLastfmEnriched(lastfmTop);
          setArtistProfile(null);
          setArtistSimilar([]);
          setPage(pageToLoad);
          setVisibleCount(20);
          const trackRes = await audio2Api.searchTracksQuick({ q: queryToUse, limit: 5 });
          setTrackResults(trackRes.data?.tracks || []);
        } else {
          const current = useApiStore.getState();
          setSearchMainInfo(searchMainInfo || main);
          setSearchResults([...(current.searchResults as SpotifyArtist[]), ...artists]);
          setRelatedSearchResults([...(current.relatedSearchResults as SpotifyArtist[]), ...relatedFlattened]);
          setTrackSearchResults([...(current.trackSearchResults as SpotifyTrackLite[]), ...tracks]);
          setLastfmArtists((prev) => [...prev, ...lastfmTop]);
          setLastfmEnriched((prev) => [...prev, ...lastfmTop]);
          setPage(pageToLoad);
        }

        setHasMoreLastfm(Boolean(data.has_more_lastfm));
      } else {
        const response = await audio2Api.searchArtistProfile({ q: queryToUse, similar_limit: 10 });
        const data = response.data || {};
        const main = data.main as ArtistInfo | null;
        const similar = Array.isArray(data.similar) ? data.similar : [];
        const trackRes = await audio2Api.searchTracksQuick({ q: queryToUse, limit: 5 });
        setTrackResults(trackRes.data?.tracks || []);
        setArtistProfile(main);
        setArtistSimilar(similar);
        setSearchMainInfo(main);
        setSearchResults([]);
        setRelatedSearchResults([]);
        setTrackSearchResults([]);
        setLastfmArtists([]);
        setLastfmEnriched([]);
        setHasMoreLastfm(false);
        setVisibleCount(0);
      }
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setSearching(false);
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  };

  const handleLoadMore = () => {
    if (searchMode !== 'tag') return;
    if (isLoadingMore || !hasMoreLastfm) return;
    performSearch(searchQuery, page + 1, true);
  };

  // Infinite scroll observer for Last.fm cards
  useEffect(() => {
    if (searchMode !== 'tag') return;
    const target = loadMoreRef.current;
    if (!target) return;
    const totalList = (lastfmEnriched.length ? lastfmEnriched : lastfmArtists).length;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const currentTotal = (lastfmEnriched.length ? lastfmEnriched : lastfmArtists).length;
          if (visibleCount < currentTotal) {
            setVisibleCount((prev) => Math.min(prev + 20, currentTotal));
            return;
          }
          if (!isLoadingMore && !isLoading && hasMoreLastfm && searchQuery) {
            handleLoadMore();
          }
        });
      },
      { root: null, rootMargin: '200px', threshold: 0 }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [isLoadingMore, isLoading, hasMoreLastfm, searchQuery, page, visibleCount, lastfmEnriched, lastfmArtists, searchMode]);

  // Triggered from topbar search
  useEffect(() => {
    if (searchTrigger && searchQuery && searchTrigger !== lastTriggerRef.current) {
      lastTriggerRef.current = searchTrigger;
      performSearch(searchQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTrigger]);

  return (
    <div className="space-y-6">
      {searchMode === 'artist' && artistProfile && (
        <div className="space-y-4">
          <div
            className="card"
            style={{
              background: 'var(--panel-2)',
              border: `1px solid var(--border)`,
              borderRadius: 16,
              padding: 16,
              display: 'grid',
              gridTemplateColumns: '220px 1fr',
              gap: 16,
              alignItems: 'stretch'
            }}
          >
            <div
              style={{ cursor: artistProfile.spotify?.id ? 'pointer' : 'default' }}
              onClick={() => {
                if (artistProfile.spotify?.id) {
                  navigate(`/artists/discography/${artistProfile.spotify.id}`);
                }
              }}
            >
              {(() => {
                const spImg = artistProfile.spotify?.images?.[0]?.url;
                const lfmImgs = Array.isArray(artistProfile.lastfm?.image) ? artistProfile.lastfm?.image : [];
                const lfmPreferred =
                  lfmImgs.find((im: any) => im?.size === 'extralarge') ||
                  lfmImgs.find((im: any) => im?.size === 'large') ||
                  lfmImgs.find((im: any) => im?.size === 'medium');
                const lfmUrl = lfmPreferred?.['#text'];
                const img = spImg || lfmUrl;
                if (img) {
                  return (
                    <img
                      src={img}
                      alt={artistProfile.spotify?.name || searchQuery}
                      style={{ width: '100%', height: 220, objectFit: 'cover', borderRadius: 12 }}
                    />
                  );
                }
                return (
                  <div
                    style={{
                      width: '100%',
                      height: 220,
                      borderRadius: 12,
                      background: 'var(--panel)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                  >
                    <Music className="h-12 w-12 text-muted-foreground" />
                  </div>
                );
              })()}
            </div>
            <div className="space-y-3">
              <div>
                <h2 className="text-2xl font-bold">{artistProfile.spotify?.name || searchQuery}</h2>
                <p className="text-sm text-muted-foreground">Bio de Last.fm + datos de Spotify</p>
              </div>
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                {artistProfile.spotify?.followers?.total && (
                  <span>{artistProfile.spotify.followers.total.toLocaleString()} followers (Spotify)</span>
                )}
                {artistProfile.spotify?.popularity !== undefined && (
                  <span>Popularidad: {artistProfile.spotify.popularity}/100</span>
                )}
                {artistProfile.lastfm?.stats?.listeners && (
                  <span>{Number(artistProfile.lastfm.stats.listeners).toLocaleString()} oyentes (Last.fm)</span>
                )}
                {artistProfile.lastfm?.stats?.playcount && (
                  <span>{Number(artistProfile.lastfm.stats.playcount).toLocaleString()} reproducciones (Last.fm)</span>
                )}
              </div>
              {artistProfile.lastfm?.summary && (
                <div
                  className="text-sm text-muted-foreground"
                  style={{ maxHeight: 160, overflow: 'hidden', cursor: artistProfile.spotify?.id ? 'pointer' : 'default' }}
                  onClick={() => {
                    if (artistProfile.spotify?.id) {
                      navigate(`/artists/discography/${artistProfile.spotify.id}`);
                    }
                  }}
                  dangerouslySetInnerHTML={{
                    __html: (() => {
                      const text = artistProfile.lastfm.summary.replace(/<br\s*\/?>/gi, ' ').replace(/<\/p>/gi, ' ').replace(/<[^>]+>/g, '');
                      const words = text.split(/\s+/).filter(Boolean).slice(0, 80).join(' ');
                      return `${words}${text.length > words.length ? '…' : ''}`;
                    })()
                  }}
                />
              )}
              {artistProfile.spotify?.id && (
                <button
                  onClick={() => navigate(`/artists/discography/${artistProfile.spotify.id}`)}
                  style={{
                    padding: '8px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border)',
                    background: 'var(--panel)',
                    cursor: 'pointer',
                    fontSize: 12,
                    width: 'fit-content'
                  }}
                >
                  Ver bio completa y discografía
                </button>
              )}
              {Array.isArray(artistProfile.lastfm?.tags) && artistProfile.lastfm.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 text-xs">
                  {artistProfile.lastfm.tags.slice(0, 10).map((t: any) => (
                    <span
                      key={t.name || t}
                      style={{ padding: '4px 8px', borderRadius: 8, background: 'var(--panel)', border: `1px solid var(--border)` }}
                    >
                      {t.name || t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {artistSimilar.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xl font-semibold">Artistas afines</h3>
              <div className="grid-cards" style={{ gap: 18 }}>
                {artistSimilar.slice(0, 10).map((a: any, idx: number) => {
                  const spImg = a.spotify?.images?.[0]?.url;
                  const lfmImgList = Array.isArray(a.image) ? a.image : [];
                  const lfmPreferred =
                    lfmImgList.find((im: any) => im?.size === 'extralarge') ||
                    lfmImgList.find((im: any) => im?.size === 'large') ||
                    lfmImgList.find((im: any) => im?.size === 'medium');
                  const img = spImg || lfmPreferred?.['#text'];
                  return (
                    <div
                      key={`sim-${idx}-${a.name}`}
                      className="card"
                      style={{
                        background: 'var(--panel-2)',
                        border: `1px solid var(--border)`,
                        borderRadius: 16,
                        padding: 14,
                        minWidth: 220
                      }}
                    >
                      {img ? (
                        <img
                          src={img}
                          alt={a.name}
                          loading="lazy"
                          style={{ width: '100%', height: 140, objectFit: 'cover', borderRadius: 12, marginBottom: 8 }}
                        />
                      ) : (
                        <div
                          style={{
                            width: '100%',
                            height: 140,
                            borderRadius: 12,
                            background: 'var(--panel)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginBottom: 8
                          }}
                        >
                          <Music className="h-10 w-10 text-muted-foreground" />
                        </div>
                      )}
                      <div className="font-semibold">{a.name || a.spotify?.name}</div>
                      {a.spotify?.followers?.total !== undefined && (
                        <div className="text-xs text-muted-foreground">
                          {a.spotify.followers.total.toLocaleString()} followers (Spotify)
                        </div>
                      )}
                      {a.spotify?.popularity !== undefined && (
                        <div className="text-xs text-muted-foreground">
                          Popularidad: {a.spotify.popularity}/100
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {searchMode === 'tag' && (lastfmEnriched.length > 0 || lastfmArtists.length > 0) && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Top artistas (Last.fm)</h2>
          <div className="grid-cards" style={{ gap: 18 }}>
            {(lastfmEnriched.length ? lastfmEnriched : lastfmArtists).slice(0, visibleCount).map((a: any, idx: number) => {
              const images = Array.isArray(a.spotify?.images) && a.spotify?.images.length
                ? a.spotify.images.map((im: any) => ({ '#text': im.url }))
                : Array.isArray(a.image)
                  ? a.image
                  : [];
              const preferred =
                images.find((im: any) => im?.size === 'large') ||
                images.find((im: any) => im?.size === 'extralarge') ||
                images.find((im: any) => im?.size === 'medium');
              const fallback = images[images.length - 1];
              const img = preferred || fallback;
              const artistLink = a.spotify?.id ? `/artists/discography/${a.spotify.id}` : a.url;
              const linkProps = a.spotify?.id
                ? { onClick: (e: any) => { e.preventDefault(); navigate(artistLink); } }
                : {};
              return (
                <a
                  key={`lfm-${idx}-${a.name}`}
                  className="card"
                  style={{
                    background: 'var(--panel-2)',
                    border: `1px solid var(--border)`,
                    borderRadius: 16,
                    padding: 14,
                    minWidth: 220,
                    textDecoration: 'none'
                  }}
                  href={artistLink}
                  target={a.spotify?.id ? '_self' : '_blank'}
                  rel="noreferrer"
                  {...linkProps}
                >
                  {img?.['#text'] ? (
                    <img
                      src={img['#text']}
                      alt={a.name}
                      loading="lazy"
                      style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 12, marginBottom: 8 }}
                    />
                  ) : (
                    <div
                      style={{
                        width: '100%',
                        height: 120,
                        borderRadius: 12,
                        background: 'var(--panel)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: 8
                      }}
                    >
                      <Music className="h-10 w-10 text-muted-foreground" />
                    </div>
                  )}
                  <div className="font-semibold">{a.name}</div>
                  {a.spotify?.followers?.total !== undefined && (
                    <div className="text-xs text-muted-foreground">
                      {a.spotify.followers.total.toLocaleString()} followers (Spotify)
                    </div>
                  )}
                  {a.spotify?.popularity !== undefined && (
                    <div className="text-xs text-muted-foreground">
                      Popularity (Spotify): {a.spotify.popularity}/100
                    </div>
                  )}
                  {a.listeners && (
                    <div className="text-xs text-muted-foreground">{Number(a.listeners).toLocaleString()} listeners (Last.fm)</div>
                  )}
                </a>
              );
            })}
          </div>
          <div ref={loadMoreRef} style={{ height: 1 }} />
          {isLoadingMore && (
            <div className="text-sm text-muted-foreground" style={{ textAlign: 'center' }}>
              Cargando más artistas...
            </div>
          )}
        </div>
      )}
      {isLoading && (
        <div className="text-sm text-muted-foreground">Buscando...</div>
      )}
      {trackResults.length > 0 && !artistProfile && (
        <div className="space-y-3">
          <h3 className="text-xl font-semibold">Álbumes con esta canción</h3>
          <div className="space-y-2">
            {Array.from(
              trackResults.reduce((map: Map<string, any>, t: any) => {
                const albumId = t.album?.id;
                if (!albumId) return map;
                if (map.has(albumId)) return map;
                map.set(albumId, t);
                return map;
              }, new Map<string, any>())
            ).map(([albumId, t], idx) => {
              const albumImg = t.album?.images?.[0]?.url;
              const artistNames = (t.artists || []).map((a: any) => a.name).join(', ');
              return (
                <div
                  key={albumId || `${t.name}-${idx}`}
                  className="card"
                  style={{ display: 'grid', gridTemplateColumns: '60px 1fr 140px', gap: 10, alignItems: 'center' }}
                >
                  {albumImg ? (
                    <img src={albumImg} alt={t.album?.name || t.name} style={{ width: 60, height: 60, borderRadius: 8, objectFit: 'cover' }} />
                  ) : (
                    <div
                      style={{
                        width: 60,
                        height: 60,
                        borderRadius: 8,
                        background: 'var(--panel)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      <Music className="h-5 w-5 text-muted-foreground" />
                    </div>
                  )}
                  <div style={{ overflow: 'hidden' }}>
                    <div className="font-semibold" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {t.album?.name || t.name}
                    </div>
                    <div className="text-xs text-muted-foreground" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {artistNames}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    {albumId && (
                      <button
                        className="btn-ghost"
                        style={{ borderRadius: 8, padding: '6px 10px' }}
                        onClick={() => navigate(`/albums/${albumId}`)}
                      >
                        Ver álbum
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
