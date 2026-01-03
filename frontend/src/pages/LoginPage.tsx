import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { audio2Api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { AlertCircle, CheckCircle } from 'lucide-react';
import { useApiStore } from '@/store/useApiStore';

export function LoginPage() {
  const navigate = useNavigate();
  const { setToken, setAuthenticated, setUserEmail, setUserId } = useApiStore();

  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await handleLogin();
      } else {
        await handleSignup();
      }
    } catch (err: any) {
      console.error('Error en autenticación:', err);
      const msg = err.response?.data?.detail || 'Error de autenticación. Revisa la consola.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
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
            onClick={() => setMode('login')}
            style={{ flex: 1 }}
          >
            Iniciar sesión
          </Button>
          <Button
            type="button"
            variant={mode === 'signup' ? 'default' : 'outline'}
            onClick={() => setMode('signup')}
            style={{ flex: 1 }}
          >
            Crear usuario
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
                ¡Usuario creado exitosamente!
              </p>
              <p style={{ fontSize: '14px', color: '#166534', margin: '4px 0 0 0' }}>
                Redirigiendo al dashboard...
              </p>
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
              Contraseña
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
              placeholder="Mínimo 8 caracteres"
            />
          </div>

          {mode === 'signup' && (
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
             loading ? (mode === 'login' ? '⏳ Entrando...' : '⏳ Creando cuenta...') :
             mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}
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
              ? 'Introduce tu email y contraseña para entrar.'
              : 'Crea tu usuario administrador (solo la primera vez).'}
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
          📡 Conectado a API: http://localhost:8000
        </div>
      </div>
    </div>
  );
}
