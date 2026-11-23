import React, { useMemo } from 'react';
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { monitoringApi } from '../api/monitoring';
import { useApi } from '../hooks/useApi';
import { formatAxis, formatMetric, formatTime } from '../utils/format';
import { EmptyState, ErrorState, LoadingState } from './States';

const AXIS_TICK = { fontSize: 10, fill: 'rgb(var(--muted))', fontFamily: '"IBM Plex Mono", ui-monospace, monospace' };

function ChartTooltip({ active, payload, unit, metric }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 shadow-pop">
      <p className="font-mono text-[10.5px] text-muted">{formatTime(point.t)}</p>
      <p className="text-[13px] font-semibold tabular-nums text-content">{formatMetric(point.v, unit, metric) ?? 'no sample'}</p>
    </div>
  );
}

/**
 * One Prometheus time series, fetched through the backend's metric catalog.
 * Gaps (no sample) are drawn as gaps - they are not interpolated.
 */
export function TimeSeriesChart({ job, metric, range = '15m', title, threshold, thresholdLabel, color = 'rgb(var(--brand))', height = 190, pollMs = 15000 }) {
  const { data, error, loading, reload } = useApi(() => monitoringApi.timeseries(job, metric, range), [job, metric, range], {
    interval: pollMs,
    enabled: Boolean(job),
  });

  const points = useMemo(() => (data?.points || []).map((p) => ({ t: p.t, v: p.v })), [data]);
  const hasSamples = points.some((p) => p.v !== null);
  const unit = data?.unit;
  const gradientId = `grad-${job}-${metric}`.replace(/[^a-z0-9-]/gi, '');
  const latest = [...points].reverse().find((p) => p.v !== null);

  return (
    <div className="card flex flex-col">
      <div className="card-header">
        <h3 className="card-title">{title || data?.label || metric}</h3>
        <span className="font-mono text-[11px] tabular-nums text-muted">
          {latest ? `now ${formatMetric(latest.v, unit, metric)}` : ''}
        </span>
      </div>
      <div className="px-2 pb-2 pt-3" style={{ height }}>
        {loading && !data ? (
          <LoadingState className="py-6" />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} className="py-4" />
        ) : !data?.available ? (
          <EmptyState title="Metric unavailable" description={`Prometheus could not provide this series (${data?.reason || 'unknown reason'}).`} className="py-4" />
        ) : !hasSamples ? (
          <EmptyState title="No samples in this range" description="Prometheus has no data for this metric in the selected time range." className="py-4" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgb(var(--line))" strokeOpacity={0.7} vertical={false} />
              <XAxis dataKey="t" tickFormatter={formatTime} tick={AXIS_TICK} tickLine={false} minTickGap={48} stroke="rgb(var(--line))" />
              <YAxis
                width={48}
                tick={AXIS_TICK}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => formatAxis(value, unit)}
                stroke="rgb(var(--line))"
                domain={unit === 'ratio' || unit === 'state' ? [0, (max) => Math.max(1, max)] : [0, 'auto']}
                allowDecimals
              />
              <Tooltip content={<ChartTooltip unit={unit} metric={metric} />} />
              {threshold !== undefined ? (
                <ReferenceLine y={threshold} stroke="rgb(var(--danger))" strokeDasharray="4 4" label={{ value: thresholdLabel || 'alert threshold', ...AXIS_TICK, fill: 'rgb(var(--danger))', position: 'insideTopRight' }} />
              ) : null}
              <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.75} fill={`url(#${gradientId})`} connectNulls={false} isAnimationActive={false} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

export default TimeSeriesChart;
