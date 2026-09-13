import { AlertTriangle, CheckCircle2, Info, XCircle, X } from 'lucide-react';

/**
 * AlertCard — severity-toned callout with an optional single action.
 *
 * Consumes the `alerts[]` shape: { id, severity, title, message,
 * actionLabel, actionRoute }. `onDismiss` is optional and purely local —
 * dismissing only hides the card for this session (see the UI-only rule).
 */

const SEVERITY = {
  danger: {
    icon: XCircle,
    wrap: 'border-red-200 bg-red-50',
    iconTone: 'bg-red-100 text-red-600',
    title: 'text-red-900',
    body: 'text-red-700',
    action:
      'bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500',
  },
  warning: {
    icon: AlertTriangle,
    wrap: 'border-amber-200 bg-amber-50',
    iconTone: 'bg-amber-100 text-amber-600',
    title: 'text-amber-900',
    body: 'text-amber-800',
    action:
      'bg-amber-600 text-white hover:bg-amber-700 focus-visible:ring-amber-500',
  },
  success: {
    icon: CheckCircle2,
    wrap: 'border-emerald-200 bg-emerald-50',
    iconTone: 'bg-emerald-100 text-emerald-600',
    title: 'text-emerald-900',
    body: 'text-emerald-800',
    action:
      'bg-emerald-600 text-white hover:bg-emerald-700 focus-visible:ring-emerald-500',
  },
  info: {
    icon: Info,
    wrap: 'border-blue-200 bg-blue-50',
    iconTone: 'bg-blue-100 text-blue-600',
    title: 'text-blue-900',
    body: 'text-blue-800',
    action: 'bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-500',
  },
};

export default function AlertCard({ alert, onAction, onDismiss, className = '' }) {
  const tone = SEVERITY[alert.severity] ?? SEVERITY.info;
  const Icon = tone.icon;

  return (
    <div
      role={alert.severity === 'danger' ? 'alert' : 'status'}
      className={`flex gap-3 rounded-xl border p-4 ${tone.wrap} ${className}`}
    >
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone.iconTone}`}
      >
        <Icon size={17} aria-hidden="true" />
      </span>

      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold leading-snug ${tone.title}`}>{alert.title}</p>
        {alert.message && (
          <p className={`mt-1 text-xs leading-relaxed ${tone.body}`}>{alert.message}</p>
        )}
        {alert.actionLabel && (
          <button
            type="button"
            onClick={() => onAction?.(alert)}
            className={`mt-3 inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${tone.action}`}
          >
            {alert.actionLabel}
          </button>
        )}
      </div>

      {onDismiss && (
        <button
          type="button"
          onClick={() => onDismiss(alert)}
          aria-label={`Dismiss: ${alert.title}`}
          className="-mr-1 -mt-1 h-7 w-7 shrink-0 rounded-lg text-slate-400 transition-colors hover:bg-black/5 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
        >
          <X size={15} aria-hidden="true" className="mx-auto" />
        </button>
      )}
    </div>
  );
}
