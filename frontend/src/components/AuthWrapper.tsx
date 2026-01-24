import { useEffect } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useApiStore } from '@/store/useApiStore';
import { LoginPage } from '@/pages/LoginPage';

type JwtPayload = { exp?: number };

const decodeJwtPayload = (token: string): JwtPayload | null => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + (4 - (base64.length % 4)) % 4, '=');
    const json = atob(padded);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
};

const getTokenExpiryMs = (token: string): number | null => {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return null;
  return payload.exp * 1000;
};

export function AuthWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token, logout } = useApiStore();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (isAuthenticated && location.pathname === '/login') {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, location.pathname, navigate]);

  useEffect(() => {
    if (!token) return;
    const expiryMs = getTokenExpiryMs(token);
    if (!expiryMs) {
      logout();
      return;
    }
    const remainingMs = expiryMs - Date.now();
    if (remainingMs <= 0) {
      logout();
      return;
    }
    const timeout = setTimeout(() => logout(), remainingMs);
    return () => clearTimeout(timeout);
  }, [logout, token]);

  if (!isAuthenticated) {
    if (location.pathname !== '/login') {
      return <Navigate to="/login" replace />;
    }
    return (
      <div className="flex h-screen bg-background">
        <main className="flex-1 flex items-center justify-center p-6">
          <LoginPage />
        </main>
      </div>
    );
  }

  return <>{children}</>;
}
