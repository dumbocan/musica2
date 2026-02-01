import { useCallback, useEffect, useRef, useState } from 'react';
import { audio2Api } from '@/lib/api';
import { useApiStore } from '@/store/useApiStore';

type DashboardStats = {
  artists_total: number;
  albums_total: number;
  tracks_total: number;
  artists_missing_images: number;
  albums_missing_images: number;
  albums_without_tracks: number;
  tracks_without_youtube: number;
  tracks_with_spotify_id: number;
  tracks_with_local_file: number;
  youtube_links_total: number;
  youtube_downloads_completed: number;
  youtube_links_pending: number;
  youtube_links_failed: number;
};

type YtdlpLogEntry = {
  ts?: string;
  spotify_track_id?: string;
  spotify_artist_id?: string;
  youtube_video_id?: string;
  track_name?: string;
  artist_name?: string;
  album_name?: string;
  source?: string;
};

export function SettingsPage() {
  const setServiceStatus = useApiStore((s) => s.setServiceStatus);
  const [maintenanceEnabled, setMaintenanceEnabled] = useState(true);
  const [maintenanceState, setMaintenanceState] = useState<'unknown' | 'running' | 'stopping' | 'idle' | 'error'>('unknown');
  const [maintenanceStarting, setMaintenanceStarting] = useState(false);
  const [maintenanceStopping, setMaintenanceStopping] = useState(false);
  const [maintenanceStopStatus, setMaintenanceStopStatus] = useState<'idle' | 'done' | 'error'>('idle');
  const [auditStatus, setAuditStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [albumMissingStatus, setAlbumMissingStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [albumIncompleteStatus, setAlbumIncompleteStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [youtubeBackfillStatus, setYoutubeBackfillStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [imagesBackfillStatus, setImagesBackfillStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [metadataStatus, setMetadataStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [chartBackfillStatus, setChartBackfillStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [albumImageRepairStatus, setAlbumImageRepairStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [ytdlpRevalidateStatus, setYtdlpRevalidateStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [purgeId, setPurgeId] = useState('');
  const [purgeStatus, setPurgeStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [actionStatuses, setActionStatuses] = useState<Record<string, boolean>>({});
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logsEnabled, setLogsEnabled] = useState(true);
  const [logError, setLogError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [youtubeUsage, setYoutubeUsage] = useState<{
    requests_total?: number;
    next_reset_at_unix?: number;
    reset_hour_local?: number;
    requests_limit?: number;
    remaining?: number;
  } | null>(null);
  const [youtubeUsageError, setYoutubeUsageError] = useState<string | null>(null);
  const [ytdlpEnabled, setYtdlpEnabled] = useState<boolean | null>(null);
  const [ytdlpUsage, setYtdlpUsage] = useState<{
    requests_total?: number;
    requests_limit?: number;
    remaining?: number;
    next_reset_at_unix?: number;
  } | null>(null);
  const [ytdlpLogCount, setYtdlpLogCount] = useState<number | null>(null);
  const [ytdlpLogPath, setYtdlpLogPath] = useState<string | null>(null);
  const [ytdlpLogs, setYtdlpLogs] = useState<YtdlpLogEntry[]>([]);
  const [ytdlpError, setYtdlpError] = useState<string | null>(null);
  const [serviceSnapshot, setServiceSnapshot] = useState<{
    spotify?: { status?: string | null; last_error?: string | null };
    lastfm?: { status?: string | null; last_error?: string | null };
    database?: { status?: string | null; last_error?: string | null };
  } | null>(null);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const logBoxRef = useRef<HTMLDivElement | null>(null);
  const lastLogIdRef = useRef<number | null>(null);
  const startGraceRef = useRef<number | null>(null);
  const MAINTENANCE_GRACE_MS = 5000;

  const refreshHealth = async () => {
    setHealthLoading(true);
    try {
      const res = await audio2Api.healthDetailed?.();
      const services = res?.data?.services ?? null;
      setServiceSnapshot(services);
      setServiceStatus(
        services
          ? { spotify: services.spotify, lastfm: services.lastfm }
          : null
      );
      setHealthError(null);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'Error cargando estado');
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    setHealthLoading(true);
    audio2Api
      .healthDetailed?.()
      .then((res) => {
        if (!active) return;
        const services = res?.data?.services ?? null;
        setServiceSnapshot(services);
        setServiceStatus(
          services
            ? { spotify: services.spotify, lastfm: services.lastfm }
            : null
        );
        setHealthError(null);
      })
      .catch((err) => {
        if (!active) return;
        setHealthError(err instanceof Error ? err.message : 'Error cargando estado');
      })
      .finally(() => {
        if (!active) return;
        setHealthLoading(false);
      });
    return () => {
      active = false;
    };
  }, [setServiceStatus]);

  useEffect(() => {
    let active = true;
    let interval: ReturnType<typeof setInterval> | null = null;
    const pollIntervalMs = 5 * 60 * 1000;

    const load = async () => {
      try {
        const res = await audio2Api.getYoutubeUsage();
        if (!active) return;
        setYoutubeUsage(res.data ?? null);
        setYoutubeUsageError(null);
      } catch (err) {
        if (!active) return;
        setYoutubeUsageError(err instanceof Error ? err.message : 'Error cargando cuota YouTube');
      }
    };

    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };

    const startPolling = () => {
      if (!interval) {
        interval = setInterval(load, pollIntervalMs);
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        load();
        startPolling();
      } else {
        stopPolling();
      }
    };

    handleVisibility();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      active = false;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  const refreshYtdlpStatus = useCallback(async () => {
    try {
      const res = await audio2Api.getYoutubeFallbackStatus();
      const data = res.data ?? {};
      setYtdlpEnabled(Boolean(data.enabled));
      setYtdlpUsage(data.usage ?? null);
      setYtdlpLogCount(typeof data.log_count === 'number' ? data.log_count : null);
      setYtdlpLogPath(typeof data.log_path === 'string' ? data.log_path : null);
      setYtdlpError(null);
    } catch (err) {
      setYtdlpError(err instanceof Error ? err.message : 'Error cargando fallback');
    }
  }, []);

  const refreshYtdlpLogs = useCallback(async () => {
    try {
      const res = await audio2Api.getYoutubeFallbackLogs({ limit: 200 });
      const items = Array.isArray(res.data?.items) ? res.data.items : [];
      setYtdlpLogs(items);
      if (typeof res.data?.count === 'number') {
        setYtdlpLogCount(res.data.count);
      }
      if (typeof res.data?.log_path === 'string') {
        setYtdlpLogPath(res.data.log_path);
      }
      setYtdlpError(null);
    } catch (err) {
      setYtdlpError(err instanceof Error ? err.message : 'Error cargando logs de fallback');
    }
  }, []);

  useEffect(() => {
    let active = true;
    let interval: ReturnType<typeof setInterval> | null = null;
    const pollIntervalMs = 60 * 1000;

    const load = async () => {
      if (!active) return;
      await refreshYtdlpStatus();
      await refreshYtdlpLogs();
    };

    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };

    const startPolling = () => {
      if (!interval) {
        interval = setInterval(load, pollIntervalMs);
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void load();
        startPolling();
      } else {
        stopPolling();
      }
    };

    handleVisibility();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      active = false;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [refreshYtdlpLogs, refreshYtdlpStatus]);

  const refreshDashboardStats = useCallback(async () => {
    setDashboardLoading(true);
    try {
      const res = await audio2Api.getDashboardStats();
      setDashboardStats(res.data ?? null);
      setDashboardError(null);
    } catch (err) {
      setDashboardError(err instanceof Error ? err.message : 'Error cargando métricas');
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshDashboardStats();
  }, [refreshDashboardStats]);

  useEffect(() => {
    let active = true;
    const refreshMaintenance = async () => {
      try {
        const res = await audio2Api.getMaintenanceStatus();
        if (!active) return;
        const enabled = Boolean(res.data?.enabled);
        const running = Boolean(res.data?.running);
        if (enabled !== maintenanceEnabled) {
          setMaintenanceEnabled(enabled);
        }
        const now = Date.now();
        const withinGrace =
          startGraceRef.current !== null && startGraceRef.current + MAINTENANCE_GRACE_MS > now;
        if (!running && !withinGrace) {
          startGraceRef.current = null;
        }
        setMaintenanceState(running || withinGrace ? 'running' : 'idle');
      } catch {
        if (!active) return;
        setMaintenanceState('error');
      }
    };
    refreshMaintenance();
    const interval = window.setInterval(refreshMaintenance, 5000);
    return () => {
      active = false;
      window.clearInterval(interval);
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
    const timer = window.setInterval(fetchLogs, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [logsEnabled]);

  const handleMaintenanceToggleEnabled = useCallback(async () => {
    const newValue = !maintenanceEnabled;
    try {
      await audio2Api.toggleMaintenance(newValue);
      setMaintenanceEnabled(newValue);
    } catch {
      // ignore error
    }
  }, [maintenanceEnabled]);

  const handleToggleYtdlp = useCallback(async () => {
    const newValue = !(ytdlpEnabled ?? false);
    try {
      await audio2Api.toggleYoutubeFallback(newValue);
      setYtdlpEnabled(newValue);
    } catch (err) {
      setYtdlpError(err instanceof Error ? err.message : 'Error cambiando fallback');
    } finally {
      void refreshYtdlpStatus();
      void refreshYtdlpLogs();
    }
  }, [refreshYtdlpLogs, refreshYtdlpStatus, ytdlpEnabled]);

  const handleMaintenanceStart = useCallback(async () => {
    setMaintenanceStarting(true);
    setMaintenanceStopStatus('idle');
    setMaintenanceState('running');
    try {
      await audio2Api.startMaintenance();
      startGraceRef.current = Date.now();
    } catch {
      setMaintenanceState('error');
    } finally {
      setMaintenanceStarting(false);
      void refreshDashboardStats();
    }
  }, [refreshDashboardStats]);

  const handleStopAllMaintenance = useCallback(async () => {
    setMaintenanceStopStatus('idle');
    setMaintenanceStopping(true);
    setMaintenanceState('stopping');
    try {
      await audio2Api.stopMaintenance();
      setMaintenanceState('idle');
      setMaintenanceStopStatus('done');
      startGraceRef.current = null;
    } catch {
      setMaintenanceStopStatus('error');
      setMaintenanceState('error');
    } finally {
      setMaintenanceStopping(false);
      void refreshDashboardStats();
    }
  }, [refreshDashboardStats]);

  const handleMaintenanceToggle = useCallback(async () => {
    if (maintenanceState === 'running' || maintenanceState === 'stopping') {
      await handleStopAllMaintenance();
    } else {
      await handleMaintenanceStart();
    }
  }, [handleMaintenanceStart, handleStopAllMaintenance, maintenanceState]);

  const handleAuditLibrary = async () => {
    if (auditStatus === 'running') return;
    setAuditStatus('running');
    try {
      await audio2Api.auditLibrary();
      setAuditStatus('done');
    } catch {
      setAuditStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const refreshActionStatuses = useCallback(async () => {
    try {
      const res = await audio2Api.getMaintenanceActionStatus();
      setActionStatuses(res.data?.actions ?? {});
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshActionStatuses();
    const interval = window.setInterval(refreshActionStatuses, 8000);
    return () => window.clearInterval(interval);
  }, [refreshActionStatuses]);

  useEffect(() => {
    const hasRunningAction = Object.values(actionStatuses).some(Boolean);
    if (!hasRunningAction) return;
    const interval = window.setInterval(() => {
      void refreshDashboardStats();
    }, 6000);
    return () => window.clearInterval(interval);
  }, [actionStatuses, refreshDashboardStats]);

  const handleBackfillAlbumsMissing = async () => {
    if (albumMissingStatus === 'running') return;
    setAlbumMissingStatus('running');
    try {
      await audio2Api.backfillAlbumTracks({ mode: 'missing', limit: 200, concurrency: 2 });
      setAlbumMissingStatus('done');
    } catch {
      setAlbumMissingStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const handleBackfillAlbumsIncomplete = async () => {
    if (albumIncompleteStatus === 'running') return;
    setAlbumIncompleteStatus('running');
    try {
      await audio2Api.backfillAlbumTracks({ mode: 'incomplete', limit: 200, concurrency: 2 });
      setAlbumIncompleteStatus('done');
    } catch {
      setAlbumIncompleteStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const handleBackfillYoutubeLinks = async () => {
    if (youtubeBackfillStatus === 'running') return;
    setYoutubeBackfillStatus('running');
    try {
      await audio2Api.backfillYoutubeLinks({ limit: 200 });
      setYoutubeBackfillStatus('done');
    } catch {
      setYoutubeBackfillStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const handleRevalidateYtdlpLinks = async () => {
    if (ytdlpRevalidateStatus === 'running') return;
    setYtdlpRevalidateStatus('running');
    try {
      await audio2Api.revalidateYtdlpLinks({ limit: 500 });
      setYtdlpRevalidateStatus('done');
    } catch {
      setYtdlpRevalidateStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
      void refreshYtdlpStatus();
      void refreshYtdlpLogs();
    }
  };

  const handleBackfillImages = async () => {
    if (imagesBackfillStatus === 'running') return;
    setImagesBackfillStatus('running');
    try {
      await audio2Api.backfillImages();
      setImagesBackfillStatus('done');
    } catch {
      setImagesBackfillStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const handleRepairAlbumImages = async () => {
    if (albumImageRepairStatus === 'running') return;
    setAlbumImageRepairStatus('running');
    try {
      await audio2Api.repairAlbumImages({ limit: 20000, background: true });
      setAlbumImageRepairStatus('done');
    } catch {
      setAlbumImageRepairStatus('error');
    } finally {
      void refreshActionStatuses();
    }
  };

  const handleRefreshMissingMetadata = async () => {
    if (metadataStatus === 'running') return;
    setMetadataStatus('running');
    try {
      await audio2Api.refreshMissingArtists({ limit: 200, use_spotify: true, use_lastfm: true });
      setMetadataStatus('done');
    } catch {
      setMetadataStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
    }
  };

  const handleChartBackfill = async () => {
    if (chartBackfillStatus === 'running') return;
    setChartBackfillStatus('running');
    try {
      await audio2Api.backfillChart({ chart_source: 'billboard', chart_name: 'hot-100', weeks: 20 });
      setChartBackfillStatus('done');
    } catch {
      setChartBackfillStatus('error');
    } finally {
      void refreshDashboardStats();
      void refreshActionStatuses();
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
    } finally {
      void refreshDashboardStats();
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

  const dashboardCards = [
    { label: 'Artistas en BD', value: dashboardStats?.artists_total },
    { label: 'Álbumes en BD', value: dashboardStats?.albums_total },
    { label: 'Pistas en BD', value: dashboardStats?.tracks_total },
    { label: 'Artistas sin imagen', value: dashboardStats?.artists_missing_images },
    { label: 'Álbumes sin imagen', value: dashboardStats?.albums_missing_images },
    { label: 'Álbumes sin tracks', value: dashboardStats?.albums_without_tracks },
    { label: 'Tracks sin link YouTube', value: dashboardStats?.tracks_without_youtube },
    { label: 'Tracks con archivo local', value: dashboardStats?.tracks_with_local_file },
  ];
  const tracksTotal = Math.max(dashboardStats?.tracks_total ?? 0, 1);
  const tracksWithSpotify = Math.max(dashboardStats?.tracks_with_spotify_id ?? 0, 1);
  const artistsTotal = Math.max(dashboardStats?.artists_total ?? 0, 1);
  const albumsTotal = Math.max(dashboardStats?.albums_total ?? 0, 1);
  const youtubeLinks = Math.max(dashboardStats?.youtube_links_total ?? 0, 0);
  const downloadsCompleted = dashboardStats?.youtube_downloads_completed ?? 0;
  const linksPending = dashboardStats?.youtube_links_pending ?? Math.max(youtubeLinks - downloadsCompleted, 0);
  const linksFailed = dashboardStats?.youtube_links_failed ?? 0;
  const artistsMissingImages = dashboardStats?.artists_missing_images ?? 0;
  const albumsMissingImages = dashboardStats?.albums_missing_images ?? 0;
  const albumsWithoutTracks = dashboardStats?.albums_without_tracks ?? 0;
  const tracksWithLocalFile = dashboardStats?.tracks_with_local_file ?? 0;
  const albumsWithTracks = Math.max(albumsTotal - albumsWithoutTracks, 0);
  const artistsWithImages = Math.max(artistsTotal - artistsMissingImages, 0);
  const albumsWithImages = Math.max(albumsTotal - albumsMissingImages, 0);
  const radialData = [
    {
      label: 'Links YouTube',
      value: youtubeLinks,
      total: tracksWithSpotify,
      color: 'hsl(165, 74%, 48%)',
      helper: 'links / tracks Spotify',
    },
    {
      label: 'Descargas completadas',
      value: downloadsCompleted,
      total: Math.max(youtubeLinks, 1),
      color: 'hsl(204, 100%, 45%)',
      helper: 'completadas / links',
    },
    {
      label: 'Links pendientes',
      value: linksPending,
      total: Math.max(youtubeLinks, 1),
      color: 'hsl(15, 84%, 56%)',
      helper: 'pendientes / links',
    },
    {
      label: 'Links fallidos',
      value: linksFailed,
      total: Math.max(youtubeLinks, 1),
      color: 'hsl(6, 89%, 53%)',
      helper: 'fallidos / links',
    },
    {
      label: 'Archivos locales',
      value: tracksWithLocalFile,
      total: tracksTotal,
      color: 'hsl(220, 72%, 54%)',
      helper: 'locales / tracks',
    },
    {
      label: 'Artistas con imagen',
      value: artistsWithImages,
      total: artistsTotal,
      color: 'hsl(141, 76%, 35%)',
      helper: 'con imagen / total',
    },
    {
      label: 'Álbumes con imagen',
      value: albumsWithImages,
      total: albumsTotal,
      color: 'hsl(197, 73%, 46%)',
      helper: 'con imagen / total',
    },
    {
      label: 'Álbumes con tracks',
      value: albumsWithTracks,
      total: albumsTotal,
      color: 'hsl(205, 79%, 52%)',
      helper: 'con tracks / total',
    },
  ];

  const maintenanceButtonRunning =
    maintenanceState === 'running' || maintenanceState === 'stopping' || maintenanceStarting;
  const maintenanceButtonStyle = maintenanceButtonRunning
    ? {
        boxShadow: '0 0 16px rgba(14, 165, 233, 0.95)',
        background: '#0ea5e9',
        color: '#020617',
      }
    : {};
  const actionGlowStyle = {
    boxShadow: '0 0 16px rgba(14, 165, 233, 0.8)',
    background: '#0ea5e9',
    color: '#020617',
  };
  const baseActionStyle = { width: '100%', justifyContent: 'center' };
  const actionActiveFlag = (key: string) => Boolean(actionStatuses[key]);
  const actionButtonStyle = (actionKey: string) => ({
    ...baseActionStyle,
    ...(actionActiveFlag(actionKey) ? actionGlowStyle : {}),
  });
  const actionLabel = (
    base: string,
    status: 'idle' | 'running' | 'done' | 'error',
    actionKey: string
  ) => {
    const active = actionActiveFlag(actionKey);
    if (status === 'running') return 'Enviando...';
    if (status === 'error') return `${base} (error)`;
    if (active) return `Detener ${base}`;
    return base;
  };

  const renderServiceStatus = (
    label: string,
    service?: { status?: string | null; last_error?: string | null }
  ) => {
    const status = service?.status ?? 'unknown';
    const text =
      status === 'online' ? 'online' : status === 'offline' ? 'offline' : 'desconocido';
    const color = status === 'online' ? '#22c55e' : status === 'offline' ? '#ef4444' : '#f59e0b';
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: 11 }}>
          {label}:{' '}
          <span style={{ color, fontWeight: 600 }}>{text}</span>
        </div>
        {service?.last_error && status !== 'online' && (
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)' }}>
            {service.last_error}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="page">
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '280px minmax(0, 1fr) 360px',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <aside style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div style={{ fontWeight: 700, fontSize: 18 }}>Mantenimiento</div>
            <div style={{ color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
              Acciones críticas y medidas rápidas para controlar la sincronización.
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 14 }}>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                <input
                  type="checkbox"
                  checked={maintenanceEnabled}
                  onChange={handleMaintenanceToggleEnabled}
                  style={{ width: 16, height: 16, cursor: 'pointer' }}
                />
                <span style={{ fontSize: 13 }}>Mant. habilitado</span>
              </label>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 14 }}>
              <button
                type="button"
                className="btn-ghost"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  transition: 'box-shadow 0.4s ease, background 0.4s ease',
                  ...(maintenanceButtonRunning ? maintenanceButtonStyle : {}),
                }}
                onClick={handleMaintenanceToggle}
                disabled={maintenanceStarting || maintenanceStopping}
              >
                {maintenanceState === 'stopping'
                  ? 'Parando mantenimiento'
                  : maintenanceStarting
                  ? 'Iniciando mantenimiento...'
                  : maintenanceButtonRunning
                  ? 'Detener mantenimiento'
                  : 'Forzar mantenimiento'}
              </button>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, opacity: 0.7 }}>
              Estado: {maintenanceState === 'running' ? 'activo' : maintenanceState === 'idle' ? 'en espera' : maintenanceState === 'error' ? 'error' : 'desconocido'}
            </div>
            <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>
              Stop: {maintenanceStopStatus === 'done' ? 'detenido' : maintenanceStopStatus === 'error' ? 'error' : 'en espera'}
            </div>
            <button
              type="button"
              className="btn-ghost"
              style={{
                ...actionButtonStyle('audit'),
                marginTop: 12,
              }}
              onClick={handleAuditLibrary}
              disabled={auditStatus === 'running'}
            >
              {actionLabel('Comprobar BD', auditStatus, 'audit')}
            </button>
            <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>
              Auditoría: {auditStatus === 'done' ? 'enviado' : auditStatus === 'error' ? 'error' : 'en espera'}
            </div>
            <button
              type="button"
              className="btn-ghost"
              style={{
                ...actionButtonStyle('repair_album_images'),
                marginTop: 12,
              }}
              onClick={handleRepairAlbumImages}
              disabled={albumImageRepairStatus === 'running'}
            >
              {actionLabel('Reparar imágenes de álbum', albumImageRepairStatus, 'repair_album_images')}
            </button>
            <div style={{ marginTop: 4, fontSize: 11, opacity: 0.7 }}>
              Reparación imágenes: {albumImageRepairStatus === 'done' ? 'en cola' : albumImageRepairStatus === 'error' ? 'error' : 'en espera'}
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Backfills y metadata</div>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>Limita 200 por acción</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('albums_missing')}
                onClick={handleBackfillAlbumsMissing}
                disabled={albumMissingStatus === 'running'}
              >
                {actionLabel('Albums sin tracks', albumMissingStatus, 'albums_missing')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {albumMissingStatus === 'done' ? 'enviado' : albumMissingStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('albums_incomplete')}
                onClick={handleBackfillAlbumsIncomplete}
                disabled={albumIncompleteStatus === 'running'}
              >
                {actionLabel('Albums incompletos', albumIncompleteStatus, 'albums_incomplete')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {albumIncompleteStatus === 'done' ? 'enviado' : albumIncompleteStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('youtube_links')}
                onClick={handleBackfillYoutubeLinks}
                disabled={youtubeBackfillStatus === 'running'}
              >
                {actionLabel('Links YouTube', youtubeBackfillStatus, 'youtube_links')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {youtubeBackfillStatus === 'done' ? 'enviado' : youtubeBackfillStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('ytdlp_revalidate')}
                onClick={handleRevalidateYtdlpLinks}
                disabled={ytdlpRevalidateStatus === 'running'}
              >
                {actionLabel('Revalidar links fallback', ytdlpRevalidateStatus, 'ytdlp_revalidate')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {ytdlpRevalidateStatus === 'done' ? 'enviado' : ytdlpRevalidateStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('images_backfill')}
                onClick={handleBackfillImages}
                disabled={imagesBackfillStatus === 'running'}
              >
                {actionLabel('Repoblar imágenes', imagesBackfillStatus, 'images_backfill')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {imagesBackfillStatus === 'done' ? 'enviado' : imagesBackfillStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('metadata_refresh')}
                onClick={handleRefreshMissingMetadata}
                disabled={metadataStatus === 'running'}
              >
                {actionLabel('Metadata faltante', metadataStatus, 'metadata_refresh')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
                Estado: {metadataStatus === 'done' ? 'enviado' : metadataStatus === 'error' ? 'error' : 'en espera'}
              </div>

              <button
                type="button"
                className="btn-ghost"
                style={actionButtonStyle('chart_backfill')}
                onClick={handleChartBackfill}
                disabled={chartBackfillStatus === 'running'}
              >
                {actionLabel('Hot‑100 backfill', chartBackfillStatus, 'chart_backfill')}
              </button>
              <div style={{ fontSize: 11, opacity: 0.7 }}>
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
        </aside>

        <main style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 18 }}>Dashboard profesional</div>
                <div style={{ color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
                  Estadísticas clave de la base sin necesidad de recargar.
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={refreshDashboardStats}
                disabled={dashboardLoading}
                style={{ padding: '4px 12px', fontSize: 11 }}
              >
                {dashboardLoading ? 'Actualizando...' : 'Refrescar datos'}
              </button>
            </div>
            {dashboardError && (
              <div style={{ marginTop: 10, fontSize: 11, color: '#ef4444' }}>{dashboardError}</div>
            )}
            <div
              style={{
                marginTop: 16,
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: 12,
              }}
            >
              {dashboardCards.map((item) => (
                <MetricCard key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
            <div
              style={{
                marginTop: 16,
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 12,
              }}
            >
              {radialData.map((metric) => (
                <RadialStat
                  key={metric.label}
                  label={metric.label}
                  value={metric.value}
                  total={metric.total}
                  color={metric.color}
                  helper={metric.helper}
                />
              ))}
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>Servicios</div>
                <div style={{ color: 'var(--muted)', fontSize: 12 }}>Consulta estado global y uso de APIs.</div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={refreshHealth}
                disabled={healthLoading}
                style={{ padding: '4px 10px', fontSize: 11 }}
              >
                {healthLoading ? 'Actualizando...' : 'Actualizar'}
              </button>
            </div>
            {healthError ? (
              <div style={{ marginTop: 10, fontSize: 11, color: '#ef4444' }}>{healthError}</div>
            ) : (
              <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
                {renderServiceStatus('Spotify', serviceSnapshot?.spotify)}
                {renderServiceStatus('Last.fm', serviceSnapshot?.lastfm)}
                {renderServiceStatus('Base de datos', serviceSnapshot?.database)}
                <div
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.12)',
                    background: 'rgba(255,255,255,0.02)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600 }}>YouTube API</div>
                  <div
                    style={{
                      marginTop: 6,
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 12,
                      fontSize: 11,
                      color: 'var(--muted)',
                    }}
                  >
                    <span>
                      Usado:{' '}
                      <strong style={{ color: 'inherit' }}>
                        {typeof youtubeUsage?.requests_total === 'number'
                          ? youtubeUsage.requests_total.toLocaleString()
                          : '—'}
                      </strong>
                      / {typeof youtubeUsage?.requests_limit === 'number'
                          ? youtubeUsage.requests_limit
                          : 80}
                    </span>
                    <span>
                      Restante:{' '}
                      <strong style={{ color: youtubeUsage?.remaining !== undefined && youtubeUsage.remaining < 10 ? '#ef4444' : 'inherit' }}>
                        {typeof youtubeUsage?.remaining === 'number'
                          ? youtubeUsage.remaining
                          : '—'}
                      </strong>
                    </span>
                  </div>
                  <div style={{ fontSize: 10, marginTop: 4, color: 'var(--muted)' }}>
                    Reset: {youtubeUsage?.next_reset_at_unix
                      ? new Date(youtubeUsage.next_reset_at_unix * 1000).toLocaleString()
                      : '—'}
                  </div>
                  {youtubeUsageError && (
                    <div style={{ marginTop: 6, fontSize: 10, color: '#ef4444' }}>{youtubeUsageError}</div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>Fallback yt-dlp</div>
                <div style={{ color: 'var(--muted)', fontSize: 12 }}>
                  Controla el respaldo de enlaces cuando la API está limitada.
                </div>
              </div>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  void refreshYtdlpStatus();
                  void refreshYtdlpLogs();
                }}
                style={{ padding: '4px 10px', fontSize: 11 }}
              >
                Actualizar
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={Boolean(ytdlpEnabled)}
                  onChange={handleToggleYtdlp}
                  style={{ width: 16, height: 16, cursor: 'pointer' }}
                />
                <span style={{ fontSize: 13 }}>Fallback habilitado</span>
              </label>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                Guardados: {typeof ytdlpLogCount === 'number' ? ytdlpLogCount.toLocaleString() : '—'}
              </span>
            </div>
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 11, color: 'var(--muted)' }}>
              <span>
                Uso:{' '}
                <strong style={{ color: 'inherit' }}>
                  {typeof ytdlpUsage?.requests_total === 'number'
                    ? ytdlpUsage.requests_total.toLocaleString()
                    : '—'}
                </strong>
                / {typeof ytdlpUsage?.requests_limit === 'number'
                    ? ytdlpUsage.requests_limit
                    : '—'}
              </span>
              <span>
                Restante:{' '}
                <strong style={{ color: ytdlpUsage?.remaining !== undefined && ytdlpUsage.remaining < 10 ? '#ef4444' : 'inherit' }}>
                  {typeof ytdlpUsage?.remaining === 'number'
                    ? ytdlpUsage.remaining
                    : '—'}
                </strong>
              </span>
              <span>
                Reset: {ytdlpUsage?.next_reset_at_unix
                  ? new Date(ytdlpUsage.next_reset_at_unix * 1000).toLocaleString()
                  : '—'}
              </span>
            </div>
            {ytdlpLogPath && (
              <div style={{ marginTop: 6, fontSize: 10, color: 'var(--muted)' }}>
                Log: {ytdlpLogPath}
              </div>
            )}
            {ytdlpError && (
              <div style={{ marginTop: 6, fontSize: 10, color: '#ef4444' }}>{ytdlpError}</div>
            )}
            <div
              style={{
                marginTop: 10,
                maxHeight: 220,
                overflow: 'auto',
                background: 'rgba(10, 12, 18, 0.85)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
                padding: 10,
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                fontSize: 11,
                lineHeight: 1.5,
                color: '#d1d5db',
                whiteSpace: 'pre-wrap',
              }}
            >
              {ytdlpLogs.length
                ? ytdlpLogs
                    .map((entry) => {
                      const ts = entry.ts ? new Date(entry.ts).toLocaleString() : '—';
                      const artist = entry.artist_name || entry.spotify_artist_id || 'artista?';
                      const track = entry.track_name || entry.spotify_track_id || 'track?';
                      const video = entry.youtube_video_id || 'sin video';
                      return `${ts} · ${artist} — ${track} · ${video}`;
                    })
                    .join('\n')
                : 'Sin logs todavía...'}
            </div>
          </div>
        </main>

        <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Terminal backend</div>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>
                Log en tiempo real (últimas ~1000 líneas).
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
              height: 520,
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
        </section>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value?: number | null }) {
  const display = typeof value === 'number' ? value.toLocaleString() : '—';
  return (
    <div
      style={{
        padding: '14px 16px',
        borderRadius: 12,
        border: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(255,255,255,0.02)',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{display}</div>
    </div>
  );
}

function RadialStat({
  label,
  value,
  total,
  color,
  helper,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
  helper?: string;
}) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const normalizedTotal = total > 0 ? total : 1;
  const rawPercent = Math.min(Math.max(value / normalizedTotal, 0), 1);
  const strokeDashoffset = circumference * (1 - rawPercent);
  return (
    <div
      style={{
        borderRadius: 12,
        border: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(255,255,255,0.02)',
        padding: 18,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 6,
      }}
    >
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4, color: 'var(--muted)' }}>
        {label}
      </div>
      <svg width={110} height={110} viewBox="0 0 110 110">
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="10"
        />
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          transform="rotate(-90 55 55)"
        />
        <text
          x="55"
          y="55"
          textAnchor="middle"
          dominantBaseline="central"
          fill="#fff"
          style={{ fontSize: 18, fontWeight: 700 }}
        >
          {!Number.isFinite(value / normalizedTotal) ? '—' : Math.round(rawPercent * 100)}%
        </text>
      </svg>
      <div style={{ fontSize: 12, fontWeight: 600 }}>
        {value.toLocaleString()} / {total.toLocaleString()}
      </div>
      {helper && <div style={{ fontSize: 10, color: 'var(--muted)' }}>{helper}</div>}
    </div>
  );
}
