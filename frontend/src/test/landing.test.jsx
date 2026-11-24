import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../api/auth', () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn(), changePassword: vi.fn() },
}));
import { authApi } from '../api/auth';
import { tokenStore } from '../api/client';
import { healthApi } from '../api/health';
import { AppRoutes } from '../App';
import { DEMO_APP_URL, REPOSITORY_URL } from '../config/links';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../context/ToastContext';
import { SERVER_PROBE } from '../hooks/useServerStatus';

const ADMIN = { id: 1, email: 'admin@test.local', full_name: 'Admin', role: 'admin', permissions: [] };

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

describe('product page', () => {
  it('is what a visitor who is not signed in sees at the site root', async () => {
    renderApp('/');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Monitoring, incidents and controlled remediation in one console.');
    // Nobody was asked who the visitor is: there is no stored session.
    expect(authApi.me).not.toHaveBeenCalled();

    for (const name of ['Six parts, one closed loop', 'From a signal to a verified fix', 'Small services with narrow jobs', 'OrbitCrate is the workload being watched']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument();
    }
    for (const name of ['Monitoring', 'Incidents', 'Security findings', 'Controlled remediation', 'Audit trail', 'VigilAI assistant']) {
      expect(screen.getByRole('heading', { level: 3, name })).toBeInTheDocument();
    }
  });

  it('offers sign-in, never registration', async () => {
    renderApp('/');
    const signIn = await screen.findAllByRole('link', { name: 'Sign in' });
    expect(signIn.length).toBeGreaterThan(0);
    signIn.forEach((link) => expect(link).toHaveAttribute('href', '/login'));
    // No link or button invites the visitor to create an account.
    for (const role of ['link', 'button']) {
      expect(screen.queryByRole(role, { name: /sign up|register|create (an )?account|free trial|get started/i })).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/sign up|create (an )?account|free trial/i)).not.toBeInTheDocument();
    expect(screen.getByText(/accounts are issued by its Administrator/)).toBeInTheDocument();
  });

  it('links to the demonstration application and to the documentation in a new tab', async () => {
    renderApp('/');
    for (const name of ['Open the demo application', 'Open OrbitCrate']) {
      const link = await screen.findByRole('link', { name });
      expect(link).toHaveAttribute('href', DEMO_APP_URL);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noreferrer');
    }
    expect(DEMO_APP_URL).toBe('/orbitcrate/');
    const documents = within(screen.getByRole('heading', { name: 'Read how it is built and how it was tested' }).closest('section'));
    const links = documents.getAllByRole('link');
    expect(links).toHaveLength(6);
    links.forEach((link) => expect(link.getAttribute('href')).toMatch(new RegExp(`^${REPOSITORY_URL}/blob/main/docs/[a-z-]+\\.md$`)));
  });

  it('describes the roles as the permission matrix defines them', async () => {
    renderApp('/');
    const table = within(await screen.findByRole('table'));
    const cells = (name) => within(table.getByRole('rowheader', { name }).closest('tr')).getAllByRole('cell').map((cell) => within(cell).getByRole('img').getAttribute('aria-label'));
    expect(cells('Request remediation')).toEqual(['Allowed', 'Allowed']);
    expect(cells('Approve or reject remediation')).toEqual(['Not allowed', 'Allowed']);
    expect(cells('Use demonstration controls')).toEqual(['Not allowed', 'Allowed']);
  });

  it('leads to the sign-in page, and the sign-in page leads back', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await user.click((await screen.findAllByRole('link', { name: 'Sign in' }))[0]);
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'What is VigilOps?' }));
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Monitoring, incidents');
  });

  it('offers the console instead of sign-in to someone who is signed in', async () => {
    tokenStore.set('valid-token');
    authApi.me.mockResolvedValue(ADMIN);
    renderApp('/welcome');
    const links = await screen.findAllByRole('link', { name: 'Open the console' });
    links.forEach((link) => expect(link).toHaveAttribute('href', '/'));
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  });

  it('sends an unknown address to the product page, and a console address to sign-in', async () => {
    const { unmount } = renderApp('/no-such-page');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Monitoring, incidents');
    unmount();
    renderApp('/audit');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});

describe('product page while the server is waking up', () => {
  const defaults = { ...SERVER_PROBE };
  afterEach(() => {
    Object.assign(SERVER_PROBE, defaults);
    healthApi.ping.mockImplementation(async () => true);
  });

  it('says whether the demonstration environment is answering', async () => {
    Object.assign(SERVER_PROBE, { slowAfterMs: 0, retryEveryMs: 20 });
    let answering = false;
    healthApi.ping.mockImplementation(async () => answering);
    renderApp('/');
    expect(await screen.findByText(/Demonstration environment is starting/)).toBeInTheDocument();
    answering = true;
    expect(await screen.findByText('Demonstration environment is ready')).toBeInTheDocument();
  });
});
