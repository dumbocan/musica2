import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { usePlaylistTrackRemoval, removeTrackFromPlaylistAndReload } from './usePlaylistTrackRemoval';
import { usePlaylistTrackAddition, addTrackToPlaylistAndReload } from './usePlaylistTrackAddition';
import { audio2Api } from '@/lib/api';

// Mock de la API
vi.mock('@/lib/api', () => ({
  audio2Api: {
    removeTrackFromPlaylist: vi.fn(),
    getPlaylistTracks: vi.fn(),
    addTrackToPlaylist: vi.fn(),
  },
}));

describe('usePlaylistTrackRemoval', () => {
  const onSuccess = vi.fn();
  const onError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('removeTrackFromPlaylist', () => {
    it('debe eliminar un track exitosamente y retornar los tracks actualizados', async () => {
      // Mock de respuestas
      const mockServerTracks = [
        { id: 2, name: 'Track 2', artist: { name: 'Artist' } },
      ];
      
      (audio2Api.removeTrackFromPlaylist as any).mockResolvedValue({
        data: { success: true, message: 'Track removed' },
      });
      
      (audio2Api.getPlaylistTracks as any).mockResolvedValue({
        data: mockServerTracks,
      });

      const { result } = renderHook(() => 
        usePlaylistTrackRemoval({ onSuccess, onError })
      );

      const response = await result.current.removeTrackFromPlaylist(1, 1);

      expect(response.success).toBe(true);
      expect(response.tracks).toEqual(mockServerTracks);
      expect(onSuccess).toHaveBeenCalledWith('Canción eliminada correctamente');
      expect(audio2Api.removeTrackFromPlaylist).toHaveBeenCalledWith(1, 1);
      expect(audio2Api.getPlaylistTracks).toHaveBeenCalledWith(1);
    });

    it('debe manejar error cuando el track no existe', async () => {
      (audio2Api.removeTrackFromPlaylist as any).mockResolvedValue({
        data: { success: false, error: 'not_found', message: 'Track not found' },
      });

      const { result } = renderHook(() => 
        usePlaylistTrackRemoval({ onSuccess, onError })
      );

      const response = await result.current.removeTrackFromPlaylist(1, 999);

      expect(response.success).toBe(false);
      expect(response.error).toBe('not_found');
    });

    it('debe recargar tracks incluso cuando hay error', async () => {
      const mockServerTracks = [{ id: 1, name: 'Track 1' }];
      
      (audio2Api.removeTrackFromPlaylist as any).mockRejectedValue(
        new Error('Network error')
      );
      
      (audio2Api.getPlaylistTracks as any).mockResolvedValue({
        data: mockServerTracks,
      });

      const { result } = renderHook(() => 
        usePlaylistTrackRemoval({ onSuccess, onError })
      );

      const response = await result.current.removeTrackFromPlaylist(1, 1);

      expect(response.success).toBe(false);
      expect(response.tracks).toEqual(mockServerTracks);
      expect(onError).toHaveBeenCalled();
    });
  });
});

describe('removeTrackFromPlaylistAndReload (standalone)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('debe funcionar fuera de hooks', async () => {
    const mockServerTracks = [{ id: 1, name: 'Track 1' }];
    
    (audio2Api.removeTrackFromPlaylist as any).mockResolvedValue({
      data: { success: true, message: 'Removed' },
    });
    
    (audio2Api.getPlaylistTracks as any).mockResolvedValue({
      data: mockServerTracks,
    });

    const result = await removeTrackFromPlaylistAndReload(1, 1);

    expect(result.success).toBe(true);
    expect(result.tracks).toEqual(mockServerTracks);
  });
});

describe('usePlaylistTrackAddition', () => {
  const onSuccess = vi.fn();
  const onError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('addTrackToPlaylist', () => {
    it('debe añadir un track exitosamente', async () => {
      const mockServerTracks = [
        { id: 1, name: 'Track 1', artist: { name: 'Artist' } },
      ];
      
      (audio2Api.addTrackToPlaylist as any).mockResolvedValue({
        data: { success: true, playlist_track: { id: 1 } },
      });
      
      (audio2Api.getPlaylistTracks as any).mockResolvedValue({
        data: mockServerTracks,
      });

      const { result } = renderHook(() => 
        usePlaylistTrackAddition({ onSuccess, onError })
      );

      const response = await result.current.addTrackToPlaylist(1, 1);

      expect(response.success).toBe(true);
      expect(response.alreadyExists).toBe(false);
      expect(response.tracks).toEqual(mockServerTracks);
      expect(onSuccess).toHaveBeenCalledWith('Canción añadida correctamente');
    });

    it('debe detectar cuando el track ya existe', async () => {
      (audio2Api.addTrackToPlaylist as any).mockResolvedValue({
        data: { already_exists: true, message: 'Already exists' },
      });

      const { result } = renderHook(() => 
        usePlaylistTrackAddition({ onSuccess, onError })
      );

      const response = await result.current.addTrackToPlaylist(1, 1);

      expect(response.success).toBe(true);
      expect(response.alreadyExists).toBe(true);
      expect(onSuccess).toHaveBeenCalledWith('La canción ya estaba en la lista');
    });

    it('debe manejar error 404 como track ya existente', async () => {
      const error = { response: { status: 404 } };
      (audio2Api.addTrackToPlaylist as any).mockRejectedValue(error);

      const { result } = renderHook(() => 
        usePlaylistTrackAddition({ onSuccess, onError })
      );

      const response = await result.current.addTrackToPlaylist(1, 1);

      expect(response.success).toBe(true);
      expect(response.alreadyExists).toBe(true);
    });
  });

  describe('addMultipleTracksToPlaylist', () => {
    it('debe añadir múltiples tracks y contar correctamente', async () => {
      (audio2Api.addTrackToPlaylist as any)
        .mockResolvedValueOnce({ data: { success: true, playlist_track: { id: 1 } } })
        .mockResolvedValueOnce({ data: { already_exists: true } })
        .mockResolvedValueOnce({ data: { success: true, playlist_track: { id: 3 } } });

      const { result } = renderHook(() => 
        usePlaylistTrackAddition({ onSuccess, onError })
      );

      const response = await result.current.addMultipleTracksToPlaylist(1, [1, 2, 3]);

      expect(response.added).toBe(2);
      expect(response.skipped).toBe(1);
      expect(response.message).toContain('2');
      expect(response.message).toContain('1');
    });

    it('debe manejar errores individuales sin detener el batch', async () => {
      (audio2Api.addTrackToPlaylist as any)
        .mockResolvedValueOnce({ data: { success: true, playlist_track: { id: 1 } } })
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValueOnce({ data: { success: true, playlist_track: { id: 3 } } });

      const { result } = renderHook(() => 
        usePlaylistTrackAddition({ onSuccess, onError })
      );

      const response = await result.current.addMultipleTracksToPlaylist(1, [1, 2, 3]);

      expect(response.added).toBe(2);
      expect(response.message).toContain('errores');
    });
  });
});

describe('addTrackToPlaylistAndReload (standalone)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('debe funcionar fuera de hooks', async () => {
    const mockServerTracks = [{ id: 1, name: 'Track 1' }];
    
    (audio2Api.addTrackToPlaylist as any).mockResolvedValue({
      data: { success: true, playlist_track: { id: 1 } },
    });
    
    (audio2Api.getPlaylistTracks as any).mockResolvedValue({
      data: mockServerTracks,
    });

    const result = await addTrackToPlaylistAndReload(1, 1);

    expect(result.success).toBe(true);
    expect(result.tracks).toEqual(mockServerTracks);
  });
});
