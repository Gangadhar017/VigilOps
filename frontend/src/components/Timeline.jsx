import React from 'react';
import { formatDateTime, titleCase, utcTitle } from '../utils/format';
import { StatusBadge } from './StatusBadge';

/**
 * Vertical timeline.
 * items: [{ id, at, title, actor, details, outcome?, from?, to? }]
 */
export function Timeline({ items, emptyLabel = 'No events recorded yet.' }) {
  if (!items?.length) return <p className="text-[13px] text-muted">{emptyLabel}</p>;
  return (
    <ol className="relative ml-1 space-y-5 border-l border-line pl-5">
      {items.map((item, index) => (
        <li key={item.id ?? index} className="relative">
          <span
            className="absolute -left-[24.5px] top-[5px] h-2 w-2 rounded-[2px] bg-brand ring-4 ring-surface"
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[13px] font-medium text-content">{item.title}</span>
            {item.from && item.to ? (
              <span className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-muted">
                {titleCase(item.from)} → {titleCase(item.to)}
              </span>
            ) : null}
            {item.outcome && item.outcome !== 'SUCCESS' ? <StatusBadge status={item.outcome} /> : null}
          </div>
          <p className="mt-0.5 font-mono text-[11px] text-muted" title={utcTitle(item.at)}>
            {formatDateTime(item.at)}
            {item.actor ? ` · ${item.actor}` : ''}
          </p>
          {item.details ? <p className="mt-1.5 whitespace-pre-wrap break-words text-[13px] leading-5 text-content/90">{item.details}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export default Timeline;
