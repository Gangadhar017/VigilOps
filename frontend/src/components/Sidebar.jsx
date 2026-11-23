import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity, AlertTriangle, Bot, ClipboardList, LayoutDashboard, LogOut, Settings, ShieldAlert, Wrench, X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true, group: 'Operate' },
  { to: '/monitoring', label: 'Monitoring', icon: Activity, group: 'Operate' },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle, group: 'Operate' },
  { to: '/findings', label: 'Security Findings', icon: ShieldAlert, group: 'Secure' },
  { to: '/remediation', label: 'Remediation', icon: Wrench, group: 'Secure' },
  { to: '/audit', label: 'Audit Logs', icon: ClipboardList, group: 'Govern' },
  { to: '/help', label: 'VigilAI / Help', icon: Bot, group: 'Support' },
  { to: '/settings', label: 'Settings', icon: Settings, group: 'Support' },
];

const GROUPS = NAV_ITEMS.reduce((groups, item) => {
  const last = groups[groups.length - 1];
  if (last && last.name === item.group) last.items.push(item);
  else groups.push({ name: item.group, items: [item] });
  return groups;
}, []);

/**
 * Product lockup. `onChrome` is for the dark navigation chrome, where the
 * colours do not follow the theme.
 */
export function Brand({ onChrome = false }) {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="h-8 w-8 rounded-[7px] ring-1 ring-white/10" />
      <div className="leading-none">
        <p className={`text-[15px] font-semibold tracking-tight ${onChrome ? 'text-chrome-text' : 'text-content'}`}>VigilOps</p>
        <p className={`mt-1 font-mono text-[9.5px] uppercase tracking-[0.14em] ${onChrome ? 'text-chrome-muted' : 'text-muted'}`}>
          Secure Cloud Operations
        </p>
      </div>
    </div>
  );
}

function initials(user) {
  const source = (user?.full_name || user?.email || '?').trim();
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || '?';
}

export function Sidebar({ open, onClose, badges = {} }) {
  const { user, logout } = useAuth();
  return (
    <>
      {open ? <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={onClose} aria-hidden="true" /> : null}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-chrome-line bg-chrome text-chrome-text transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="Primary"
      >
        <div className="flex h-[52px] shrink-0 items-center justify-between border-b border-chrome-line px-4">
          <Brand onChrome />
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-md text-chrome-muted hover:bg-white/5 hover:text-chrome-text lg:hidden"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-3">
          {GROUPS.map((group) => (
            <div key={group.name} className="mb-4 last:mb-0">
              <p className="mb-1.5 px-2.5 font-mono text-[9.5px] font-medium uppercase tracking-[0.16em] text-chrome-muted/70" aria-hidden="true">
                {group.name}
              </p>
              <div className="space-y-px">
                {group.items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `relative flex items-center justify-between gap-3 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition-colors focus-visible:ring-offset-chrome ${
                        isActive ? 'bg-white/[0.07] text-chrome-text' : 'text-chrome-muted hover:bg-white/[0.04] hover:text-chrome-text'
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive ? <span className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-accent" aria-hidden="true" /> : null}
                        <span className="flex items-center gap-2.5">
                          <Icon size={16} strokeWidth={1.75} className={isActive ? 'text-accent' : ''} aria-hidden="true" />
                          {label}
                        </span>
                        {badges[to] ? (
                          <span
                            className="rounded bg-[#ff6363]/15 px-1.5 py-px font-mono text-[10.5px] font-medium tabular-nums text-[#ff8f8f]"
                            aria-label={`${badges[to]} need attention`}
                          >
                            {badges[to]}
                          </span>
                        ) : null}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-chrome-line p-3">
          <div className="mb-2.5 flex items-center gap-2.5 px-0.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-white/[0.07] font-mono text-[11px] font-medium text-chrome-text" aria-hidden="true">
              {initials(user)}
            </span>
            <div className="min-w-0 leading-tight">
              <p className="truncate text-[13px] font-medium text-chrome-text">{user?.full_name || user?.email}</p>
              <p className="truncate text-[11px] text-chrome-muted">
                {user?.email} · {user?.role === 'admin' ? 'Administrator' : 'Operator'}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn h-8 w-full border border-chrome-line text-xs text-chrome-text hover:bg-white/[0.05] focus-visible:ring-offset-chrome"
            onClick={logout}
          >
            <LogOut size={14} aria-hidden="true" /> Logout
          </button>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
