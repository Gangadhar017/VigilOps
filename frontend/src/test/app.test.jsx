import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/auth', () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), changePassword: vi.fn() },
}));
vi.mock('../api/remediation', () => ({
  remediationApi: { create: vi.fn() },
}));
import { authApi } from '../api/auth';
import { errorMessage, tokenStore } from '../api/client';
import { remediationApi } from '../api/remediation';
import { AppRoutes } from '../App';
import { MetricCard } from '../components/MetricCard';
import { RequestRemediation } from '../components/RequestRemediation';
import { StatusBadge, toneFor } from '../components/StatusBadge';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../context/ToastContext';
import { formatBytes, formatDuration, formatMetric } from '../utils/format';

const OPERATOR = { id: 2, email: 'op@test.local', full_name: 'Op', role: 'operator', permissions: ['remediation:request', 'incidents:view'] };

function renderApp(path = '/') {
  return render(
    <AuthProvider>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </ToastProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('formatting', () => {
  it('formats metrics by unit and returns null for missing values', () => {
    expect(formatMetric(1, 'state')).toBe('Up');
    expect(formatMetric(0, 'state')).toBe('Down');
    expect(formatMetric(2.073, 'req/s')).toBe('2.07 req/s');
    expect(formatMetric(0.25, 'ratio')).toBe('25.0%');
    expect(formatMetric(0.0047, 'seconds', 'latency_p95')).toBe('5 ms');
    expect(formatMetric(1.5, 'seconds', 'latency_p95')).toBe('1.50 s');
    expect(formatMetric(0.9, 'cores')).toBe('90.0%');
    expect(formatMetric(55259136, 'bytes')).toBe('52.7 MiB');
    expect(formatMetric(3725, 'seconds', 'uptime')).toBe('1h 2m');
    expect(formatMetric(null, 'req/s')).toBeNull();
    expect(formatMetric(Number.NaN, 'ratio')).toBeNull();
  });

  it('formats durations and sizes', () => {
    expect(formatDuration(42)).toBe('42s');
    expect(formatDuration(125)).toBe('2m 5s');
    expect(formatBytes(1024)).toBe('1.0 KiB');
  });

  it('turns API errors into readable messages', () => {
    expect(errorMessage({ response: { status: 409, data: { detail: 'Invalid transition.' } } })).toBe('Invalid transition.');
    expect(errorMessage({ response: { status: 403, data: {} } })).toMatch(/not permitted/);
    expect(errorMessage({})).toMatch(/Cannot reach the VigilOps API/);
  });
});

describe('shared components', () => {
  it('never shows a number when a metric is unavailable', () => {
    render(<MetricCard label="CPU usage" value={null} unavailableReason="Prometheus: no data" />);
    expect(screen.getByText('Unavailable')).toBeInTheDocument();
    expect(screen.getByText('Prometheus: no data')).toBeInTheDocument();
  });

  it('maps statuses to consistent tones', () => {
    expect(toneFor('CRITICAL')).toBe('danger');
    expect(toneFor('succeeded')).toBe('success');
    expect(toneFor('PENDING_APPROVAL')).toBe('warning');
    render(<StatusBadge status="REMEDIATION_PENDING" />);
    expect(screen.getByText('Remediation Pending')).toBeInTheDocument();
  });
});

describe('authentication flow', () => {
  it('redirects signed-out users to the login page', async () => {
    renderApp('/remediation');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it('shows the backend error on failed sign-in and does not fall back to any account', async () => {
    authApi.login.mockRejectedValue({ response: { status: 401, data: { detail: 'Incorrect e-mail or password.' } } });
    const user = userEvent.setup();
    renderApp('/login');
    await user.type(await screen.findByLabelText('E-mail'), 'someone@test.local');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect e-mail or password.');
    expect(authApi.login).toHaveBeenCalledTimes(1);
    expect(authApi.login).toHaveBeenCalledWith('someone@test.local', 'wrong-password');
    expect(tokenStore.get()).toBeNull();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('drops an invalid stored token instead of trusting it', async () => {
    tokenStore.set('stale-token');
    authApi.me.mockRejectedValue({ response: { status: 401 } });
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
  });
});

describe('RequestRemediation', () => {
  const automation = {
    supported: true,
    action_code: 'ACTION-002',
    action: {
      code: 'ACTION-002',
      name: 'Correct public storage configuration',
      description: 'Updates the allowlisted YAML configuration.',
      steps: ['Set public_access to false.'],
      verification: ['Run the security scanner again.'],
    },
  };

  function renderPanel(props, user = OPERATOR) {
    tokenStore.set('token');
    authApi.me.mockResolvedValue(user);
    return render(
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter>
            <RequestRemediation sourceType="finding" sourceId={7} {...props} />
          </MemoryRouter>
        </ToastProvider>
      </AuthProvider>,
    );
  }

  it('explains why automation is unavailable and offers no button', () => {
    renderPanel({ automation: { supported: false, reason: 'Automated correction is not implemented for SEC-003.' } });
    expect(screen.getByText(/not implemented for SEC-003/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Request remediation' })).toBeNull();
  });

  it('requires a justification and only submits a request for approval', async () => {
    remediationApi.create.mockResolvedValue({ id: 12, status: 'PENDING_APPROVAL' });
    const user = userEvent.setup();
    renderPanel({ automation });
    const open = screen.getByRole('button', { name: 'Request remediation' });
    await waitFor(() => expect(open).toBeEnabled());
    await user.click(open);

    const submit = screen.getByRole('button', { name: 'Submit request' });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/Justification/), 'Bucket must not be public.');
    expect(submit).toBeEnabled();
    await user.click(submit);
    await waitFor(() => expect(remediationApi.create).toHaveBeenCalledWith('finding', 7, 'ACTION-002', 'Bucket must not be public.'));
  });

  it('disables the button for users without permission or with a request in flight', async () => {
    const { unmount } = renderPanel({ automation }, { ...OPERATOR, permissions: [] });
    await waitFor(() => expect(authApi.me).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: 'Request remediation' })).toBeDisabled();
    unmount();

    renderPanel({ automation, activeRequest: { id: 3, status: 'PENDING_APPROVAL' } });
    expect(screen.getByRole('button', { name: 'Request remediation' })).toBeDisabled();
    expect(screen.getByText(/Request #3 is already pending approval/)).toBeInTheDocument();
  });
});
