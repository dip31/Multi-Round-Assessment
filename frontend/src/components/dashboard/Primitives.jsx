import { AlertCircle, Inbox, RefreshCw } from 'lucide-react';

/* ────────────────────────────────────────────────────────────────────
 * Card — the base light surface every dashboard panel sits on.
 * ──────────────────────────────────────────────────────────────────── */
export function Card({ as: Tag = 'div', className = '', padded = true, children, ...rest }) {
  return (
    <Tag
      className={[
        'rounded-xl border border-slate-200 bg-white shadow-sm',
        padded ? 'p-5 sm:p-6' : '',
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </Tag>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * SectionHeader — title + optional description and trailing actions.
 * ──────────────────────────────────────────────────────────────────── */
export function SectionHeader({ title, description, actions, id, className = '' }) {
  return (
    <div
      id={id}
      className={`mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between ${className}`}
    >
      <div className="min-w-0">
        <h2 className="font-display text-lg font-bold tracking-tight text-slate-900">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * StatusBadge — one vocabulary for every status pill on the dashboards.
 * ──────────────────────────────────────────────────────────────────── */
const STATUS_STYLES = {
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  active: 'bg-accent/10 text-accent ring-accent/20',
  'in-progress': 'bg-accent/10 text-accent ring-accent/20',
  pending: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  scheduled: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  open: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  'registration-open': 'bg-blue-50 text-blue-700 ring-blue-600/20',
  terminated: 'bg-red-50 text-red-700 ring-red-600/20',
  'at-risk': 'bg-red-50 text-red-700 ring-red-600/20',
  warning: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  info: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  danger: 'bg-red-50 text-red-700 ring-red-600/20',
  neutral: 'bg-slate-100 text-slate-600 ring-slate-500/20',
};

const STATUS_LABELS = {
  completed: 'Completed',
  active: 'In progress',
  'in-progress': 'In progress',
  pending: 'Not started',
  scheduled: 'Scheduled',
  open: 'Open',
  'registration-open': 'Registration open',
  terminated: 'Ended early',
  'at-risk': 'At risk',
};

export function StatusBadge({ status, label, size = 'sm', className = '' }) {
  const key = String(status ?? 'neutral').toLowerCase();
  const tone = STATUS_STYLES[key] ?? STATUS_STYLES.neutral;
  const text = label ?? STATUS_LABELS[key] ?? status;
  const sizing = size === 'xs' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ring-1 ring-inset ${tone} ${sizing} ${className}`}
    >
      {text}
    </span>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * ProgressBar
 * ──────────────────────────────────────────────────────────────────── */
export function ProgressBar({
  value = 0,
  max = 100,
  color,
  showLabel = false,
  label,
  size = 'md',
  className = '',
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const height = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3' : 'h-2';

  return (
    <div className={className}>
      {(showLabel || label) && (
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="font-medium text-slate-600">{label}</span>
          {showLabel && (
            <span className="font-mono font-medium text-slate-900">{Math.round(pct)}%</span>
          )}
        </div>
      )}
      <div
        className={`w-full overflow-hidden rounded-full bg-slate-100 ${height}`}
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label || 'Progress'}
      >
        <div
          className={`${height} rounded-full transition-[width] duration-500 ease-out`}
          style={{ width: `${pct}%`, backgroundColor: color || '#6C63FF' }}
        />
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
 * EmptyState / ErrorState
 * ──────────────────────────────────────────────────────────────────── */
export function EmptyState({
  icon: Icon = Inbox,
  title = 'Nothing here yet',
  message,
  action,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center px-6 py-12 text-center ${className}`}>
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100">
        <Icon size={22} aria-hidden="true" className="text-slate-400" />
      </span>
      <p className="font-display text-base font-semibold text-slate-900">{title}</p>
      {message && <p className="mt-1 max-w-sm text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'We could not load this dashboard. Please try again.',
  onRetry,
  className = '',
}) {
  return (
    <Card className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
        <AlertCircle size={22} aria-hidden="true" className="text-red-500" />
      </span>
      <p className="font-display text-base font-semibold text-slate-900">{title}</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        >
          <RefreshCw size={15} aria-hidden="true" />
          Try again
        </button>
      )}
    </Card>
  );
}
