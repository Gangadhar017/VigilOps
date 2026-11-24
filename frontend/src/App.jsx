import React from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { LoadingState } from './components/States';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { AppLayout } from './layouts/AppLayout';
import AuditLogs from './pages/AuditLogs';
import Dashboard from './pages/Dashboard';
import FindingDetail from './pages/FindingDetail';
import Findings from './pages/Findings';
import Help from './pages/Help';
import IncidentDetail from './pages/IncidentDetail';
import Incidents from './pages/Incidents';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Monitoring from './pages/Monitoring';
import Remediation from './pages/Remediation';
import RemediationDetail from './pages/RemediationDetail';
import Settings from './pages/Settings';

/**
 * The console. Its pages require a signed-in user; the backend enforces the same.
 *
 * A visitor who is not signed in sees the public product page at the site root
 * and is sent to the sign-in page from everywhere else. A session that has just
 * ended (sign-out, expiry, a stored token the server no longer accepts) goes to
 * the sign-in page from the root as well, so that the reason can be shown there.
 */
function Console() {
  const { user, loading, sessionEnded } = useAuth();
  const location = useLocation();
  if (loading) return <LoadingState label="Checking your session…" className="min-h-screen" />;
  if (user) return <AppLayout />;
  if (location.pathname === '/' && !sessionEnded) return <Landing />;
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* The product page, also for someone who is signed in. */}
      <Route path="/welcome" element={<Landing />} />
      <Route element={<Console />}>
        <Route index element={<Dashboard />} />
        <Route path="monitoring" element={<Monitoring />} />
        <Route path="incidents" element={<Incidents />} />
        <Route path="incidents/:id" element={<IncidentDetail />} />
        <Route path="findings" element={<Findings />} />
        <Route path="findings/:id" element={<FindingDetail />} />
        <Route path="remediation" element={<Remediation />} />
        <Route path="remediation/:id" element={<RemediationDetail />} />
        <Route path="audit" element={<AuditLogs />} />
        <Route path="help" element={<Help />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
