import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, RefreshCw } from 'lucide-react';

export function PageHeader({ title, subtitle, back, actions, onRefresh, refreshing, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {back ? (
          <Link to={back.to} className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-content">
            <ChevronLeft size={14} aria-hidden="true" /> {back.label}
          </Link>
        ) : null}
        <h1 className="text-xl text-content">{title}</h1>
        {subtitle ? <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p> : null}
        {children}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {actions}
        {onRefresh ? (
          <button type="button" className="btn-secondary btn-sm" onClick={onRefresh} disabled={refreshing} aria-label="Refresh data">
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" /> Refresh
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default PageHeader;
