import { useCallback, useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  limit?: number;
  sortOption?: 'pop-desc' | 'pop-asc' | 'name-asc';
  userId?: number | null;
}

type PaginatedArtistsResponse = Artist[] | { items: Artist[], total?: number };

export function usePaginatedArtists({ limit = 200, sortOption = 'pop-desc', userId }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState<number | null>(null);
  const offsetRef = useRef(0);
  const artistsRef = useRef<Artist[]>([]);

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
      if (replace) {
        setIsLoading(true);
      } else {
        setIsLoadingMore(true);
      }
      setError('');
      try {
        const res = await audio2Api.getAllArtists({
          offset,
          limit,
          order: sortOption,
          user_id: userId ?? undefined,
        });
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
        if (replace) {
          setIsLoading(false);
        } else {
          setIsLoadingMore(false);
        }
      }
    },
    [limit, normalizeResponse, sortOption, userId]
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

  useEffect(() => {
    reload();
  }, [reload]);

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
