import React from 'react';
import { FlaskConical, Radio } from 'lucide-react';
import { formatTime } from '../utils/format';

/** Marks a value as live telemetry read from Prometheus. */
export function LiveTag({ at, label = 'Live · Prometheus' }) {
  return (
    <span className="tag" title="Measured values queried from Prometheus by the backend">
      <Radio size={11} className="text-ok" aria-hidden="true" />
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
