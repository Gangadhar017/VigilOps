import React from 'react';
import { titleCase } from '../utils/format';

const TONES = {
  success: 'border-ok/40 bg-ok/10 text-ok',
  danger: 'border-danger/40 bg-danger/10 text-danger',
  warning: 'border-warn/40 bg-warn/10 text-warn',
  info: 'border-info/40 bg-info/10 text-info',
  brand: 'border-brand/40 bg-brand/10 text-brand',
  neutral: 'border-line bg-raised text-muted',
};

// One place that decides how every status / severity in the platform looks.
const STATUS_TONE = {
  // severities
  CRITICAL: 'danger', HIGH: 'warning', MEDIUM: 'info', LOW: 'neutral',
  // incidents
  OPEN: 'danger', ACKNOWLEDGED: 'warning', IN_PROGRESS: 'info', RESOLVED: 'success', CLOSED: 'neutral',
  // findings
  REMEDIATION_PENDING: 'info', ACCEPTED_RISK: 'neutral',
  // remediation
  PENDING_APPROVAL: 'warning', APPROVED: 'info', REJECTED: 'neutral', QUEUED: 'info', RUNNING: 'brand',
  VERIFYING: 'brand', SUCCEEDED: 'success', FAILED: 'danger', CANCELLED: 'neutral',
  // scans / audit / generic
  COMPLETED: 'success', SUCCESS: 'success', FAILURE: 'danger', DENIED: 'warning',
  UP: 'success', DOWN: 'danger', UNKNOWN: 'neutral', FIRING: 'danger', PENDING: 'warning',
  ADMIN: 'brand', OPERATOR: 'info', ACTIVE: 'success', INACTIVE: 'neutral',
};

export function toneFor(status) {
  return STATUS_TONE[String(status || '').toUpperCase()] || 'neutral';
}

export function StatusBadge({ status, label, tone, icon: Icon, className = '' }) {
  const resolved = tone || toneFor(status);
  return (
    <span className={`badge ${TONES[resolved] || TONES.neutral} ${className}`}>
      {Icon ? <Icon size={12} aria-hidden="true" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />}
      {label || titleCase(status || 'unknown')}
    </span>
  );
}

export default StatusBadge;
