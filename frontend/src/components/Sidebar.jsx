import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity, AlertTriangle, Bot, ClipboardList, LayoutDashboard, LogOut, Settings, ShieldAlert, Wrench, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/monitoring', label: 'Monitoring', icon: Activity },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { to: '/findings', label: 'Security Findings', icon: ShieldAlert },
  { to: '/remediation', label: 'Remediation', icon: Wrench },
  { to: '/audit', label: 'Audit Logs', icon: ClipboardList },
  { to: '/help', label: 'VigilAI / Help', icon: Bot },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="h-8 w-8" />
      <div className="leading-tight">
        <p className="text-base font-semibold text-content">VigilOps</p>
        <p className="text-[11px] text-muted">Secure Cloud Operations</p>
      </div>
    </div>
  );
}

export function Sidebar({ open, onClose, badges = {} }) {
  const { user, logout } = useAuth();
  return (
    <>
      {open ? <div className="fixed inset-0 z-30 bg-slate-950/50 lg:hidden" onClick={onClose} aria-hidden="true" /> : null}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface transition-transform lg:static lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Primary"
      >
        <div className="flex h-14 items-center justify-between border-b border-line px-4">
          <Brand />
          <button type="button" className="btn-ghost btn-sm lg:hidden" onClick={onClose} aria-label="Close navigation">
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-brand/15 text-brand' : 'text-muted hover:bg-raised hover:text-content'
                }`
              }
            >
              <span className="flex items-center gap-3">
                <Icon size={17} aria-hidden="true" />
                {label}
              </span>
              {badges[to] ? (
                <span className="rounded-full bg-danger/15 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-danger" aria-label={`${badges[to]} need attention`}>
                  {badges[to]}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          <div className="mb-2 px-1">
            <p className="truncate text-sm font-medium text-content">{user?.full_name || user?.email}</p>
            <p className="truncate text-xs text-muted">
              {user?.email} · {user?.role === 'admin' ? 'Administrator' : 'Operator'}
            </p>
          </div>
          <button type="button" className="btn-secondary w-full" onClick={logout}>
            <LogOut size={15} aria-hidden="true" /> Logout
          </button>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
