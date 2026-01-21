import { useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';

export function SettingsPage() {
  const [maintenanceState, setMaintenanceState] = useState<'unknown' | 'running' | 'idle' | 'error'>('unknown');
  const [maintenanceStarting, setMaintenanceStarting] = useState(false);
  const [maintenanceStopping, setMaintenanceStopping] = useState(false);
  const [maintenanceStopStatus, setMaintenanceStopStatus] = useState<'idle' | 'done' | 'error'>('idle');
  const [auditStatus, setAuditStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [albumMissingStatus, setAlbumMissingStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [albumIncompleteStatus, setAlbumIncompleteStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [youtubeBackfillStatus, setYoutubeBackfillStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [metadataStatus, setMetadataStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [chartBackfillStatus, setChartBackfillStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [purgeId, setPurgeId] = useState('');
  const [purgeStatus, setPurgeStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logsEnabled, setLogsEnabled] = useState(true);
  const [logError, setLogError] = useState<string | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);
  const lastLogIdRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    audio2Api
      .getMaintenanceStatus()
      .then((res) => {
        if (!active) return;
        setMaintenanceState(res.data?.running ? 'running' : 'idle');
      })
      .catch(() => {
        if (!active) return;
        setMaintenanceState('error');
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!logsEnabled) return;
    let cancelled = false;
    const fetchLogs = async () => {
      try {
        const res = await audio2Api.getMaintenanceLogs({
          since_id: lastLogIdRef.current ?? undefined,
          limit: 200,
          scope: 'maintenance',
        });
        if (cancelled) return;
        const items = res.data?.items || [];
        const responseLastId = typeof res.data?.last_id === 'number' ? res.data.last_id : null;
        if (responseLastId !== null && lastLogIdRef.current !== null && responseLastId < lastLogIdRef.current) {
          // Backend restarted; reset cursor so we can read new logs.
          lastLogIdRef.current = null;
          setLogLines([]);
        }
        if (items.length) {
          const newLines = items.map((item: { line?: string }) => item.line || '').filter(Boolean);
          lastLogIdRef.current = responseLastId ?? lastLogIdRef.current;
          setLogLines((prev) => {
            const combined = [...prev, ...newLines];
            return combined.length > 1000 ? combined.slice(-1000) : combined;
          });
          requestAnimationFrame(() => {
            if (logBoxRef.current) {
              logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
            }
          });
        } else if (responseLastId !== null) {
          lastLogIdRef.current = responseLastId;
        }
        setLogError(null);
      } catch (err) {
        if (cancelled) return;
        setLogError(err instanceof Error ? err.message : 'Error cargando logs');
      }
    };
    void fetchLogs();
    const timer = window.setInterval(fetchLogs, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [logsEnabled]);

  const handleMaintenanceStart = async () => {
    setMaintenanceStarting(true);
    try {
      const res = await audio2Api.getMaintenanceStatus({ start: true });
      setMaintenanceState(res.data?.running ? 'running' : 'idle');
    } catch {
      setMaintenanceState('error');
    } finally {
      setMaintenanceStarting(false);
    }
  };

  const handleMaintenanceStop = async () => {
    setMaintenanceStopping(true);
    try {
      await audio2Api.stopMaintenance();
      setMaintenanceState('idle');
      setMaintenanceStopStatus('done');
    } catch {
      setMaintenanceStopStatus('error');
    } finally {
      setMaintenanceStopping(false);
    }
  };

  const handleAuditLibrary = async () => {
    setAuditStatus('running');
    try {
      await audio2Api.auditLibrary();
      setAuditStatus('done');
    } catch {
      setAuditStatus('error');
    }
  };

  const handleBackfillAlbumsMissing = async () => {
    setAlbumMissingStatus('running');
    try {
      await audio2Api.backfillAlbumTracks({ mode: 'missing', limit: 200, concurrency: 2 });
      setAlbumMissingStatus('done');
    } catch {
      setAlbumMissingStatus('error');
    }
  };

  const handleBackfillAlbumsIncomplete = async () => {
    setAlbumIncompleteStatus('running');
    try {
      await audio2Api.backfillAlbumTracks({ mode: 'incomplete', limit: 200, concurrency: 2 });
      setAlbumIncompleteStatus('done');
    } catch {
      setAlbumIncompleteStatus('error');
    }
  };

  const handleBackfillYoutubeLinks = async () => {
    setYoutubeBackfillStatus('running');
    try {
      await audio2Api.backfillYoutubeLinks({ limit: 200 });
      setYoutubeBackfillStatus('done');
    } catch {
      setYoutubeBackfillStatus('error');
    }
  };

  const handleRefreshMissingMetadata = async () => {
    setMetadataStatus('running');
    try {
      await audio2Api.refreshMissingArtists({ limit: 200, use_spotify: true, use_lastfm: true });
      setMetadataStatus('done');
    } catch {
      setMetadataStatus('error');
    }
  };

  const handleChartBackfill = async () => {
    setChartBackfillStatus('running');
    try {
      await audio2Api.backfillChart({ chart_source: 'billboard', chart_name: 'hot-100', weeks: 20 });
      setChartBackfillStatus('done');
    } catch {
      setChartBackfillStatus('error');
    }
  };

  const handlePurgeArtist = async () => {
    const trimmed = purgeId.trim();
    if (!trimmed) return;
    setPurgeStatus('running');
    try {
      const isSpotifyId = /^[A-Za-z0-9]{22}$/.test(trimmed);
      await audio2Api.purgeArtist(isSpotifyId ? { spotify_id: trimmed } : { name: trimmed });
      setPurgeStatus('done');
    } catch {
      setPurgeStatus('error');
    }
  };

  const handleClearLogs = async () => {
    try {
      await audio2Api.clearMaintenanceLogs();
      setLogLines([]);
      lastLogIdRef.current = null;
    } catch (err) {
      setLogError(err instanceof Error ? err.message : 'Error limpiando logs');
    }
  };

  return (
    <div className="page">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <div className="card" style={{ maxWidth: 360, width: '100%' }}>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Mantenimiento</div>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              Acciones rápidas y backfills. Revisa el terminal para el progreso.
            </div>
          </div>

          <button
            type="button"
            className="btn-ghost"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={handleMaintenanceStart}
            disabled={maintenanceStarting}
          >
            {maintenanceStarting ? 'Iniciando...' : 'Forzar mantenimiento'}
          </button>
          <button
            type="button"
            className="btn-ghost"
            style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
            onClick={handleMaintenanceStop}
            disabled={maintenanceStopping}
          >
            {maintenanceStopping ? 'Deteniendo...' : 'Detener procesos'}
          </button>
          <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
            Estado: {maintenanceState === 'running' ? 'activo' : maintenanceState === 'idle' ? 'en espera' : maintenanceState === 'error' ? 'error' : '...'}
          </div>
          <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>
            Stop: {maintenanceStopStatus === 'done' ? 'detenido' : maintenanceStopStatus === 'error' ? 'error' : 'en espera'}
          </div>

          <button
            type="button"
            className="btn-ghost"
            style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
            onClick={handleAuditLibrary}
            disabled={auditStatus === 'running'}
          >
            {auditStatus === 'running' ? 'Comprobando...' : 'Comprobar BD'}
          </button>
          <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
            Auditoría: {auditStatus === 'done' ? 'enviado' : auditStatus === 'error' ? 'error' : 'en espera'}
          </div>

          <div style={{ marginTop: 18 }}>
            <div style={{ fontWeight: 700, fontSize: 14 }}>Backfills</div>

            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
              onClick={handleBackfillAlbumsMissing}
              disabled={albumMissingStatus === 'running'}
            >
              {albumMissingStatus === 'running' ? 'Rellenando...' : 'Albums sin tracks'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Estado: {albumMissingStatus === 'done' ? 'enviado' : albumMissingStatus === 'error' ? 'error' : 'en espera'}
            </div>

            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
              onClick={handleBackfillAlbumsIncomplete}
              disabled={albumIncompleteStatus === 'running'}
            >
              {albumIncompleteStatus === 'running' ? 'Rellenando...' : 'Albums incompletos'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Estado: {albumIncompleteStatus === 'done' ? 'enviado' : albumIncompleteStatus === 'error' ? 'error' : 'en espera'}
            </div>

            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
              onClick={handleBackfillYoutubeLinks}
              disabled={youtubeBackfillStatus === 'running'}
            >
              {youtubeBackfillStatus === 'running' ? 'Buscando...' : 'Links YouTube'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Estado: {youtubeBackfillStatus === 'done' ? 'enviado' : youtubeBackfillStatus === 'error' ? 'error' : 'en espera'}
            </div>

            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
              onClick={handleRefreshMissingMetadata}
              disabled={metadataStatus === 'running'}
            >
              {metadataStatus === 'running' ? 'Actualizando...' : 'Metadata faltante'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Estado: {metadataStatus === 'done' ? 'enviado' : metadataStatus === 'error' ? 'error' : 'en espera'}
            </div>

            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 10 }}
              onClick={handleChartBackfill}
              disabled={chartBackfillStatus === 'running'}
            >
              {chartBackfillStatus === 'running' ? 'Backfill...' : 'Hot‑100 backfill'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Estado: {chartBackfillStatus === 'done' ? 'enviado' : chartBackfillStatus === 'error' ? 'error' : 'en espera'}
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Purgar artista</div>
            <input
              value={purgeId}
              onChange={(event) => setPurgeId(event.target.value)}
              placeholder="Spotify ID o nombre"
              className="input"
            />
            <button
              type="button"
              className="btn-ghost"
              style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
              onClick={handlePurgeArtist}
              disabled={purgeStatus === 'running'}
            >
              {purgeStatus === 'running' ? 'Borrando...' : 'Purgar artista'}
            </button>
            <div style={{ marginTop: 6, fontSize: 11, opacity: 0.7 }}>
              Purga: {purgeStatus === 'done' ? 'listo' : purgeStatus === 'error' ? 'error' : 'en espera'}
            </div>
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Terminal backend</div>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>
                Log en tiempo real (memoria). Solo se guardan las últimas ~1000 líneas.
              </div>
              <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}>
                Estado: {logsEnabled ? 'activo' : 'pausado'} · Último ID: {lastLogIdRef.current ?? 0}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => setLogsEnabled((prev) => !prev)}
              >
                {logsEnabled ? 'Pausar' : 'Reanudar'}
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={handleClearLogs}
              >
                Limpiar
              </button>
            </div>
          </div>
          {logError && (
            <div style={{ marginTop: 8, fontSize: 11, color: '#ef4444' }}>
              {logError}
            </div>
          )}
          <div
            ref={logBoxRef}
            style={{
              marginTop: 12,
              height: 420,
              overflow: 'auto',
              background: 'rgba(10, 12, 18, 0.9)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 10,
              padding: 12,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
              fontSize: 11,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              color: '#d1d5db',
            }}
          >
            {logLines.length ? logLines.join('\n') : 'Sin logs todavía...'}
          </div>
        </div>
      </div>
    </div>
  );
}
