import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/auth';
import { tokenStore, UNAUTHORIZED_EVENT } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState('');
  // True from the moment a session ends (sign-out, expiry, a stored token the
  // server refuses) until the sign-in page has been shown.  The site root uses
  // it to send that visitor to the sign-in page instead of the product page.
  const [sessionEnded, setSessionEnded] = useState(false);

  // Restore the session (if any) by asking the backend who the token belongs to.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (!tokenStore.get()) {
        setLoading(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        tokenStore.clear();
        if (!cancelled) setSessionEnded(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  // Any API call that returns 401 ends the session.
  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setSessionEnded(true);
      setSessionMessage('Your session has ended. Please sign in again.');
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password);
    tokenStore.set(data.access_token);
    setSessionMessage('');
    setSessionEnded(false);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout(); // revokes the token on the server
    } catch {
      /* the local session is cleared regardless */
    }
    tokenStore.clear();
    setSessionEnded(true);
    setUser(null);
    setSessionMessage('');
  }, []);

  const acknowledgeSessionEnd = useCallback(() => setSessionEnded(false), []);

  const value = useMemo(() => {
    const permissions = new Set(user?.permissions || []);
    return {
      user,
      loading,
      sessionMessage,
      sessionEnded,
      acknowledgeSessionEnd,
      login,
      logout,
      isAdmin: user?.role === 'admin',
      // UI hint only - every permission is enforced again by the backend.
      can: (permission) => permissions.has(permission),
    };
  }, [user, loading, sessionMessage, sessionEnded, acknowledgeSessionEnd, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
