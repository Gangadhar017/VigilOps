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
import Login from './pages/Login';
import Monitoring from './pages/Monitoring';
import Remediation from './pages/Remediation';
import RemediationDetail from './pages/RemediationDetail';
import Settings from './pages/Settings';

/** Routes below this guard require a signed-in user. The backend enforces the same. */
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <LoadingState label="Checking your session…" className="min-h-screen" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return children;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
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
