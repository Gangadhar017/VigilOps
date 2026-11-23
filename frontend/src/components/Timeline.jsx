import React from 'react';
import { formatDateTime, titleCase, utcTitle } from '../utils/format';
import { StatusBadge } from './StatusBadge';

/**
 * Vertical timeline.
 * items: [{ id, at, title, actor, details, outcome?, from?, to? }]
 */
export function Timeline({ items, emptyLabel = 'No events recorded yet.' }) {
  if (!items?.length) return <p className="text-sm text-muted">{emptyLabel}</p>;
  return (
    <ol className="relative space-y-4 border-l border-line pl-5">
      {items.map((item, index) => (
        <li key={item.id ?? index} className="relative">
          <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface bg-brand" aria-hidden="true" />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium text-content">{item.title}</span>
            {item.from && item.to ? (
              <span className="text-xs text-muted">
                {titleCase(item.from)} → {titleCase(item.to)}
              </span>
            ) : null}
            {item.outcome && item.outcome !== 'SUCCESS' ? <StatusBadge status={item.outcome} /> : null}
          </div>
          <p className="text-xs text-muted" title={utcTitle(item.at)}>
            {formatDateTime(item.at)}
            {item.actor ? ` · ${item.actor}` : ''}
          </p>
          {item.details ? <p className="mt-1 whitespace-pre-wrap break-words text-sm text-content">{item.details}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export default Timeline;
