import { useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';

export function YoutubeRequestCounter() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    let interval: ReturnType<typeof setInterval> | null = null;
    const pollIntervalMs = 5 * 60 * 1000;
    const load = async () => {
      try {
        const res = await audio2Api.getYoutubeUsage();
        if (!isMounted) return;
        const next = Number(res.data?.requests_total);
        setCount(Number.isFinite(next) ? next : null);
      } catch {
        if (!isMounted) return;
        setCount(null);
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
      isMounted = false;
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 20,
        right: 20,
        background: 'var(--panel)',
        color: 'inherit',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '10px 14px',
        boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
        fontSize: 12,
        zIndex: 30,
      }}
    >
      <div style={{ color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.6 }}>YouTube requests</div>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{count ?? '—'}</div>
    </div>
  );
}
