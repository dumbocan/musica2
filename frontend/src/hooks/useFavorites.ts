import { useCallback, useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';

type FavoriteTarget = 'artist' | 'album' | 'track';

type FavoriteItem = {
  artist_id?: number;
  album_id?: number;
  track_id?: number;
};

export const getUserIdFromToken = (): number | null => {
  const token = localStorage.getItem('token');
  if (!token) return null;
  const payloadB64 = token.split('.')[1];
  if (!payloadB64) return null;
  try {
    // JWT payload uses URL-safe base64.
    const normalized = payloadB64.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + (4 - (normalized.length % 4 || 4)) % 4, '=');
    const payloadJson = atob(padded);
    const payload = JSON.parse(payloadJson);
    return typeof payload?.user_id === 'number' ? payload.user_id : null;
  } catch {
    return null;
  }
};

export const useFavorites = (targetType: FavoriteTarget, userId?: number | null) => {
  const [favoriteIds, setFavoriteIds] = useState<Set<number>>(new Set());
  // Prefer token user_id to avoid writing favorites to a stale store user id.
  const effectiveUserId = getUserIdFromToken() ?? userId ?? null;
  const inFlightKeyRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadFavorites = async () => {
      if (!effectiveUserId) {
        setFavoriteIds(new Set());
        return;
      }
      const requestKey = `${effectiveUserId}:${targetType}`;
      if (inFlightKeyRef.current === requestKey) return;
      inFlightKeyRef.current = requestKey;
      try {
        const res = await audio2Api.listFavorites({ user_id: effectiveUserId, target_type: targetType });
        if (cancelled) return;
        const next = new Set<number>();
        (res.data || []).forEach((fav: FavoriteItem) => {
          const id =
            targetType === 'artist'
              ? fav?.artist_id
              : targetType === 'album'
              ? fav?.album_id
              : fav?.track_id;
          if (typeof id === 'number') {
            next.add(id);
          }
        });
        setFavoriteIds(next);
      } catch (err) {
        console.error('Failed to load favorites', err);
      } finally {
        if (inFlightKeyRef.current === requestKey) {
          inFlightKeyRef.current = null;
        }
      }
    };
    loadFavorites();
    return () => {
      cancelled = true;
    };
  }, [effectiveUserId, targetType]);

  const toggleFavorite = useCallback(
    async (targetId: number) => {
      if (!effectiveUserId) return;
      try {
        if (favoriteIds.has(targetId)) {
          await audio2Api.removeFavorite(targetType, targetId, effectiveUserId);
          setFavoriteIds((prev) => {
            const next = new Set(prev);
            next.delete(targetId);
            return next;
          });
        } else {
          await audio2Api.addFavorite(targetType, targetId, effectiveUserId);
          setFavoriteIds((prev) => {
            const next = new Set(prev);
            next.add(targetId);
            return next;
          });
        }
      } catch (err) {
        console.error('Failed to toggle favorite', err);
      }
    },
    [effectiveUserId, favoriteIds, targetType]
  );

  return { favoriteIds, toggleFavorite, setFavoriteIds, effectiveUserId };
};
