import React from 'react';
import { FlaskConical } from 'lucide-react';
import { formatTime } from '../utils/format';

/** Marks a value as live telemetry read from Prometheus. */
export function LiveTag({ at, label = 'Live · Prometheus' }) {
  return (
    <span className="tag" title="Measured values queried from Prometheus by the backend">
      <span className="relative mr-0.5 flex h-1.5 w-1.5" aria-hidden="true">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ok" />
      </span>
      {label}
      {at ? ` · ${formatTime(at)}` : ''}
    </span>
  );
}

/** Marks a record that exists because of a deliberately injected demo fault. */
export function SimulatedTag({ title }) {
  return (
    <span className="badge border-warn/40 bg-warn/10 text-warn" title={title || 'Triggered by a controlled demonstration fault'}>
      <FlaskConical size={11} aria-hidden="true" />
      Simulated fault
    </span>
  );
}
