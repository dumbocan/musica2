import { useState } from 'react';
import { Network, Server, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

interface RequestLog {
  id: string;
  method: string;
  url: string;
  status: number | null;
  response: any;
  error: any;
  timestamp: Date;
}

export function NetworkDebugger() {
  const [logs, setLogs] = useState<RequestLog[]>([]);

  const [isOpen, setIsOpen] = useState(false);

  const getStatusIcon = (status: number | null) => {
    if (!status) return <AlertCircle className="h-4 w-4 text-gray-500" />;
    if (status >= 200 && status < 300) return <CheckCircle className="h-4 w-4 text-green-500" />;
    return <XCircle className="h-4 w-4 text-red-500" />;
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          backgroundColor: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '50%',
          width: '50px',
          height: '50px',
          cursor: 'pointer',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '20px'
        }}
        title="API Debug Monitor"
      >
        🔍
      </button>
    );
  }

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '12px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        width: '90%',
        maxWidth: '800px',
        maxHeight: '80vh',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#f8fafc'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Network className="h-6 w-6 text-blue-500" />
            <h2 style={{ fontSize: '24px', fontWeight: 'bold' }}>
              API Monitor
            </h2>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            style={{
              padding: '8px',
              border: 'none',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              borderRadius: '4px'
            }}
          >
            ✕
          </button>
        </div>

        {/* Status */}
        <div style={{
          padding: '16px 24px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          gap: '16px',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server className="h-5 w-5 text-green-500" />
            <span style={{ fontWeight: '500' }}>API: http://localhost:8000</span>
          </div>
          <span style={{
            padding: '4px 8px',
            backgroundColor: '#dcfce7',
            color: '#166534',
            border: '1px solid #bbf7d0',
            borderRadius: '20px',
            fontSize: '12px',
            fontWeight: '500'
          }}>
            ✅ Conectado
          </span>
        </div>

        {/* Logs */}
        <div style={{ padding: '20px 24px', maxHeight: '400px', overflowY: 'auto' }}>
          <div style={{ marginBottom: '16px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '12px' }}>
              Request Logs
            </h3>
            <button
              onClick={() => setLogs([])}
              style={{
                padding: '6px 12px',
                backgroundColor: '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Clear All
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {logs.map((log) => (
              <div key={log.id} style={{
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '16px',
                backgroundColor: '#fafafa'
              }}>
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                  {getStatusIcon(log.status)}
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: '500',
                    backgroundColor: log.status && log.status >= 200 && log.status < 300 ? '#dcfce7' :
                                    log.status && log.status >= 400 ? '#fed7d7' : '#e5e7eb',
                    color: log.status && log.status >= 200 && log.status < 300 ? '#166534' :
                           log.status && log.status >= 400 ? '#991b1b' : '#374151'
                  }}>
                    {log.method} {log.status || 'ERR'}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: '14px', flex: 1 }}>
                    {log.url.replace('http://localhost:8000', '')}
                  </span>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>
                    {log.timestamp.toLocaleTimeString()}
                  </span>
                </div>

                {/* Response/Error */}
                {log.error ? (
                  <pre style={{
                    backgroundColor: '#fef2f2',
                    color: '#991b1b',
                    padding: '12px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    overflow: 'auto',
                    border: '1px solid #fecaca'
                  }}>
                    ❌ ERROR: {JSON.stringify(log.error, null, 2)}
                  </pre>
                ) : log.response ? (
                  <pre style={{
                    backgroundColor: '#f0fdf4',
                    color: '#166534',
                    padding: '12px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    overflow: 'auto',
                    border: '1px solid #bbf7d0'
                  }}>
                    ✅ RESPONSE: {JSON.stringify(log.response, null, 2)}
                  </pre>
                ) : null}
              </div>
            ))}
          </div>

          {logs.length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '40px',
              color: '#6b7280',
              border: '2px dashed #d1d5db',
              borderRadius: '8px'
            }}>
              <AlertCircle style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
              <p>No requests logged yet</p>
              <p style={{ fontSize: '14px', marginTop: '4px' }}>
                Start navigating the app to see API calls
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'center',
          gap: '12px',
          backgroundColor: '#f8fafc'
        }}>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 16px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            🔄 Refresh App
          </button>
        </div>
      </div>
    </div>
  );
}
