import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { securityApi } from '../api/security';
import { ConfirmDialog } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { RequestRemediation } from '../components/RequestRemediation';
import { ErrorState, InlineError, LoadingState, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { formatDateTime, humanAction, utcTitle } from '../utils/format';

const ACTIVE_REMEDIATION = ['PENDING_APPROVAL', 'APPROVED', 'QUEUED', 'RUNNING', 'VERIFYING'];

function historyDetails(entry) {
  const meta = entry.metadata || {};
  if (meta.reason) return String(meta.reason);
  if (meta.verification) return `${meta.verification} (scan #${meta.scan_id}).`;
  if (meta.remediation_request_id) return `Remediation request #${meta.remediation_request_id}.`;
  if (meta.scan_id) return `Scan #${meta.scan_id}.`;
  return '';
}

export default function FindingDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const { notify } = useToast();
  const { data: finding, error, loading, refreshing, reload, setData } = useApi(() => securityApi.finding(id), [id], { interval: 8000 });
  const [dialog, setDialog] = useState(null); // 'accept' | 'revoke'
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');

  if (loading && !finding) return <LoadingState label="Loading finding…" />;
  if (error && !finding) return <ErrorState message={error} onRetry={reload} />;

  const closeDialog = () => {
    setDialog(null);
    setReason('');
    setDialogError('');
  };

  const confirm = async () => {
    setBusy(true);
    setDialogError('');
    try {
      const updated = dialog === 'accept' ? await securityApi.acceptRisk(finding.id, reason.trim()) : await securityApi.revokeRiskAcceptance(finding.id);
      setData(updated);
      notify(dialog === 'accept' ? 'Finding marked as accepted risk.' : 'Risk acceptance revoked; the finding is open again.');
      closeDialog();
    } catch (err) {
      setDialogError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const guidance = finding.guidance || {};
  const rule = finding.rule;
  const activeRequest = finding.remediation_requests.find((request) => ACTIVE_REMEDIATION.includes(request.status));
  const timeline = finding.history.map((entry, index) => ({
    id: index,
    at: entry.at,
    title: humanAction(entry.action.replace(/^FINDING_/, '')),
    actor: entry.actor,
    details: historyDetails(entry),
    outcome: entry.outcome,
  }));

  return (
    <>
      <PageHeader
        back={{ to: '/findings', label: 'Security Findings' }}
        title={`${finding.rule_id} · ${finding.rule_name}`}
        onRefresh={reload}
        refreshing={refreshing}
        actions={
          can('findings:accept_risk') ? (
            finding.status === 'OPEN' ? (
              <button type="button" className="btn-secondary btn-sm" onClick={() => setDialog('accept')}>
                Accept risk
              </button>
            ) : finding.status === 'ACCEPTED_RISK' ? (
              <button type="button" className="btn-secondary btn-sm" onClick={() => setDialog('revoke')}>
                Revoke risk acceptance
              </button>
            ) : null
          ) : null
        }
      >
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={finding.status} />
          <StatusBadge status={finding.severity} />
          <span className="tag font-mono">{finding.resource_identifier}</span>
          <span className="tag font-mono">{finding.target_file}</span>
        </div>
      </PageHeader>

      <InlineError message={error} onRetry={reload} className="mb-4" />
      {finding.status === 'RESOLVED' ? (
        <Notice tone="success" className="mb-4">
          Resolved on {formatDateTime(finding.resolved_at)}: a scan verified that {finding.rule_id} is no longer violated for this resource. The finding is kept for history
          and reopens automatically if the violation returns.
        </Notice>
      ) : null}
      {finding.status === 'ACCEPTED_RISK' ? (
        <Notice tone="warning" className="mb-4">
          Accepted risk since {formatDateTime(finding.accepted_risk_at)}: {finding.accepted_risk_reason}
        </Notice>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">What was detected</h2>
            </div>
            <div className="card-body">
              <p className="text-sm text-content">{guidance.problem}</p>
              <dl className="kv mt-4">
                <dt>Affected resource</dt>
                <dd>{guidance.affected_resource}</dd>
                <dt>Evidence</dt>
                <dd>
                  <ul className="list-disc space-y-1 pl-5">
                    {(finding.evidence?.details || [finding.evidence?.summary]).filter(Boolean).map((detail) => (
                      <li key={detail}>{detail}</li>
                    ))}
                  </ul>
                </dd>
                <dt>Detection logic</dt>
                <dd>{guidance.detection_logic}</dd>
                <dt>Security impact</dt>
                <dd>{guidance.security_impact}</dd>
                <dt>First detected</dt>
                <dd title={utcTitle(finding.first_detected_at)}>{formatDateTime(finding.first_detected_at)}</dd>
                <dt>Last seen</dt>
                <dd title={utcTitle(finding.last_seen_at)}>
                  {formatDateTime(finding.last_seen_at)} · detected in {finding.detection_count} scan{finding.detection_count === 1 ? '' : 's'}
                </dd>
              </dl>
              <details className="mt-4">
                <summary className="cursor-pointer text-xs font-medium text-muted hover:text-content">Raw evidence</summary>
                <pre className="mono-block mt-2">{JSON.stringify(finding.evidence?.matches ?? finding.evidence, null, 2)}</pre>
              </details>
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2 className="card-title">How to fix it</h2>
            </div>
            <div className="card-body">
              <p className="text-sm text-content">{guidance.recommendation}</p>
              {guidance.recommended_steps?.length ? (
                <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-content">
                  {guidance.recommended_steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              ) : null}
              {finding.status === 'OPEN' || finding.status === 'REMEDIATION_PENDING' ? (
                <div className="mt-4">
                  <RequestRemediation automation={guidance.automation} sourceType="finding" sourceId={finding.id} activeRequest={activeRequest} />
                </div>
              ) : null}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Remediation requests</h2>
            </div>
            <div className="card-body">
              {finding.remediation_requests.length === 0 ? (
                <p className="text-sm text-muted">No remediation has been requested for this finding.</p>
              ) : (
                <ul className="space-y-2">
                  {finding.remediation_requests.map((request) => (
                    <li key={request.id}>
                      <Link to={`/remediation/${request.id}`} className="flex items-center justify-between gap-2 rounded-md border border-line px-3 py-2 hover:border-brand/50">
                        <span className="text-sm text-content">
                          #{request.id} · {request.action_code}
                        </span>
                        <StatusBadge status={request.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2 className="card-title">History</h2>
            </div>
            <div className="card-body">
              <Timeline items={timeline} />
            </div>
          </section>

          {rule ? (
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Rule</h2>
              </div>
              <dl className="kv card-body">
                <dt>ID</dt>
                <dd className="font-mono text-xs">{rule.id}</dd>
                <dt>Name</dt>
                <dd>{rule.name}</dd>
                <dt>Severity</dt>
                <dd>
                  <StatusBadge status={rule.severity} />
                </dd>
                <dt>Applies to</dt>
                <dd className="font-mono text-xs">{rule.resource_types.join(', ')}</dd>
              </dl>
            </section>
          ) : null}
        </div>
      </div>

      <ConfirmDialog
        open={dialog === 'accept'}
        title="Accept risk for this finding"
        description="The finding will stay visible with the status Accepted risk. Your justification is recorded in the audit trail."
        confirmLabel="Accept risk"
        busy={busy}
        error={dialogError}
        noteLabel="Justification"
        noteRequired
        noteMinLength={10}
        note={reason}
        onNoteChange={setReason}
        onConfirm={confirm}
        onClose={closeDialog}
      />
      <ConfirmDialog
        open={dialog === 'revoke'}
        title="Revoke risk acceptance"
        description="The finding returns to Open and can be remediated again."
        confirmLabel="Revoke"
        busy={busy}
        error={dialogError}
        onConfirm={confirm}
        onClose={closeDialog}
      />
    </>
  );
}
