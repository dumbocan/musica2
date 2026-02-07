import { useEffect, useMemo, useState } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';
import type { Playlist } from '@/types/api';

type AddToPlaylistModalProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  resolveTrackIds: () => Promise<number[]>;
};

type View = 'select' | 'create';

export function AddToPlaylistModal({
  open,
  title,
  subtitle,
  onClose,
  resolveTrackIds,
}: AddToPlaylistModalProps) {
  const userId = useApiStore((s) => s.userId) || 1;
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState('');
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [message, setMessage] = useState('');
  const [previewPlaylistId, setPreviewPlaylistId] = useState<number | null>(null);
  const [previewTracks, setPreviewTracks] = useState<Array<{ id?: number; name?: string; artist?: string }>>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [removingTrackId, setRemovingTrackId] = useState<number | null>(null);
  const [view, setView] = useState<View>('select');

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setMessage('');
    audio2Api
      .getAllPlaylists()
      .then((res) => {
        if (cancelled) return;
        setPlaylists(res.data || []);
      })
      .catch(() => {
        if (cancelled) return;
        setMessage('No se pudieron cargar las listas');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      setSelected(new Set());
      setFilter('');
      setNewName('');
      setNewDescription('');
      setMessage('');
      setPreviewPlaylistId(null);
      setPreviewTracks([]);
      setView('select');
    }
  }, [open]);

  useEffect(() => {
    const firstSelected = Array.from(selected)[0] ?? null;
    if (!firstSelected) {
      setPreviewPlaylistId(null);
      setPreviewTracks([]);
      return;
    }
    if (previewPlaylistId === null || !selected.has(previewPlaylistId)) {
      setPreviewPlaylistId(firstSelected);
    }
  }, [previewPlaylistId, selected]);

  useEffect(() => {
    if (!previewPlaylistId) return;
    let cancelled = false;
    setPreviewLoading(true);
    audio2Api
      .getPlaylistTracks(previewPlaylistId)
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res.data) ? res.data : [];
        setPreviewTracks(
          items.map((item: { id?: number; name?: string; artist?: { name?: string } }) => ({
            id: item.id,
            name: item.name,
            artist: item.artist?.name,
          }))
        );
      })
      .catch(() => {
        if (!cancelled) setPreviewTracks([]);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [previewPlaylistId]);

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return playlists;
    return playlists.filter((p) => `${p.name} ${p.description || ''}`.toLowerCase().includes(q));
  }, [filter, playlists]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreateList = async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      const res = await audio2Api.createPlaylist({
        name,
        description: newDescription.trim(),
        user_id: userId,
      });
      const created = res.data as Playlist;
      setPlaylists((prev) => [created, ...prev]);
      setSelected((prev) => new Set(prev).add(created.id));
      setNewName('');
      setNewDescription('');
      setMessage(`Lista "${created.name}" creada`);
      setView('select');
    } catch {
      setMessage('No se pudo crear la lista');
    }
  };

  const handleAdd = async () => {
    if (!selected.size) {
      setMessage('Selecciona al menos una lista');
      return;
    }
    setAdding(true);
    setMessage('');
    try {
      const trackIds = await resolveTrackIds();
      if (!trackIds.length) {
        setMessage('No hay canciones disponibles para añadir');
        return;
      }
      let added = 0;
      let skipped = 0;
      for (const playlistId of selected) {
        for (const trackId of trackIds) {
          try {
            await audio2Api.addTrackToPlaylist(playlistId, trackId);
            added += 1;
          } catch (err: unknown) {
            const status =
              err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { status?: number } }).response?.status
                : undefined;
            if (status === 404) skipped += 1;
          }
        }
      }
      setMessage(`Añadidas ${added} pistas${skipped ? ` · ${skipped} ya estaban` : ''}`);
      if (previewPlaylistId) {
        const refreshed = await audio2Api.getPlaylistTracks(previewPlaylistId);
        const items = Array.isArray(refreshed.data) ? refreshed.data : [];
        setPreviewTracks(
          items.map((item: { id?: number; name?: string; artist?: { name?: string } }) => ({
            id: item.id,
            name: item.name,
            artist: item.artist?.name,
          }))
        );
      }
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveTrack = async (trackId: number) => {
    if (!previewPlaylistId) return;
    setRemovingTrackId(trackId);
    try {
      await audio2Api.removeTrackFromPlaylist(previewPlaylistId, trackId);
      setPreviewTracks((prev) => prev.filter((t) => t.id !== trackId));
      setMessage('Canción eliminada');
    } catch {
      setMessage('No se pudo eliminar la canción');
    } finally {
      setRemovingTrackId(null);
    }
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.55)',
        zIndex: 70,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="card"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(720px, 100%)',
          maxHeight: '85vh',
          overflow: 'auto',
          background: 'var(--panel-2)',
          border: '1px solid var(--border)',
          display: 'grid',
          gap: 12,
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {view === 'create' ? (
              <button
                className="badge"
                onClick={() => setView('select')}
                type="button"
                style={{ padding: '6px 10px' }}
              >
                ← Volver
              </button>
            ) : null}
            <div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>
                {view === 'create' ? 'Nueva lista' : title}
              </div>
              {subtitle && view === 'select' ? (
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>{subtitle}</div>
              ) : null}
            </div>
          </div>
          {view === 'select' ? (
            <button
              type="button"
              onClick={() => setView('create')}
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: 'var(--accent)',
                border: 'none',
                color: 'var(--accent-foreground)',
                fontSize: 20,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              aria-label="Crear nueva lista"
            >
              +
            </button>
          ) : (
            <button className="badge" onClick={onClose} type="button">
              Cerrar
            </button>
          )}
        </div>

        {/* Body según vista */}
        {view === 'create' ? (
          <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 16, background: 'var(--panel)' }}>
            <div style={{ display: 'grid', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Nombre de la lista
                </label>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Mi playlist..."
                  className="search-input"
                  autoFocus
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Descripción (opcional)
                </label>
                <input
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Una descripción..."
                  className="search-input"
                />
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button
                  className="badge"
                  type="button"
                  onClick={() => void handleCreateList()}
                  disabled={!newName.trim()}
                  style={{ opacity: newName.trim() ? 1 : 0.5 }}
                >
                  Crear lista
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10, background: 'var(--panel)' }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Listas existentes</div>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Buscar lista..."
                className="search-input"
                style={{ marginBottom: 8 }}
              />
              <div style={{ display: 'grid', gap: 6, maxHeight: 260, overflow: 'auto' }}>
                {loading ? (
                  <div style={{ color: 'var(--muted)' }}>Cargando listas...</div>
                ) : visible.length ? (
                  visible.map((p) => (
                    <label
                      key={p.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '8px 10px',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        background: selected.has(p.id) ? 'rgba(5, 247, 165, 0.12)' : 'var(--panel-2)',
                        cursor: 'pointer',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(p.id)}
                        onChange={() => toggleSelect(p.id)}
                      />
                      <span style={{ fontWeight: 600 }}>{p.name}</span>
                      {p.description ? <span style={{ color: 'var(--muted)', fontSize: 12 }}>· {p.description}</span> : null}
                      <button
                        type="button"
                        className="badge"
                        style={{ marginLeft: 'auto', fontSize: 11 }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setPreviewPlaylistId(p.id);
                        }}
                      >
                        Ver
                      </button>
                    </label>
                  ))
                ) : (
                  <div style={{ color: 'var(--muted)' }}>No hay listas</div>
                )}
              </div>
            </div>

            <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10, background: 'var(--panel)' }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Contenido actual de la lista</div>
              {!previewPlaylistId ? (
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>Selecciona una lista para ver lo que ya incluye.</div>
              ) : previewLoading ? (
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>Cargando canciones...</div>
              ) : previewTracks.length ? (
                <ol style={{ margin: 0, paddingLeft: 18, maxHeight: 180, overflow: 'auto', display: 'grid', gap: 4 }}>
                  {previewTracks.map((track, idx) => (
                    <li
                      key={`${track.id || idx}-${track.name || ''}`}
                      style={{
                        fontSize: 13,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '4px 0',
                      }}
                    >
                      <span style={{ flex: 1, minWidth: 0 }}>
                        {track.name || 'Sin título'}
                        {track.artist ? <span style={{ color: 'var(--muted)' }}> · {track.artist}</span> : null}
                      </span>
                      {track.id ? (
                        <button
                          type="button"
                          onClick={() => void handleRemoveTrack(track.id!)}
                          disabled={removingTrackId === track.id}
                          style={{
                            width: 24,
                            height: 24,
                            borderRadius: '50%',
                            background: 'var(--destructive)',
                            border: 'none',
                            color: 'var(--destructive-foreground)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            opacity: removingTrackId === track.id ? 0.5 : 1,
                            fontSize: 14,
                            fontWeight: 700,
                          }}
                          title="Eliminar de la lista"
                        >
                          {removingTrackId === track.id ? '...' : '×'}
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ol>
              ) : (
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>Esta lista aún no tiene canciones.</div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <div style={{ color: 'var(--muted)', fontSize: 13 }}>{message}</div>
              <button
                type="button"
                className="badge"
                onClick={() => void handleAdd()}
                disabled={adding}
                style={{ opacity: adding ? 0.6 : 1 }}
              >
                {adding ? 'Añadiendo...' : 'Añadir a lista'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
