import { useCallback } from 'react';
import { audio2Api } from '@/lib/api';

interface UsePlaylistTrackRemovalOptions {
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
}

interface RemoveTrackResult {
  success: boolean;
  message: string;
}

/**
 * Hook reutilizable para eliminar tracks de playlists.
 * Centraliza la lógica de:
 * 1. Llamar a la API para eliminar
 * 2. Verificar la respuesta
 * 3. Recargar la playlist desde el servidor
 * 4. Manejar errores
 */
export function usePlaylistTrackRemoval(options: UsePlaylistTrackRemovalOptions = {}) {
  const { onSuccess, onError } = options;

  const removeTrackFromPlaylist = useCallback(async (
    playlistId: number,
    trackId: number
  ): Promise<RemoveTrackResult> => {
    try {
      // 1. Llamar a la API para eliminar
      const response = await audio2Api.removeTrackFromPlaylist(playlistId, trackId);

      // 2. Verificar respuesta
      if (!response.data?.success) {
        throw new Error(response.data?.message || 'Error desconocido');
      }

      // 3. Recargar la playlist desde el servidor para confirmar
      const verifyRes = await audio2Api.getPlaylistTracks(playlistId);
      const serverTracks = verifyRes.data || [];

      const message = 'Canción eliminada correctamente';
      onSuccess?.(message);

      return {
        success: true,
        message,
        tracks: serverTracks,
      } as RemoveTrackResult;

    } catch (error: any) {
      console.error('Error eliminando track:', error);
      const message = error.message || 'No se pudo eliminar la canción';
      
      // Intentar recargar para mantener sincronización
      try {
        const res = await audio2Api.getPlaylistTracks(playlistId);
        onError?.(message);
        return {
          success: false,
          message,
          tracks: res.data || [],
        } as RemoveTrackResult;
      } catch (reloadError) {
        console.error('Error recargando playlist:', reloadError);
        onError?.(message);
        return {
          success: false,
          message,
          tracks: [],
        } as RemoveTrackResult;
      }
    }
  }, [onSuccess, onError]);

  return { removeTrackFromPlaylist };
}

/**
 * Función helper standalone para usar fuera de hooks
 * Útil para casos donde no se puede usar hooks (dentro de callbacks, etc.)
 */
export async function removeTrackFromPlaylistAndReload(
  playlistId: number,
  trackId: number
): Promise<RemoveTrackResult> {
  try {
    // 1. Llamar a la API para eliminar
    const response = await audio2Api.removeTrackFromPlaylist(playlistId, trackId);

    // 2. Verificar respuesta
    if (!response.data?.success) {
      throw new Error(response.data?.message || 'Error desconocido');
    }

    // 3. Recargar la playlist desde el servidor para confirmar
    const verifyRes = await audio2Api.getPlaylistTracks(playlistId);
    const serverTracks = verifyRes.data || [];

    return {
      success: true,
      message: 'Canción eliminada correctamente',
      tracks: serverTracks,
    } as RemoveTrackResult;

  } catch (error: any) {
    console.error('Error eliminando track:', error);
    const message = error.message || 'No se pudo eliminar la canción';
    
    // Intentar recargar para mantener sincronización
    try {
      const res = await audio2Api.getPlaylistTracks(playlistId);
      return {
        success: false,
        message,
        tracks: res.data || [],
      } as RemoveTrackResult;
    } catch (reloadError) {
      console.error('Error recargando playlist:', reloadError);
      return {
        success: false,
        message,
        tracks: [],
      } as RemoveTrackResult;
    }
  }
}
