import React from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';

export function Spinner({ size = 18, className = '' }) {
  return <Loader2 size={size} className={`animate-spin ${className}`} aria-hidden="true" />;
}

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-2.5 py-10 text-[13px] text-muted ${className}`}>
      <Spinner size={15} />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title = 'Nothing to show', description, icon: Icon = Inbox, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 px-4 py-10 text-center ${className}`}>
      <span className="mb-1 flex h-9 w-9 items-center justify-center rounded-md border border-line bg-raised/60 text-muted">
        <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
      </span>
      <p className="text-[13px] font-medium text-content">{title}</p>
      {description ? <p className="max-w-md text-[13px] leading-5 text-muted">{description}</p> : null}
      {action || null}
    </div>
  );
}

export function ErrorState({ message, onRetry, className = '' }) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center gap-3 px-4 py-10 text-center ${className}`}>
      <span className="flex h-9 w-9 items-center justify-center rounded-md border border-danger/35 bg-danger/10 text-danger">
        <AlertTriangle size={16} strokeWidth={1.75} aria-hidden="true" />
      </span>
      <p className="max-w-md text-[13px] leading-5 text-content">{message || 'The data could not be loaded.'}</p>
      {onRetry ? (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={13} aria-hidden="true" /> Retry
        </button>
      ) : null}
    </div>
  );
}

/** Slim banner used when a refresh fails but older data is still on screen. */
export function InlineError({ message, onRetry, className = '' }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={`flex flex-wrap items-center gap-3 rounded-md border border-l-2 border-danger/30 border-l-danger bg-danger/[0.07] px-3 py-2 text-[13px] text-content ${className}`}
    >
      <AlertTriangle size={15} className="shrink-0 text-danger" aria-hidden="true" />
      <span className="flex-1">{message}</span>
      {onRetry ? (
        <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={13} aria-hidden="true" /> Retry
        </button>
      ) : null}
    </div>
  );
}

export function Notice({ tone = 'info', icon: Icon, children, className = '' }) {
  // A coloured rule on the left edge carries the tone; the fill stays quiet.
  const tones = {
    info: 'border-info/25 border-l-info bg-info/[0.07]',
    warning: 'border-warn/30 border-l-warn bg-warn/[0.08]',
    success: 'border-ok/25 border-l-ok bg-ok/[0.07]',
    neutral: 'border-line border-l-muted/60 bg-raised/50',
  };
  const iconTones = { info: 'text-info', warning: 'text-warn', success: 'text-ok', neutral: 'text-muted' };
  return (
    <div className={`flex items-start gap-2.5 rounded-md border border-l-2 px-3 py-2.5 text-[13px] leading-5 text-content ${tones[tone] || tones.info} ${className}`}>
      {Icon ? <Icon size={15} className={`mt-0.5 shrink-0 ${iconTones[tone] || iconTones.info}`} aria-hidden="true" /> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
