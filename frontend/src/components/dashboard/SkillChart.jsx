import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { Card, SectionHeader } from './Primitives';
import { chartAxisTick, chartPalette } from '../../config/chartPalette';

/**
 * SkillChart — radar of the student's skill profile with the batch
 * benchmark overlaid on the same axes, so gaps are visible as area
 * difference rather than needing a second chart.
 *
 * `data` is the `skills[]` shape: { skill, score, benchmark }.
 */

const SCORE_COLOR = chartPalette.accent;
const BENCH_COLOR = '#94a3b8';

/** Two-line polar tick so long skill names ("Logical Reasoning") don't clip. */
function SkillAngleTick({ x, y, cx, cy, payload }) {
  const words = String(payload?.value ?? '').split(' ');
  const lines =
    words.length > 1 ? [words.slice(0, -1).join(' '), words[words.length - 1]] : [words[0]];

  const anchor = x < cx - 1 ? 'end' : x > cx + 1 ? 'start' : 'middle';

  return (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fill="#475569"
      fontSize={11}
      fontWeight={500}
      dominantBaseline="central"
    >
      {lines.map((line, i) => (
        <tspan
          key={line + i}
          x={x}
          dy={lines.length > 1 ? (i === 0 ? -6 : 12) : 0}
        >
          {line}
        </tspan>
      ))}
    </text>
  );
}

function SkillTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  const gap = row.score - row.benchmark;

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-slate-500">{row.skill}</p>
      <p className="flex items-center gap-2">
        <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ backgroundColor: SCORE_COLOR }} />
        <span className="text-slate-600">You</span>
        <span className="ml-auto font-mono font-semibold tabular-nums text-slate-900">
          {row.score}%
        </span>
      </p>
      <p className="mt-0.5 flex items-center gap-2">
        <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ backgroundColor: BENCH_COLOR }} />
        <span className="text-slate-600">Benchmark</span>
        <span className="ml-auto font-mono font-semibold tabular-nums text-slate-900">
          {row.benchmark}%
        </span>
      </p>
      <p
        className={`mt-1 border-t border-slate-100 pt-1 font-medium ${
          gap < 0 ? 'text-red-600' : 'text-emerald-600'
        }`}
      >
        {gap < 0 ? `${Math.abs(gap)} below batch` : gap === 0 ? 'At batch level' : `${gap} above batch`}
      </p>
    </div>
  );
}

export default function SkillChart({ data = [], className = '' }) {
  const gaps = data.filter((s) => s.score < s.benchmark).sort((a, b) => a.score - b.score);

  return (
    <Card className={className}>
      <SectionHeader
        title="Skill breakdown"
        description="Your score against the batch benchmark, by competency"
      />

      {/* Legend */}
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs">
        <span className="inline-flex items-center gap-1.5 text-slate-700">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: SCORE_COLOR }}
          />
          You
        </span>
        <span className="inline-flex items-center gap-1.5 text-slate-500">
          <span
            aria-hidden="true"
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: BENCH_COLOR }}
          />
          Batch benchmark
        </span>
      </div>

      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="68%" margin={{ top: 16, right: 34, bottom: 16, left: 34 }}>
            <PolarGrid stroke="#e2e8f0" />
            <PolarAngleAxis dataKey="skill" tick={<SkillAngleTick />} />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tickCount={5}
              tick={{ ...chartAxisTick, fontSize: 10 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<SkillTooltip />} />

            <Radar
              name="Batch benchmark"
              dataKey="benchmark"
              stroke={BENCH_COLOR}
              strokeWidth={1.5}
              strokeDasharray="5 4"
              fill={BENCH_COLOR}
              fillOpacity={0.08}
              dot={{ r: 2.5, fill: BENCH_COLOR, strokeWidth: 0 }}
              isAnimationActive={false}
            />
            <Radar
              name="You"
              dataKey="score"
              stroke={SCORE_COLOR}
              strokeWidth={2}
              fill={SCORE_COLOR}
              fillOpacity={0.22}
              dot={{ r: 3, fill: SCORE_COLOR, strokeWidth: 0 }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Exact values — the radar shows shape, this shows numbers. */}
      <ul className="mt-5 grid grid-cols-1 gap-x-6 gap-y-2 border-t border-slate-100 pt-4 sm:grid-cols-2">
        {data.map((s) => {
          const gap = s.score - s.benchmark;
          return (
            <li key={s.skill} className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-slate-600">{s.skill}</span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="font-mono font-semibold tabular-nums text-slate-900">
                  {s.score}
                </span>
                <span
                  className={`font-mono tabular-nums ${
                    gap < 0 ? 'text-red-600' : 'text-emerald-600'
                  }`}
                >
                  {gap > 0 ? `+${gap}` : gap}
                </span>
              </span>
            </li>
          );
        })}
      </ul>

      {gaps.length > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          Below benchmark in{' '}
          <span className="font-medium text-slate-700">
            {gaps.map((g) => g.skill).join(', ')}
          </span>
          .
        </p>
      )}
    </Card>
  );
}
