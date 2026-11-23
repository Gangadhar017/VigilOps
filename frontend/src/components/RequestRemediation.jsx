import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Ban, ListChecks, ShieldCheck, Wrench } from 'lucide-react';
import { errorMessage } from '../api/client';
import { remediationApi } from '../api/remediation';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ConfirmDialog } from './Modal';

/**
 * "Automated remediation" panel shown on incident and finding pages.
 * `automation` comes from the backend ({ supported, action_code, action, reason }).
 * Submitting only creates a request in PENDING_APPROVAL - nothing is executed here.
 */
export function RequestRemediation({ automation, sourceType, sourceId, activeRequest }) {
  const { can } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      const request = await remediationApi.create(sourceType, sourceId, automation.action_code, note.trim());
      notify(`Remediation request #${request.id} submitted for Administrator approval.`);
      navigate(`/remediation/${request.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (!automation?.supported) {
    return (
      <div className="rounded-md border border-line bg-raised/50 p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-content">
          <Ban size={15} className="text-muted" aria-hidden="true" /> Automated remediation is not available
        </p>
        <p className="mt-1 text-sm text-muted">{automation?.reason || 'Follow the recommended steps manually.'}</p>
      </div>
    );
  }

  const action = automation.action;
  return (
    <div className="rounded-md border border-brand/30 bg-brand/5 p-3">
      <p className="flex items-center gap-2 text-sm font-medium text-content">
        <Wrench size={15} className="text-brand" aria-hidden="true" />
        {action.code} · {action.name}
      </p>
      <p className="mt-1 text-sm text-muted">{action.description}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="mb-1 flex items-center gap-1.5 eyebrow">
            <ListChecks size={12} aria-hidden="true" /> What the worker does
          </p>
          <ul className="list-disc space-y-1 pl-5 text-xs text-content">
            {action.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 flex items-center gap-1.5 eyebrow">
            <ShieldCheck size={12} aria-hidden="true" /> How success is verified
          </p>
          <ul className="list-disc space-y-1 pl-5 text-xs text-content">
            {action.verification.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn-primary btn-sm"
          onClick={() => setOpen(true)}
          disabled={!can('remediation:request') || Boolean(activeRequest)}
        >
          Request remediation
        </button>
        <p className="text-xs text-muted">
          {activeRequest
            ? `Request #${activeRequest.id} is already ${activeRequest.status.replace(/_/g, ' ').toLowerCase()}.`
            : 'Requires Administrator approval before anything is executed.'}
        </p>
      </div>

      <ConfirmDialog
        open={open}
        title={`Request ${action.code}`}
        description="The request is sent for Administrator approval. It is executed by the restricted worker only after it has been approved and dispatched."
        confirmLabel="Submit request"
        busy={busy}
        error={error}
        noteLabel="Justification"
        notePlaceholder="Why is this remediation needed?"
        noteRequired
        noteMinLength={10}
        note={note}
        onNoteChange={setNote}
        onConfirm={submit}
        onClose={() => {
          setOpen(false);
          setError('');
        }}
      />
    </div>
  );
}

export default RequestRemediation;
