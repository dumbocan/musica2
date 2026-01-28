import { useCallback, useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  limit?: number;
  sortOption?: 'pop-desc' | 'pop-asc' | 'name-asc';
  userId?: number | null;
  searchTerm?: string;
  genreFilter?: string;
}

type PaginatedArtistsResponse = Artist[] | { items: Artist[], total?: number };

const inFlightRequests = new Map<string, ReturnType<typeof audio2Api.getAllArtists>>();
const responseCache = new Map<string, { ts: number; data: PaginatedArtistsResponse }>();
const CACHE_TTL_MS = 2000;

export function usePaginatedArtists({ limit = 50, sortOption = 'pop-desc', userId, searchTerm, genreFilter }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState<number | null>(null);
  const offsetRef = useRef(0);
  const artistsRef = useRef<Artist[]>([]);
  const inFlightKeyRef = useRef<string | null>(null);
  const lastReloadKeyRef = useRef<string | null>(null);

  const normalizeResponse = useCallback((payload: PaginatedArtistsResponse): { items: Artist[]; total: number | null } => {
    if (Array.isArray(payload)) {
      return { items: payload, total: payload.length };
    }
    if (payload && Array.isArray(payload.items)) {
      return {
        items: payload.items,
        total: typeof payload.total === 'number' ? payload.total : null,
      };
    }
    return { items: [], total: null };
  }, []);

  const fetchPage = useCallback(
    async (offset: number, replace: boolean) => {
      const requestKey = JSON.stringify({
        offset,
        limit,
        sortOption,
        userId,
        searchTerm: searchTerm ?? '',
        genreFilter: genreFilter ?? '',
      });
      if (inFlightKeyRef.current === requestKey) return;
      inFlightKeyRef.current = requestKey;
      if (replace) {
        setIsLoading(true);
      } else {
        setIsLoadingMore(true);
      }
      setError('');
      try {
        const params = {
          offset,
          limit,
          order: sortOption,
          user_id: userId ?? undefined,
          search: searchTerm ?? undefined,
          genre: genreFilter ?? undefined,
        };
        if (replace && offset === 0) {
          const cached = responseCache.get(requestKey);
          if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
            const { items, total: totalCount } = normalizeResponse(cached.data);
            artistsRef.current = items;
            setArtists(items);
            setTotal(totalCount ?? items.length);
            offsetRef.current = items.length;
            if (typeof totalCount === 'number') {
              setHasMore(items.length < totalCount);
            } else {
              setHasMore(items.length >= limit);
            }
            return;
          }
        }
        if (!inFlightRequests.has(requestKey)) {
          const request = audio2Api.getAllArtists(params).finally(() => {
            inFlightRequests.delete(requestKey);
          });
          inFlightRequests.set(requestKey, request);
        }
        const res = await inFlightRequests.get(requestKey)!;
        responseCache.set(requestKey, { ts: Date.now(), data: res.data });
        const { items, total: totalCount } = normalizeResponse(res.data);
        const base = replace ? [] : artistsRef.current;
        const combined = replace ? items : [...base, ...items];
        artistsRef.current = combined;
        setArtists(combined);
        setTotal(totalCount ?? combined.length);
        offsetRef.current = combined.length;
        if (typeof totalCount === 'number') {
          setHasMore(combined.length < totalCount);
        } else {
          setHasMore(items.length >= limit);
        }
      } catch {
        setError('Failed to load artists. Please try again.');
      } finally {
        if (inFlightKeyRef.current === requestKey) {
          inFlightKeyRef.current = null;
        }
        if (replace) {
          setIsLoading(false);
        } else {
          setIsLoadingMore(false);
        }
      }
    },
    [genreFilter, limit, normalizeResponse, searchTerm, sortOption, userId]
  );

  const reload = useCallback(() => {
    offsetRef.current = 0;
    setHasMore(true);
    fetchPage(0, true);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    if (isLoading || isLoadingMore || !hasMore) return;
    fetchPage(offsetRef.current, false);
  }, [fetchPage, hasMore, isLoading, isLoadingMore]);

  const reloadKey = JSON.stringify({
    limit,
    sortOption,
    userId,
    searchTerm: searchTerm ?? '',
    genreFilter: genreFilter ?? '',
  });

  useEffect(() => {
    if (lastReloadKeyRef.current === reloadKey) return;
    lastReloadKeyRef.current = reloadKey;
    reload();
  }, [reload, reloadKey]);

  const removeArtist = useCallback((artistId: number) => {
    artistsRef.current = artistsRef.current.filter((artist) => artist.id !== artistId);
    setArtists(artistsRef.current);
    setTotal((prev) => (typeof prev === 'number' ? Math.max(prev - 1, 0) : null));
  }, []);

  const updateArtistFavorite = useCallback((artistId: number, isFavorite: boolean) => {
    artistsRef.current = artistsRef.current.map((artist) =>
      artist.id === artistId ? { ...artist, is_favorite: isFavorite } : artist
    );
    setArtists(artistsRef.current);
  }, []);

  return {
    artists,
    isLoading,
    isLoadingMore,
    error,
    total,
    hasMore,
    reload,
    loadMore,
    removeArtist,
    updateArtistFavorite,
  };
}
