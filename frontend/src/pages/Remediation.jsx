import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Cpu } from 'lucide-react';
import { remediationApi } from '../api/remediation';
import { DataTable, Pagination, nextSort } from '../components/DataTable';
import { FilterBar, SearchInput, SelectFilter } from '../components/Filters';
import { PageHeader } from '../components/PageHeader';
import { InlineError, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useApi, useDebounced } from '../hooks/useApi';
import { formatDateTime, timeAgo, utcTitle } from '../utils/format';

const STATUSES = ['PENDING_APPROVAL', 'APPROVED', 'QUEUED', 'RUNNING', 'VERIFYING', 'SUCCEEDED', 'FAILED', 'REJECTED', 'CANCELLED'];
const PAGE_SIZE = 15;

export default function Remediation() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(params.get('status') || '');
  const [mine, setMine] = useState(false);
  const [sorting, setSorting] = useState({ sort: 'created_at', order: 'desc' });
  const [page, setPage] = useState(1);
  const q = useDebounced(search);

  const { data, error, loading, refreshing, reload } = useApi(
    () => remediationApi.list({ q, status, mine: mine || undefined, sort: sorting.sort, order: sorting.order, page, page_size: PAGE_SIZE }),
    [q, status, mine, sorting.sort, sorting.order, page],
    { interval: 6000 },
  );
  const catalog = useApi(() => remediationApi.actions(), [], { interval: 15000 });

  const change = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  const columns = [
    { key: 'id', header: 'Request', sortable: true, render: (row) => <span className="font-mono text-xs">#{row.id}</span> },
    {
      key: 'action_code',
      header: 'Action',
      sortable: true,
      render: (row) => (
        <div className="min-w-[12rem]">
          <p className="font-medium text-content">
            <span className="font-mono text-xs">{row.action_code}</span> · {row.action_name}
          </p>
          <p className="mt-0.5 break-all text-xs text-muted">{row.target}</p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', sortable: true, render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'source',
      header: 'Source',
      render: (row) => (
        <span className="whitespace-nowrap text-xs">
          {row.source_type === 'incident' ? 'Incident' : 'Finding'} #{row.source_id}
        </span>
      ),
    },
    { key: 'requested_by_email', header: 'Requested by', render: (row) => <span className="text-xs">{row.requested_by_email}</span> },
    { key: 'approved_by_email', header: 'Decided by', render: (row) => <span className="text-xs">{row.approved_by_email || '—'}</span> },
    {
      key: 'created_at',
      header: 'Requested',
      sortable: true,
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-muted" title={utcTitle(row.created_at)}>
          {formatDateTime(row.created_at)}
        </span>
      ),
    },
  ];

  const worker = catalog.data?.worker;

  return (
    <>
      <PageHeader
        title="Remediation"
        subtitle="Controlled remediation: a request must be approved and dispatched by an Administrator, is executed by the restricted worker, and only succeeds after verification."
        onRefresh={() => {
          reload();
          catalog.reload();
        }}
        refreshing={refreshing}
      />

      {worker && !worker.online ? (
        <Notice tone="warning" icon={AlertTriangle} className="mb-4">
          The remediation worker is offline{worker.last_seen_at ? ` (last seen ${timeAgo(worker.last_seen_at)})` : ''}. Dispatched requests stay queued until it is running:{' '}
          <code>docker compose ps worker</code>.
        </Notice>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="card xl:col-span-3">
          <FilterBar>
            <SearchInput value={search} onChange={change(setSearch)} placeholder="Search target, action or #id" label="Search remediation requests" />
            <SelectFilter label="Status" value={status} onChange={change(setStatus)} options={STATUSES} />
            <label className="flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--brand))]" checked={mine} onChange={(event) => change(setMine)(event.target.checked)} />
              My requests
            </label>
          </FilterBar>
          {data ? <InlineError message={error} onRetry={reload} className="m-3" /> : null}
          <DataTable
            caption="Remediation requests"
            columns={columns}
            rows={data?.items}
            loading={loading}
            error={error}
            onRetry={reload}
            sort={sorting.sort}
            order={sorting.order}
            onSort={(key) => {
              setSorting((current) => nextSort(current, key, 'desc'));
              setPage(1);
            }}
            onRowClick={(row) => navigate(`/remediation/${row.id}`)}
            emptyTitle={q || status || mine ? 'No requests match these filters' : 'No remediation has been requested'}
            emptyDescription="Remediation is requested from an incident or a security finding that supports an automated action."
          />
          <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total || 0} onPageChange={setPage} />
        </div>

        <aside className="space-y-4">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Restricted worker</h2>
              {worker ? <StatusBadge status={worker.online ? 'UP' : 'DOWN'} label={worker.online ? 'Online' : 'Offline'} /> : null}
            </div>
            <div className="card-body text-sm text-muted">
              <p className="flex items-center gap-2 text-content">
                <Cpu size={15} aria-hidden="true" /> {worker?.worker_id || 'No worker has reported yet'}
              </p>
              {worker?.last_seen_at ? <p className="mt-1 text-xs">Heartbeat {timeAgo(worker.last_seen_at)} · {worker.jobs_processed} job(s) processed</p> : null}
              <p className="mt-2 text-xs">Runs only the allowlisted actions below. It has no network port, no shell access and no access to the Docker daemon.</p>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Supported actions (allowlist)</h2>
            </div>
            <ul className="divide-y divide-line">
              {(catalog.data?.actions || []).map((action) => (
                <li key={action.code} className="p-4">
                  <p className="text-sm font-medium text-content">
                    <span className="font-mono text-xs">{action.code}</span> · {action.name}
                  </p>
                  <p className="mt-1 text-xs text-muted">{action.description}</p>
                  <p className="mt-1 text-xs text-muted">Applies to: {action.source_type}s · Risk: {action.risk}</p>
                </li>
              ))}
            </ul>
            <p className="border-t border-line p-4 text-xs text-muted">
              {isAdmin ? 'As an Administrator you approve, reject, dispatch and retry requests.' : 'As an Operator you can request remediation and cancel your own pending requests.'}
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
