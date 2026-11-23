import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ClipboardCheck, FlaskConical, ShieldAlert, XCircle } from 'lucide-react';
import { monitoringApi } from '../api/monitoring';
import { LiveTag } from '../components/DataSourceTag';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, InlineError, LoadingState, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { TimeSeriesChart } from '../components/TimeSeriesChart';
import { useApi } from '../hooks/useApi';
import { formatDateTime, formatMetric, humanAction, timeAgo, utcTitle } from '../utils/format';

const SEVERITIES = [
  ['CRITICAL', 'bg-danger'],
  ['HIGH', 'bg-warn'],
  ['MEDIUM', 'bg-info'],
  ['LOW', 'bg-muted'],
];
const HEADLINE_METRICS = ['request_rate', 'error_rate_5xx', 'error_rate_4xx', 'latency_p95', 'cpu_usage', 'memory_rss', 'uptime'];
const CARD_LINK = 'font-mono text-[10.5px] uppercase tracking-[0.08em] text-brand hover:underline';

/** Counts per severity as thin proportional bars, so the figures can be read at a glance. */
function SeverityChart({ title, counts, emptyLabel, to }) {
  const rows = SEVERITIES.map(([severity, color]) => ({ severity, color, count: counts?.[severity] || 0 }));
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const highest = Math.max(1, ...rows.map((row) => row.count));
  return (
    <div className="card flex flex-col">
      <div className="card-header">
        <h2 className="card-title">{title}</h2>
        <Link to={to} className={CARD_LINK}>
          View all
        </Link>
      </div>
      {total === 0 ? (
        <EmptyState title={emptyLabel} icon={CheckCircle2} className="flex-1 py-8" />
      ) : (
        <div className="flex flex-1 flex-col gap-4 p-4">
          <div className="flex items-baseline gap-2">
            <span className="stat text-content">{total}</span>
            <span className="eyebrow">total</span>
          </div>
          <ul className="space-y-2.5">
            {rows.map((row) => (
              <li key={row.severity} className="grid grid-cols-[4.75rem_1fr_1.75rem] items-center gap-3">
                <span className="eyebrow flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-[1px] ${row.color}`} aria-hidden="true" />
                  {row.severity}
                </span>
                <span className="h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden="true">
                  <span className={`block h-full rounded-full ${row.color}`} style={{ width: `${(row.count / highest) * 100}%` }} />
                </span>
                <span className={`text-right font-mono text-xs tabular-nums ${row.count ? 'text-content' : 'text-muted/70'}`}>{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function HealthRow({ label, ok, detail, unknown }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2.5">
      <span className="text-[13px] text-content">{label}</span>
      <span className="flex items-center gap-2.5 text-right">
        {detail ? <span className="font-mono text-[11px] text-muted">{detail}</span> : null}
        <StatusBadge status={unknown ? 'UNKNOWN' : ok ? 'UP' : 'DOWN'} label={unknown ? 'Unknown' : ok ? 'Healthy' : 'Unavailable'} />
      </span>
    </li>
  );
}

function ResourceCard({ resource, generatedAt }) {
  return (
    <div className="card overflow-hidden">
      <div className="card-header">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-content">{resource.name}</h3>
          <p className="truncate text-xs text-muted">{resource.description}</p>
        </div>
        <div className="flex items-center gap-2">
          <LiveTag at={generatedAt} />
          <StatusBadge status={resource.status} />
        </div>
      </div>
      {/* Metric cells share hairlines: a 1px gap over a line-coloured background. */}
      <dl className="grid grid-cols-2 gap-px bg-line/70 sm:grid-cols-4">
        {HEADLINE_METRICS.map((key) => {
          const metric = resource.metrics?.[key];
          const value = metric?.available ? formatMetric(metric.value, metric.unit, key) : null;
          return (
            <div key={key} title={metric?.description} className="flex min-h-[68px] flex-col justify-between bg-surface px-4 py-3">
              <dt className="text-[11px] leading-4 text-muted">{metric?.label || key.replace(/_/g, ' ')}</dt>
              {value !== null ? (
                <dd className="mt-1.5 text-[15px] font-semibold leading-5 tabular-nums text-content">{value}</dd>
              ) : (
                <dd className="mt-1.5 text-[13px] leading-5 text-muted" title={metric?.reason || 'Prometheus has no value for this metric'}>
                  Unavailable
                </dd>
              )}
            </div>
          );
        })}
        {/* Seven metrics in a four-column grid: fill the last cell so the hairlines stay complete. */}
        <div className="bg-surface" aria-hidden="true" />
      </dl>
    </div>
  );
}

export default function Dashboard() {
  const summary = useApi(() => monitoringApi.dashboard(), [], { interval: 10000 });
  const overview = useApi(() => monitoringApi.overview(), [], { interval: 10000 });

  if (summary.loading && !summary.data) return <LoadingState label="Loading overview…" />;
  if (summary.error && !summary.data) return <ErrorState message={summary.error} onRetry={summary.reload} />;

  const s = summary.data;
  const o = overview.data;
  const targets = o?.targets?.targets || [];
  const targetsUp = targets.filter((target) => target.health === 'up').length;
  const scan = s.latest_scan;
  const demoApp = (o?.resources || []).find((resource) => resource.resource_type === 'application');
  const refresh = () => {
    summary.reload();
    overview.reload();
  };

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Operational and security posture of the monitored environment. Counts come from stored records; health and metrics are live Prometheus telemetry."
        onRefresh={refresh}
        refreshing={summary.refreshing || overview.refreshing}
      />

      <InlineError message={summary.error} onRetry={summary.reload} className="mb-4" />

      {s.incidents.simulated_active > 0 ? (
        <Notice tone="warning" icon={FlaskConical} className="mb-4">
          {s.incidents.simulated_active} active incident{s.incidents.simulated_active > 1 ? 's were' : ' was'} triggered by a controlled demonstration fault.
          The telemetry is real; the cause was injected deliberately.
        </Notice>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Active incidents"
          value={s.incidents.active}
          tone={s.incidents.active ? 'danger' : 'success'}
          icon={AlertTriangle}
          to="/incidents?active=1"
          hint={`${s.incidents.resolved_last_24h} resolved in the last 24 hours`}
        />
        <MetricCard
          label="Open security findings"
          value={s.findings.open}
          tone={s.findings.open ? 'warning' : 'success'}
          icon={ShieldAlert}
          to="/findings?status=OPEN"
          hint={`${s.findings.by_status.REMEDIATION_PENDING} with remediation pending · ${s.findings.by_status.RESOLVED} resolved`}
        />
        <MetricCard
          label="Pending approvals"
          value={s.remediation.pending_approval}
          tone={s.remediation.pending_approval ? 'warning' : 'default'}
          icon={ClipboardCheck}
          to="/remediation?status=PENDING_APPROVAL"
          hint={`${s.remediation.in_progress} approved or in progress`}
        />
        <MetricCard
          label="Remediation results"
          value={
            <span className="flex items-baseline gap-2">
              <span className="text-ok">{s.remediation.succeeded}</span>
              <span className="eyebrow mr-2">succeeded</span>
              <span className={s.remediation.failed ? 'text-danger' : 'text-content'}>{s.remediation.failed}</span>
              <span className="eyebrow">failed</span>
            </span>
          }
          tone={s.remediation.failed ? 'danger' : 'default'}
          icon={s.remediation.failed ? XCircle : CheckCircle2}
          to="/remediation"
          hint="Verified outcomes of executed requests"
        />
      </div>

      <section className="mt-8" aria-labelledby="health-heading">
        <h2 id="health-heading" className="section-title">
          Monitored resources
        </h2>
        {overview.loading && !o ? (
          <div className="card">
            <LoadingState label="Querying Prometheus…" />
          </div>
        ) : overview.error && !o ? (
          <div className="card">
            <ErrorState message={overview.error} onRetry={overview.reload} />
          </div>
        ) : (
          <>
            {!o.prometheus.available ? (
              <Notice tone="warning" icon={AlertTriangle} className="mb-3">
                Prometheus is unavailable ({o.prometheus.error}). Live metrics cannot be shown until it is reachable again; no values are estimated.
              </Notice>
            ) : null}
            <div className="grid gap-4 lg:grid-cols-2">
              {o.resources.map((resource) => (
                <ResourceCard key={resource.id} resource={resource} generatedAt={o.generated_at} />
              ))}
            </div>
          </>
        )}
      </section>

      {demoApp?.job ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <TimeSeriesChart job={demoApp.job} metric="request_rate" range="15m" title={`${demoApp.name} · HTTP request rate (15 min)`} />
          <TimeSeriesChart
            job={demoApp.job}
            metric="error_rate_5xx"
            range="15m"
            title={`${demoApp.name} · HTTP 5xx error rate (15 min)`}
            color="rgb(var(--danger))"
            threshold={0.2}
            thresholdLabel="alert at 20%"
          />
        </div>
      ) : null}

      <section className="mt-8" aria-labelledby="posture-heading">
        <h2 id="posture-heading" className="section-title">
          Incidents, findings and platform
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          <SeverityChart title="Active incidents by severity" counts={s.incidents.active_by_severity} emptyLabel="No active incidents" to="/incidents" />
          <SeverityChart title="Unresolved findings by severity" counts={s.findings.unresolved_by_severity} emptyLabel="No unresolved findings" to="/findings" />

          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Platform health</h2>
              <Link to="/monitoring" className={CARD_LINK}>
                Monitoring
              </Link>
            </div>
            <ul className="divide-y divide-line/70 px-4">
              <HealthRow label="Backend API" ok={s.platform.backend.healthy} detail={`v${s.platform.backend.version}`} />
              <HealthRow label="Database" ok={s.platform.database.healthy} detail={s.platform.database.error || 'PostgreSQL'} />
              <HealthRow label="Prometheus" ok={o?.prometheus?.available} unknown={!o} detail={o?.prometheus?.error} />
              <HealthRow label="Alertmanager" ok={o?.alertmanager?.available} unknown={!o} detail={o?.alertmanager?.error} />
              <HealthRow
                label="Monitoring targets"
                ok={targets.length > 0 && targetsUp === targets.length}
                unknown={!o || !o.targets.available}
                detail={o?.targets?.available ? `${targetsUp} of ${targets.length} up` : o?.targets?.reason}
              />
              <HealthRow
                label="Remediation worker"
                ok={s.platform.worker.online}
                detail={s.platform.worker.last_seen_at ? `seen ${timeAgo(s.platform.worker.last_seen_at)}` : s.platform.worker.detail}
              />
            </ul>
          </div>
        </div>
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Latest security scan</h2>
            <Link to="/findings" className={CARD_LINK}>
              Findings
            </Link>
          </div>
          {scan ? (
            <dl className="kv p-4">
              <dt>Status</dt>
              <dd>
                <StatusBadge status={scan.status} />
              </dd>
              <dt>Completed</dt>
              <dd title={utcTitle(scan.completed_at)}>{formatDateTime(scan.completed_at)}</dd>
              <dt>Requested by</dt>
              <dd>{scan.requested_by}</dd>
              <dt>Trigger</dt>
              <dd>{humanAction(scan.trigger)}</dd>
              <dt>Result</dt>
              <dd>
                {scan.summary?.violations_detected ?? 0} violations in {(scan.summary?.files_scanned || []).length} file(s) · {scan.summary?.new_findings ?? 0} new ·{' '}
                {scan.summary?.resolved_findings ?? 0} resolved
              </dd>
            </dl>
          ) : (
            <EmptyState title="No scan has been run yet" description="Run a scan from the Security Findings page." />
          )}
        </div>

        <div className="card lg:col-span-2">
          <div className="card-header">
            <h2 className="card-title">Recent audit events</h2>
            <Link to="/audit" className={CARD_LINK}>
              Audit logs
            </Link>
          </div>
          {s.recent_audit_events.length === 0 ? (
            <EmptyState title="No audit events yet" />
          ) : (
            <ul className="divide-y divide-line/70">
              {s.recent_audit_events.map((event) => (
                <li key={event.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 transition-colors hover:bg-raised/40">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] text-content">
                      {humanAction(event.action)}
                      {event.entity_id ? <span className="text-muted"> · {event.entity_type} #{event.entity_id}</span> : null}
                    </p>
                    <p className="truncate font-mono text-[11px] text-muted">{event.actor}</p>
                  </div>
                  <div className="flex items-center gap-2.5">
                    {event.outcome !== 'SUCCESS' ? <StatusBadge status={event.outcome} /> : null}
                    <span className="font-mono text-[11px] text-muted" title={utcTitle(event.created_at)}>
                      {timeAgo(event.created_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
