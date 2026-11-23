import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, EyeOff, Info, LogIn } from 'lucide-react';
import { errorMessage } from '../api/client';
import { Brand } from '../components/Sidebar';
import { Spinner } from '../components/States';
import { useAuth } from '../context/AuthContext';
import { useServerStatus } from '../hooks/useServerStatus';

// What the console brings together, in the order of the navigation.
const CAPABILITIES = [
  ['01', 'Monitoring', 'Live telemetry from Prometheus. A value that cannot be read is shown as unavailable, never estimated.'],
  ['02', 'Incidents', 'Opened by real alerts, deduplicated, and resolved only with evidence.'],
  ['03', 'Security findings', 'Cloud configuration scanned against rules SEC-001 to SEC-005.'],
  ['04', 'Remediation', 'Requested, approved by an Administrator, executed by a restricted worker, then verified.'],
];

/** Dark introduction panel beside the form (above it on small screens). */
function Introduction() {
  return (
    <div className="relative flex flex-col justify-between overflow-hidden bg-chrome px-6 py-7 text-chrome-text sm:px-10 lg:w-[46%] lg:max-w-[640px] lg:px-12 lg:py-10">
      <div className="dotgrid-chrome pointer-events-none absolute inset-0" aria-hidden="true" />
      <div
        className="pointer-events-none absolute -left-32 -top-40 h-[420px] w-[420px] rounded-full opacity-[0.16] blur-3xl"
        style={{ background: 'rgb(var(--accent))' }}
        aria-hidden="true"
      />
      <div className="relative">
        <Brand onChrome />
      </div>

      <div className="relative mt-8 lg:mt-0">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-accent">Operations and security console</p>
        <p className="mt-3 max-w-md text-[26px] font-semibold leading-[1.15] tracking-tight sm:text-[32px]">
          See it, decide it, fix it, and keep the record.
        </p>
        <ul className="mt-8 hidden max-w-md divide-y divide-chrome-line border-y border-chrome-line lg:block">
          {CAPABILITIES.map(([index, name, text]) => (
            <li key={index} className="flex gap-4 py-3.5">
              <span className="pt-0.5 font-mono text-[10.5px] text-chrome-muted">{index}</span>
              <div>
                <p className="text-[13px] font-medium">{name}</p>
                <p className="mt-0.5 text-[12.5px] leading-5 text-chrome-muted">{text}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <p className="relative mt-8 hidden font-mono text-[10px] uppercase tracking-[0.14em] text-chrome-muted/80 lg:block">
        Every action is recorded in the audit trail
      </p>
    </div>
  );
}

export default function Login() {
  const { user, loading, login, sessionMessage } = useAuth();
  const server = useServerStatus();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const destination = location.state?.from && location.state.from !== '/login' ? location.state.from : '/';
  if (!loading && user) return <Navigate to={destination} replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(destination, { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Sign-in failed. Please try again.'));
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  };

  const banner = 'mt-5 flex items-start gap-2.5 rounded-md border border-l-2 px-3 py-2.5 text-[13px] leading-5 text-content';

  return (
    <div className="flex min-h-screen flex-col bg-canvas lg:flex-row">
      <Introduction />

      <div className="flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-[380px]">
          <p className="eyebrow">Sign-in required</p>
          <h1 className="mt-2 text-[26px] leading-8 text-content">Sign in</h1>
          <p className="mt-1.5 text-[13px] leading-5 text-muted">Use your VigilOps account to access the operations platform.</p>

          {sessionMessage && !error ? (
            <p className={`${banner} border-info/25 border-l-info bg-info/[0.07]`}>
              <Info size={15} className="mt-0.5 shrink-0 text-info" aria-hidden="true" />
              {sessionMessage}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className={`${banner} border-danger/30 border-l-danger bg-danger/[0.07]`}>
              <AlertCircle size={15} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
              {error}
            </p>
          ) : null}
          {server.status === 'starting' && !error ? (
            <p role="status" className={`${banner} border-info/25 border-l-info bg-info/[0.07]`}>
              <Spinner size={15} className="mt-0.5 shrink-0 text-info" />
              <span>
                The server is starting. On hosting that sleeps when nobody is using it, this takes about a minute. You can sign in as soon
                as it is ready; there is no need to reload the page.
              </span>
            </p>
          ) : null}
          {server.status === 'unreachable' && !error ? (
            <p role="alert" className={`${banner} border-danger/30 border-l-danger bg-danger/[0.07]`}>
              <AlertCircle size={15} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
              <span>
                The server is not answering.{' '}
                <button type="button" className="font-medium underline underline-offset-2" onClick={server.retry}>
                  Check again
                </button>
              </span>
            </p>
          ) : null}

          <form className="mt-7 space-y-4" onSubmit={submit} noValidate>
            <div>
              <label className="label" htmlFor="email">
                E-mail
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                required
                autoFocus
                className="input h-10"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  className="input h-10 pr-10"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-3 text-muted transition-colors hover:text-content"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              className="btn-primary h-10 w-full text-sm"
              disabled={submitting || !email.trim() || !password || server.status === 'starting'}
            >
              {submitting ? <Spinner size={16} /> : <LogIn size={16} aria-hidden="true" />}
              {submitting ? 'Signing in…' : server.status === 'starting' ? 'Waiting for the server…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-8 border-t border-line pt-4 text-xs leading-5 text-muted">
            Accounts are created by an Administrator. There is no self-registration.
          </p>
        </div>
      </div>
    </div>
  );
}
