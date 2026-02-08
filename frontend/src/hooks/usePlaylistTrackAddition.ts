import { useCallback } from 'react';
import { audio2Api } from '@/lib/api';

interface UsePlaylistTrackAdditionOptions {
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
}

interface AddTrackResult {
  success: boolean;
  message: string;
  alreadyExists?: boolean;
  tracks?: any[];
}

/**
 * Hook reutilizable para añadir tracks a playlists.
 * Centraliza la lógica de:
 * 1. Llamar a la API para añadir
 * 2. Verificar la respuesta (incluyendo si ya existe)
 * 3. Recargar la playlist desde el servidor para confirmar
 * 4. Manejar errores
 */
export function usePlaylistTrackAddition(options: UsePlaylistTrackAdditionOptions = {}) {
  const { onSuccess, onError } = options;

  const addTrackToPlaylist = useCallback(async (
    playlistId: number,
    trackId: number
  ): Promise<AddTrackResult> => {
    try {
      // 1. Llamar a la API para añadir
      const response = await audio2Api.addTrackToPlaylist(playlistId, trackId);

      // 2. Verificar respuesta
      if (response.data?.already_exists) {
        const message = 'La canción ya estaba en la lista';
        onSuccess?.(message);
        return {
          success: true,
          message,
          alreadyExists: true,
        };
      }

      if (!response.data?.playlist_track) {
        throw new Error(response.data?.message || 'Error al añadir la canción');
      }

      // 3. Recargar la playlist desde el servidor para confirmar
      const verifyRes = await audio2Api.getPlaylistTracks(playlistId);
      const serverTracks = verifyRes.data || [];

      const message = 'Canción añadida correctamente';
      onSuccess?.(message);

      return {
        success: true,
        message,
        alreadyExists: false,
        tracks: serverTracks,
      };

    } catch (error: any) {
      console.error('Error añadiendo track:', error);
      
      // Verificar si es error 404 (ya existe)
      const status = error?.response?.status;
      if (status === 404) {
        const message = 'La canción ya estaba en la lista';
        onSuccess?.(message);
        return {
          success: true,
          message,
          alreadyExists: true,
        };
      }

      const message = error.message || 'No se pudo añadir la canción';
      
      // Intentar recargar para mantener sincronización
      try {
        const res = await audio2Api.getPlaylistTracks(playlistId);
        onError?.(message);
        return {
          success: false,
          message,
          tracks: res.data || [],
        };
      } catch (reloadError) {
        console.error('Error recargando playlist:', reloadError);
        onError?.(message);
        return {
          success: false,
          message,
          tracks: [],
        };
      }
    }
  }, [onSuccess, onError]);

  /**
   * Añade múltiples tracks a una playlist
   * Útil para añadir en batch
   */
  const addMultipleTracksToPlaylist = useCallback(async (
    playlistId: number,
    trackIds: number[]
  ): Promise<{ added: number; skipped: number; message: string }> => {
    let added = 0;
    let skipped = 0;
    const errors: string[] = [];

    for (const trackId of trackIds) {
      try {
        const result = await addTrackToPlaylist(playlistId, trackId);
        if (result.success) {
          if (result.alreadyExists) {
            skipped += 1;
          } else {
            added += 1;
          }
        } else {
          errors.push(`Track ${trackId}: ${result.message}`);
        }
      } catch (error) {
        errors.push(`Track ${trackId}: Error desconocido`);
      }
    }

    let message = '';
    if (added > 0 && skipped > 0) {
      message = `Añadidas ${added} pistas · ${skipped} ya estaban`;
    } else if (added > 0) {
      message = `Añadidas ${added} pistas`;
    } else if (skipped > 0) {
      message = `${skipped} pistas ya estaban en la lista`;
    } else {
      message = 'No se pudo añadir ninguna pista';
    }

    if (errors.length > 0) {
      message += ` · ${errors.length} errores`;
      console.error('Errores al añadir tracks:', errors);
    }

    return { added, skipped, message };
  }, [addTrackToPlaylist]);

  return { addTrackToPlaylist, addMultipleTracksToPlaylist };
}

/**
 * Función helper standalone para usar fuera de hooks
 * Útil para casos donde no se puede usar hooks (dentro de callbacks, etc.)
 */
export async function addTrackToPlaylistAndReload(
  playlistId: number,
  trackId: number
): Promise<AddTrackResult> {
  try {
    // 1. Llamar a la API para añadir
    const response = await audio2Api.addTrackToPlaylist(playlistId, trackId);

    // 2. Verificar respuesta
    if (response.data?.already_exists) {
      return {
        success: true,
        message: 'La canción ya estaba en la lista',
        alreadyExists: true,
      };
    }

    if (!response.data?.playlist_track) {
      throw new Error(response.data?.message || 'Error al añadir la canción');
    }

    // 3. Recargar la playlist desde el servidor para confirmar
    const verifyRes = await audio2Api.getPlaylistTracks(playlistId);
    const serverTracks = verifyRes.data || [];

    return {
      success: true,
      message: 'Canción añadida correctamente',
      alreadyExists: false,
      tracks: serverTracks,
    };

  } catch (error: any) {
    console.error('Error añadiendo track:', error);
    
    // Verificar si es error 404 (ya existe)
    const status = error?.response?.status;
    if (status === 404) {
      return {
        success: true,
        message: 'La canción ya estaba en la lista',
        alreadyExists: true,
      };
    }

    const message = error.message || 'No se pudo añadir la canción';
    
    // Intentar recargar para mantener sincronización
    try {
      const res = await audio2Api.getPlaylistTracks(playlistId);
      return {
        success: false,
        message,
        tracks: res.data || [],
      };
    } catch (reloadError) {
      console.error('Error recargando playlist:', reloadError);
      return {
        success: false,
        message,
        tracks: [],
      };
    }
  }
}

/**
 * Añade múltiples tracks a múltiples playlists
 * Útil para operaciones batch
 */
export async function addTracksToMultiplePlaylists(
  playlistIds: number[],
  trackIds: number[]
): Promise<{ 
  totalAdded: number; 
  totalSkipped: number; 
  errors: number;
  message: string 
}> {
  let totalAdded = 0;
  let totalSkipped = 0;
  let totalErrors = 0;

  for (const playlistId of playlistIds) {
    for (const trackId of trackIds) {
      try {
        const result = await addTrackToPlaylistAndReload(playlistId, trackId);
        if (result.success) {
          if (result.alreadyExists) {
            totalSkipped += 1;
          } else {
            totalAdded += 1;
          }
        } else {
          totalErrors += 1;
        }
      } catch (error) {
        totalErrors += 1;
      }
    }
  }

  let message = '';
  if (totalAdded > 0) {
    message = `Añadidas ${totalAdded} pistas`;
  }
  if (totalSkipped > 0) {
    message += message ? ` · ${totalSkipped} ya estaban` : `${totalSkipped} ya estaban`;
  }
  if (totalErrors > 0) {
    message += ` · ${totalErrors} errores`;
  }

  return {
    totalAdded,
    totalSkipped,
    errors: totalErrors,
    message: message || 'No se realizaron cambios',
  };
}
