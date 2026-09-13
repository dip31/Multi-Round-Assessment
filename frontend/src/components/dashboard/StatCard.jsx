import { TrendingDown, TrendingUp, Minus } from 'lucide-react';

/**
 * StatCard — the four-up summary tiles at the top of each dashboard.
 *
 * `trend` is optional: { direction: 'up' | 'down' | 'flat', value: '6%',
 * label: 'vs last month', positive: true }. `positive` controls the colour
 * independently of the arrow direction, because a falling rank is good news
 * and a rising "pending tasks" count is not.
 */
export default function StatCard({
  label,
  value,
  unit,
  hint,
  icon: Icon,
  iconTone = 'accent',
  trend,
  className = '',
}) {
  const toneMap = {
    accent: 'bg-accent/10 text-accent',
    success: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-red-50 text-red-600',
    neutral: 'bg-slate-100 text-slate-500',
  };

  const TrendIcon =
    trend?.direction === 'up' ? TrendingUp : trend?.direction === 'down' ? TrendingDown : Minus;

  const trendTone =
    trend?.positive === true
      ? 'text-emerald-600'
      : trend?.positive === false
        ? 'text-red-600'
        : 'text-slate-500';

  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {Icon && (
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${toneMap[iconTone] ?? toneMap.accent}`}
          >
            <Icon size={17} aria-hidden="true" />
          </span>
        )}
      </div>

      <div className="mt-3 flex items-baseline gap-1">
        <span className="font-display text-2xl font-bold tracking-tight text-slate-900 tabular-nums">
          {value}
        </span>
        {unit && <span className="text-sm font-medium text-slate-500">{unit}</span>}
      </div>

      {(trend || hint) && (
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          {trend && (
            <span className={`inline-flex items-center gap-1 font-medium ${trendTone}`}>
              <TrendIcon size={13} aria-hidden="true" />
              {trend.value}
            </span>
          )}
          {(trend?.label || hint) && (
            <span className="text-slate-500">{trend?.label ?? hint}</span>
          )}
        </div>
      )}
    </div>
  );
}
