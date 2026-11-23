import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { FileCode2, Info, Play } from 'lucide-react';
import { errorMessage } from '../api/client';
import { securityApi } from '../api/security';
import { DataTable, Pagination, nextSort } from '../components/DataTable';
import { FilterBar, SearchInput, SelectFilter } from '../components/Filters';
import { Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, InlineError, LoadingState, Notice, Spinner } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useApi, useDebounced } from '../hooks/useApi';
import { formatBytes, formatDateTime, humanAction, timeAgo, utcTitle } from '../utils/format';

const STATUSES = ['OPEN', 'REMEDIATION_PENDING', 'RESOLVED', 'ACCEPTED_RISK'];
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const RULES = ['SEC-001', 'SEC-002', 'SEC-003', 'SEC-004', 'SEC-005'];
const TABS = [
  { key: 'findings', label: 'Findings' },
  { key: 'scans', label: 'Scan history' },
  { key: 'rules', label: 'Rules' },
  { key: 'targets', label: 'Configuration files' },
];
const PAGE_SIZE = 15;

function FindingsTab({ refreshKey }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(params.get('status') || '');
  const [severity, setSeverity] = useState('');
  const [rule, setRule] = useState('');
  const [sorting, setSorting] = useState({ sort: 'severity', order: 'asc' });
  const [page, setPage] = useState(1);
  const q = useDebounced(search);

  const { data, error, loading, reload } = useApi(
    () => securityApi.findings({ q, status, severity, rule_id: rule, sort: sorting.sort, order: sorting.order, page, page_size: PAGE_SIZE }),
    [q, status, severity, rule, sorting.sort, sorting.order, page, refreshKey],
    { interval: 15000 },
  );
  const change = (setter) => (value) => {
    setter(value);
    setPage(1);
  };
  const filtered = q || status || severity || rule;

  const columns = [
    { key: 'rule_id', header: 'Rule', sortable: true, render: (row) => <span className="whitespace-nowrap font-mono text-xs font-semibold">{row.rule_id}</span> },
    {
      key: 'rule_name',
      header: 'Finding',
      render: (row) => (
        <div className="min-w-[14rem]">
          <p className="font-medium text-content">{row.rule_name}</p>
          <p className="mt-0.5 text-xs text-muted">{row.evidence?.summary}</p>
        </div>
      ),
    },
    { key: 'severity', header: 'Severity', sortable: true, render: (row) => <StatusBadge status={row.severity} /> },
    { key: 'status', header: 'Status', sortable: true, render: (row) => <StatusBadge status={row.status} /> },
    {
      key: 'resource',
      header: 'Affected resource',
      sortable: true,
      render: (row) => (
        <div>
          <p className="font-mono text-xs">{row.resource_identifier}</p>
          <p className="text-xs text-muted">{row.target_file}</p>
        </div>
      ),
    },
    {
      key: 'last_seen_at',
      header: 'Last seen',
      sortable: true,
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-muted" title={utcTitle(row.last_seen_at)}>
          {timeAgo(row.last_seen_at)}
        </span>
      ),
    },
  ];

  return (
    <>
      <FilterBar>
        <SearchInput value={search} onChange={change(setSearch)} placeholder="Search rule, resource or file" label="Search findings" />
        <SelectFilter label="Status" value={status} onChange={change(setStatus)} options={STATUSES} />
        <SelectFilter label="Severity" value={severity} onChange={change(setSeverity)} options={SEVERITIES} />
        <SelectFilter label="Rule" value={rule} onChange={change(setRule)} options={RULES} />
      </FilterBar>
      {data ? <InlineError message={error} onRetry={reload} className="m-3" /> : null}
      <DataTable
        caption="Security findings"
        columns={columns}
        rows={data?.items}
        loading={loading}
        error={error}
        onRetry={reload}
        sort={sorting.sort}
        order={sorting.order}
        onSort={(key) => {
          setSorting((current) => nextSort(current, key));
          setPage(1);
        }}
        onRowClick={(row) => navigate(`/findings/${row.id}`)}
        emptyTitle={filtered ? 'No findings match these filters' : 'No findings recorded'}
        emptyDescription={filtered ? 'Try clearing the search or filters.' : 'Run a scan to evaluate the configuration files in the scan workspace.'}
      />
      <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total || 0} onPageChange={setPage} />
    </>
  );
}

function ScansTab({ refreshKey }) {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => securityApi.scans({ page, page_size: 10 }), [page, refreshKey]);
  const columns = [
    { key: 'id', header: 'Scan', render: (row) => <span className="font-mono text-xs">#{row.id}</span> },
    { key: 'status', header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
    { key: 'trigger', header: 'Trigger', render: (row) => humanAction(row.trigger) },
    { key: 'requested_by_label', header: 'Requested by' },
    { key: 'target', header: 'Target', render: (row) => <span className="font-mono text-xs">{row.target === '*' ? 'all files' : row.target}</span> },
    {
      key: 'result',
      header: 'Result',
      render: (row) =>
        row.status === 'FAILED' ? (
          <span className="text-xs text-danger">{row.error}</span>
        ) : (
          <span className="text-xs">
            {row.result_summary.violations_detected} violations · {row.result_summary.new_findings} new · {row.result_summary.reopened_findings} reopened ·{' '}
            {row.result_summary.resolved_findings} resolved
            {Object.keys(row.result_summary.files_failed || {}).length ? (
              <span className="block text-danger">{Object.values(row.result_summary.files_failed).join('; ')}</span>
            ) : null}
            {row.result_summary.note ? <span className="block text-muted">{row.result_summary.note}</span> : null}
          </span>
        ),
    },
    {
      key: 'completed_at',
      header: 'Completed',
      render: (row) => (
        <span className="whitespace-nowrap text-xs text-muted" title={utcTitle(row.completed_at)}>
          {formatDateTime(row.completed_at)}
        </span>
      ),
    },
  ];
  return (
    <>
      <DataTable caption="Scan history" columns={columns} rows={data?.items} loading={loading} error={error} onRetry={reload} emptyTitle="No scans have been run yet" />
      <Pagination page={page} pageSize={10} total={data?.total || 0} onPageChange={setPage} />
    </>
  );
}

function RulesTab() {
  const { data, error, loading, reload } = useApi(() => securityApi.rules(), []);
  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  return (
    <div className="divide-y divide-line">
      {data.rules.map((rule) => (
        <article key={rule.id} className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-content">{rule.id}</span>
            <h3 className="text-sm font-semibold text-content">{rule.name}</h3>
            <StatusBadge status={rule.severity} />
            {rule.automated_action ? <StatusBadge tone="brand" label={`Automated: ${rule.automated_action}`} /> : <StatusBadge tone="neutral" label="Manual fix" />}
          </div>
          <dl className="kv mt-3">
            <dt>Description</dt>
            <dd>{rule.description}</dd>
            <dt>Detection logic</dt>
            <dd>{rule.detection_logic}</dd>
            <dt>Security impact</dt>
            <dd>{rule.impact}</dd>
            <dt>Corrective action</dt>
            <dd>{rule.recommendation}</dd>
            <dt>Applies to</dt>
            <dd className="font-mono text-xs">{rule.resource_types.join(', ')}</dd>
          </dl>
        </article>
      ))}
    </div>
  );
}

function TargetsTab({ refreshKey }) {
  const { data, error, loading, reload } = useApi(() => securityApi.targets(), [refreshKey]);
  const [viewing, setViewing] = useState(null);
  const [content, setContent] = useState(null);
  const [contentError, setContentError] = useState('');

  const open = async (name) => {
    setViewing(name);
    setContent(null);
    setContentError('');
    try {
      setContent(await securityApi.target(name));
    } catch (err) {
      setContentError(errorMessage(err));
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data.targets.length)
    return (
      <EmptyState
        icon={FileCode2}
        title="The scan workspace is empty"
        description="Place vigilops/v1 YAML configuration files in the scan workspace volume. In demo mode an Administrator can restore the sample configuration from Settings → Demo controls."
      />
    );
  return (
    <>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">File</th>
              <th scope="col">Size</th>
              <th scope="col">Modified</th>
              <th scope="col">Automated remediation</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {data.targets.map((target) => (
              <tr key={target.name}>
                <td className="font-mono text-xs font-medium">{target.name}</td>
                <td className="text-xs">{formatBytes(target.size_bytes)}</td>
                <td className="text-xs text-muted" title={utcTitle(target.modified_at)}>
                  {formatDateTime(target.modified_at)}
                </td>
                <td>{target.remediation_allowed ? <StatusBadge tone="brand" label="Allowlisted" /> : <StatusBadge tone="neutral" label="Read-only" />}</td>
                <td className="text-right">
                  <button type="button" className="btn-secondary btn-sm" onClick={() => open(target.name)}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Modal open={Boolean(viewing)} title={viewing || ''} onClose={() => setViewing(null)} size="lg">
        {contentError ? <ErrorState message={contentError} /> : !content ? <LoadingState /> : <pre className="mono-block max-h-[60vh] whitespace-pre">{content.content}</pre>}
      </Modal>
    </>
  );
}

export default function Findings() {
  const { can } = useAuth();
  const { notify } = useToast();
  const [tab, setTab] = useState('findings');
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState('');
  const [lastScan, setLastScan] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const runScan = async () => {
    setScanning(true);
    setScanError('');
    try {
      const scan = await securityApi.runScan();
      setLastScan(scan);
      setRefreshKey((key) => key + 1);
      if (scan.status === 'COMPLETED') {
        notify(`Scan #${scan.id} completed: ${scan.result_summary.violations_detected} violation(s) detected.`);
      } else {
        notify(`Scan #${scan.id} failed: ${scan.error}`, 'error');
      }
    } catch (err) {
      setScanError(errorMessage(err));
    } finally {
      setScanning(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Security Findings"
        subtitle="Results of the deterministic configuration scanner for rules SEC-001 to SEC-005."
        actions={
          <button type="button" className="btn-primary btn-sm" onClick={runScan} disabled={scanning || !can('scans:run')}>
            {scanning ? <Spinner size={14} /> : <Play size={14} aria-hidden="true" />}
            {scanning ? 'Scanning…' : 'Run scan'}
          </button>
        }
      />

      <Notice icon={Info} tone="neutral" className="mb-4">
        Scope: the scanner evaluates authorised local YAML configuration files in the scan workspace. It does not assess a live cloud account.
      </Notice>
      <InlineError message={scanError} className="mb-4" />
      {lastScan ? (
        <Notice tone={lastScan.status === 'COMPLETED' ? 'success' : 'warning'} className="mb-4">
          Scan #{lastScan.id} {lastScan.status.toLowerCase()} at {formatDateTime(lastScan.completed_at)}:{' '}
          {lastScan.status === 'COMPLETED'
            ? `${(lastScan.result_summary.files_scanned || []).length} file(s) scanned, ${lastScan.result_summary.violations_detected} violation(s), ${lastScan.result_summary.new_findings} new, ${lastScan.result_summary.reopened_findings} reopened, ${lastScan.result_summary.resolved_findings} resolved.`
            : lastScan.error}
          {lastScan.result_summary?.note ? ` ${lastScan.result_summary.note}` : ''}
        </Notice>
      ) : null}

      <div className="card">
        <div className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line px-3" role="tablist" aria-label="Security views">
          {TABS.map((item) => (
            <button key={item.key} type="button" role="tab" aria-selected={tab === item.key} className={`tab whitespace-nowrap ${tab === item.key ? 'tab-active' : ''}`} onClick={() => setTab(item.key)}>
              {item.label}
            </button>
          ))}
        </div>
        {tab === 'findings' ? <FindingsTab refreshKey={refreshKey} /> : null}
        {tab === 'scans' ? <ScansTab refreshKey={refreshKey} /> : null}
        {tab === 'rules' ? <RulesTab /> : null}
        {tab === 'targets' ? <TargetsTab refreshKey={refreshKey} /> : null}
      </div>
    </>
  );
}
