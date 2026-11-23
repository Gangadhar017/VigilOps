import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

/** Accessible modal dialog: focus moves in, Escape closes, focus returns on close. */
export function Modal({ open, title, onClose, children, footer, size = 'md' }) {
  const panelRef = useRef(null);
  const previousFocus = useRef(null);
  // Callers usually pass a new onClose function on every render; keeping it in
  // a ref means focus is moved only when the dialog actually opens or closes.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return undefined;
    previousFocus.current = document.activeElement;
    const focusable = panelRef.current?.querySelector('[data-autofocus], textarea, input, select, button');
    focusable?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') onCloseRef.current?.();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previousFocus.current?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  const widths = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-3xl' };
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/60 p-0 sm:items-center sm:p-4" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`card flex max-h-[90vh] w-full flex-col shadow-pop ${widths[size] || widths.md} rounded-b-none sm:rounded-b-xl`}
      >
        <div className="card-header">
          <h2 className="card-title">{title}</h2>
          <button type="button" className="btn-ghost btn-sm" onClick={onClose} aria-label="Close dialog">
            <X size={16} />
          </button>
        </div>
        <div className="card-body overflow-y-auto">{children}</div>
        {footer ? <div className="flex flex-wrap justify-end gap-2 border-t border-line px-4 py-3">{footer}</div> : null}
      </div>
    </div>
  );
}

/**
 * Confirmation for an action that changes state. Optionally collects a note
 * (for example a justification) that can be required.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  danger = false,
  busy = false,
  error,
  noteLabel,
  notePlaceholder,
  noteRequired = false,
  noteMinLength = 0,
  note = '',
  onNoteChange,
  extra,
  onConfirm,
  onClose,
}) {
  const tooShort = noteLabel && noteRequired && note.trim().length < noteMinLength;
  return (
    <Modal
      open={open}
      title={title}
      onClose={busy ? undefined : onClose}
      size="sm"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy || tooShort}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </>
      }
    >
      {description ? <p className="text-sm text-muted">{description}</p> : null}
      {noteLabel ? (
        <div className="mt-3">
          <label className="label" htmlFor="confirm-note">
            {noteLabel}
            {noteRequired ? ' (required)' : ' (optional)'}
          </label>
          <textarea
            id="confirm-note"
            data-autofocus
            rows={3}
            className="input"
            maxLength={2000}
            placeholder={notePlaceholder}
            value={note}
            onChange={(event) => onNoteChange?.(event.target.value)}
          />
          {noteRequired && noteMinLength ? <p className="field-hint">At least {noteMinLength} characters.</p> : null}
        </div>
      ) : null}
      {extra}
      {error ? (
        <p role="alert" className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-content">
          {error}
        </p>
      ) : null}
    </Modal>
  );
}

export default Modal;
