import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';
import { Info } from 'lucide-react';
import { Card, SectionHeader, StatusBadge } from './Primitives';
import { scoreColor } from '../../config/chartPalette';
import { formatRelative } from './formatters';

/**
 * ReadinessDonut — headline placement-readiness gauge.
 *
 * `readiness` is the `readiness` block: { score, band, delta, deltaLabel,
 * roundsCounted, roundsTotal, updatedAt, breakdown[] }. Each breakdown row
 * carries a `weight`; a row with a null score (round not yet attempted) is
 * excluded from the weighted total and labelled as such rather than being
 * silently counted as zero.
 */

const BAND_TONE = {
  'At risk': { badge: 'danger', text: 'text-red-600' },
  Developing: { badge: 'warning', text: 'text-amber-600' },
  'On track': { badge: 'info', text: 'text-blue-600' },
  'Placement ready': { badge: 'success', text: 'text-emerald-600' },
};

export default function ReadinessDonut({ readiness, className = '' }) {
  const score = readiness?.score ?? 0;
  const band = readiness?.band ?? 'Developing';
  const tone = BAND_TONE[band] ?? BAND_TONE.Developing;
  const ringColor = scoreColor(score);

  const gauge = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: Math.max(0, 100 - score) },
  ];

  const breakdown = readiness?.breakdown ?? [];
  const scored = breakdown.filter((r) => typeof r.score === 'number');
  const pending = breakdown.filter((r) => typeof r.score !== 'number');
  const weightSum = scored.reduce((acc, r) => acc + (r.weight ?? 0), 0);

  return (
    <Card className={className}>
      <SectionHeader
        title="Placement readiness"
        description="Weighted across every attempted round"
      />

      <div className="relative mx-auto h-[190px] w-full max-w-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={gauge}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
              innerRadius="72%"
              outerRadius="100%"
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={ringColor} />
              <Cell fill="#e2e8f0" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Centre readout — absolutely positioned over the ring. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-4xl font-bold leading-none tracking-tight text-slate-900 tabular-nums">
            {score}
          </span>
          <span className="mt-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            out of 100
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-col items-center gap-2">
        <StatusBadge status={tone.badge} label={band} />
        {typeof readiness?.delta === 'number' && (
          <p className="text-xs text-slate-500">
            <span className={`font-semibold ${readiness.delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {readiness.delta >= 0 ? '+' : ''}
              {readiness.delta} points
            </span>{' '}
            {readiness.deltaLabel}
          </p>
        )}
      </div>

      <ul className="mt-5 space-y-3 border-t border-slate-100 pt-4">
        {breakdown.map((row) => {
          const hasScore = typeof row.score === 'number';
          const pct = hasScore ? row.score : 0;
          const rowColor = hasScore ? scoreColor(row.score) : '#cbd5e1';

          return (
            <li key={row.label}>
              <div className="flex items-baseline justify-between gap-3 text-xs">
                <span className="font-medium text-slate-600">
                  {row.label}
                  <span className="ml-1.5 font-normal text-slate-400">
                    {Math.round((row.weight ?? 0) * 100)}% weight
                  </span>
                </span>
                <span
                  className={`font-mono font-semibold tabular-nums ${
                    hasScore ? 'text-slate-900' : 'text-slate-400'
                  }`}
                >
                  {hasScore ? `${row.score}%` : 'Not attempted'}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-1.5 rounded-full"
                  style={{ width: `${pct}%`, backgroundColor: rowColor }}
                />
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex items-start gap-2 rounded-lg bg-slate-50 p-3">
        <Info size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-slate-400" />
        <p className="text-xs leading-relaxed text-slate-600">
          {pending.length > 0 ? (
            <>
              Score covers{' '}
              <span className="font-medium text-slate-900">
                {readiness?.roundsCounted ?? scored.length} of {readiness?.roundsTotal ?? breakdown.length}
              </span>{' '}
              rounds
              {weightSum < 1 && (
                <>
                  {' '}
                  ({Math.round(weightSum * 100)}% of total weight) — {pending.map((p) => p.label).join(', ')}{' '}
                  still pending
                </>
              )}
              .
            </>
          ) : (
            <>
              Based on all {readiness?.roundsTotal ?? breakdown.length} rounds. Weighted by round
              importance.
            </>
          )}
        </p>
      </div>

      {readiness?.updatedAt && (
        <p className="mt-3 text-center text-[11px] text-slate-400">
          Updated {formatRelative(readiness.updatedAt)}
        </p>
      )}
    </Card>
  );
}
