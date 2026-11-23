// Formatting helpers. All timestamps from the API are UTC ISO strings; they are
// shown in the viewer's local time with the UTC value available as a tooltip.

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export function formatTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function utcTitle(value) {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
}

export function timeAgo(value) {
  if (!value) return '—';
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (Number.isNaN(seconds)) return '—';
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function formatDuration(totalSeconds) {
  if (totalSeconds === null || totalSeconds === undefined || Number.isNaN(totalSeconds)) return '—';
  const seconds = Math.max(0, Math.round(totalSeconds));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
}

/**
 * Format a metric value according to its unit (as declared by the backend's
 * metric catalog). Returns null for missing values so callers can show an
 * explicit "unavailable" state instead of a number.
 */
export function formatMetric(value, unit, key) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  switch (unit) {
    case 'state':
      return value >= 1 ? 'Up' : 'Down';
    case 'req/s':
      return `${value.toFixed(2)} req/s`;
    case 'ratio':
      return `${(value * 100).toFixed(value > 0 && value < 0.1 ? 2 : 1)}%`;
    case 'seconds':
      if (key === 'uptime') return formatDuration(value);
      return value < 1 ? `${Math.round(value * 1000)} ms` : `${value.toFixed(2)} s`;
    case 'cores':
      return `${(value * 100).toFixed(1)}%`;
    case 'bytes':
      return formatBytes(value);
    default:
      return String(Math.round(value * 100) / 100);
  }
}

/** Axis tick formatter matching formatMetric but shorter. */
export function formatAxis(value, unit) {
  if (value === null || value === undefined) return '';
  switch (unit) {
    case 'ratio':
      return `${Math.round(value * 100)}%`;
    case 'cores':
      return `${Math.round(value * 100)}%`;
    case 'seconds':
      return value < 1 ? `${Math.round(value * 1000)}ms` : `${value.toFixed(1)}s`;
    case 'bytes':
      return `${Math.round(value / 1024 ** 2)}Mi`;
    case 'state':
      return value >= 1 ? 'up' : 'down';
    default:
      return String(Math.round(value * 100) / 100);
  }
}

export const titleCase = (text = '') =>
  String(text).toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export const humanAction = (action = '') => titleCase(action);
