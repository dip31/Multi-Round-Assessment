import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, Info, X } from 'lucide-react';

/**
 * Lightweight toast for UI-only action feedback.
 *
 * IMPORTANT: these confirm that a *preview* action was noticed — they must not
 * be used to imply anything was persisted to a backend. Every dashboard action
 * that has no real endpoint says so in its own copy.
 */

const TONES = {
  info: { icon: Info, ring: 'ring-slate-200', iconTone: 'text-blue-500' },
  success: { icon: CheckCircle2, ring: 'ring-emerald-200', iconTone: 'text-emerald-500' },
};

export function useToast(defaultMs = 4200) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef(new Map());
  const idRef = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (message, { tone = 'info', duration = defaultMs } = {}) => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev.slice(-2), { id, message, tone }]);

      const timer = setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        timersRef.current.delete(id);
      }, duration);

      timersRef.current.set(id, timer);
      return id;
    },
    [defaultMs],
  );

  // Clear every pending timer on unmount.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  return { toasts, push, dismiss };
}

export function Toaster({ toasts = [], onDismiss }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
    >
      {toasts.map((t) => {
        const tone = TONES[t.tone] ?? TONES.info;
        const Icon = tone.icon;

        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl bg-white p-3.5 shadow-lg ring-1 ${tone.ring}`}
          >
            <Icon size={17} aria-hidden="true" className={`mt-0.5 shrink-0 ${tone.iconTone}`} />
            <p className="flex-1 text-sm leading-snug text-slate-700">{t.message}</p>
            <button
              type="button"
              onClick={() => onDismiss?.(t.id)}
              aria-label="Dismiss notification"
              className="-mr-1 -mt-1 h-6 w-6 shrink-0 rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              <X size={14} aria-hidden="true" className="mx-auto" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default Toaster;
