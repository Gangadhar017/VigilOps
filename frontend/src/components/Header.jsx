import React from 'react';
import { FlaskConical, Menu, Moon, Sun } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { StatusBadge } from './StatusBadge';

export function Header({ onMenu, demoMode, environment }) {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-2">
        <button type="button" className="btn-ghost btn-sm lg:hidden" onClick={onMenu} aria-label="Open navigation">
          <Menu size={18} />
        </button>
        {environment ? <span className="tag hidden uppercase sm:inline-flex">{environment}</span> : null}
        {demoMode ? (
          <span className="badge border-warn/40 bg-warn/10 text-warn" title="Demonstration controls are enabled on this server. Incidents caused by injected faults are labelled.">
            <FlaskConical size={11} aria-hidden="true" />
            <span className="hidden sm:inline">Demo controls enabled</span>
            <span className="sm:hidden">Demo mode</span>
          </span>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <StatusBadge status={user?.role} label={user?.role === 'admin' ? 'Administrator' : 'Operator'} />
        <button
          type="button"
          className="btn-ghost btn-sm"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </header>
  );
}

export default Header;
