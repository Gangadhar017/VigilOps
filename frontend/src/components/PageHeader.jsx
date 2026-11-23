import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, RefreshCw } from 'lucide-react';

export function PageHeader({ title, subtitle, back, actions, onRefresh, refreshing, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-line pb-5">
      <div className="min-w-0">
        {back ? (
          <Link
            to={back.to}
            className="mb-2 inline-flex items-center gap-1 font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted transition-colors hover:text-content"
          >
            <ChevronLeft size={13} aria-hidden="true" /> {back.label}
          </Link>
        ) : null}
        <h1 className="text-[22px] leading-7 text-content">{title}</h1>
        {subtitle ? <p className="mt-1.5 max-w-3xl text-[13px] leading-5 text-muted">{subtitle}</p> : null}
        {children}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {actions}
        {onRefresh ? (
          <button type="button" className="btn-secondary btn-sm" onClick={onRefresh} disabled={refreshing} aria-label="Refresh data">
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" /> Refresh
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default PageHeader;
