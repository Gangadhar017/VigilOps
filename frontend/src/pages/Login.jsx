import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, EyeOff, Info, LogIn } from 'lucide-react';
import { errorMessage } from '../api/client';
import { Brand } from '../components/Sidebar';
import { Spinner } from '../components/States';
import { useAuth } from '../context/AuthContext';
import { useServerStatus } from '../hooks/useServerStatus';

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

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex justify-center">
          <Brand />
        </div>
        <div className="card p-6">
          <h1 className="text-lg text-content">Sign in</h1>
          <p className="mt-1 text-sm text-muted">Use your VigilOps account to access the operations platform.</p>

          {sessionMessage && !error ? (
            <p className="mt-4 flex items-start gap-2 rounded-lg border border-info/30 bg-info/10 px-3 py-2 text-sm text-content">
              <Info size={16} className="mt-0.5 shrink-0 text-info" aria-hidden="true" />
              {sessionMessage}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-content">
              <AlertCircle size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
              {error}
            </p>
          ) : null}
          {server.status === 'starting' && !error ? (
            <p role="status" className="mt-4 flex items-start gap-2 rounded-lg border border-info/30 bg-info/10 px-3 py-2 text-sm text-content">
              <Spinner size={16} />
              <span>
                The server is starting. On hosting that sleeps when nobody is using it, this takes about a minute. You can sign in as soon
                as it is ready; there is no need to reload the page.
              </span>
            </p>
          ) : null}
          {server.status === 'unreachable' && !error ? (
            <p role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-content">
              <AlertCircle size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
              <span>
                The server is not answering.{' '}
                <button type="button" className="font-medium underline" onClick={server.retry}>
                  Check again
                </button>
              </span>
            </p>
          ) : null}

          <form className="mt-5 space-y-4" onSubmit={submit} noValidate>
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
                className="input"
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
                  className="input pr-10"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-muted hover:text-content"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              className="btn-primary w-full"
              disabled={submitting || !email.trim() || !password || server.status === 'starting'}
            >
              {submitting ? <Spinner size={16} /> : <LogIn size={16} aria-hidden="true" />}
              {submitting ? 'Signing in…' : server.status === 'starting' ? 'Waiting for the server…' : 'Sign in'}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          Accounts are created by an Administrator. There is no self-registration.
        </p>
      </div>
    </div>
  );
}
