import { useCallback, useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  pageSize?: number;
  searchTerm?: string;
  sortOption?: 'pop-desc' | 'pop-asc' | 'name-asc';
}

export function usePaginatedArtists({ pageSize = 30, searchTerm = '', sortOption = 'pop-desc' }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasMore, setHasMore] = useState(true);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);
    setError('');
    setArtists([]);
    setOffset(0);
    try {
      const res = await audio2Api.getAllArtists({ offset: 0, limit: pageSize, order: sortOption });
      const data = res.data || [];
      setArtists(data);
      setOffset(data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [pageSize, sortOption]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading || searchTerm.trim()) return;
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset, limit: pageSize, order: sortOption });
      const data = res.data || [];
      setArtists((prev) => [...prev, ...data]);
      setOffset((prev) => prev + data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [hasMore, isLoading, offset, pageSize, searchTerm, sortOption]);

  return {
    artists,
    isLoading,
    error,
    hasMore,
    loadInitial,
    loadMore,
    setArtists,
  };
}
