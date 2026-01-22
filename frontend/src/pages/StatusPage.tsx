import { useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';

type ServiceStatus = {
  status: string | null;
  last_checked: string | null;
  last_error: string | null;
};

type DetailedHealth = {
  status: string;
  services: {
    spotify: ServiceStatus;
    lastfm: ServiceStatus;
    database: ServiceStatus;
  };
};

type SearchMetrics = {
  local: Record<string, number>;
  external: Record<string, number>;
};

const POLL_INTERVAL_MS = 5000;

const formatMetricKey = (key: string) => {
  if (key === 'global') return 'Global';
  if (key === 'anon') return 'Anon';
  return `Usuario ${key}`;
};

const renderMetricRows = (values: Record<string, number>) => {
  const entries = Object.entries(values)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  return entries.map(([key, value]) => (
    <div
      key={key}
      className="flex justify-between text-sm text-muted"
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <span>{formatMetricKey(key)}</span>
      <span>{value}</span>
    </div>
  ));
};

export function StatusPage() {
  const [data, setData] = useState<DetailedHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<SearchMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const res = await audio2Api.healthDetailed?.();
        if (!active) return;
        setData(res?.data ?? null);
        setError(null);
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : 'Error cargando estado';
        setError(message);
      }
      try {
        const metricsRes = await audio2Api.getSearchMetrics();
        if (!active) return;
        setMetrics(metricsRes.data ?? null);
        setMetricsError(null);
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : 'Error cargando métricas';
        setMetricsError(message);
      }
    };

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="space-y-4">
      <div className="card" style={{ maxWidth: 640 }}>
        <h2 style={{ fontWeight: 700, marginBottom: 10 }}>Status de Servicios</h2>
        {error && <div className="badge" style={{ color: '#ef4444' }}>{error}</div>}
        {!data && !error && <div style={{ color: 'var(--muted)' }}>Cargando...</div>}
        {data && (
          <div className="space-y-2">
            {Object.entries(data.services).map(([key, svc]) => (
              <div key={key} className="card" style={{ marginBottom: 8, padding: 10, background: 'var(--panel-2)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ textTransform: 'capitalize' }}>{key}</span>
                  <span className="badge" style={{
                    background: svc.status === 'online' ? 'rgba(110,193,164,0.15)' : 'rgba(239,68,68,0.15)',
                    color: svc.status === 'online' ? '#6ec1a4' : '#ef4444',
                    borderColor: 'transparent'
                  }}>
                    {svc.status ?? 'n/a'}
                  </span>
                </div>
                {svc.last_error && (
                  <div style={{ color: '#ef4444', fontSize: 12, marginTop: 6 }}>
                    {svc.last_error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        <h2 style={{ fontWeight: 700, marginBottom: 10 }}>Métricas de búsqueda</h2>
        {metricsError && <div className="badge" style={{ color: '#ef4444' }}>{metricsError}</div>}
        {!metrics && !metricsError && <div style={{ color: 'var(--muted)' }}>Esperando métricas...</div>}
        {metrics && (
          <div className="space-y-4">
            {['local', 'external'].map((category) => (
              <div key={category}>
                <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                  {category === 'local' ? 'Resoluciones locales' : 'Resoluciones externas'}
                </div>
                <div className="space-y-1">
                  {renderMetricRows(metrics[category as keyof SearchMetrics])}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
