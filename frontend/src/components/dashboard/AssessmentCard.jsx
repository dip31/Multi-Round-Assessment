import { ArrowRight, Brain, CheckCircle2, Clock, Code2, Mic } from 'lucide-react';
import { StatusBadge } from './Primitives';
import { formatDateTime, formatDuration, formatScore } from './formatters';

/**
 * AssessmentCard — one assessment round (aptitude / coding / interview).
 *
 * Consumes the `rounds[]` shape from the mock data, which mirrors
 * `AssessmentRound` in the backend ORM (`roundType`, `status`, `score`).
 */

const ROUND_META = {
  aptitude: { icon: Brain, tone: 'bg-accent/10 text-accent', label: 'Aptitude' },
  coding: { icon: Code2, tone: 'bg-blue-50 text-blue-600', label: 'Coding' },
  interview: { icon: Mic, tone: 'bg-amber-50 text-amber-600', label: 'Interview' },
};

export default function AssessmentCard({ round, onOpen, className = '' }) {
  const meta = ROUND_META[round.roundType] ?? ROUND_META.aptitude;
  const Icon = meta.icon;
  const isComplete = round.status === 'completed';
  const hasScore = typeof round.score === 'number';
  const pct = hasScore && round.maxScore ? Math.round((round.score / round.maxScore) * 100) : null;

  const scoreTone =
    pct === null
      ? 'text-slate-400'
      : pct >= 75
        ? 'text-emerald-600'
        : pct >= 60
          ? 'text-accent'
          : pct >= 45
            ? 'text-amber-600'
            : 'text-red-600';

  return (
    <article
      className={`group flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-accent/30 hover:shadow-md ${className}`}
    >
      <div className="flex items-start gap-3">
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${meta.tone}`}>
          <Icon size={19} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-display text-base font-semibold leading-tight text-slate-900">
              {round.title}
            </h3>
            <StatusBadge status={round.status} size="xs" />
          </div>
          <p className="mt-1 text-sm leading-snug text-slate-500">{round.description}</p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-slate-100 pt-4">
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Score</dt>
          <dd className={`mt-0.5 font-mono text-lg font-semibold tabular-nums ${scoreTone}`}>
            {formatScore(round.score)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Questions
          </dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-slate-900">
            {round.questionsAttempted}
            <span className="text-sm font-normal text-slate-400">/{round.questionsTotal}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Duration</dt>
          <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-slate-900">
            {formatDuration(round.durationMinutes)}
          </dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        <p className="inline-flex items-center gap-1.5 text-xs text-slate-500">
          {round.attemptedAt ? (
            <>
              <CheckCircle2 size={13} aria-hidden="true" className="text-emerald-500" />
              Attempted {formatDateTime(round.attemptedAt)}
            </>
          ) : (
            <>
              <Clock size={13} aria-hidden="true" className="text-slate-400" />
              Not attempted yet
            </>
          )}
        </p>
        <button
          type="button"
          onClick={() => onOpen?.(round)}
          className={[
            'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
            isComplete
              ? 'text-accent hover:bg-accent/10'
              : 'bg-accent text-white hover:bg-accent/90',
          ].join(' ')}
        >
          {isComplete ? 'View result' : 'Start now'}
          <ArrowRight
            size={14}
            aria-hidden="true"
            className="transition-transform group-hover:translate-x-0.5"
          />
        </button>
      </div>
    </article>
  );
}
