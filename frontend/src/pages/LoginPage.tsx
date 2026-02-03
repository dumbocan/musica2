import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { AlertCircle, CheckCircle } from 'lucide-react';
import { useApiStore } from '@/store/useApiStore';

export function LoginPage() {
  const navigate = useNavigate();
  const { setToken, setAuthenticated, setUserEmail, setUserId } = useApiStore();

  const [mode, setMode] = useState<'login' | 'signup' | 'recover'>('login');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    recoveryCode: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [lookupResult, setLookupResult] = useState<string | null>(null);
  const [dbStatus, setDbStatus] = useState<'online' | 'offline' | 'unknown'>('unknown');
  const [dbError, setDbError] = useState<string | null>(null);
  const dbCheckInFlight = useRef(false);

  const switchMode = (nextMode: 'login' | 'signup' | 'recover') => {
    setMode(nextMode);
    setError('');
    setSuccess(false);
    setLookupResult(null);
  };

  useEffect(() => {
    let active = true;
    const checkDbStatus = async () => {
      if (dbCheckInFlight.current) return;
      dbCheckInFlight.current = true;
      try {
        const response = await audio2Api.dbStatus();
        const status = response.data?.status;
        if (!active) return;
        if (status === 'online' || status === 'offline') {
          setDbStatus(status);
        } else {
          setDbStatus('unknown');
        }
        setDbError(response.data?.last_error || null);
      } catch (err) {
        if (!active) return;
        setDbStatus('offline');
        setDbError('No se pudo conectar con la API');
      } finally {
        dbCheckInFlight.current = false;
      }
    };
    checkDbStatus();
    return () => {
      active = false;
    };
  }, []);

  const handleLogin = async () => {
    if (!formData.email.trim() || !formData.password.trim()) {
      setError('Introduce email y contraseña');
      return;
    }
    if (formData.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return;
    }

    const loginResp = await audio2Api.login({
      email: formData.email.trim(),
      password: formData.password
    });

    const token = loginResp.data?.access_token;
    if (token) {
      setToken(token);
      setAuthenticated(true);
      setUserEmail(formData.email.trim());
      try {
        const profile = await audio2Api.getCurrentUser();
        setUserId(profile.data?.id ?? null);
      } catch (profileErr) {
        console.error('Failed to fetch current user', profileErr);
        setUserId(null);
      }
      setSuccess(true);
      setTimeout(() => navigate('/'), 300);
    } else {
      throw new Error('No se recibió token');
    }
  };

  const handleSignup = async () => {
    // Basic validation
    if (!formData.email.trim() || !formData.password.trim()) {
      setError('Todos los campos son obligatorios');
      return;
    }
    if (formData.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    // Create or update the first user (idempotent)
    await audio2Api.createFirstUser({
      name: formData.email.split('@')[0] || 'Usuario',
      email: formData.email.trim(),
      password: formData.password
    });

    // Auto-login right after creation
    await handleLogin();
  };

  const handleRecovery = async () => {
    if (!formData.email.trim() || !formData.password.trim() || !formData.recoveryCode.trim()) {
      setError('Introduce email, nueva contraseña y código de recuperación');
      return;
    }
    if (formData.password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    await audio2Api.resetPassword({
      email: formData.email.trim(),
      recovery_code: formData.recoveryCode.trim(),
      new_password: formData.password
    });
    setSuccess(true);
    setTimeout(() => {
      setSuccess(false);
      switchMode('login');
      setFormData(prev => ({
        ...prev,
        password: '',
        confirmPassword: '',
        recoveryCode: ''
      }));
    }, 700);
  };

  const handleLookup = async () => {
    if (!formData.email.trim() || !formData.recoveryCode.trim()) {
      setError('Introduce email y código de recuperación');
      return;
    }
    setError('');
    try {
      const response = await audio2Api.accountLookup({
        email: formData.email.trim(),
        recovery_code: formData.recoveryCode.trim()
      });
      const username = response.data?.username || 'Sin usuario';
      setLookupResult(`Usuario: ${username}`);
    } catch (err) {
      console.error('Error en lookup:', err);
      const msg =
        err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? (err.response.data as { detail: string }).detail
          : err instanceof Error
            ? err.message
            : 'No se pudo comprobar el usuario.';
      setError(msg);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setLookupResult(null);

    try {
      if (mode === 'login') {
        await handleLogin();
      } else if (mode === 'signup') {
        await handleSignup();
      } else {
        await handleRecovery();
      }
    } catch (err) {
      console.error('Error en autenticación:', err);
      const msg =
        err && typeof err === 'object' && 'response' in err && err.response && typeof err.response === 'object' && 'data' in err.response && err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? (err.response.data as { detail: string }).detail
          : err instanceof Error
            ? err.message
            : 'Error de autenticación. Revisa la consola.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setLookupResult(null);
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#f8fafc',
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '12px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        padding: '40px',
        width: '100%',
        maxWidth: '400px'
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            fontSize: '32px',
            marginBottom: '8px'
          }}>🎵</div>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '4px' }}>
            Audio2
          </h1>
          <p style={{ color: '#6b7280', fontSize: '14px' }}>
            Inicia sesión o crea el primer usuario administrador
          </p>
        </div>

        {/* Mode switch */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <Button
            type="button"
            variant={mode === 'login' ? 'default' : 'outline'}
            onClick={() => switchMode('login')}
            style={{ flex: 1, fontSize: 13 }}
          >
            Iniciar sesión
          </Button>
          <Button
            type="button"
            variant={mode === 'signup' ? 'default' : 'outline'}
            onClick={() => switchMode('signup')}
            style={{ flex: 1, fontSize: 13 }}
          >
            Crear usuario
          </Button>
          <Button
            type="button"
            variant={mode === 'recover' ? 'default' : 'outline'}
            onClick={() => switchMode('recover')}
            style={{ flex: 1, fontSize: 13 }}
          >
            Recuperar
          </Button>
        </div>

        {/* Success Message */}
        {success && (
          <div style={{
            padding: '16px',
            backgroundColor: '#dcfce7',
            borderRadius: '8px',
            border: '1px solid #bbf7d0',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <CheckCircle className="h-5 w-5 text-green-600" />
            <div>
              <p style={{ fontWeight: '500', color: '#166534', margin: 0 }}>
                ✅ ¡Listo!
              </p>
              {mode === 'recover' ? (
                <p style={{ fontSize: '14px', color: '#166534', margin: '4px 0 0 0' }}>
                  Contraseña actualizada. Ya puedes iniciar sesión.
                </p>
              ) : (
                <p style={{ fontSize: '14px', color: '#166534', margin: '4px 0 0 0' }}>
                  Sesión iniciada. Redirigiendo al dashboard...
                </p>
              )}
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div style={{
            padding: '16px',
            backgroundColor: '#fef2f2',
            borderRadius: '8px',
            border: '1px solid #fecaca',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <AlertCircle className="h-5 w-5 text-red-600" />
            <p style={{ color: '#991b1b', margin: 0 }}>
              {error}
            </p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              fontSize: '14px',
              fontWeight: '500',
              color: '#374151',
              marginBottom: '6px'
            }}>
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              disabled={loading || success}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '16px',
                outline: 'none'
              }}
              placeholder="tu@email.com"
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              fontSize: '14px',
              fontWeight: '500',
              color: '#374151',
              marginBottom: '6px'
            }}>
              {mode === 'recover' ? 'Nueva contraseña' : 'Contraseña'}
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              disabled={loading || success}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '16px',
                outline: 'none'
              }}
              placeholder={mode === 'recover' ? 'Nueva contraseña (mínimo 8)' : 'Mínimo 8 caracteres'}
            />
          </div>

          {mode === 'recover' && (
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                fontSize: '14px',
                fontWeight: '500',
                color: '#374151',
                marginBottom: '6px'
              }}>
                Código de recuperación
              </label>
              <input
                type="password"
                value={formData.recoveryCode}
                onChange={(e) => handleInputChange('recoveryCode', e.target.value)}
                disabled={loading || success}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '16px',
                  outline: 'none'
                }}
                placeholder="Código configurado en .env"
              />
              <button
                type="button"
                onClick={handleLookup}
                disabled={loading || success}
                style={{
                  marginTop: '10px',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid #d1d5db',
                  backgroundColor: '#f8fafc',
                  fontSize: '13px',
                  cursor: loading || success ? 'not-allowed' : 'pointer'
                }}
              >
                Comprobar usuario
              </button>
              {lookupResult && (
                <p style={{ marginTop: '8px', fontSize: '13px', color: '#0f766e' }}>
                  {lookupResult}
                </p>
              )}
            </div>
          )}

          {(mode === 'signup' || mode === 'recover') && (
            <div style={{ marginBottom: '32px' }}>
              <label style={{
                display: 'block',
                fontSize: '14px',
                fontWeight: '500',
                color: '#374151',
                marginBottom: '6px'
              }}>
                Confirmar contraseña
              </label>
              <input
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                disabled={loading || success}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '16px',
                  outline: 'none'
                }}
                placeholder="Repite la contraseña"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading || success}
            style={{
              width: '100%',
              padding: '12px 24px',
              backgroundColor: success ? '#10b981' : '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '500',
              cursor: loading || success ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.8 : 1
            }}
          >
            {success ? '✅ Listo' :
             loading ? (mode === 'login' ? '⏳ Entrando...' : mode === 'signup' ? '⏳ Creando cuenta...' : '⏳ Actualizando contraseña...') :
             mode === 'login' ? 'Iniciar sesión' : mode === 'signup' ? 'Crear cuenta' : 'Restablecer contraseña'}
          </button>
        </form>

        {/* Info */}
        <div style={{
          marginTop: '24px',
          padding: '16px',
          backgroundColor: '#f0f9ff',
          borderRadius: '8px',
          border: '1px solid #bae6fd'
        }}>
          <p style={{ fontSize: '14px', color: '#374151', margin: 0, lineHeight: '1.5' }}>
            {mode === 'login'
              ? 'Introduce tu email y contraseña. No necesitas nombre de usuario.'
              : mode === 'signup'
                ? 'Crea tu usuario administrador (solo la primera vez).'
                : 'Introduce email, nueva contraseña y el código configurado en AUTH_RECOVERY_CODE.'}
          </p>
        </div>

        {/* API Status */}
        <div style={{
          marginTop: '16px',
          padding: '12px',
          backgroundColor: '#f8fafc',
          borderRadius: '6px',
          border: '1px solid #e2e8f0',
          fontSize: '12px',
          color: '#6b7280',
          textAlign: 'center'
        }}>
          <div>📡 Conectado a API: http://localhost:8000</div>
          <div style={{
            marginTop: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor:
                dbStatus === 'online'
                  ? '#16a34a'
                  : dbStatus === 'offline'
                    ? '#dc2626'
                    : '#94a3b8'
            }} />
            <span>
              Base de datos:
              {dbStatus === 'online' ? ' online' : dbStatus === 'offline' ? ' offline' : ' verificando...'}
            </span>
          </div>
          {dbStatus === 'offline' && dbError && (
            <div style={{ marginTop: '6px', color: '#b91c1c' }}>
              {dbError}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
