import { useCallback, useEffect, useState } from 'react';
import { audio2Api } from '@/lib/api';

type ChartRawEntry = {
  chart_source: string;
  chart_name: string;
  chart_date: string;
  rank: number;
  title: string;
  artist: string;
};

type ChartRawSummary = {
  total_rows: number;
  distinct_dates: number;
  distinct_titles: number;
};

export function HistoricalDbPage() {
  const [chartName, setChartName] = useState('hot-100');
  const [entries, setEntries] = useState<ChartRawEntry[]>([]);
  const [summary, setSummary] = useState<ChartRawSummary | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const limit = 200;

  const loadEntries = useCallback(async (reset: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const res = await audio2Api.getChartRaw({
        chart_name: chartName,
        offset: reset ? 0 : offset,
        limit,
      });
      const items = res.data?.items || [];
      setEntries((prev) => (reset ? items : [...prev, ...items]));
      if (res.data?.summary) {
        setSummary(res.data.summary);
      }
      if (reset) {
        setOffset(limit);
      } else {
        setOffset((prev) => prev + limit);
      }
    } catch (err: unknown) {
      const message =
        err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? (err.response.data as { detail: string }).detail
          : err instanceof Error
            ? err.message
            : 'Error cargando historico';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [chartName, limit, offset]);

  useEffect(() => {
    setEntries([]);
    setSummary(null);
    setOffset(0);
    void loadEntries(true);
  }, [chartName, loadEntries]);

  const hasMore = summary ? entries.length < summary.total_rows : true;

  return (
    <div className="page">
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>BD historico</div>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>
              Registros top 5 por semana desde Billboard.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <label style={{ fontSize: 12, color: 'var(--muted)' }}>Chart</label>
            <select
              value={chartName}
              onChange={(e) => setChartName(e.target.value)}
              className="input"
              style={{ minWidth: 200 }}
            >
              <option value="hot-100">Hot 100 (US)</option>
              <option value="billboard-global-200">Global 200</option>
            </select>
          </div>
        </div>
        {summary && (
          <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap', fontSize: 12 }}>
            <div>
              <strong>{summary.total_rows}</strong> filas
            </div>
            <div>
              <strong>{summary.distinct_dates}</strong> semanas
            </div>
            <div>
              <strong>{summary.distinct_titles}</strong> canciones
            </div>
          </div>
        )}
      </div>

      <div className="card">
        {loading && (
          <div className="badge" style={{ marginBottom: 8 }}>
            Cargando...
          </div>
        )}
        {error && (
          <div className="badge" style={{ marginBottom: 8, borderColor: '#ef4444', color: '#fecaca' }}>
            {error}
          </div>
        )}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--muted)', fontSize: 12 }}>
                <th style={{ padding: '8px 6px', width: 120 }}>Fecha</th>
                <th style={{ padding: '8px 6px', width: 70 }}>Rank</th>
                <th style={{ padding: '8px 6px', width: 320 }}>Titulo</th>
                <th style={{ padding: '8px 6px', width: 260 }}>Artista</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((row, idx) => (
                <tr key={`${row.chart_date}-${row.rank}-${idx}`} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '10px 6px', fontSize: 12, color: 'var(--muted)' }}>{row.chart_date}</td>
                  <td style={{ padding: '10px 6px', fontWeight: 700 }}>{row.rank}</td>
                  <td style={{ padding: '10px 6px', fontWeight: 600 }}>{row.title}</td>
                  <td style={{ padding: '10px 6px', color: 'var(--muted)' }}>{row.artist}</td>
                </tr>
              ))}
              {!loading && entries.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ padding: '14px 6px', color: 'var(--muted)' }}>
                    Sin datos aún.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {hasMore && (
          <div style={{ marginTop: 12 }}>
            <button
              className="btn-ghost"
              onClick={() => void loadEntries(false)}
              disabled={loading}
            >
              Cargar mas
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
