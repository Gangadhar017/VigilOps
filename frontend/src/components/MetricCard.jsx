import React from 'react';
import { Link } from 'react-router-dom';

/**
 * A single headline figure. `value` may be null/undefined, in which case an
 * explicit "Unavailable" state is rendered - the UI never substitutes a number.
 */
export function MetricCard({ label, value, hint, icon: Icon, tone = 'default', to, unavailableReason, footer }) {
  const tones = {
    default: 'text-content',
    danger: 'text-danger',
    warning: 'text-warn',
    success: 'text-ok',
    brand: 'text-brand',
  };
  const missing = value === null || value === undefined;
  const body = (
    <div className="card h-full p-4 transition-colors hover:border-brand/40">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
        {Icon ? <Icon size={18} className="shrink-0 text-muted" aria-hidden="true" /> : null}
      </div>
      {missing ? (
        <p className="mt-2 text-lg font-semibold text-muted" title={unavailableReason || undefined}>
          Unavailable
        </p>
      ) : (
        <p className={`mt-2 text-2xl font-semibold tabular-nums ${tones[tone] || tones.default}`}>{value}</p>
      )}
      {missing && unavailableReason ? <p className="mt-1 text-xs text-muted">{unavailableReason}</p> : null}
      {!missing && hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
      {footer ? <div className="mt-3">{footer}</div> : null}
    </div>
  );
  return to ? (
    <Link to={to} className="block h-full rounded-xl">
      {body}
    </Link>
  ) : (
    body
  );
}

export default MetricCard;
