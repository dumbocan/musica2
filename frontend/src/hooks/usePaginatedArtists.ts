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

  const mergeUnique = useCallback((current: Artist[], incoming: Artist[]) => {
    const seen = new Set(current.map((artist) => artist.id));
    const merged = [...current];
    incoming.forEach((artist) => {
      if (!seen.has(artist.id)) {
        seen.add(artist.id);
        merged.push(artist);
      }
    });
    return merged;
  }, []);

  const loadInitial = useCallback(async () => {
    setIsLoading(true);
    setError('');
    setArtists([]);
    setOffset(0);
    try {
      const res = await audio2Api.getAllArtists({ offset: 0, limit: pageSize, order: sortOption });
      const data = res.data || [];
      setArtists(mergeUnique([], data));
      setOffset(data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [mergeUnique, pageSize, sortOption]);

  const loadMore = useCallback(async () => {
    if (!hasMore || isLoading) return;
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset, limit: pageSize, order: sortOption });
      const data = res.data || [];
      setArtists((prev) => mergeUnique(prev, data));
      setOffset((prev) => prev + data.length);
      setHasMore(data.length === pageSize && data.length > 0);
    } catch (err) {
      console.error('Failed to load artists:', err);
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [hasMore, isLoading, offset, pageSize, sortOption, mergeUnique]);

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
