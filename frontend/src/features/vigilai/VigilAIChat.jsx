import React, { useEffect, useRef, useState } from 'react';
import { AlertCircle, BookOpen, Database, Info, RotateCcw, Send, ShieldOff } from 'lucide-react';
import { SafeText } from './SafeText';
import { SuggestedQuestions } from './SuggestedQuestions';

function MessageMeta({ message }) {
  const sources = message.sources || [];
  const live = (message.live_data || []).filter((item) => !item.denied);
  if (!sources.length && !live.length && message.mode !== 'refusal') return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5 border-t border-line/70 pt-2">
      {message.mode === 'refusal' ? (
        <span className="tag">
          <ShieldOff size={11} aria-hidden="true" /> Declined
        </span>
      ) : null}
      {live.length ? (
        <span className="tag" title={live.map((item) => item.tool).join(', ')}>
          <Database size={11} className="text-ok" aria-hidden="true" /> Live platform data
        </span>
      ) : null}
      {sources.slice(0, 3).map((source) => (
        <span key={`${source.document}-${source.section}`} className="tag" title={source.document}>
          <BookOpen size={11} aria-hidden="true" /> {source.section || source.title}
        </span>
      ))}
    </div>
  );
}

/**
 * Presentational chat panel body: message list, suggestions and composer.
 * All state lives in VigilAIWidget so the conversation survives navigation.
 */
export function VigilAIChat({ messages, suggestions, sending, error, maxLength = 1000, onSend, onRetry, inputRef }) {
  const [draft, setDraft] = useState('');
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages, sending, error]);

  const submit = (text) => {
    const value = (text ?? draft).trim();
    if (!value || sending) return;
    onSend(value);
    setDraft('');
  };

  const hasUserMessage = messages.some((message) => message.role === 'user');

  return (
    <>
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3" role="log" aria-live="polite" aria-label="Conversation with VigilAI">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[88%] rounded-lg px-3 py-2 text-[13px] leading-5 ${
                message.role === 'user' ? 'rounded-br-[3px] bg-content text-canvas' : 'rounded-bl-[3px] border border-line bg-raised/60 text-content'
              }`}
            >
              {message.notice ? (
                <p className="mb-2 flex items-start gap-1.5 rounded border border-l-2 border-warn/30 border-l-warn bg-warn/[0.08] px-2 py-1 text-xs text-content">
                  <Info size={13} className="mt-0.5 shrink-0 text-warn" aria-hidden="true" />
                  {message.notice}
                </p>
              ) : null}
              {message.role === 'user' ? <p className="whitespace-pre-wrap break-words">{message.content}</p> : <SafeText text={message.content} />}
              {message.role === 'assistant' ? <MessageMeta message={message} /> : null}
            </div>
          </div>
        ))}

        {sending ? (
          <div className="flex justify-start" role="status" aria-label="VigilAI is preparing an answer">
            <div className="flex items-center gap-1 rounded-lg rounded-bl-[3px] border border-line bg-raised/60 px-3 py-3">
              {[0, 1, 2].map((dot) => (
                <span key={dot} className="typing-dot h-1.5 w-1.5 rounded-[1px] bg-brand" style={{ animationDelay: `${dot * 0.15}s` }} />
              ))}
            </div>
          </div>
        ) : null}

        {error ? (
          <div role="alert" className="flex items-start gap-2 rounded-md border border-l-2 border-danger/30 border-l-danger bg-danger/[0.07] px-3 py-2 text-[13px] text-content">
            <AlertCircle size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
            <div className="flex-1">
              <p>{error}</p>
              {onRetry ? (
                <button type="button" className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline" onClick={onRetry}>
                  <RotateCcw size={12} aria-hidden="true" /> Try again
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {!hasUserMessage ? <SuggestedQuestions questions={suggestions} onSelect={submit} disabled={sending} /> : null}
        <div ref={endRef} />
      </div>

      <form
        className="border-t border-line p-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="flex items-end gap-2">
          <label htmlFor="vigilai-input" className="sr-only">
            Ask VigilAI about VigilOps
          </label>
          <textarea
            id="vigilai-input"
            ref={inputRef}
            rows={1}
            maxLength={maxLength}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="Ask about VigilOps…"
            className="input max-h-28 min-h-[36px] resize-none"
          />
          <button type="submit" className="btn-primary w-9 shrink-0 px-0" disabled={sending || !draft.trim()} aria-label="Send message">
            <Send size={16} />
          </button>
        </div>
        <p className="mt-1.5 text-[11px] leading-4 text-muted">VigilAI is read-only and answers only VigilOps questions. Enter to send, Shift+Enter for a new line.</p>
      </form>
    </>
  );
}

export default VigilAIChat;
