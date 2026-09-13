import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Award,
  BarChart3,
  CalendarDays,
  Clock,
  ExternalLink,
  Flame,
  MapPin,
  Percent,
  Play,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';

import DashboardLayout from '../components/dashboard/DashboardLayout';
import DashboardSkeleton from '../components/dashboard/DashboardSkeleton';
import StatCard from '../components/dashboard/StatCard';
import AssessmentCard from '../components/dashboard/AssessmentCard';
import ActivityTimeline from '../components/dashboard/ActivityTimeline';
import AlertCard from '../components/dashboard/AlertCard';
import PerformanceTrendChart from '../components/dashboard/PerformanceTrendChart';
import SkillChart from '../components/dashboard/SkillChart';
import ReadinessDonut from '../components/dashboard/ReadinessDonut';
import Toaster, { useToast } from '../components/dashboard/Toast';
import {
  Card,
  EmptyState,
  ErrorState,
  SectionHeader,
  StatusBadge,
} from '../components/dashboard/Primitives';
import { formatDateTime, formatDuration } from '../components/dashboard/formatters';
import { useDashboardData } from '../hooks/useDashboardData';

/**
 * Student dashboard — placement-prep workspace.
 *
 * This is a NEW page that deliberately coexists with the existing dark
 * `/dashboard` launcher (which is untouched). That launcher is the entry point
 * for actually sitting an assessment; this page is the wider progress view.
 * They cross-link in both directions.
 *
 * UI-only: every action either navigates to a real existing route, or raises a
 * toast. Nothing here writes to a backend.
 */

const STAT_ICONS = {
  'assessments-taken': Target,
  'avg-score': Percent,
  'practice-hours': Clock,
  'batch-percentile': Award,
};

const STAT_ICON_TONES = {
  'assessments-taken': 'accent',
  'avg-score': 'success',
  'practice-hours': 'warning',
  'batch-percentile': 'neutral',
};

const DIFFICULTY_TONE = {
  easy: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  medium: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  hard: 'bg-red-50 text-red-700 ring-red-600/20',
};

const TYPE_ICON_TONE = {
  interview: 'bg-amber-50 text-amber-600',
  aptitude: 'bg-accent/10 text-accent',
  drive: 'bg-blue-50 text-blue-600',
  default: 'bg-slate-100 text-slate-500',
};

/** Renders a stat value with its unit: 12, 71%, 28.5 h, 68th. */
function formatStatValue({ value, unit }) {
  const raw = String(value ?? '');

  // Percentile reads as an ordinal; everything else gets thousands separators.
  if (unit === 'th') return `${raw}th`;
  if (unit === '%') return `${raw}%`;
  if (unit) return `${raw} ${unit}`;
  return raw.replace(/(\d)(?=(\d{3})+$)/, '$1,');
}

export default function StudentDashboard() {
  const { data, loading, error, refetch } = useDashboardData('student');
  const { toasts, push, dismiss } = useToast();
  const navigate = useNavigate();

  // Dismissed alerts are session-local only — nothing is persisted.
  const [dismissedAlerts, setDismissedAlerts] = useState(() => new Set());

  const visibleAlerts = useMemo(
    () => (data?.alerts ?? []).filter((a) => !dismissedAlerts.has(a.id)),
    [data, dismissedAlerts],
  );

  const notifications = useMemo(
    () =>
      (data?.alerts ?? []).map((a) => ({
        id: a.id,
        title: a.title,
        detail: a.message,
        time: 'Today',
        read: false,
      })),
    [data],
  );

  const handleRoundOpen = (round) => {
    if (round.route) {
      navigate(round.route);
      return;
    }
    push(`"${round.title}" is not wired to a route yet.`);
  };

  const handleAlertAction = (alert) => {
    if (alert.actionRoute) {
      navigate(alert.actionRoute);
      return;
    }
    push(`${alert.actionLabel} — this is a preview action, nothing was saved.`);
  };

  const handleRecommendation = (rec) => {
    push(`Opening "${rec.title}" — practice engine is not part of this build.`);
  };

  const handleUpcoming = (item) => {
    push(`${item.title} — scheduling is a preview action, nothing was saved.`);
  };

  const handleExport = () => {
    push('Report export is a preview action — no file was generated.');
  };

  // ── Loading / error ────────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout
        role="student"
        title="Placement readiness"
        subtitle="Your assessment progress, skills and next steps"
      >
        <DashboardSkeleton />
      </DashboardLayout>
    );
  }

  if (error || !data) {
    return (
      <DashboardLayout role="student" title="Placement readiness">
        <ErrorState
          title="Dashboard unavailable"
          message={error?.message ?? 'No dashboard data was returned.'}
          onRetry={refetch}
        />
      </DashboardLayout>
    );
  }

  const { profile, readiness, stats, rounds, performanceTrend, skills, upcoming, recommendations, activity } =
    data;

  return (
    <DashboardLayout
      role="student"
      title={`Welcome back, ${profile.name.split(' ')[0]}`}
      subtitle={`${profile.departmentShort} · Roll ${profile.rollNumber} · Class of ${profile.graduationYear}`}
      profile={{ name: profile.name, initials: profile.initials, email: profile.email }}
      notifications={notifications}
      headerActions={
        <>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            <Play size={15} aria-hidden="true" />
            Assessment launcher
          </Link>
          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            <BarChart3 size={15} aria-hidden="true" />
            Export report
          </button>
        </>
      }
    >
      {/* ── Alerts ──────────────────────────────────────────────────── */}
      {visibleAlerts.length > 0 && (
        <section aria-label="Alerts" className="mb-6 space-y-3">
          {visibleAlerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onAction={handleAlertAction}
              onDismiss={(a) => setDismissedAlerts((prev) => new Set(prev).add(a.id))}
            />
          ))}
        </section>
      )}

      {/* ── Stats ───────────────────────────────────────────────────── */}
      <section aria-label="Summary" id="overview" className="mb-6 scroll-mt-24">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <StatCard
              key={stat.id}
              label={stat.label}
              value={formatStatValue(stat)}
              icon={STAT_ICONS[stat.id] ?? Target}
              iconTone={STAT_ICON_TONES[stat.id] ?? 'accent'}
              trend={{
                direction: stat.trend,
                value:
                  stat.delta === null || stat.delta === undefined
                    ? null
                    : `${stat.delta > 0 ? '+' : ''}${stat.delta}${stat.unit === '%' ? ' pts' : ''}`,
                label: stat.hint,
                positive: stat.delta > 0,
              }}
            />
          ))}
        </div>
      </section>

      {/* ── Rounds ──────────────────────────────────────────────────── */}
      <section id="assessments" className="mb-6 scroll-mt-24">
        <SectionHeader
          title="Your assessment rounds"
          description="Three rounds make up a full placement readiness cycle"
          actions={
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:underline"
            >
              Open launcher
              <ExternalLink size={14} aria-hidden="true" />
            </Link>
          }
        />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {rounds.map((round) => (
            <AssessmentCard key={round.id} round={round} onOpen={handleRoundOpen} />
          ))}
        </div>
      </section>

      {/* ── Trend + readiness ───────────────────────────────────────── */}
      <section id="progress" className="mb-6 grid scroll-mt-24 grid-cols-1 gap-4 xl:grid-cols-3">
        <PerformanceTrendChart data={performanceTrend} className="xl:col-span-2" />
        <ReadinessDonut readiness={readiness} />
      </section>

      {/* ── Skills + recommendations ────────────────────────────────── */}
      <section id="practice" className="mb-6 grid scroll-mt-24 grid-cols-1 gap-4 xl:grid-cols-2">
        <SkillChart data={skills} />

        <Card>
          <SectionHeader
            title="Recommended for you"
            description="Generated from your weakest areas and recent attempts"
          />
          <ul className="space-y-4">
            {recommendations.map((rec) => (
              <li key={rec.id} className="flex gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
                  <Sparkles size={16} aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-display text-sm font-semibold text-slate-900">
                      {rec.title}
                    </h3>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                        DIFFICULTY_TONE[rec.difficulty] ?? DIFFICULTY_TONE.medium
                      }`}
                    >
                      {rec.difficulty}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">{rec.reason}</p>
                  <div className="mt-2 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleRecommendation(rec)}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                    >
                      {rec.ctaLabel}
                      <ArrowRight size={12} aria-hidden="true" />
                    </button>
                    <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                      <Clock size={11} aria-hidden="true" />
                      ~{rec.estimatedMinutes} min · {rec.category}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      {/* ── Upcoming + activity ─────────────────────────────────────── */}
      <section id="upcoming" className="grid scroll-mt-24 grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <SectionHeader
            title="Upcoming"
            description="Scheduled sessions and drives"
            actions={<CalendarDays size={16} aria-hidden="true" className="text-slate-400" />}
          />
          {upcoming.length === 0 ? (
            <EmptyState
              icon={CalendarDays}
              title="Nothing scheduled"
              message="New sessions will appear here once your placement cell publishes them."
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {upcoming.map((item) => (
                <li key={item.id} className="flex gap-3 py-3.5 first:pt-0 last:pb-0">
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                      TYPE_ICON_TONE[item.type] ?? TYPE_ICON_TONE.default
                    }`}
                  >
                    <CalendarDays size={16} aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-sm font-semibold text-slate-900">
                        {item.title}
                      </h3>
                      <StatusBadge status={item.status} size="xs" />
                      {item.mandatory && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-700 ring-1 ring-inset ring-red-600/20">
                          <Flame size={10} aria-hidden="true" />
                          Mandatory
                        </span>
                      )}
                    </div>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <Clock size={12} aria-hidden="true" />
                        {formatDateTime(item.scheduledFor)} · {formatDuration(item.durationMinutes)}
                      </span>
                      {item.location && (
                        <span className="inline-flex items-center gap-1">
                          <MapPin size={12} aria-hidden="true" />
                          {item.location}
                        </span>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleUpcoming(item)}
                    className="h-8 shrink-0 self-center rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    Details
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <SectionHeader
            title="Recent activity"
            description="Your last few actions on the platform"
            actions={<TrendingUp size={16} aria-hidden="true" className="text-slate-400" />}
          />
          <ActivityTimeline items={activity} />
        </Card>
      </section>

      <Toaster toasts={toasts} onDismiss={dismiss} />
    </DashboardLayout>
  );
}
