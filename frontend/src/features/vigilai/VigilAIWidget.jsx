import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Minus, Trash2, X } from 'lucide-react';
import { errorMessage } from '../../api/client';
import { vigilaiApi } from '../../api/vigilai';
import { VigilAIChat } from './VigilAIChat';

export const WELCOME_MESSAGE =
  "Hi! I'm VigilAI, your VigilOps assistant. I can help you understand monitoring, incidents, security findings, remediation workflows, and platform troubleshooting. How can I help?";

/** Other parts of the app (the Help page) can open the widget with a question. */
export const ASK_EVENT = 'vigilai:ask';
export const askVigilAI = (question) => window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: { question } }));

const welcome = () => ({ id: 'welcome', role: 'assistant', content: WELCOME_MESSAGE });
const MAX_HISTORY_TURNS = 6;

/**
 * Floating VigilAI assistant: a small button in the bottom-right corner that
 * opens a compact chat panel. Closed by default; it never replaces the page.
 * The conversation is kept in memory for the current session only.
 */
export function VigilAIWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([welcome()]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState(null);
  const lastQuestion = useRef('');
  const nextId = useRef(1);
  const inputRef = useRef(null);
  const launcherRef = useRef(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Assistant status (mode, suggestions) is fetched the first time the panel opens.
  useEffect(() => {
    if (!open || status) return;
    vigilaiApi
      .status()
      .then(setStatus)
      .catch(() => setStatus({ enabled: true, mode: 'unknown' }));
  }, [open, status]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const close = useCallback(() => {
    setOpen(false);
    launcherRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close]);

  const send = useCallback(async (question) => {
    lastQuestion.current = question;
    setError('');
    // Only genuine conversation turns are sent as context (not the welcome text or failures).
    const history = messagesRef.current
      .filter((message) => message.id !== 'welcome')
      .slice(-MAX_HISTORY_TURNS)
      .map(({ role, content }) => ({ role, content: content.slice(0, 3500) }));
    // A trailing user turn is a question that never got an answer (a failed send).
    while (history.length && history[history.length - 1].role === 'user') history.pop();
    setMessages((list) => [...list, { id: `u${nextId.current++}`, role: 'user', content: question }]);
    setSending(true);
    try {
      const response = await vigilaiApi.chat(question, history);
      setMessages((list) => [
        ...list,
        {
          id: `a${nextId.current++}`,
          role: 'assistant',
          content: response.reply,
          mode: response.mode,
          notice: response.notice,
          sources: response.sources,
          live_data: response.live_data,
        },
      ]);
    } catch (err) {
      setError(errorMessage(err, 'VigilAI could not answer right now. The rest of VigilOps is not affected.'));
    } finally {
      setSending(false);
    }
  }, []);

  const retry = useCallback(() => {
    const question = lastQuestion.current;
    if (!question) return;
    // Remove the unanswered question so it is not shown twice.
    setMessages((list) => {
      const index = [...list].reverse().findIndex((message) => message.role === 'user' && message.content === question);
      if (index === -1) return list;
      const position = list.length - 1 - index;
      return position === list.length - 1 ? list.slice(0, position) : list;
    });
    send(question);
  }, [send]);

  // "Ask VigilAI" buttons elsewhere in the app.
  useEffect(() => {
    const onAsk = (event) => {
      setOpen(true);
      const question = event.detail?.question;
      if (question) send(question);
    };
    window.addEventListener(ASK_EVENT, onAsk);
    return () => window.removeEventListener(ASK_EVENT, onAsk);
  }, [send]);

  const clear = () => {
    setMessages([welcome()]);
    setError('');
    lastQuestion.current = '';
  };

  const modeLabel = status?.enabled === false ? 'Disabled' : status?.mode === 'ai' ? 'Gemini' : status?.mode === 'documentation' ? 'Documentation mode' : '';

  return (
    <>
      {open ? (
        <section
          role="dialog"
          aria-label="VigilAI assistant"
          className="fixed inset-x-2 bottom-2 z-40 flex h-[min(78vh,600px)] flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-pop sm:inset-x-auto sm:bottom-20 sm:right-5 sm:h-[min(72vh,580px)] sm:w-[390px]"
        >
          <header className="flex items-center justify-between gap-2 border-b border-line bg-raised/60 px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand/15 text-brand">
                <Bot size={17} aria-hidden="true" />
              </span>
              <div className="min-w-0 leading-tight">
                <p className="text-sm font-semibold text-content">VigilAI</p>
                <p className="truncate text-[11px] text-muted">VigilOps assistant · read-only{modeLabel ? ` · ${modeLabel}` : ''}</p>
              </div>
            </div>
            <div className="flex items-center">
              <button type="button" className="btn-ghost btn-sm" onClick={clear} aria-label="Clear conversation" title="Clear conversation">
                <Trash2 size={15} />
              </button>
              <button type="button" className="btn-ghost btn-sm" onClick={close} aria-label="Minimize VigilAI" title="Minimize">
                <Minus size={16} />
              </button>
              <button type="button" className="btn-ghost btn-sm sm:hidden" onClick={close} aria-label="Close VigilAI">
                <X size={16} />
              </button>
            </div>
          </header>
          <VigilAIChat
            messages={messages}
            suggestions={status?.suggested_questions?.slice(0, 4)}
            sending={sending}
            error={error}
            maxLength={status?.max_input_chars || 1000}
            onSend={send}
            onRetry={retry}
            inputRef={inputRef}
          />
        </section>
      ) : null}

      <button
        ref={launcherRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-label={open ? 'Close VigilAI assistant' : 'Open VigilAI assistant'}
        aria-expanded={open}
        title="VigilAI assistant"
        className={`fixed bottom-5 right-5 z-40 h-12 w-12 items-center justify-center rounded-full bg-brand text-white shadow-pop transition-transform hover:scale-105 dark:text-slate-900 ${
          open ? 'hidden sm:flex' : 'flex'
        }`}
      >
        {open ? <X size={22} /> : <Bot size={24} />}
      </button>
    </>
  );
}

export default VigilAIWidget;
