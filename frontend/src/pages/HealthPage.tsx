import { useEffect } from 'react';
import { audio2Api } from '@/lib/api';
import { useState } from 'react';

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

export function HealthPage() {
  const [data, setData] = useState<DetailedHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setError(null);
        const res = await audio2Api.healthDetailed?.();
        if (res?.data) setData(res.data);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Error fetching health';
        setError(message);
      }
    };
    load();
  }, []);

  return (
    <div className="card" style={{ maxWidth: 620 }}>
      <h2 style={{ fontWeight: 700, marginBottom: 10 }}>Estado de servicios</h2>
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
  );
}
