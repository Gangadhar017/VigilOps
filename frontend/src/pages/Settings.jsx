import React, { useState } from 'react';
import { AlertTriangle, Check, FlaskConical, KeyRound, Minus, RotateCcw, UserPlus } from 'lucide-react';
import { authApi } from '../api/auth';
import { errorMessage } from '../api/client';
import { demoApi, settingsApi, usersApi } from '../api/settings';
import { ConfirmDialog, Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, InlineError, LoadingState, Notice, Spinner } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { useApi } from '../hooks/useApi';
import { formatDateTime, timeAgo, utcTitle } from '../utils/format';

const PASSWORD_HINT = 'At least 10 characters with upper-case and lower-case letters and a digit.';

/* ------------------------------------------------------------------ Profile */
function ProfileTab() {
  const { user, logout } = useAuth();
  const { notify } = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (next !== confirm) {
      setError('The new passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      await authApi.changePassword(current, next);
      notify('Password changed. Please sign in again.');
      await logout(); // every existing session was invalidated by the backend
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Your account</h2>
        </div>
        <dl className="kv card-body">
          <dt>Name</dt>
          <dd>{user.full_name || '—'}</dd>
          <dt>E-mail</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd>
            <StatusBadge status={user.role} label={user.role === 'admin' ? 'Administrator' : 'Operator'} />
          </dd>
          <dt>Last sign-in</dt>
          <dd title={utcTitle(user.last_login_at)}>{formatDateTime(user.last_login_at)}</dd>
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Change password</h2>
        </div>
        <form className="card-body space-y-3" onSubmit={submit}>
          <div>
            <label className="label" htmlFor="pw-current">Current password</label>
            <input id="pw-current" type="password" autoComplete="current-password" className="input" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </div>
          <div>
            <label className="label" htmlFor="pw-new">New password</label>
            <input id="pw-new" type="password" autoComplete="new-password" className="input" value={next} onChange={(e) => setNext(e.target.value)} required />
            <p className="field-hint">{PASSWORD_HINT}</p>
          </div>
          <div>
            <label className="label" htmlFor="pw-confirm">Confirm new password</label>
            <input id="pw-confirm" type="password" autoComplete="new-password" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
          </div>
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          <button type="submit" className="btn-primary" disabled={busy || !current || !next || !confirm}>
            {busy ? <Spinner size={15} /> : <KeyRound size={15} aria-hidden="true" />} Change password
          </button>
          <p className="field-hint">Changing your password signs out all of your sessions.</p>
        </form>
      </section>
    </div>
  );
}

/* -------------------------------------------------------------------- Users */
function UsersTab() {
  const { user: me } = useAuth();
  const { notify } = useToast();
  const { data, error, loading, reload } = useApi(() => usersApi.list({ page_size: 100, sort: 'email', order: 'asc' }), []);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'operator' });
  const [resetting, setResetting] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const act = async (work, success) => {
    setBusy(true);
    setFormError('');
    try {
      await work();
      notify(success);
      reload();
      return true;
    } catch (err) {
      setFormError(errorMessage(err));
      notify(errorMessage(err), 'error');
      return false;
    } finally {
      setBusy(false);
    }
  };

  const create = async (event) => {
    event.preventDefault();
    if (await act(() => usersApi.create(form), `User ${form.email} created.`)) {
      setCreating(false);
      setForm({ email: '', full_name: '', password: '', role: 'operator' });
    }
  };

  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;

  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">Users</h2>
        <button type="button" className="btn-primary btn-sm" onClick={() => { setCreating(true); setFormError(''); }}>
          <UserPlus size={14} aria-hidden="true" /> Add user
        </button>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">User</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
              <th scope="col">Last sign-in</th>
              <th scope="col" className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((user) => (
              <tr key={user.id}>
                <td>
                  <p className="font-medium text-content">{user.full_name || user.email}</p>
                  <p className="text-xs text-muted">{user.email}{user.id === me.id ? ' · you' : ''}</p>
                </td>
                <td>
                  <select
                    aria-label={`Role of ${user.email}`}
                    className="input w-auto py-1 text-xs"
                    value={user.role}
                    disabled={busy}
                    onChange={(event) => act(() => usersApi.update(user.id, { role: event.target.value }), `Role of ${user.email} updated.`)}
                  >
                    <option value="operator">Operator</option>
                    <option value="admin">Administrator</option>
                  </select>
                </td>
                <td><StatusBadge status={user.is_active ? 'ACTIVE' : 'INACTIVE'} /></td>
                <td className="text-xs text-muted" title={utcTitle(user.last_login_at)}>{user.last_login_at ? timeAgo(user.last_login_at) : 'never'}</td>
                <td>
                  <div className="flex justify-end gap-2">
                    <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={() => { setResetting(user); setNewPassword(''); setFormError(''); }}>
                      Reset password
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      disabled={busy || user.id === me.id}
                      onClick={() => act(() => usersApi.update(user.id, { is_active: !user.is_active }), `${user.email} ${user.is_active ? 'deactivated' : 'reactivated'}.`)}
                    >
                      {user.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={creating} title="Add user" onClose={() => setCreating(false)} size="sm">
        <form className="space-y-3" onSubmit={create}>
          <div>
            <label className="label" htmlFor="new-email">E-mail</label>
            <input id="new-email" data-autofocus type="email" required className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="new-name">Full name</label>
            <input id="new-name" className="input" maxLength={120} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </div>
          <div>
            <label className="label" htmlFor="new-role">Role</label>
            <select id="new-role" className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="operator">Operator</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="new-password">Initial password</label>
            <input id="new-password" type="password" autoComplete="new-password" required className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <p className="field-hint">{PASSWORD_HINT}</p>
          </div>
          {formError ? <p role="alert" className="text-sm text-danger">{formError}</p> : null}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-secondary" onClick={() => setCreating(false)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={busy}>Create user</button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(resetting)} title={`Reset password for ${resetting?.email || ''}`} onClose={() => setResetting(null)} size="sm">
        <form
          className="space-y-3"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await act(() => usersApi.resetPassword(resetting.id, newPassword), `Password reset for ${resetting.email}.`)) setResetting(null);
          }}
        >
          <div>
            <label className="label" htmlFor="reset-password">New password</label>
            <input id="reset-password" data-autofocus type="password" autoComplete="new-password" required className="input" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            <p className="field-hint">{PASSWORD_HINT} The user's existing sessions are signed out.</p>
          </div>
          {formError ? <p role="alert" className="text-sm text-danger">{formError}</p> : null}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-secondary" onClick={() => setResetting(null)}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={busy || !newPassword}>Reset password</button>
          </div>
        </form>
      </Modal>
    </section>
  );
}

/* ----------------------------------------------------------------- Platform */
function RuntimeSetting({ item, canManage, onSaved }) {
  const { notify } = useToast();
  const [value, setValue] = useState(item.value);
  const [busy, setBusy] = useState(false);
  const dirty = value !== item.value;

  const save = async (nextValue) => {
    setBusy(true);
    try {
      await settingsApi.update(item.key, nextValue);
      notify(`${item.label} updated.`);
      onSaved();
    } catch (err) {
      notify(errorMessage(err), 'error');
      setValue(item.value);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-wrap items-start justify-between gap-3 p-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-content">{item.label}</p>
        <p className="mt-0.5 text-xs text-muted">{item.description}</p>
        <p className="mt-1 font-mono text-[11px] text-muted">{item.key} · default {String(item.default)}</p>
      </div>
      {item.type === 'bool' ? (
        <button
          type="button"
          role="switch"
          aria-checked={Boolean(value)}
          aria-label={item.label}
          disabled={!canManage || busy}
          onClick={() => { setValue(!value); save(!value); }}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${value ? 'bg-brand' : 'bg-line'}`}
        >
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${value ? 'left-[22px]' : 'left-0.5'}`} />
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <input
            type="number"
            aria-label={item.label}
            className="input w-24 py-1.5"
            min={item.minimum ?? undefined}
            max={item.maximum ?? undefined}
            value={value}
            disabled={!canManage || busy}
            onChange={(event) => setValue(event.target.value === '' ? '' : Number(event.target.value))}
          />
          {canManage ? (
            <button type="button" className="btn-secondary btn-sm" disabled={!dirty || busy || value === ''} onClick={() => save(value)}>
              Save
            </button>
          ) : null}
        </div>
      )}
    </li>
  );
}

function PlatformTab({ data, reload }) {
  const { system, assistant, scanner, remediation } = data;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="card lg:col-span-2">
        <div className="card-header">
          <h2 className="card-title">Runtime settings</h2>
          {!data.can_manage ? <span className="text-xs text-muted">Read-only for your role</span> : null}
        </div>
        <ul className="divide-y divide-line">
          {data.runtime_settings.map((item) => (
            <RuntimeSetting key={`${item.key}-${String(item.value)}`} item={item} canManage={data.can_manage} onSaved={reload} />
          ))}
        </ul>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">System</h2>
        </div>
        <dl className="kv card-body">
          <dt>Platform</dt>
          <dd>{system.project} · v{system.version}</dd>
          <dt>Environment</dt>
          <dd className="capitalize">{system.environment}</dd>
          <dt>Demo controls</dt>
          <dd>{system.demo_controls_enabled ? 'Enabled' : 'Disabled'}</dd>
          <dt>Session length</dt>
          <dd>{system.session_minutes} minutes</dd>
          <dt>Login rate limit</dt>
          <dd>{system.login_rate_limit.attempts} failed attempts per {Math.round(system.login_rate_limit.window_seconds / 60)} minutes</dd>
          <dt>API documentation</dt>
          <dd>{system.api_docs_enabled ? 'Enabled (development)' : 'Disabled'}</dd>
        </dl>
        {system.placeholder_secrets_in_use ? (
          <Notice tone="warning" icon={AlertTriangle} className="m-4 mt-0">
            This server is using the placeholder secrets from <code>.env.example</code>. That is acceptable for local development only; generate real values with{' '}
            <code>python scripts/generate_env.py</code> before sharing or deploying.
          </Notice>
        ) : null}
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">VigilAI</h2>
          <StatusBadge tone={assistant.api_key_configured ? 'success' : 'info'} label={assistant.api_key_configured ? 'Live AI configured' : 'Documentation mode'} />
        </div>
        <dl className="kv card-body">
          <dt>Provider</dt>
          <dd className="capitalize">{assistant.provider}</dd>
          <dt>Model</dt>
          <dd className="font-mono text-xs">{assistant.model || '—'}</dd>
          <dt>API key</dt>
          <dd>{assistant.api_key_configured ? 'Configured on the server (never shown)' : 'Not configured - set GEMINI_API_KEY in .env and restart the backend'}</dd>
          <dt>Rate limits</dt>
          <dd>{assistant.rate_limit_per_minute} messages per user per minute · {assistant.daily_request_limit || 'no'} AI requests per day</dd>
          <dt>Timeout</dt>
          <dd>{assistant.timeout_seconds} seconds</dd>
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Security scanner</h2>
        </div>
        <dl className="kv card-body">
          <dt>Scope</dt>
          <dd>{scanner.workspace}</dd>
          <dt>Max file size</dt>
          <dd>{Math.round(scanner.max_file_bytes / 1024)} KiB</dd>
          <dt>Remediation allowlist</dt>
          <dd className="font-mono text-xs">{scanner.remediation_writable_targets.join(', ') || '—'}</dd>
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Remediation</h2>
          <StatusBadge status={remediation.worker.online ? 'UP' : 'DOWN'} label={remediation.worker.online ? 'Worker online' : 'Worker offline'} />
        </div>
        <dl className="kv card-body">
          <dt>Worker</dt>
          <dd>{remediation.worker.worker_id || '—'}{remediation.worker.last_seen_at ? ` · heartbeat ${timeAgo(remediation.worker.last_seen_at)}` : ''}</dd>
          <dt>Max attempts</dt>
          <dd>{remediation.max_attempts}</dd>
          <dt>Action timeout</dt>
          <dd>{remediation.action_timeout_seconds} seconds</dd>
          <dt>Verification timeout</dt>
          <dd>{remediation.verification_timeout_seconds} seconds</dd>
        </dl>
      </section>
    </div>
  );
}

/* -------------------------------------------------------------- Permissions */
function PermissionsTab({ matrix }) {
  const Mark = ({ allowed }) => (allowed ? <Check size={16} className="mx-auto text-ok" aria-label="allowed" /> : <Minus size={16} className="mx-auto text-muted" aria-label="not allowed" />);
  return (
    <section className="card">
      <div className="card-header">
        <h2 className="card-title">Role permission matrix</h2>
        <span className="text-xs text-muted">Enforced by the backend on every request</span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Permission</th>
              <th scope="col" className="text-center">Administrator</th>
              <th scope="col" className="text-center">Operator</th>
            </tr>
          </thead>
          <tbody>
            {matrix.map((row) => (
              <tr key={row.permission}>
                <td>
                  <p className="text-content">{row.description}</p>
                  <p className="font-mono text-[11px] text-muted">{row.permission}</p>
                </td>
                <td><Mark allowed={row.admin} /></td>
                <td><Mark allowed={row.operator} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------ Demo controls */
function DemoTab() {
  const { can } = useAuth();
  const { notify } = useToast();
  const { data, error, loading, reload } = useApi(() => demoApi.status(), [], { interval: 5000 });
  const [pending, setPending] = useState(null); // fault mode or 'reset'
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');

  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} onRetry={reload} />;
  if (!data.enabled)
    return (
      <div className="card">
        <EmptyState
          icon={FlaskConical}
          title="Demonstration controls are disabled"
          description={`This server runs in ${data.environment} mode with demo controls turned off. They are never available in production.`}
        />
      </div>
    );

  const allowed = can('demo:control');
  const current = data.demo_app?.fault_mode;

  const confirm = async () => {
    setBusy(true);
    setDialogError('');
    try {
      if (pending === 'reset') {
        const result = await demoApi.resetConfig();
        notify(`Sample configuration restored and scanned: ${result.scan.result_summary.violations_detected} violation(s) detected.`);
      } else {
        await demoApi.injectFault(pending);
        notify(pending === 'none' ? 'Fault cleared on the demo application.' : `Controlled fault "${pending}" injected. Watch Monitoring and Incidents.`);
      }
      setPending(null);
      reload();
    } catch (err) {
      setDialogError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Notice tone="warning" icon={FlaskConical}>
        These controls exist only for the local demonstration environment. They deliberately break the demo application or restore an insecure sample configuration so the
        platform's detection and remediation can be shown. Everything they trigger is labelled as simulated and recorded in the audit trail.
      </Notice>
      <InlineError message={error} onRetry={reload} />
      {!allowed ? <Notice tone="neutral">Only an Administrator can use the demonstration controls.</Notice> : null}

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Controlled faults on the demo application</h2>
          {!allowed ? null : data.demo_app_reachable ? (
            <StatusBadge tone={current && current !== 'none' ? 'warning' : 'success'} label={current && current !== 'none' ? `Active fault: ${current}` : 'No fault active'} />
          ) : (
            <StatusBadge status="DOWN" label="Demo app unreachable" />
          )}
        </div>
        <ul className="divide-y divide-line">
          {Object.entries(data.fault_modes)
            .filter(([mode]) => mode !== 'none')
            .map(([mode, description]) => (
              <li key={mode} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium capitalize text-content">{mode}</p>
                  <p className="text-xs text-muted">{description}</p>
                </div>
                <button type="button" className="btn-secondary btn-sm" disabled={!allowed || current === mode} onClick={() => setPending(mode)}>
                  {current === mode ? 'Active' : 'Inject'}
                </button>
              </li>
            ))}
        </ul>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line p-4">
          <p className="text-xs text-muted">
            To demonstrate remediation, recover through an incident (ACTION-001). "Clear fault" restores the application directly, without the approval workflow.
          </p>
          <button type="button" className="btn-secondary btn-sm" disabled={!allowed || !current || current === 'none'} onClick={() => setPending('none')}>
            Clear fault
          </button>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Sample cloud configuration</h2>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 p-4">
          <p className="min-w-0 flex-1 text-sm text-muted">
            Restores <code>cloud-infrastructure.yaml</code> in the scan workspace to its insecure baseline (violating SEC-001 to SEC-005) and runs a scan. The restricted worker
            performs the restore; existing findings are kept and reopen when the violations return.
          </p>
          <button type="button" className="btn-secondary btn-sm" disabled={!allowed} onClick={() => setPending('reset')}>
            <RotateCcw size={14} aria-hidden="true" /> Reset sample configuration
          </button>
        </div>
      </section>

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending === 'reset' ? 'Reset the sample configuration' : pending === 'none' ? 'Clear the active fault' : `Inject the "${pending}" fault`}
        description={
          pending === 'reset'
            ? 'The sample configuration returns to its insecure baseline and is scanned again.'
            : pending === 'none'
            ? 'The demo application returns to normal operation immediately.'
            : `${data.fault_modes[pending] || ''} Prometheus will observe the change and an alert may open an incident.`
        }
        confirmLabel={pending === 'reset' ? 'Reset' : pending === 'none' ? 'Clear fault' : 'Inject fault'}
        danger={pending !== 'reset' && pending !== 'none'}
        busy={busy}
        error={dialogError}
        onConfirm={confirm}
        onClose={() => { setPending(null); setDialogError(''); }}
      />
    </div>
  );
}

/* --------------------------------------------------------------------- Page */
export default function Settings() {
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi(() => settingsApi.get(), []);
  const [tab, setTab] = useState('profile');

  const tabs = [
    { key: 'profile', label: 'Profile' },
    ...(can('users:manage') ? [{ key: 'users', label: 'Users' }] : []),
    { key: 'platform', label: 'Platform' },
    { key: 'permissions', label: 'Permissions' },
    { key: 'demo', label: 'Demo controls' },
  ];

  return (
    <>
      <PageHeader title="Settings" subtitle="Your account, user management, platform configuration and demonstration controls." />
      <div className="mb-4 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line" role="tablist" aria-label="Settings sections">
        {tabs.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={tab === item.key} className={`tab whitespace-nowrap ${tab === item.key ? 'tab-active' : ''}`} onClick={() => setTab(item.key)}>
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'profile' ? <ProfileTab /> : null}
      {tab === 'users' && can('users:manage') ? <UsersTab /> : null}
      {tab === 'demo' ? <DemoTab /> : null}
      {tab === 'platform' || tab === 'permissions' ? (
        loading && !data ? (
          <LoadingState />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : tab === 'platform' ? (
          <PlatformTab data={data} reload={reload} />
        ) : (
          <PermissionsTab matrix={data.permission_matrix} />
        )
      ) : null}
    </>
  );
}
