import React from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';

export function Spinner({ size = 18, className = '' }) {
  return <Loader2 size={size} className={`animate-spin ${className}`} aria-hidden="true" />;
}

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-2 py-10 text-muted ${className}`}>
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title = 'Nothing to show', description, icon: Icon = Inbox, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 px-4 py-10 text-center ${className}`}>
      <Icon size={28} className="text-muted/70" aria-hidden="true" />
      <p className="font-medium text-content">{title}</p>
      {description ? <p className="max-w-md text-sm text-muted">{description}</p> : null}
      {action || null}
    </div>
  );
}

export function ErrorState({ message, onRetry, className = '' }) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center gap-3 px-4 py-10 text-center ${className}`}>
      <AlertTriangle size={28} className="text-danger" aria-hidden="true" />
      <p className="max-w-md text-sm text-content">{message || 'The data could not be loaded.'}</p>
      {onRetry ? (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={14} aria-hidden="true" /> Retry
        </button>
      ) : null}
    </div>
  );
}

/** Slim banner used when a refresh fails but older data is still on screen. */
export function InlineError({ message, onRetry, className = '' }) {
  if (!message) return null;
  return (
    <div role="alert" className={`flex flex-wrap items-center gap-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-content ${className}`}>
      <AlertTriangle size={16} className="shrink-0 text-danger" aria-hidden="true" />
      <span className="flex-1">{message}</span>
      {onRetry ? (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={14} aria-hidden="true" /> Retry
        </button>
      ) : null}
    </div>
  );
}

export function Notice({ tone = 'info', icon: Icon, children, className = '' }) {
  const tones = {
    info: 'border-info/30 bg-info/10',
    warning: 'border-warn/40 bg-warn/10',
    success: 'border-ok/30 bg-ok/10',
    neutral: 'border-line bg-raised/60',
  };
  return (
    <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm text-content ${tones[tone] || tones.info} ${className}`}>
      {Icon ? <Icon size={16} className="mt-0.5 shrink-0 text-muted" aria-hidden="true" /> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
