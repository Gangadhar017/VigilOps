import React from 'react';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from 'lucide-react';
import { EmptyState, ErrorState, LoadingState } from './States';

/**
 * Server-driven table: sorting, pagination and the loading / empty / error
 * states are handled here so every list page behaves the same way.
 *
 * columns: [{ key, header, sortable?, sortKey?, render?(row), className? }]
 */
export function DataTable({
  columns,
  rows,
  loading,
  error,
  onRetry,
  sort,
  order,
  onSort,
  onRowClick,
  rowKey = (row) => row.id,
  emptyTitle = 'No results',
  emptyDescription,
  caption,
}) {
  if (loading && !rows) return <LoadingState />;
  if (error && !rows) return <ErrorState message={error} onRetry={onRetry} />;
  if (!rows || rows.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />;

  return (
    <div className="table-wrap">
      <table className="table">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => {
              const sortKey = column.sortKey || column.key;
              const active = sort === sortKey;
              const ariaSort = !column.sortable ? undefined : active ? (order === 'asc' ? 'ascending' : 'descending') : 'none';
              return (
                <th key={column.key} scope="col" aria-sort={ariaSort} className={column.className || ''}>
                  {column.sortable && onSort ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 uppercase tracking-[0.1em] transition-colors hover:text-content"
                      onClick={() => onSort(sortKey)}
                    >
                      {column.header}
                      {active ? (
                        order === 'asc' ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" />
                      ) : (
                        <ChevronsUpDown size={12} className="opacity-50" aria-hidden="true" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? 'row-link' : ''}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === 'Enter') onRowClick(row);
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <td key={column.key} className={column.className || ''}>
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPageChange }) {
  if (!total) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 font-mono text-[11px] text-muted" aria-label="Pagination">
      <span className="tabular-nums">
        Showing {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-2">
        <button type="button" className="btn-secondary btn-sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          <ChevronLeft size={14} aria-hidden="true" /> Previous
        </button>
        <span className="tabular-nums">
          Page {page} of {pages}
        </span>
        <button type="button" className="btn-secondary btn-sm" onClick={() => onPageChange(page + 1)} disabled={page >= pages}>
          Next <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

/** Helper for pages: toggles direction when the same column is clicked again. */
export function nextSort(current, key, defaultOrder = 'asc') {
  if (current.sort === key) return { sort: key, order: current.order === 'asc' ? 'desc' : 'asc' };
  return { sort: key, order: defaultOrder };
}

export default DataTable;
