import { useCallback, useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  pageSize?: number;
  searchTerm?: string;
  sortOption?: 'pop-desc' | 'pop-asc' | 'name-asc';
}

export function usePaginatedArtists({ pageSize = 20, searchTerm = '', sortOption = 'pop-desc' }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState<number | null>(null);
  const hasFetched = useRef(false);
  const lastSort = useRef(sortOption);

  const normalizeResponse = useCallback((payload: any): { items: Artist[]; total: number | null } => {
    if (Array.isArray(payload)) {
      return { items: payload, total: null };
    }
    if (payload && Array.isArray(payload.items)) {
      return { items: payload.items, total: typeof payload.total === 'number' ? payload.total : null };
    }
    return { items: [], total: null };
  }, []);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);
    setError('');
    setArtists([]);
    setOffset(0);
    try {
      const res = await audio2Api.getAllArtists({ offset: 0, limit: pageSize, order: sortOption });
      const { items, total: totalCount } = normalizeResponse(res.data);
      setArtists(items);
      setTotal(totalCount ?? items.length);
      setOffset(items.length);
      const effectiveTotal = totalCount ?? null;
      setHasMore(effectiveTotal !== null ? items.length < effectiveTotal : items.length === pageSize);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [normalizeResponse, pageSize, sortOption]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading) return;
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset, limit: pageSize, order: sortOption });
      const { items, total: totalCount } = normalizeResponse(res.data);
      setArtists((prev) => [...prev, ...items]);
      const nextOffset = offset + items.length;
      const nextTotal = totalCount ?? total;
      setOffset(nextOffset);
      setTotal(nextTotal ?? null);
      setHasMore(
        nextTotal !== null
          ? nextOffset < nextTotal
          : items.length === pageSize
      );
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [hasMore, isLoading, offset, pageSize, sortOption, normalizeResponse, total]);

  useEffect(() => {
    const shouldFetch = !hasFetched.current || lastSort.current !== sortOption;
    if (!shouldFetch) return;
    hasFetched.current = true;
    lastSort.current = sortOption;
    loadInitial();
  }, [loadInitial, sortOption]);

  return {
    artists,
    isLoading,
    error,
    hasMore,
    total,
    loadInitial,
    loadMore,
    setArtists,
  };
}
