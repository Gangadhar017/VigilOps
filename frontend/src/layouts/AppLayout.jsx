import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { monitoringApi } from '../api/monitoring';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { VigilAIWidget } from '../features/vigilai/VigilAIWidget';
import { useApi } from '../hooks/useApi';

/** Shared shell: navigation, header, page content and the floating VigilAI widget. */
export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  // One light request drives the navigation badges and the demo-mode indicator.
  const { data: summary } = useApi(() => monitoringApi.dashboard(), [], { interval: 20000 });

  const badges = {
    '/incidents': summary?.incidents?.active || 0,
    '/remediation': summary?.remediation?.pending_approval || 0,
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} badges={badges} />
      <div className="flex min-w-0 flex-1 flex-col overflow-x-clip">
        <Header
          onMenu={() => setMenuOpen(true)}
          demoMode={Boolean(summary?.platform?.demo_controls_enabled)}
          environment={summary?.platform?.backend?.environment}
        />
        <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 pb-24 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
      <VigilAIWidget />
    </div>
  );
}

export default AppLayout;
