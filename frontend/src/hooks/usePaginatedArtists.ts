import { useCallback, useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';
import type { Artist } from '@/types/api';

interface Options {
  limit?: number;
  sortOption?: 'pop-desc' | 'pop-asc' | 'name-asc';
}

type PaginatedArtistsResponse = Artist[] | { items: Artist[], total?: number };

export function usePaginatedArtists({ limit = 500, sortOption = 'pop-desc' }: Options = {}) {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [total, setTotal] = useState<number | null>(null);

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

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const res = await audio2Api.getAllArtists({ offset: 0, limit, order: sortOption });
      const { items, total: totalCount } = normalizeResponse(res.data);
      setArtists(items);
      setTotal(totalCount ?? items.length);
    } catch {
      setError('Failed to load artists. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [limit, normalizeResponse, sortOption]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    artists,
    isLoading,
    error,
    total,
    reload: fetchAll,
  };
}
