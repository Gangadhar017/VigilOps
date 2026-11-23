import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { incidentsApi } from '../api/incidents';
import { DataTable, Pagination, nextSort } from '../components/DataTable';
import { SimulatedTag } from '../components/DataSourceTag';
import { FilterBar, SearchInput, SelectFilter } from '../components/Filters';
import { PageHeader } from '../components/PageHeader';
import { InlineError } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { useApi, useDebounced } from '../hooks/useApi';
import { formatDateTime, timeAgo, utcTitle } from '../utils/format';

const STATUSES = ['OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'];
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const PAGE_SIZE = 15;

export default function Incidents() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(params.get('status') || '');
  const [severity, setSeverity] = useState(params.get('severity') || '');
  const [activeOnly, setActiveOnly] = useState(params.get('active') === '1');
  const [sorting, setSorting] = useState({ sort: 'detected_at', order: 'desc' });
  const [page, setPage] = useState(1);
  const q = useDebounced(search);

  const { data, error, loading, refreshing, reload } = useApi(
    () =>
      incidentsApi.list({
        q,
        status,
        severity,
        active_only: activeOnly || undefined,
        sort: sorting.sort,
        order: sorting.order,
        page,
        page_size: PAGE_SIZE,
      }),
    [q, status, severity, activeOnly, sorting.sort, sorting.order, page],
    { interval: 10000 },
  );

  const change = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  const columns = [
    { key: 'id', header: 'ID', sortable: true, render: (row) => <span className="font-mono text-xs">INC-{row.id}</span> },
    {
      key: 'title',
      header: 'Incident',
      sortable: true,
      render: (row) => (
        <div className="min-w-[14rem]">
          <p className="font-medium text-content">{row.title}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted">{row.alert_name}</span>
            {row.is_simulated ? <SimulatedTag title={row.simulation_note} /> : null}
            {row.signal_stale ? <StatusBadge tone="warning" label="Signal stale" /> : null}
          </div>
        </div>
      ),
    },
    { key: 'severity', header: 'Severity', sortable: true, render: (row) => <StatusBadge status={row.severity} /> },
    { key: 'status', header: 'Status', sortable: true, render: (row) => <StatusBadge status={row.status} /> },
    { key: 'affected_resource', header: 'Resource', className: 'whitespace-nowrap' },
    {
      key: 'detected_at',
      header: 'Detected',
      sortable: true,
      render: (row) => (
        <span title={utcTitle(row.detected_at)} className="whitespace-nowrap text-xs">
          {formatDateTime(row.detected_at)}
        </span>
      ),
    },
    {
      key: 'last_occurrence_at',
      header: 'Last occurrence',
      sortable: true,
      render: (row) => (
        <span title={utcTitle(row.last_occurrence_at)} className="whitespace-nowrap text-xs text-muted">
          {timeAgo(row.last_occurrence_at)}
        </span>
      ),
    },
    {
      key: 'occurrence_count',
      header: 'Notifications',
      sortable: true,
      className: 'text-right',
      render: (row) => <span className="tabular-nums">{row.occurrence_count}</span>,
    },
  ];

  return (
    <>
      <PageHeader
        title="Incidents"
        subtitle="Incidents are opened automatically from Prometheus alerts delivered by Alertmanager. Repeated notifications for the same alert update one incident instead of creating duplicates."
        onRefresh={reload}
        refreshing={refreshing}
      />
      <div className="card">
        <FilterBar>
          <SearchInput value={search} onChange={change(setSearch)} placeholder="Search title, alert, resource or ID" label="Search incidents" />
          <SelectFilter label="Status" value={status} onChange={change(setStatus)} options={STATUSES} />
          <SelectFilter label="Severity" value={severity} onChange={change(setSeverity)} options={SEVERITIES} />
          <label className="flex items-center gap-2 text-xs text-muted">
            <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={activeOnly} onChange={(event) => change(setActiveOnly)(event.target.checked)} />
            Active only
          </label>
        </FilterBar>
        {data ? <InlineError message={error} onRetry={reload} className="m-3" /> : null}
        <DataTable
          caption="Incidents"
          columns={columns}
          rows={data?.items}
          loading={loading}
          error={error}
          onRetry={reload}
          sort={sorting.sort}
          order={sorting.order}
          onSort={(key) => {
            setSorting((current) => nextSort(current, key, key === 'severity' ? 'asc' : 'desc'));
            setPage(1);
          }}
          onRowClick={(row) => navigate(`/incidents/${row.id}`)}
          emptyTitle={q || status || severity || activeOnly ? 'No incidents match these filters' : 'No incidents have been recorded'}
          emptyDescription={
            q || status || severity || activeOnly
              ? 'Try clearing the search or filters.'
              : 'Incidents appear here when a Prometheus alert fires. An Administrator can inject a controlled fault from Settings → Demo controls.'
          }
        />
        <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total || 0} onPageChange={setPage} />
      </div>
    </>
  );
}
