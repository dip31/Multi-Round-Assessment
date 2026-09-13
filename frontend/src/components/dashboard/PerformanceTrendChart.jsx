import { useMemo, useState } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card, SectionHeader } from './Primitives';
import {
  chartAxisTick,
  chartGridStroke,
  chartPalette,
  chartTooltipLabelStyle,
  chartTooltipStyle,
} from '../../config/chartPalette';

/**
 * PerformanceTrendChart — score progression across rounds.
 *
 * `data` is the `performanceTrend[]` shape: one row per evaluation with
 * `label` plus a score per round type. `overall` renders as the filled area
 * behind the individual round lines.
 *
 * Both controls (range, series visibility) are local component state —
 * no persistence, per the UI-only rule.
 */

const SERIES = [
  { key: 'overall', name: 'Overall', color: chartPalette.accent, kind: 'area' },
  { key: 'aptitude', name: 'Aptitude', color: chartPalette.mid, kind: 'line' },
  { key: 'coding', name: 'Coding', color: chartPalette.good, kind: 'line' },
  { key: 'interview', name: 'Interview', color: chartPalette.warn, kind: 'line' },
];

const RANGES = [
  { id: '3m', label: '3M', points: 3 },
  { id: '6m', label: '6M', points: 6 },
  { id: 'all', label: 'All', points: Infinity },
];

function TrendTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div style={chartTooltipStyle} className="px-3 py-2">
      <p style={chartTooltipLabelStyle}>{label}</p>
      <ul className="space-y-1">
        {payload.map((entry) => (
          <li key={entry.dataKey} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-slate-600">{entry.name}</span>
            <span className="ml-auto font-mono font-semibold tabular-nums text-slate-900">
              {entry.value == null ? '—' : `${entry.value}%`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PerformanceTrendChart({ data = [], className = '' }) {
  const [range, setRange] = useState('6m');
  const [hidden, setHidden] = useState(() => new Set(['interview']));

  const visible = useMemo(() => {
    const points = RANGES.find((r) => r.id === range)?.points ?? Infinity;
    return Number.isFinite(points) ? data.slice(-points) : data;
  }, [data, range]);

  const toggleSeries = (key) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <Card className={className}>
      <SectionHeader
        title="Performance trend"
        description="Score per round across your evaluation history"
        actions={
          <div
            role="group"
            aria-label="Time range"
            className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5"
          >
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setRange(r.id)}
                aria-pressed={range === r.id}
                className={[
                  'rounded-md px-2.5 py-1 text-xs font-semibold transition-colors',
                  'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                  range === r.id
                    ? 'bg-white text-accent shadow-sm'
                    : 'text-slate-500 hover:text-slate-700',
                ].join(' ')}
              >
                {r.label}
              </button>
            ))}
          </div>
        }
      />

      {/* Series toggles */}
      <div className="mb-4 flex flex-wrap gap-2">
        {SERIES.map((s) => {
          const off = hidden.has(s.key);
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => toggleSeries(s.key)}
              aria-pressed={!off}
              className={[
                'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
                off
                  ? 'border-slate-200 bg-white text-slate-400'
                  : 'border-slate-200 bg-slate-50 text-slate-700',
              ].join(' ')}
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: off ? '#cbd5e1' : s.color }}
              />
              {s.name}
            </button>
          );
        })}
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={visible} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="edi5-overall-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chartPalette.accent} stopOpacity={0.22} />
                <stop offset="100%" stopColor={chartPalette.accent} stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke={chartGridStroke} strokeDasharray="4 4" vertical={false} />
            <XAxis
              dataKey="label"
              tick={chartAxisTick}
              tickLine={false}
              axisLine={{ stroke: chartGridStroke }}
              dy={6}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 25, 50, 75, 100]}
              tick={chartAxisTick}
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<TrendTooltip />} cursor={{ stroke: chartGridStroke }} />

            {!hidden.has('overall') && (
              <Area
                type="monotone"
                dataKey="overall"
                name="Overall"
                stroke={chartPalette.accent}
                strokeWidth={2.5}
                fill="url(#edi5-overall-fill)"
                dot={{ r: 3, strokeWidth: 2, fill: '#fff', stroke: chartPalette.accent }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            )}

            {SERIES.filter((s) => s.kind === 'line').map(
              (s) =>
                !hidden.has(s.key) && (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={s.color}
                    strokeWidth={2}
                    strokeDasharray={s.key === 'interview' ? '5 4' : undefined}
                    dot={{ r: 3, strokeWidth: 2, fill: '#fff', stroke: s.color }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ),
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-xs text-slate-500">
        Interview scores begin in June — the round was not attempted before then.
      </p>
    </Card>
  );
}
