import React, { useEffect, useState } from 'react';
import { AlertTriangle, ArrowUpRight } from 'lucide-react';
import { monitoringApi } from '../api/monitoring';
import { LiveTag } from '../components/DataSourceTag';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, InlineError, LoadingState, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { TimeSeriesChart } from '../components/TimeSeriesChart';
import { DEMO_APP_URL } from '../config/links';
import { useApi } from '../hooks/useApi';
import { formatDateTime, formatMetric, utcTitle } from '../utils/format';

const RANGES = [
  { key: '5m', label: '5 min' },
  { key: '15m', label: '15 min' },
  { key: '1h', label: '1 hour' },
  { key: '6h', label: '6 hours' },
];

const CARDS = ['availability', 'request_rate', 'error_rate_5xx', 'error_rate_4xx', 'latency_p95', 'cpu_usage', 'memory_rss', 'uptime'];

// The dashed threshold lines mirror the alert rules in monitoring/alert_rules.yml.
// They are drawn for orientation only: if a rule's threshold is changed, update it here too.
const CHARTS = [
  { metric: 'request_rate' },
  { metric: 'error_rate_5xx', color: 'rgb(var(--danger))', threshold: 0.2, thresholdLabel: 'alert at 20%' },
  { metric: 'error_rate_4xx', color: 'rgb(var(--warn))' },
  { metric: 'latency_p95', color: 'rgb(var(--info))', threshold: 1, thresholdLabel: 'alert at 1 s' },
  { metric: 'cpu_usage', color: 'rgb(var(--warn))', threshold: 0.8, thresholdLabel: 'alert at 80%' },
  { metric: 'memory_rss', color: 'rgb(var(--info))', threshold: 250 * 1024 * 1024, thresholdLabel: 'alert at 250 MiB' },
];

export default function Monitoring() {
  const { data, error, loading, refreshing, reload } = useApi(() => monitoringApi.overview(), [], { interval: 10000 });
  const [job, setJob] = useState('');
  const [range, setRange] = useState('15m');

  const resources = (data?.resources || []).filter((resource) => resource.job);
  useEffect(() => {
    if (!job && resources.length) setJob(resources[0].job);
  }, [job, resources]);

  if (loading && !data) return <LoadingState label="Querying Prometheus…" />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;

  const selected = resources.find((resource) => resource.job === job);
  const targets = data.targets.targets || [];
  const alerts = data.alerts.alerts || [];
  // Alert thresholds apply to the demo application's rules only.
  const showThresholds = selected?.resource_type === 'application';

  return (
    <>
      <PageHeader
        title="Monitoring"
        subtitle="Live telemetry scraped by Prometheus. Every value is a real measurement; when Prometheus has no sample the metric is shown as unavailable."
        onRefresh={reload}
        refreshing={refreshing}
        actions={
          <a href={DEMO_APP_URL} target="_blank" rel="noreferrer" className="btn-secondary btn-sm" title="OrbitCrate, the monitored demonstration application">
            Open the monitored application <ArrowUpRight size={13} aria-hidden="true" />
          </a>
        }
      >
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <LiveTag at={data.generated_at} />
          <span className="tag">scrape interval {data.scrape_interval_seconds}s</span>
          <StatusBadge status={data.prometheus.available ? 'UP' : 'DOWN'} label={`Prometheus ${data.prometheus.available ? 'available' : 'unavailable'}`} />
          <StatusBadge status={data.alertmanager.available ? 'UP' : 'DOWN'} label={`Alertmanager ${data.alertmanager.available ? 'available' : 'unavailable'}`} />
        </div>
      </PageHeader>

      <InlineError message={error} onRetry={reload} className="mb-4" />
      {!data.prometheus.available ? (
        <Notice tone="warning" icon={AlertTriangle} className="mb-4">
          Prometheus cannot be reached ({data.prometheus.error}). Metrics and target status are unavailable until the monitoring service recovers. Check it with{' '}
          <code>docker compose ps prometheus</code>.
        </Notice>
      ) : null}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Monitored resource">
          {resources.map((resource) => (
            <button
              key={resource.job}
              type="button"
              role="tab"
              aria-selected={resource.job === job}
              onClick={() => setJob(resource.job)}
              className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium ${
                resource.job === job ? 'border-brand bg-brand/10 text-content' : 'border-line bg-surface text-muted hover:text-content'
              }`}
            >
              {resource.name}
              <StatusBadge status={resource.status} />
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 rounded-md border border-line bg-surface p-1" role="group" aria-label="Time range">
          {RANGES.map((option) => (
            <button
              key={option.key}
              type="button"
              aria-pressed={range === option.key}
              onClick={() => setRange(option.key)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium ${range === option.key ? 'bg-brand text-white dark:text-slate-900' : 'text-muted hover:text-content'}`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {selected ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {CARDS.map((key) => {
              const metric = selected.metrics?.[key];
              const value = metric?.available ? formatMetric(metric.value, metric.unit, key) : null;
              const tone = key === 'availability' && metric?.available ? (metric.value >= 1 ? 'success' : 'danger') : 'default';
              return (
                <MetricCard
                  key={key}
                  label={metric?.label || key.replace(/_/g, ' ')}
                  value={value}
                  tone={tone}
                  hint={metric?.description}
                  unavailableReason={metric?.reason ? `Prometheus: ${metric.reason}` : 'No value from Prometheus'}
                />
              );
            })}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {CHARTS.map((chart) => (
              <TimeSeriesChart
                key={`${job}-${chart.metric}`}
                job={job}
                metric={chart.metric}
                range={range}
                color={chart.color}
                threshold={showThresholds ? chart.threshold : undefined}
                thresholdLabel={chart.thresholdLabel}
              />
            ))}
          </div>
        </>
      ) : (
        <div className="card">
          <EmptyState title="No monitored resources" description="No resources with a Prometheus job are registered." />
        </div>
      )}

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <section className="card" aria-labelledby="targets-heading">
          <div className="card-header">
            <h2 id="targets-heading" className="card-title">
              Scrape targets
            </h2>
            <span className="text-xs text-muted">{data.targets.available ? `${targets.filter((t) => t.health === 'up').length} of ${targets.length} up` : ''}</span>
          </div>
          {!data.targets.available ? (
            <EmptyState title="Target status unavailable" description={`Prometheus: ${data.targets.reason}`} icon={AlertTriangle} />
          ) : targets.length === 0 ? (
            <EmptyState title="No scrape targets" />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Job</th>
                    <th scope="col">Instance</th>
                    <th scope="col">Health</th>
                    <th scope="col">Last scrape</th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((target) => (
                    <tr key={`${target.job}-${target.instance}`}>
                      <td className="font-medium">{target.job}</td>
                      <td className="font-mono text-xs">{target.instance}</td>
                      <td>
                        <div className="flex flex-wrap items-center gap-1.5">
                          <StatusBadge status={target.health === 'up' ? 'UP' : target.health === 'down' ? 'DOWN' : 'UNKNOWN'} />
                          {target.stale ? <StatusBadge tone="warning" label="Stale" /> : null}
                        </div>
                        {target.last_error ? <p className="mt-1 max-w-xs break-words text-xs text-danger">{target.last_error}</p> : null}
                      </td>
                      <td className="text-xs text-muted" title={utcTitle(target.last_scrape)}>
                        {target.last_scrape ? `${Math.round(target.last_scrape_age_seconds)}s ago` : 'never'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card" aria-labelledby="alerts-heading">
          <div className="card-header">
            <h2 id="alerts-heading" className="card-title">
              Alert rules currently active
            </h2>
            <span className="text-xs text-muted">from Prometheus</span>
          </div>
          {!data.alerts.available ? (
            <EmptyState title="Alert status unavailable" description={`Prometheus: ${data.alerts.reason}`} icon={AlertTriangle} />
          ) : alerts.length === 0 ? (
            <EmptyState title="No alerts are pending or firing" description="All alert rules are currently inactive." />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Alert</th>
                    <th scope="col">State</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Active since</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert) => (
                    <tr key={`${alert.name}-${alert.instance}`}>
                      <td>
                        <p className="font-medium">{alert.name}</p>
                        <p className="text-xs text-muted">{alert.summary}</p>
                      </td>
                      <td>
                        <StatusBadge status={alert.state.toUpperCase()} />
                      </td>
                      <td>
                        <StatusBadge status={alert.severity} />
                      </td>
                      <td className="text-xs text-muted" title={utcTitle(alert.active_at)}>
                        {formatDateTime(alert.active_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
