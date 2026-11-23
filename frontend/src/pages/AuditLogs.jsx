import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Info, X } from 'lucide-react';
import { auditApi } from '../api/audit';
import { DataTable, Pagination, nextSort } from '../components/DataTable';
import { FilterBar, SearchInput, SelectFilter } from '../components/Filters';
import { Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { InlineError, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { useApi, useDebounced } from '../hooks/useApi';
import { formatDateTime, humanAction, utcTitle } from '../utils/format';

const PAGE_SIZE = 25;
const toIso = (localValue, endOfDay = false) => {
  if (!localValue) return undefined;
  const date = new Date(`${localValue}T${endOfDay ? '23:59:59' : '00:00:00'}`);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
};

export default function AuditLogs() {
  const [params, setParams] = useSearchParams();
  const correlationId = params.get('correlation_id') || '';
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [outcome, setOutcome] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sorting, setSorting] = useState({ sort: 'created_at', order: 'desc' });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const q = useDebounced(search);

  const meta = useApi(() => auditApi.meta(), []);
  const { data, error, loading, refreshing, reload } = useApi(
    () =>
      auditApi.list({
        q,
        category,
        outcome,
        correlation_id: correlationId,
        date_from: toIso(dateFrom),
        date_to: toIso(dateTo, true),
        sort: sorting.sort,
        order: sorting.order,
        page,
        page_size: PAGE_SIZE,
      }),
    [q, category, outcome, correlationId, dateFrom, dateTo, sorting.sort, sorting.order, page],
  );

  const change = (setter) => (value) => {
    setter(value);
    setPage(1);
  };
  const filtered = q || category || outcome || dateFrom || dateTo || correlationId;

  const columns = [
    {
      key: 'created_at',
      header: 'Time',
      sortable: true,
      render: (row) => (
        <span className="whitespace-nowrap text-xs" title={utcTitle(row.created_at)}>
          {formatDateTime(row.created_at)}
        </span>
      ),
    },
    { key: 'actor', header: 'Actor', sortable: true, render: (row) => <span className="text-xs">{row.actor_label}</span> },
    { key: 'action', header: 'Action', sortable: true, render: (row) => <span className="font-medium">{humanAction(row.action)}</span> },
    {
      key: 'entity_type',
      header: 'Resource',
      sortable: true,
      render: (row) => (
        <span className="text-xs">
          {row.entity_type}
          {row.entity_id ? ` #${row.entity_id}` : ''}
        </span>
      ),
    },
    { key: 'outcome', header: 'Outcome', sortable: true, render: (row) => <StatusBadge status={row.outcome} /> },
    {
      key: 'correlation_id',
      header: 'Correlation',
      render: (row) => <span className="font-mono text-[11px] text-muted">{row.correlation_id ? `${row.correlation_id.slice(0, 8)}…` : '—'}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Audit Logs"
        subtitle="Append-only record of important events. Audit history cannot be edited or deleted through the application."
        onRefresh={reload}
        refreshing={refreshing}
      />
      {meta.data ? (
        <Notice icon={Info} tone="neutral" className="mb-4">
          {meta.data.visibility_note}
        </Notice>
      ) : null}
      {correlationId ? (
        <Notice tone="info" className="mb-4">
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span>
              Showing events of one workflow (correlation ID <code>{correlationId}</code>).
            </span>
            <button type="button" className="btn-secondary btn-sm" onClick={() => setParams({})}>
              <X size={13} aria-hidden="true" /> Clear
            </button>
          </span>
        </Notice>
      ) : null}

      <div className="card">
        <FilterBar>
          <SearchInput value={search} onChange={change(setSearch)} placeholder="Search action, actor, resource or metadata" label="Search audit events" />
          <SelectFilter label="Category" value={category} onChange={change(setCategory)} options={(meta.data?.categories || []).map((c) => ({ value: c.key, label: c.label }))} />
          <SelectFilter label="Outcome" value={outcome} onChange={change(setOutcome)} options={meta.data?.outcomes || ['SUCCESS', 'FAILURE', 'DENIED']} />
          <label className="flex items-center gap-2 text-xs text-muted">
            From
            <input type="date" className="input w-auto py-1.5" value={dateFrom} max={dateTo || undefined} onChange={(event) => change(setDateFrom)(event.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-xs text-muted">
            To
            <input type="date" className="input w-auto py-1.5" value={dateTo} min={dateFrom || undefined} onChange={(event) => change(setDateTo)(event.target.value)} />
          </label>
        </FilterBar>
        {data ? <InlineError message={error} onRetry={reload} className="m-3" /> : null}
        <DataTable
          caption="Audit events"
          columns={columns}
          rows={data?.items}
          loading={loading}
          error={error}
          onRetry={reload}
          sort={sorting.sort}
          order={sorting.order}
          onSort={(key) => {
            setSorting((current) => nextSort(current, key, key === 'created_at' ? 'desc' : 'asc'));
            setPage(1);
          }}
          onRowClick={setSelected}
          emptyTitle={filtered ? 'No audit events match these filters' : 'No audit events recorded yet'}
          emptyDescription={filtered ? 'Try clearing the search or filters.' : undefined}
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total || 0} onPageChange={setPage} />
      </div>

      <Modal open={Boolean(selected)} title={selected ? humanAction(selected.action) : ''} onClose={() => setSelected(null)} size="lg">
        {selected ? (
          <>
            <dl className="kv">
              <dt>Event ID</dt>
              <dd className="font-mono text-xs">{selected.event_id}</dd>
              <dt>Timestamp (UTC)</dt>
              <dd className="font-mono text-xs">{utcTitle(selected.created_at)}</dd>
              <dt>Actor</dt>
              <dd>{selected.actor_label}</dd>
              <dt>Action</dt>
              <dd className="font-mono text-xs">{selected.action}</dd>
              <dt>Resource</dt>
              <dd>
                {selected.entity_type}
                {selected.entity_id ? ` #${selected.entity_id}` : ''}
              </dd>
              <dt>Outcome</dt>
              <dd>
                <StatusBadge status={selected.outcome} />
              </dd>
              <dt>Correlation ID</dt>
              <dd className="break-all font-mono text-xs">{selected.correlation_id || '—'}</dd>
              <dt>Source address</dt>
              <dd className="font-mono text-xs">{selected.source_ip || '—'}</dd>
            </dl>
            <h3 className="mb-1.5 mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Metadata</h3>
            <pre className="mono-block">{JSON.stringify(selected.metadata || {}, null, 2)}</pre>
          </>
        ) : null}
      </Modal>
    </>
  );
}
