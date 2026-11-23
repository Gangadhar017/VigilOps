import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

const ToastContext = createContext({ notify: () => {} });

const STYLES = {
  success: { icon: CheckCircle2, className: 'border-ok/40 text-ok' },
  error: { icon: AlertCircle, className: 'border-danger/40 text-danger' },
  info: { icon: Info, className: 'border-info/40 text-info' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setToasts((list) => list.filter((toast) => toast.id !== id)), []);

  const notify = useCallback(
    (message, type = 'success') => {
      const id = nextId.current++;
      setToasts((list) => [...list.slice(-3), { id, message, type }]);
      window.setTimeout(() => dismiss(id), type === 'error' ? 8000 : 4500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="pointer-events-none fixed left-1/2 top-4 z-[70] flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4" aria-live="polite">
        {toasts.map((toast) => {
          const style = STYLES[toast.type] || STYLES.info;
          const Icon = style.icon;
          return (
            <div key={toast.id} role="status" className={`pointer-events-auto flex items-start gap-3 rounded-lg border bg-surface px-3 py-2.5 shadow-pop ${style.className}`}>
              <Icon size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p className="flex-1 text-sm text-content">{toast.message}</p>
              <button type="button" onClick={() => dismiss(toast.id)} className="text-muted hover:text-content" aria-label="Dismiss notification">
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
