import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SafeText } from '../features/vigilai/SafeText';
import { VigilAIWidget, WELCOME_MESSAGE, askVigilAI } from '../features/vigilai/VigilAIWidget';

vi.mock('../api/vigilai', () => ({
  vigilaiApi: {
    status: vi.fn(),
    chat: vi.fn(),
  },
}));
import { vigilaiApi } from '../api/vigilai';

const STATUS = {
  enabled: true,
  mode: 'documentation',
  suggested_questions: ['What does SEC-001 mean?', 'Show my authorized open incidents.'],
  max_input_chars: 1000,
};

beforeEach(() => {
  vi.clearAllMocks();
  vigilaiApi.status.mockResolvedValue(STATUS);
});

describe('SafeText', () => {
  it('shows markup from the model as literal text instead of rendering it', () => {
    const { container } = render(<SafeText text={'Hello <img src=x onerror="alert(1)"> <script>alert(2)</script>'} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect(container.textContent).toContain('<script>alert(2)</script>');
  });

  it('formats bullets, bold text and inline code', () => {
    const { container } = render(<SafeText text={'Steps:\n- first **important** step\n- run `docker compose ps`\nDone.'} />);
    expect(container.querySelectorAll('li')).toHaveLength(2);
    expect(container.querySelector('strong').textContent).toBe('important');
    expect(container.querySelector('code').textContent).toBe('docker compose ps');
    expect(container.querySelectorAll('p')).toHaveLength(2);
  });
});

describe('VigilAIWidget', () => {
  it('is a closed floating button by default and makes no requests', () => {
    render(<VigilAIWidget />);
    const launcher = screen.getByRole('button', { name: 'Open VigilAI assistant' });
    expect(launcher).toHaveAttribute('aria-expanded', 'false');
    expect(launcher.className).toContain('fixed');
    expect(launcher.className).toContain('bottom-5');
    expect(launcher.className).toContain('right-5');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(vigilaiApi.status).not.toHaveBeenCalled();
    expect(vigilaiApi.chat).not.toHaveBeenCalled();
  });

  it('opens on click with the welcome message, suggestions and a focused input', async () => {
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    await user.click(screen.getByRole('button', { name: 'Open VigilAI assistant' }));
    expect(screen.getByRole('dialog', { name: 'VigilAI assistant' })).toBeInTheDocument();
    expect(screen.getByText(WELCOME_MESSAGE)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'What does SEC-001 mean?' })).toBeInTheDocument();
    expect(screen.getByLabelText('Ask VigilAI about VigilOps')).toHaveFocus();
  });

  it('sends a question with Enter and shows the answer with its sources', async () => {
    vigilaiApi.chat.mockResolvedValue({
      reply: 'SEC-001 means a storage bucket allows public access.',
      mode: 'fallback',
      scope: 'in_scope',
      notice: 'Live AI generation is not configured on this server (no Gemini API key).',
      sources: [{ document: 'security_rules.md', title: 'Security Rules and Scanner', section: 'SEC-001 Public Storage Access' }],
      live_data: [],
    });
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    await user.click(screen.getByRole('button', { name: 'Open VigilAI assistant' }));
    await user.type(screen.getByLabelText('Ask VigilAI about VigilOps'), 'What does SEC-001 mean?{Enter}');

    expect(await screen.findByText('SEC-001 means a storage bucket allows public access.')).toBeInTheDocument();
    expect(screen.getByText(/Live AI generation is not configured/)).toBeInTheDocument();
    expect(screen.getByText('SEC-001 Public Storage Access')).toBeInTheDocument();
    expect(vigilaiApi.chat).toHaveBeenCalledWith('What does SEC-001 mean?', []);
    expect(screen.getByLabelText('Ask VigilAI about VigilOps')).toHaveValue('');
  });

  it('sends earlier turns as history but never the welcome message', async () => {
    vigilaiApi.chat.mockResolvedValueOnce({ reply: 'First answer.', mode: 'ai', scope: 'in_scope', sources: [], live_data: [] });
    vigilaiApi.chat.mockResolvedValueOnce({ reply: 'Second answer.', mode: 'ai', scope: 'in_scope', sources: [], live_data: [] });
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    await user.click(screen.getByRole('button', { name: 'Open VigilAI assistant' }));
    const input = screen.getByLabelText('Ask VigilAI about VigilOps');
    await user.type(input, 'What does SEC-004 mean?{Enter}');
    await screen.findByText('First answer.');
    await user.type(input, 'How do I fix it?{Enter}');
    await screen.findByText('Second answer.');
    expect(vigilaiApi.chat).toHaveBeenLastCalledWith('How do I fix it?', [
      { role: 'user', content: 'What does SEC-004 mean?' },
      { role: 'assistant', content: 'First answer.' },
    ]);
  });

  it('shows an error with a retry option when the request fails', async () => {
    vigilaiApi.chat.mockRejectedValueOnce({ response: { status: 429, data: { detail: 'You are sending messages too quickly. Try again in 20 seconds.' } } });
    vigilaiApi.chat.mockResolvedValueOnce({ reply: 'Recovered answer.', mode: 'ai', scope: 'in_scope', sources: [], live_data: [] });
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    await user.click(screen.getByRole('button', { name: 'Open VigilAI assistant' }));
    await user.type(screen.getByLabelText('Ask VigilAI about VigilOps'), 'Show my open incidents{Enter}');

    expect(await screen.findByRole('alert')).toHaveTextContent('too quickly');
    await user.click(screen.getByRole('button', { name: /Try again/ }));
    expect(await screen.findByText('Recovered answer.')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getAllByText('Show my open incidents')).toHaveLength(1);
    expect(vigilaiApi.chat).toHaveBeenLastCalledWith('Show my open incidents', []);
  });

  it('closes with Escape and returns focus to the launcher', async () => {
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    const launcher = screen.getByRole('button', { name: 'Open VigilAI assistant' });
    await user.click(launcher);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open VigilAI assistant' })).toHaveFocus());
  });

  it('can be opened with a question from elsewhere in the app', async () => {
    vigilaiApi.chat.mockResolvedValue({ reply: 'Here are your incidents.', mode: 'ai', scope: 'in_scope', sources: [], live_data: [{ tool: 'get_authorized_open_incidents' }] });
    render(<VigilAIWidget />);
    askVigilAI('Show my authorized open incidents.');
    expect(await screen.findByText('Here are your incidents.')).toBeInTheDocument();
    expect(screen.getByText('Live platform data')).toBeInTheDocument();
  });

  it('does not send blank messages', async () => {
    const user = userEvent.setup();
    render(<VigilAIWidget />);
    await user.click(screen.getByRole('button', { name: 'Open VigilAI assistant' }));
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
    await user.type(screen.getByLabelText('Ask VigilAI about VigilOps'), '   {Enter}');
    expect(vigilaiApi.chat).not.toHaveBeenCalled();
  });
});
