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

type PaginatedArtistsResponse = Artist[] | { items: Artist[]; total?: number };

export function usePaginatedHiddenArtists({
  limit = 50,
  sortOption = 'name-asc',
  userId,
  searchTerm,
  genreFilter,
}: Options = {}) {
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
    if (Array.isArray(payload)) return { items: payload, total: payload.length };
    if (payload && Array.isArray(payload.items)) {
      return { items: payload.items, total: typeof payload.total === 'number' ? payload.total : null };
    }
    return { items: [], total: null };
  }, []);

  const fetchPage = useCallback(
    async (offset: number, replace: boolean) => {
      if (!userId) {
        setArtists([]);
        setTotal(0);
        setHasMore(false);
        return;
      }
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
      if (replace) setIsLoading(true);
      else setIsLoadingMore(true);
      setError('');
      try {
        const res = await audio2Api.getHiddenArtists({
          user_id: userId,
          offset,
          limit,
          order: sortOption,
          search: searchTerm ?? undefined,
          genre: genreFilter ?? undefined,
        });
        const { items, total: totalCount } = normalizeResponse(res.data);
        const base = replace ? [] : artistsRef.current;
        const combined = replace ? items : [...base, ...items];
        artistsRef.current = combined;
        setArtists(combined);
        setTotal(totalCount ?? combined.length);
        offsetRef.current = combined.length;
        if (typeof totalCount === 'number') setHasMore(combined.length < totalCount);
        else setHasMore(items.length >= limit);
      } catch {
        setError('Failed to load hidden artists. Please try again.');
      } finally {
        if (inFlightKeyRef.current === requestKey) inFlightKeyRef.current = null;
        if (replace) setIsLoading(false);
        else setIsLoadingMore(false);
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
  };
}
