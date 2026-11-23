import React, { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MessageSquarePlus } from 'lucide-react';
import { errorMessage } from '../api/client';
import { incidentsApi } from '../api/incidents';
import { SimulatedTag } from '../components/DataSourceTag';
import { ConfirmDialog } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { RequestRemediation } from '../components/RequestRemediation';
import { ErrorState, InlineError, LoadingState, Notice } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { Timeline } from '../components/Timeline';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { formatDateTime, titleCase, utcTitle } from '../utils/format';

const ACTIVE_REMEDIATION = ['PENDING_APPROVAL', 'APPROVED', 'QUEUED', 'RUNNING', 'VERIFYING'];

const TRANSITION_UI = {
  ACKNOWLEDGED: { label: 'Acknowledge', description: 'Confirm that someone is looking at this incident.', note: 'Note', required: false },
  IN_PROGRESS: { label: 'Start work', description: 'Mark the incident as being actively worked on.', note: 'Note', required: false },
  RESOLVED: {
    label: 'Resolve',
    description:
      'An incident can only be resolved with evidence. Describe how recovery was verified. The request is refused while Prometheus still reports the alert as firing.',
    note: 'Resolution evidence',
    required: true,
    min: 10,
  },
  CLOSED: { label: 'Close', description: 'Close the incident after review. Closed incidents are final.', note: 'Closing note', required: false },
  OPEN: { label: 'Reopen', description: 'Reopen this resolved incident.', note: 'Reason for reopening', required: true, min: 10 },
};

function Section({ title, children, action }) {
  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">{title}</h2>
        {action}
      </div>
      <div className="card-body">{children}</div>
    </section>
  );
}

function BulletList({ items }) {
  if (!items?.length) return <p className="text-sm text-muted">None documented.</p>;
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm text-content">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default function IncidentDetail() {
  const { id } = useParams();
  const { isAdmin, can } = useAuth();
  const { notify } = useToast();
  const { data: incident, error, loading, refreshing, reload, setData } = useApi(() => incidentsApi.get(id), [id], { interval: 8000 });

  const [target, setTarget] = useState(null);
  const [note, setNote] = useState('');
  const [override, setOverride] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');
  const [comment, setComment] = useState('');
  const [commentBusy, setCommentBusy] = useState(false);
  const [commentError, setCommentError] = useState('');

  if (loading && !incident) return <LoadingState label="Loading incident…" />;
  if (error && !incident) return <ErrorState message={error} onRetry={reload} />;

  const closeDialog = () => {
    setTarget(null);
    setNote('');
    setOverride(false);
    setDialogError('');
  };

  const applyTransition = async () => {
    setBusy(true);
    setDialogError('');
    try {
      const updated = await incidentsApi.transition(incident.id, target, note.trim(), override);
      setData(updated);
      notify(`Incident marked ${titleCase(updated.status)}.`);
      closeDialog();
    } catch (err) {
      setDialogError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const addComment = async (event) => {
    event.preventDefault();
    setCommentBusy(true);
    setCommentError('');
    try {
      await incidentsApi.comment(incident.id, comment.trim());
      setComment('');
      reload();
    } catch (err) {
      setCommentError(errorMessage(err));
    } finally {
      setCommentBusy(false);
    }
  };

  const recommendation = incident.recommendation || {};
  const activeRequest = incident.remediation_requests.find((request) => ACTIVE_REMEDIATION.includes(request.status));
  const ui = target ? TRANSITION_UI[target] : null;
  const timeline = incident.events.map((event) => ({
    id: event.id,
    at: event.created_at,
    title: titleCase(event.event_type),
    actor: event.actor_label,
    details: event.details,
    from: event.previous_state,
    to: event.new_state,
  }));

  return (
    <>
      <PageHeader
        back={{ to: '/incidents', label: 'Incidents' }}
        title={`INC-${incident.id} · ${incident.title}`}
        onRefresh={reload}
        refreshing={refreshing}
        actions={
          can('incidents:update')
            ? incident.allowed_transitions.map((status) => (
                <button
                  key={status}
                  type="button"
                  className={status === 'RESOLVED' ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
                  onClick={() => setTarget(status)}
                >
                  {TRANSITION_UI[status]?.label || titleCase(status)}
                </button>
              ))
            : null
        }
      >
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={incident.status} />
          <StatusBadge status={incident.severity} />
          <StatusBadge status={incident.alert_active ? 'FIRING' : 'UP'} label={incident.alert_active ? 'Alert firing' : 'Alert cleared'} />
          {incident.is_simulated ? <SimulatedTag title={incident.simulation_note} /> : null}
          {incident.signal_stale ? <StatusBadge tone="warning" label="Signal stale" /> : null}
        </div>
      </PageHeader>

      <InlineError message={error} onRetry={reload} className="mb-4" />
      {incident.is_simulated ? (
        <Notice tone="warning" className="mb-4">
          {incident.simulation_note} The alert and telemetry are real; the fault was injected deliberately for demonstration.
        </Notice>
      ) : null}
      {incident.signal_stale ? (
        <Notice tone="warning" className="mb-4">
          Alertmanager has not repeated this alert for several minutes although it is recorded as firing. Check the monitoring pipeline on the Monitoring page.
        </Notice>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Section title="Details">
            <p className="mb-4 text-sm text-content">{incident.description || 'No description was provided by the alert.'}</p>
            <dl className="kv">
              <dt>Affected resource</dt>
              <dd>{incident.affected_resource}</dd>
              <dt>Source</dt>
              <dd>
                {incident.source} · alert <span className="font-mono text-xs">{incident.alert_name}</span>
              </dd>
              <dt>Alert fingerprint</dt>
              <dd className="font-mono text-xs">{incident.alert_fingerprint}</dd>
              <dt>Detected</dt>
              <dd title={utcTitle(incident.detected_at)}>{formatDateTime(incident.detected_at)}</dd>
              <dt>Latest occurrence</dt>
              <dd title={utcTitle(incident.last_occurrence_at)}>
                {formatDateTime(incident.last_occurrence_at)} · {incident.occurrence_count} notification{incident.occurrence_count === 1 ? '' : 's'} received
              </dd>
              <dt>Acknowledged</dt>
              <dd title={utcTitle(incident.acknowledged_at)}>{formatDateTime(incident.acknowledged_at)}</dd>
              <dt>Resolved</dt>
              <dd title={utcTitle(incident.resolved_at)}>{formatDateTime(incident.resolved_at)}</dd>
              {incident.resolution_summary ? (
                <>
                  <dt>Resolution</dt>
                  <dd>{incident.resolution_summary}</dd>
                </>
              ) : null}
            </dl>
          </Section>

          <Section title="Recommendation">
            <p className="mb-3 text-sm text-content">{recommendation.problem}</p>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="mb-1.5 eyebrow">Possible causes</h3>
                <BulletList items={recommendation.possible_causes} />
              </div>
              <div>
                <h3 className="mb-1.5 eyebrow">Recommended steps</h3>
                <BulletList items={recommendation.recommended_steps} />
              </div>
            </div>
            {recommendation.troubleshooting?.length ? (
              <div className="mt-4">
                <h3 className="mb-1.5 eyebrow">Troubleshooting notes</h3>
                <BulletList items={recommendation.troubleshooting} />
              </div>
            ) : null}
            <div className="mt-4">
              <RequestRemediation automation={recommendation.automation} sourceType="incident" sourceId={incident.id} activeRequest={activeRequest} />
            </div>
          </Section>

          <Section title="Timeline">
            <Timeline items={timeline} />
            {can('incidents:update') ? (
              <form className="mt-5 border-t border-line pt-4" onSubmit={addComment}>
                <label className="label" htmlFor="incident-comment">
                  Add a note to the timeline
                </label>
                <textarea
                  id="incident-comment"
                  rows={2}
                  maxLength={2000}
                  className="input"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="What did you check or find?"
                />
                {commentError ? <p role="alert" className="mt-1 text-xs text-danger">{commentError}</p> : null}
                <button type="submit" className="btn-secondary btn-sm mt-2" disabled={commentBusy || comment.trim().length < 2}>
                  <MessageSquarePlus size={14} aria-hidden="true" /> {commentBusy ? 'Adding…' : 'Add note'}
                </button>
              </form>
            ) : null}
          </Section>
        </div>

        <div className="space-y-4">
          <Section title="Linked remediation">
            {incident.remediation_requests.length === 0 ? (
              <p className="text-sm text-muted">No remediation has been requested for this incident.</p>
            ) : (
              <ul className="space-y-2">
                {incident.remediation_requests.map((request) => (
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
          </Section>

          <Section title="Alert labels">
            <dl className="space-y-1.5">
              {Object.entries(incident.labels || {}).map(([key, value]) => (
                <div key={key} className="flex flex-wrap gap-x-2 text-xs">
                  <dt className="font-mono text-muted">{key}</dt>
                  <dd className="break-all font-mono text-content">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </Section>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(target)}
        title={ui ? `${ui.label} incident INC-${incident.id}` : ''}
        description={ui?.description}
        confirmLabel={ui?.label}
        busy={busy}
        error={dialogError}
        noteLabel={ui?.note}
        noteRequired={ui?.required}
        noteMinLength={ui?.min || 0}
        note={note}
        onNoteChange={setNote}
        extra={
          target === 'RESOLVED' && isAdmin && incident.alert_active ? (
            <label className="mt-3 flex items-start gap-2 text-xs text-muted">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[rgb(var(--brand))]" checked={override} onChange={(event) => setOverride(event.target.checked)} />
              <span>
                Administrator override: resolve even if monitoring cannot confirm that the alert cleared. The override and your evidence are recorded in the audit trail.
              </span>
            </label>
          ) : null
        }
        onConfirm={applyTransition}
        onClose={closeDialog}
      />
    </>
  );
}
