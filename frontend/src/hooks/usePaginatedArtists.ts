import { useCallback, useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  pageSize?: number;
  searchTerm?: string;
}

export function usePaginatedArtists({ pageSize = 30, searchTerm = '' }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasMore, setHasMore] = useState(true);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset: 0, limit: pageSize });
      const data = res.data || [];
      const sorted = data.sort((a, b) => (b.popularity || 0) - (a.popularity || 0));
      setArtists(sorted);
      setOffset(data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading || searchTerm.trim()) return;
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset, limit: pageSize });
      const data = res.data || [];
      setArtists((prev) => {
        const existingIds = new Set(prev.map((artist) => artist.id));
        const deduped = data.filter((artist) => !existingIds.has(artist.id));
        const combined = [...prev, ...deduped];
        return combined.sort((a, b) => (b.popularity || 0) - (a.popularity || 0));
      });
      setOffset((prev) => prev + data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [hasMore, isLoading, offset, pageSize, searchTerm]);

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
