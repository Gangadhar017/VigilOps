import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';

const VALUE_TONES = {
  default: 'text-content',
  danger: 'text-danger',
  warning: 'text-warn',
  success: 'text-ok',
  brand: 'text-brand',
};
// The coloured rule along the top edge carries the state at a glance.
const RAIL_TONES = {
  default: 'bg-line',
  danger: 'bg-danger',
  warning: 'bg-warn',
  success: 'bg-ok',
  brand: 'bg-brand',
};

/**
 * A single headline figure. `value` may be null/undefined, in which case an
 * explicit "Unavailable" state is rendered - the UI never substitutes a number.
 */
export function MetricCard({ label, value, hint, icon: Icon, tone = 'default', to, unavailableReason, footer }) {
  const missing = value === null || value === undefined;
  const body = (
    <div className="card group relative h-full overflow-hidden px-4 pb-4 pt-[18px] transition-colors hover:border-content/25">
      <span className={`absolute inset-x-0 top-0 h-[2px] ${missing ? RAIL_TONES.default : RAIL_TONES[tone] || RAIL_TONES.default}`} aria-hidden="true" />
      <div className="flex items-start justify-between gap-2">
        <p className="eyebrow">{label}</p>
        {to ? (
          <ArrowUpRight size={14} className="shrink-0 text-muted/50 transition-colors group-hover:text-content" aria-hidden="true" />
        ) : Icon ? (
          <Icon size={15} className="shrink-0 text-muted/60" aria-hidden="true" />
        ) : null}
      </div>
      {missing ? (
        <p className="mt-3 text-lg font-semibold text-muted" title={unavailableReason || undefined}>
          Unavailable
        </p>
      ) : (
        <p className={`stat mt-3 ${VALUE_TONES[tone] || VALUE_TONES.default}`}>{value}</p>
      )}
      {missing && unavailableReason ? <p className="mt-2 text-xs text-muted">{unavailableReason}</p> : null}
      {!missing && hint ? <p className="mt-2.5 text-xs leading-4 text-muted">{hint}</p> : null}
      {footer ? <div className="mt-3">{footer}</div> : null}
    </div>
  );
  return to ? (
    <Link to={to} className="block h-full rounded-lg">
      {body}
    </Link>
  ) : (
    body
  );
}

export default MetricCard;
