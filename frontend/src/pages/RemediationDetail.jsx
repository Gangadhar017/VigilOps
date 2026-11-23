import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Check, CheckCircle2, Circle, Loader2, X, XCircle } from 'lucide-react';
import { errorMessage } from '../api/client';
import { remediationApi } from '../api/remediation';
import { ConfirmDialog } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { ErrorState, InlineError, LoadingState, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { formatDateTime, formatDuration, humanAction, titleCase, utcTitle } from '../utils/format';

const IN_FLIGHT = ['QUEUED', 'RUNNING', 'VERIFYING'];
const STEPS = ['PENDING_APPROVAL', 'APPROVED', 'QUEUED', 'RUNNING', 'VERIFYING', 'SUCCEEDED'];

const OPERATIONS = {
  approve: {
    label: 'Approve',
    title: 'Approve remediation request',
    description: 'Approving records your decision. Nothing is executed until the request is dispatched to the worker.',
    note: 'Comment',
    primary: true,
  },
  reject: {
    label: 'Reject',
    title: 'Reject remediation request',
    description: 'The request is closed and the source returns to its previous state.',
    note: 'Reason',
    required: true,
    min: 5,
    danger: true,
  },
  execute: {
    label: 'Execute',
    title: 'Dispatch to the restricted worker',
    description: 'The approved action is queued for the restricted worker, which executes it and then verifies the result. This changes the target.',
    primary: true,
  },
  retry: {
    label: 'Retry',
    title: 'Retry failed remediation',
    description: 'The request is queued again using its existing approval. Make sure the cause of the failure has been addressed.',
    primary: true,
  },
  cancel: { label: 'Cancel request', title: 'Cancel remediation request', description: 'The request is withdrawn before execution.', note: 'Reason' },
};

function Stepper({ status }) {
  const terminalFailure = ['FAILED', 'REJECTED', 'CANCELLED'].includes(status);
  const currentIndex = STEPS.indexOf(status);
  return (
    <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-2" aria-label="Workflow progress">
      {STEPS.map((step, index) => {
        const done = !terminalFailure && currentIndex > index;
        const current = !terminalFailure && currentIndex === index;
        const success = step === 'SUCCEEDED' && current;
        return (
          <li key={step} className="flex items-center gap-1.5">
            <span
              className={`flex items-center gap-1.5 rounded border px-1.5 py-1 font-mono text-[10.5px] font-medium uppercase leading-none tracking-[0.06em] ${
                done || success ? 'border-ok/30 bg-ok/10 text-ok' : current ? 'border-brand/50 bg-brand/10 text-brand' : 'border-line text-muted'
              }`}
            >
              {done || success ? <Check size={11} strokeWidth={2.5} aria-hidden="true" /> : current && IN_FLIGHT.includes(step) ? <Loader2 size={11} className="animate-spin" aria-hidden="true" /> : <Circle size={8} aria-hidden="true" />}
              {titleCase(step)}
            </span>
            {index < STEPS.length - 1 ? <span className={`h-px w-4 ${done ? 'bg-ok/50' : 'bg-line'}`} aria-hidden="true" /> : null}
          </li>
        );
      })}
      {terminalFailure ? (
        <li>
          <StatusBadge status={status} icon={X} />
        </li>
      ) : null}
    </ol>
  );
}

function Checks({ result }) {
  if (!result?.checks?.length) return result?.summary ? <p className="text-sm text-content">{result.summary}</p> : <p className="text-sm text-muted">Verification has not run.</p>;
  return (
    <>
      <p className={`mb-2 flex items-center gap-2 text-sm font-medium ${result.passed ? 'text-ok' : 'text-danger'}`}>
        {result.passed ? <CheckCircle2 size={16} aria-hidden="true" /> : <XCircle size={16} aria-hidden="true" />}
        {result.summary}
      </p>
      <ul className="space-y-2">
        {result.checks.map((check) => (
          <li key={check.name} className="flex items-start gap-2 rounded-md border border-line px-3 py-2">
            {check.passed ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-ok" aria-label="passed" /> : <XCircle size={15} className="mt-0.5 shrink-0 text-danger" aria-label="failed" />}
            <div className="min-w-0">
              <p className="text-sm font-medium text-content">{titleCase(check.name)}</p>
              <p className="text-xs text-muted">{check.detail}</p>
              <p className="text-[11px] text-muted" title={utcTitle(check.observed_at)}>
                observed {formatDateTime(check.observed_at)}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

function Execution({ execution }) {
  const details = execution.execution_details || {};
  const duration = execution.completed_at ? (new Date(execution.completed_at) - new Date(execution.started_at)) / 1000 : null;
  return (
    <article className="rounded-md border border-line">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-raised/50 px-3 py-2">
        <p className="text-sm font-medium text-content">
          Attempt {execution.attempt} · <span className="font-mono text-xs">{execution.worker_identifier}</span>
        </p>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span title={utcTitle(execution.started_at)}>{formatDateTime(execution.started_at)}</span>
          {duration !== null ? <span>· {formatDuration(duration)}</span> : null}
          <StatusBadge status={execution.status} />
        </div>
      </header>
      <div className="space-y-4 p-3">
        {execution.error ? (
          <p role="alert" className="rounded-md border border-l-2 border-danger/30 border-l-danger bg-danger/[0.07] px-3 py-2 text-[13px] text-content">
            {execution.error}
          </p>
        ) : null}
        <div>
          <h4 className="mb-1.5 eyebrow">Execution</h4>
          {details.operation ? <p className="text-sm text-content">{details.operation}</p> : null}
          {details.changes ? (
            <ul className="mt-1 list-disc pl-5 text-sm text-content">
              {details.changes.map((change) => (
                <li key={change}>
                  <code>{change}</code>
                </li>
              ))}
            </ul>
          ) : null}
          {details.before && details.after ? (
            <dl className="kv mt-2">
              <dt>Before</dt>
              <dd className="font-mono text-xs">{JSON.stringify(details.before)}</dd>
              <dt>After</dt>
              <dd className="font-mono text-xs">{JSON.stringify(details.after)}</dd>
            </dl>
          ) : null}
          {details.before && !details.after ? (
            <p className="mt-1 text-xs text-muted">
              Health before the action: {details.before.ready ? 'ready' : details.before.reachable ? `not ready (HTTP ${details.before.status_code})` : `unreachable (${details.before.error})`}
            </p>
          ) : null}
          {details.recovery_calls ? (
            <p className="mt-1 text-xs text-muted">
              Recovery calls:{' '}
              {details.recovery_calls.map((call) => `#${call.attempt} ${call.status_code ? `HTTP ${call.status_code}` : call.error}`).join(', ')}
            </p>
          ) : null}
          {details.diff ? (
            <details className="mt-2" open>
              <summary className="cursor-pointer text-xs font-medium text-muted hover:text-content">Configuration diff</summary>
              <pre className="mono-block mt-2 whitespace-pre">
                {details.diff.split('\n').map((line, index) => (
                  <span
                    key={index}
                    className={`block ${line.startsWith('+') && !line.startsWith('+++') ? 'text-ok' : line.startsWith('-') && !line.startsWith('---') ? 'text-danger' : 'text-muted'}`}
                  >
                    {line || ' '}
                  </span>
                ))}
              </pre>
            </details>
          ) : null}
          {!details.operation && !execution.error ? <p className="text-sm text-muted">The action is running…</p> : null}
        </div>
        <div>
          <h4 className="mb-1.5 eyebrow">Verification</h4>
          {execution.status === 'VERIFYING' ? (
            <p className="flex items-center gap-2 text-sm text-content">
              <Loader2 size={15} className="animate-spin text-brand" aria-hidden="true" /> Collecting fresh evidence that the problem is gone…
            </p>
          ) : (
            <Checks result={execution.verification_result} />
          )}
        </div>
      </div>
    </article>
  );
}

export default function RemediationDetail() {
  const { id } = useParams();
  const { notify } = useToast();
  const [polling, setPolling] = useState(4000);
  const { data: request, error, loading, refreshing, reload, setData } = useApi(
    async () => {
      const result = await remediationApi.get(id);
      setPolling(IN_FLIGHT.includes(result.status) ? 2500 : 8000); // poll faster while the worker is busy
      return result;
    },
    [id],
    { interval: polling },
  );
  const [operation, setOperation] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');

  if (loading && !request) return <LoadingState label="Loading remediation request…" />;
  if (error && !request) return <ErrorState message={error} onRetry={reload} />;

  const closeDialog = () => {
    setOperation(null);
    setNote('');
    setDialogError('');
  };

  const run = async () => {
    setBusy(true);
    setDialogError('');
    try {
      const call = {
        approve: () => remediationApi.approve(request.id, note.trim()),
        reject: () => remediationApi.reject(request.id, note.trim()),
        execute: () => remediationApi.execute(request.id),
        retry: () => remediationApi.retry(request.id),
        cancel: () => remediationApi.cancel(request.id, note.trim()),
      }[operation];
      const updated = await call();
      setData(updated);
      setPolling(2500);
      notify(`Request #${updated.id} is now ${titleCase(updated.status)}.`);
      closeDialog();
    } catch (err) {
      setDialogError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const ui = operation ? OPERATIONS[operation] : null;
  const source = request.source_summary || {};
  const sourceLink = source.type === 'incident' ? `/incidents/${source.id}` : `/findings/${source.id}`;
  const timeline = request.timeline.map((entry, index) => ({
    id: index,
    at: entry.at,
    title: humanAction(entry.action.replace(/^REMEDIATION_/, '')),
    actor: entry.actor,
    outcome: entry.outcome,
    details: entry.metadata?.summary || entry.metadata?.reason || entry.metadata?.comment || entry.metadata?.justification || '',
  }));

  return (
    <>
      <PageHeader
        back={{ to: '/remediation', label: 'Remediation' }}
        title={`Request #${request.id} · ${request.action_code} ${request.action_name || ''}`}
        onRefresh={reload}
        refreshing={refreshing}
        actions={request.allowed_operations.map((key) => (
          <button
            key={key}
            type="button"
            className={OPERATIONS[key].danger ? 'btn-danger btn-sm' : OPERATIONS[key].primary ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
            onClick={() => setOperation(key)}
          >
            {OPERATIONS[key].label}
          </button>
        ))}
      >
        <div className="mt-3">
          <Stepper status={request.status} />
        </div>
      </PageHeader>

      <InlineError message={error} onRetry={reload} className="mb-4" />
      {request.status === 'PENDING_APPROVAL' && !request.allowed_operations.includes('approve') ? (
        <Notice tone="info" className="mb-4">
          This request is waiting for an Administrator. Requests cannot be approved by the person who submitted them unless self-approval is enabled in Settings, and Operators
          cannot approve or execute remediation.
        </Notice>
      ) : null}
      {request.status === 'FAILED' ? (
        <Notice tone="warning" className="mb-4">
          Remediation failed: {request.failure_reason} The problem is treated as not fixed, so the source {source.type} stays open.
        </Notice>
      ) : null}
      {request.status === 'SUCCEEDED' ? (
        <Notice tone="success" className="mb-4">
          The action was executed and independently verified. See the verification checks below.
        </Notice>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Request</h2>
              <StatusBadge status={request.status} />
            </div>
            <dl className="kv card-body">
              <dt>Source</dt>
              <dd>
                <Link to={sourceLink} className="font-medium text-brand hover:underline">
                  {titleCase(source.type || request.source_type)} #{request.source_id}
                </Link>{' '}
                · {source.title} {source.status ? <StatusBadge status={source.status} className="ml-1" /> : null}
              </dd>
              <dt>Target</dt>
              <dd className="break-all font-mono text-xs">{request.target}</dd>
              <dt>Justification</dt>
              <dd>{request.justification}</dd>
              <dt>Requested by</dt>
              <dd title={utcTitle(request.created_at)}>
                {request.requested_by_email} · {formatDateTime(request.created_at)}
              </dd>
              <dt>Decision</dt>
              <dd title={utcTitle(request.decided_at)}>
                {request.approved_by_email ? `${request.approved_by_email} · ${formatDateTime(request.decided_at)}` : 'Awaiting Administrator decision'}
                {request.decision_comment ? <span className="block text-muted">“{request.decision_comment}”</span> : null}
              </dd>
              <dt>Attempts</dt>
              <dd>
                {request.attempt_count} of {request.max_attempts}
              </dd>
              <dt>Correlation ID</dt>
              <dd className="font-mono text-xs">
                <Link to={`/audit?correlation_id=${request.correlation_id}`} className="text-brand hover:underline">
                  {request.correlation_id}
                </Link>
              </dd>
            </dl>
          </section>

          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Execution and verification</h2>
            </div>
            <div className="card-body space-y-3">
              {request.executions.length === 0 ? (
                <p className="text-sm text-muted">
                  {request.status === 'QUEUED'
                    ? 'Queued: waiting for the restricted worker to pick up the request.'
                    : 'Nothing has been executed. The worker runs the action only after approval and dispatch.'}
                </p>
              ) : (
                [...request.executions].reverse().map((execution) => <Execution key={execution.id} execution={execution} />)
              )}
            </div>
          </section>
        </div>

        <div className="space-y-4">
          {request.action ? (
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Action definition</h2>
              </div>
              <div className="card-body text-sm">
                <p className="text-content">{request.action.description}</p>
                <h3 className="mb-1 mt-3 eyebrow">Steps</h3>
                <ul className="list-disc space-y-1 pl-5 text-xs text-content">
                  {request.action.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
                <h3 className="mb-1 mt-3 eyebrow">Verification</h3>
                <ul className="list-disc space-y-1 pl-5 text-xs text-content">
                  {request.action.verification.map((check) => (
                    <li key={check}>{check}</li>
                  ))}
                </ul>
              </div>
            </section>
          ) : null}
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Audit trail</h2>
            </div>
            <div className="card-body">
              <Timeline items={timeline} />
            </div>
          </section>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(operation)}
        title={ui?.title || ''}
        description={ui?.description}
        confirmLabel={ui?.label}
        danger={ui?.danger}
        busy={busy}
        error={dialogError}
        noteLabel={ui?.note}
        noteRequired={ui?.required}
        noteMinLength={ui?.min || 0}
        note={note}
        onNoteChange={setNote}
        onConfirm={run}
        onClose={closeDialog}
      />
    </>
  );
}
