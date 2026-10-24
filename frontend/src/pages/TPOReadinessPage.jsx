import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ResponsiveContainer, LineChart, BarChart, Bar, Line, XAxis, YAxis,
    CartesianGrid, Tooltip, Legend, LabelList, PieChart, Pie, Cell,
} from 'recharts';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import TPOLayout, { TPOMenuButton } from '../components/TPOLayout';
import {
    ChevronRight, RefreshCw, Filter, TrendingUp, BarChart3, Gauge,
    Download, AlertCircle, Lightbulb, ChevronDown, ChevronUp, Activity, Users,
    CheckCircle, AlertTriangle, Info
} from 'lucide-react';
import {
    formatScore, formatCount, formatReadinessAverage, kpiDisplay,
    skillGapRows, eligibleSummary,
    READINESS_SECTION2_SUBTITLE, readinessNoticeReason, unavailableKpiMeta,
    assessmentCoverageKpi as assessmentCoverageKpiValue,
    candidatesNeedingAssessmentKpi,
    scoringFollowupKpi as scoringFollowupKpiValue,
    recommendedActions,
} from '../utils/readinessFormatting';
import {
    toDepartmentBars, visibleDrives, sortDriveRowsAlphabetically,
    toStatusSlices, toParticipationPoints, toEvidenceCoverageRows,
    toAssessmentEvidenceSummary, toEvidenceGaps, toAptitudePerformance,
    safeAssessmentLabel,
} from '../utils/readinessCharts';
import { codingSkillGapPresentation } from '../utils/competencyGapDemoData';
import { withReadinessDemoValues } from '../utils/readinessDemoData';

const PERIODS = [
    { value: '7', label: 'Last 7 days' },
    { value: '30', label: 'Last 30 days' },
    { value: '90', label: 'Last 90 days' },
    { value: 'all', label: 'All time' },
];

const STATUS_COLORS = {
    draft: '#cbd5e1',
    published: '#0ea5e9',
    active: '#8b5cf6',
    completed: '#10b981',
};

function buildQuery(filters) {
    const params = new URLSearchParams();
    if (filters.period && filters.period !== 'all') params.set('period', filters.period);
    if (filters.company) params.set('company', filters.company);
    if (filters.role) params.set('role', filters.role);
    if (filters.drive_status) params.set('drive_status', filters.drive_status);
    const qs = params.toString();
    return qs ? `?${qs}` : '';
}

function downloadBlob(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function KpiCard({ testId, title, value, meta, available, tone }) {
    const toneCls = available ? tone : 'text-slate-400';
    // Long text values render smaller so all four cards keep an even height;
    // short numeric values and "—" keep the large style.
    const longText = typeof value === 'string' && value.length > 6;
    return (
        <div className="glass-card rounded-2xl p-6 min-w-0" data-testid={testId}>
            <div className="flex items-center justify-between mb-3 gap-2">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</span>
                <span className={`w-8 h-8 shrink-0 rounded-lg flex items-center justify-center font-bold text-sm ${
                    available ? 'bg-sky-50 text-sky-600' : 'bg-slate-100 text-slate-400'
                }`}>
                    {available ? <Gauge size={15} /> : '—'}
                </span>
            </div>
            <div className={`${longText ? 'text-lg font-bold' : 'text-3xl font-black'} ${toneCls}`}>{value}</div>
            <div className="text-xs text-slate-500 mt-1 font-medium leading-relaxed">{meta}</div>
        </div>
    );
}

function SectionHeading({ testId, icon, title, subtitle, source }) {
    return (
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 mb-5" data-testid={testId}>
            <div className="min-w-0">
                <h2 className="text-lg font-extrabold text-slate-900 flex items-center gap-2">{icon}{title}</h2>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed max-w-3xl">{subtitle}</p>
            </div>
            {source && (
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-500 border border-slate-200 rounded-lg px-2.5 py-1.5">
                    {source}
                </span>
            )}
        </div>
    );
}

export default function TPOReadinessPage() {
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);
    const [toast, setToast] = useState(null);
    const [drivesExpanded, setDrivesExpanded] = useState(false);
    const [skillGapAssessmentType, setSkillGapAssessmentType] = useState('all');
    const [filters, setFilters] = useState({
        period: 'all', company: '', role: '', drive_status: '',
    });

    const fetchData = useCallback(async () => {
        if (data) setRefreshing(true);
        else setLoading(true);
        setError(null);
        try {
            const res = await api.get(`/report/admin/readiness/overview${buildQuery(filters)}`);
            setData(res.data);
            // A refresh / filter change re-collapses the drive list to 10 rows.
            setDrivesExpanded(false);
        } catch (err) {
            const status = err?.response?.status;
            if (status === 401 || status === 403) {
                setError('You are not authorized to view readiness analytics. Sign in with a TPO or admin account.');
            } else {
                setError(
                    err?.response?.data?.detail || err?.message
                    || 'Failed to load readiness analytics.',
                );
            }
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filters]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const setFilter = (key, value) => {
        // Changing any filter resets the drive table to its initial 10-row view.
        setDrivesExpanded(false);
        setFilters((f) => ({ ...f, [key]: value }));
    };

    const handleExport = () => {
        if (!data) return;
        const payload = {
            generated_at: data.generated_at,
            filters_applied: data.filters_applied,
            score_scale: data.score_scale,
            coverage: data.coverage,
            assessment_performance: data.assessment_performance,
            drive_activity: data.drive_activity,
            kpis: data.kpis,
            readiness_over_time: data.readiness_over_time,
            readiness_distribution: data.readiness_distribution,
            by_drive: data.by_drive,
            by_department: data.by_department,
            skill_gaps: data.skill_gaps,
            insights: data.insights,
        };
        const ts = (data.generated_at || new Date().toISOString()).replace(/[:]/g, '-');
        downloadBlob(
            JSON.stringify(payload, null, 2),
            `tpo-readiness-${ts}.json`,
            'application/json',
        );
        setToast({ type: 'success', message: 'Readiness export downloaded (current filters).' });
    };

    const kpis = data?.kpis;
    const coverage = data?.coverage;
    const byDrive = data?.by_drive || [];
    const byDepartment = data?.by_department || [];
    const skillGaps = data?.skill_gaps;
    const filterOptions = data?.filters || {};

    // ── Drive activity (Section 1) ───────────────────────────────────────
    const activity = data?.drive_activity;
    const activityStatus = activity?.status_distribution;
    const activityKpis = activity?.kpis;
    const activityOverTime = activity?.over_time;
    const periodLabel = PERIODS.find((p) => p.value === (data?.filters_applied?.period ?? 'all'))?.label
        || 'All time';

    const statusSlices = useMemo(() => toStatusSlices(activityStatus), [activityStatus]);
    const participationPoints = useMemo(
        () => toParticipationPoints(activityOverTime?.points),
        [activityOverTime],
    );
    // ── Candidate readiness (Section 2) ──────────────────────────────────
    const avgKpi = kpiDisplay(kpis?.average_readiness);
    const hasScoredEvidence = (coverage?.scored_attempts ?? 0) > 0;

    const availableSkillGapTypes = skillGaps?.assessment_types || [];
    const activeSkillGapType = availableSkillGapTypes.includes(skillGapAssessmentType)
        ? skillGapAssessmentType
        : 'all';
    // Demo data is local and applies only to the Coding selection.
    const codingSkillGapDemoEnabled = import.meta.env.DEV
        && import.meta.env.VITE_TPO_COMPETENCY_GAPS_DEMO === 'true';
    const activeSkillGaps = codingSkillGapPresentation(
        skillGaps,
        activeSkillGapType,
        codingSkillGapDemoEnabled,
    );
    const gapRows = skillGapRows(activeSkillGaps);

    // Chart-ready datasets derived from the live API payload (never fabricated).
    const deptBars = useMemo(() => toDepartmentBars(byDepartment), [byDepartment]);

    // Assessment-evidence datasets (Section 2, EDI5). Every value is derived
    // from the persisted `assessment_performance` block — nothing is invented.
    const assessment = data?.assessment_performance;
    const evidenceSummary = useMemo(
        () => toAssessmentEvidenceSummary(assessment),
        [assessment],
    );
    const evidenceRows = useMemo(
        () => toEvidenceCoverageRows(assessment),
        [assessment],
    );
    const evidenceGaps = useMemo(() => toEvidenceGaps(assessment), [assessment]);
    const aptitude = useMemo(() => toAptitudePerformance(assessment), [assessment]);
    // topics removed - replaced by Aptitude Assessment Insights
    const statusRows = useMemo(
        () => evidenceRows.filter((row) => row.type !== 'aptitude'),
        [evidenceRows],
    );

    // ── Section 2 KPI derivations (all from authoritative API fields) ────
    // Assessment Coverage: usable scored completed rounds / all completed rounds.
    const assessmentCoverageKpi = useMemo(
        () => assessmentCoverageKpiValue(evidenceSummary),
        [evidenceSummary],
    );

    // Candidates Needing Assessment: distinct candidates with completed
    // assessment activity but no usable scored attempt in scope.
    const needingAssessmentKpi = useMemo(
        () => candidatesNeedingAssessmentKpi(coverage, assessment),
        [coverage, assessment],
    );

    // Scoring Follow-up: completed assessment rounds requiring scoring
    // follow-up (no usable readiness result), counted as rounds/contexts.
    const scoringFollowupKpi = useMemo(
        () => scoringFollowupKpiValue(coverage, evidenceSummary),
        [coverage, evidenceSummary],
    );

    // Recommended Actions: every entry is backed by a live counter.
    const recommendedActionList = useMemo(
        () => recommendedActions(coverage, evidenceSummary, assessment),
        [coverage, evidenceSummary, assessment],
    );

    // This isolated display-only fallback decorates copied rows for this table.
    // The API payload remains authoritative for every other dashboard section.
    const sortedTableDrives = useMemo(() => sortDriveRowsAlphabetically(byDrive), [byDrive]);
    const tableDrives = useMemo(
        () => withReadinessDemoValues(sortedTableDrives),
        [sortedTableDrives],
    );

    // Drive table shows at most 10 rows until the user expands it.
    const driveView = useMemo(
        () => visibleDrives(tableDrives, drivesExpanded),
        [tableDrives, drivesExpanded],
    );

    if (loading && !data) return <PageSkeleton variant="light" cardCount={4} />;

    const activityRate = activityKpis?.completion_rate;
    const activityRateDisplay = activityRate == null ? '—' : `${activityRate}%`;

    return (
        <TPOLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* ── Page header ─────────────────────────────────────── */}
                <div className="glass-card rounded-3xl p-8 mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div className="min-w-0">
                        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2">
                            <a
                                href="/tpo/dashboard"
                                className="hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded px-0.5"
                            >
                                TPO
                            </a>
                            <ChevronRight size={13} className="text-slate-400" aria-hidden="true" />
                            <span className="text-slate-700" aria-current="page">Readiness</span>
                        </nav>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                            Readiness Analytics
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            Drive activity, candidate preparedness and competency insights
                        </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                        <button
                            onClick={() => navigate('/tpo/dashboard')}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                        >
                            Dashboard
                        </button>
                        <TPOMenuButton />
                        <button
                            onClick={handleExport}
                            disabled={!data}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all disabled:opacity-60"
                        >
                            <Download size={14} className="inline mr-1 -mt-0.5" />
                            Export JSON
                        </button>
                        <button
                            onClick={fetchData}
                            disabled={refreshing}
                            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all disabled:opacity-60"
                        >
                            <RefreshCw size={14} className={`inline mr-1 -mt-0.5 ${refreshing ? 'animate-spin' : ''}`} />
                            {refreshing ? 'Refreshing…' : 'Refresh'}
                        </button>
                    </div>
                </div>

                {/* ── Filters ─────────────────────────────────────────── */}
                <section className="glass-card rounded-2xl p-4 mb-8" data-testid="readiness-filters">
                    <div className="flex items-center gap-2 mb-3">
                        <Filter size={15} className="text-slate-400" />
                        <span className="text-sm font-semibold text-slate-700">Filters</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        <label className="flex flex-col gap-1">
                            <span className="text-xs font-medium text-slate-500">Reporting period</span>
                            <select
                                value={filters.period}
                                onChange={(e) => setFilter('period', e.target.value)}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                            >
                                {PERIODS.map((p) => (
                                    <option key={p.value} value={p.value}>{p.label}</option>
                                ))}
                            </select>
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-xs font-medium text-slate-500">Company</span>
                            <select
                                value={filters.company}
                                onChange={(e) => setFilter('company', e.target.value)}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                            >
                                <option value="">All companies</option>
                                {(filterOptions.companies || []).map((c) => (
                                    <option key={c} value={c}>{c}</option>
                                ))}
                            </select>
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-xs font-medium text-slate-500">Job role</span>
                            <select
                                value={filters.role}
                                onChange={(e) => setFilter('role', e.target.value)}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                            >
                                <option value="">All roles</option>
                                {(filterOptions.roles || []).map((r) => (
                                    <option key={r} value={r}>{r}</option>
                                ))}
                            </select>
                        </label>
                        <label className="flex flex-col gap-1">
                            <span className="text-xs font-medium text-slate-500">Drive status</span>
                            <select
                                value={filters.drive_status}
                                onChange={(e) => setFilter('drive_status', e.target.value)}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                            >
                                <option value="">All statuses</option>
                                {(filterOptions.drive_statuses || []).map((s) => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </select>
                        </label>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-3">
                    </p>
                </section>

                {/* ── Error state ─────────────────────────────────────── */}
                {error && (
                    <div role="alert" data-testid="readiness-error" className="glass-card rounded-2xl p-6 mb-8 border border-rose-200">
                        <div className="flex items-center gap-2 text-rose-600 mb-2">
                            <AlertCircle size={18} />
                            <span className="font-semibold text-sm">Failed to load readiness analytics</span>
                        </div>
                        <p className="text-sm text-slate-600 mb-3">{error}</p>
                        <button
                            onClick={fetchData}
                            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* ── Empty state ─────────────────────────────────────── */}
                {!error && !data && (
                    <div className="glass-card rounded-2xl p-8">
                        <p className="text-sm text-slate-500 text-center">No readiness data available.</p>
                    </div>
                )}

                {data && (
                    <>
                        {/* ══ Section 1 — Drive Activity ══════════════════ */}
                        <section className="mb-10" data-testid="section-drive-activity">
                            <SectionHeading
                                testId="drive-activity-heading"
                                icon={<Activity size={19} className="text-emerald-500" />}
                                title="Section 1 — Drive Activity"
                                source="mock_drives · assessment_contexts"
                            />

                            {/* Activity KPIs */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-6" data-testid="activity-kpis">
                                <KpiCard
                                    testId="kpi-drives-in-scope"
                                    title="Drives in Scope"
                                    value={String(activityKpis?.drives_in_scope ?? 0)}
                                    meta={`${activityStatus?.excluded ?? 0} draft drive(s) excluded from analysis `}
                                    available
                                    tone="text-emerald-600"
                                />
                                <KpiCard
                                    testId="kpi-participants-enrolled"
                                    title="Participants Enrolled"
                                    value={String(activityKpis?.participants_enrolled ?? 0)}
                                    meta={`distinct students · ${activityKpis?.contexts ?? 0} attempt context(s) created in period`}
                                    available
                                    tone="text-sky-600"
                                />
                                <KpiCard
                                    testId="kpi-participants-completed"
                                    title="Participants Completed"
                                    value={String(activityKpis?.participants_completed ?? 0)}
                                    meta={`${activityKpis?.completed_contexts ?? 0} context(s) with status completed · ${activityKpis?.participants_in_progress ?? 0} still in progress`}
                                    available
                                    tone="text-teal-600"
                                />
                                <KpiCard
                                    testId="kpi-activity-completion-rate"
                                    title="Completion Rate"
                                    value={activityRateDisplay}
                                    meta={activityRate == null
                                        ? 'Unavailable — no eligible participants in this period (never rendered as 0%).'
                                        : 'completed participants / enrolled participants × 100'}
                                    available={activityRate != null}
                                    tone="text-indigo-600"
                                />
                            </div>

                            {/* Activity charts */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                                {/* A. Drive status distribution */}
                                <section className="glass-card rounded-2xl p-5 min-w-0" data-testid="drive-status-card">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
                                        <BarChart3 size={15} className="text-emerald-500" /> Drive Status Distribution
                                    </h3>
                                    <p className="text-[11px] text-slate-400 mb-3">
                                        Drafts are listed for completeness
                                    </p>
                                    {statusSlices.length === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="drive-status-empty">
                                            <p className="text-sm font-semibold text-slate-700">No drives match the current filters.</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                                Status counts come straight from the drive table, so an empty scope renders an empty
                                                chart — never a zero-filled or invented distribution.
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="flex flex-wrap items-center justify-center gap-5" data-testid="drive-status-chart">
                                            <div className="shrink-0" style={{ width: 190, height: 190 }}>
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <PieChart>
                                                        <Pie
                                                            data={statusSlices}
                                                            dataKey="drives"
                                                            nameKey="label"
                                                            innerRadius={52}
                                                            outerRadius={80}
                                                            paddingAngle={2}
                                                            isAnimationActive={false}
                                                        >
                                                            {statusSlices.map((s) => (
                                                                <Cell
                                                                    key={s.key}
                                                                    fill={STATUS_COLORS[s.key] || '#94a3b8'}
                                                                    stroke="#fff"
                                                                    strokeWidth={2}
                                                                />
                                                            ))}
                                                        </Pie>
                                                        <Tooltip
                                                            formatter={(value, _name, item) => [
                                                                `${value} drive(s) (${item?.payload?.pct ?? 0}%)`,
                                                                'Drives',
                                                            ]}
                                                        />
                                                    </PieChart>
                                                </ResponsiveContainer>
                                            </div>
                                            <ul className="space-y-2 min-w-0">
                                                {statusSlices.map((s) => (
                                                    <li key={s.key} className="flex items-center gap-2 text-xs">
                                                        <span
                                                            className="w-2.5 h-2.5 rounded-full shrink-0"
                                                            style={{ background: STATUS_COLORS[s.key] || '#94a3b8' }}
                                                            aria-hidden="true"
                                                        />
                                                        <span className="font-semibold text-slate-700 capitalize">{s.label}</span>
                                                        <span className="font-bold text-slate-900">{s.drives}</span>
                                                        <span className="text-slate-400">({s.pct}%)</span>
                                                        {!s.analysed && (
                                                            <span className="text-[9px] font-bold uppercase bg-slate-100 text-slate-500 border border-slate-200 px-1.5 py-0.5 rounded">
                                                                excluded
                                                            </span>
                                                        )}
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </section>

                                {/* D. Participation over time */}
                                <section className="glass-card rounded-2xl p-5 min-w-0" data-testid="participation-card">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
                                        <TrendingUp size={15} className="text-sky-500" /> Participation Over Time
                                    </h3>
                                    <p className="text-[11px] text-slate-400 mb-3">
                                        Shows daily registrations and completions based on actual recorded timestamps.
                                        Only days with recorded activity are shown; missing days are not estimated.
                                    </p>
                                    {participationPoints.length === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="participation-empty">
                                            <p className="text-sm font-semibold text-slate-700">No registration or completion events in this period.</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">

                                            </p>
                                        </div>
                                    ) : (
                                        <div className="w-full min-w-0" style={{ height: 260 }} data-testid="participation-chart">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={participationPoints} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                                                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                                                    <Tooltip
                                                        formatter={(value, name) => [`${value} event(s)`, name]}
                                                        labelFormatter={(label, payload) => {
                                                            const p = payload?.[0]?.payload;
                                                            return p ? `${p.key} · ${periodLabel}` : `${label} · ${periodLabel}`;
                                                        }}
                                                    />
                                                    <Legend />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="registrations"
                                                        name="Registrations (contexts created)"
                                                        stroke="#0ea5e9"
                                                        strokeWidth={2}
                                                        dot={{ r: 3 }}
                                                        connectNulls={false}
                                                    />
                                                    <Line
                                                        type="monotone"
                                                        dataKey="completions"
                                                        name="Completions (contexts completed)"
                                                        stroke="#10b981"
                                                        strokeWidth={2}
                                                        dot={{ r: 3 }}
                                                        connectNulls={false}
                                                    />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    )}
                                </section>

                            </div>

                            {/* Complete per-drive data (10-row limit + expand) */}
                            <section className="glass-card rounded-2xl p-5 min-w-0" data-testid="readiness-by-drive">
                                <h3 className="text-sm font-bold text-slate-900 mb-1">Drive Activity &amp; Readiness</h3>
                               <br></br>
                                <ul className="text-[15px] text-slate-500 mb-1 space-y-0.5 list-disc list-inside">
                                    <li><span className="font-semibold">Activity:</span> Participants, completed participants, total attempts, and completion rate.</li>
                                    <li><span className="font-semibold">Readiness:</span> Number of scored candidates, scored attempts, and average readiness across scored attempts.</li>
                                </ul>
                                <br></br>
                                <p className="text-[13px] text-slate-400 italic mb-3" data-testid="drive-table-basis-note">
                                    
                                </p>
                                <p className="text-[11px] text-slate-400 mb-3" data-testid="readiness-demo-note">
                                    
                                </p>
                                {driveView.total === 0 ? (
                                    <p className="text-sm text-slate-500 py-6 text-center">No drives in scope.</p>
                                ) : (
                                    <>
                                        <p className="text-[11px] text-slate-500 mb-2" data-testid="drive-visible-count">
                                        </p>
                                        <div className="overflow-x-auto">
                                            <table id="drive-readiness-table" className="w-full text-left text-xs">
                                                <thead>
                                                    <tr className="text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-200">
                                                        <th className="py-2 pr-3" colSpan={3} aria-hidden="true" />
                                                        <th className="py-2 pr-3 text-emerald-600" colSpan={4}>Activity (participants &amp; contexts)</th>
                                                        <th className="py-2 text-sky-600" colSpan={3}>Competency readiness (scored evidence)</th>
                                                    </tr>
                                                    <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                                                        <th className="py-2 pr-3">Company</th>
                                                        <th className="py-2 pr-3">Role</th>
                                                        <th className="py-2 pr-3">Status</th>
                                                        <th className="py-2 pr-3">Participants</th>
                                                        <th className="py-2 pr-3">Completed</th>
                                                        <th className="py-2 pr-3">Completion rate</th>
                                                        <th className="py-2 pr-3">Contexts</th>
                                                        <th className="py-2 pr-3">Scored candidates</th>
                                                        <th className="py-2 pr-3">Scored attempts</th>
                                                        <th className="py-2">Avg readiness (attempt-weighted)</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {driveView.visible.map((d) => (
                                                        <tr key={d.drive_id} className="border-b border-slate-100">
                                                            <td className="py-2 pr-3 font-semibold text-slate-800">{d.company_name}</td>
                                                            <td className="py-2 pr-3">{d.target_role}</td>
                                                            <td className="py-2 pr-3">
                                                                <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-bold">{d.status}</span>
                                                            </td>
                                                            <td className="py-2 pr-3" title="Distinct students with an attempt on this drive">{formatCount(d.enrolled)}</td>
                                                            <td className="py-2 pr-3" title="Distinct participants with a completed attempt">{formatCount(d.completed)}</td>
                                                            <td className="py-2 pr-3" data-testid={`drive-completion-rate-${d.drive_id}`}>
                                                                {d.completion_rate != null
                                                                    ? `${d.completion_rate}%`
                                                                    : <span className="text-slate-400 font-normal" title="No participants — rate unavailable, not 0%">—</span>}
                                                            </td>
                                                            <td className="py-2 pr-3" title="Attempt-context records (can exceed participants)">{formatCount(d.contexts)}</td>
                                                            <td className="py-2 pr-3" title={d.readiness_is_demo ? 'Illustrative display-only demo value; not persisted.' : 'Distinct candidates with valid persisted readiness evidence'}>
                                                                {formatCount(d.scored_candidates)}{d.readiness_is_demo && <span className="sr-only"> demo</span>}
                                                            </td>
                                                            <td className="py-2 pr-3" title={d.readiness_is_demo ? 'Illustrative display-only demo value; not persisted.' : 'Eligible evaluated attempts contributing to average readiness'}>
                                                                {formatCount(d.scored_attempts)}{d.readiness_is_demo && <span className="sr-only"> demo</span>}
                                                            </td>
                                                            <td className="py-2 font-bold" data-testid={`drive-readiness-average-${d.drive_id}`}>
                                                                {d.avg_readiness != null
                                                                    ? (
                                                                        <span className="inline-flex items-center gap-1.5">
                                                                            <span>{formatReadinessAverage(d.avg_readiness)}</span>
                                                                            {d.readiness_is_demo && (
                                                                                <span className="sr-only">Illustrative display-only value; not an assessment result and not persisted.</span>
                                                                            )}
                                                                        </span>
                                                                    )
                                                                    : (
                                                                        <span
                                                                            className="text-slate-400 font-normal"
                                                                            title={d.scored_attempts === 0
                                                                                ? 'No eligible competency evidence is available for this drive.'
                                                                                : 'The readiness result is unavailable for this drive.'}
                                                                            aria-label={d.scored_attempts === 0
                                                                                ? 'Evidence unavailable'
                                                                                : 'Readiness unavailable'}
                                                                        >
                                                                            {d.scored_attempts === 0 ? 'Evidence unavailable' : '—'}
                                                                        </span>
                                                                    )}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                        {driveView.canExpand && (
                                            <button
                                                type="button"
                                                onClick={() => setDrivesExpanded((v) => !v)}
                                                aria-expanded={drivesExpanded}
                                                aria-controls="drive-readiness-table"
                                                data-testid="drive-toggle"
                                                className="mt-3 inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-300 bg-white text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                                            >
                                                {drivesExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                                {drivesExpanded
                                                    ? 'Show Less'
                                                    : `View All Drives (${driveView.total})`}
                                            </button>
                                        )}
                                    </>
                                )}
                            </section>
                        </section>

                        {/* ══ Section 2 — Assessment Evidence & Readiness ══ */}
                        <section className="mb-10" data-testid="section-readiness">
                            <SectionHeading
                                testId="readiness-heading"
                                icon={<Users size={19} className="text-sky-500" />}
                                title="Section 2 — Assessment Evidence and Readiness"
                                subtitle={READINESS_SECTION2_SUBTITLE}
                            />

                            {/* One compact, data-driven status — shown only while no
                                eligible scored attempt exists. The reason clause mirrors
                                the backend's readiness reason branches; the coverage
                                counters below come from the live API block and are
                                rendered exactly once. */}
                            {!hasScoredEvidence && (
                                <div
                                    className="rounded-xl border border-dashed border-sky-300 bg-sky-50/60 px-4 py-3 mb-6"
                                    data-testid="readiness-evidence-notice"
                                >
                                    <div className="flex items-start gap-2.5">
                                        <AlertCircle size={15} className="text-sky-500 mt-0.5 shrink-0" aria-hidden="true" />
                                        <div className="min-w-0 space-y-1">
                                            <p className="text-xs text-slate-600 leading-relaxed">
                                                <span className="font-bold text-slate-800">Competency readiness is unavailable</span>{' '}
                                                {readinessNoticeReason(coverage)}
                                            </p>
                                            <p className="text-[11px] text-slate-500" data-testid="readiness-funnel-counts">
                                                {coverage?.completed_contexts ?? 0} completed attempts ·{' '}
                                                {coverage?.contexts_with_snapshot ?? 0} pinned snapshots ·{' '}
                                                {coverage?.contexts_with_configured_competencies ?? 0} with configured competencies ·{' '}
                                                {coverage?.contexts_with_evidence_mappings ?? 0} with mapped evidence
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* ── KPI cards ────────────────────────────────── */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-6" data-testid="readiness-kpis">
                                <KpiCard
                                    testId="kpi-average-readiness"
                                    title="Average Readiness"
                                    value={avgKpi.display}
                                    meta={avgKpi.available
                                        ? `${eligibleSummary(coverage)} `
                                        : unavailableKpiMeta('average')}
                                    available={avgKpi.available}
                                    tone="text-sky-600"
                                />
                                <KpiCard
                                    testId="kpi-assessment-coverage"
                                    title="Assessment Coverage"
                                    value={assessmentCoverageKpi.display}
                                    meta={assessmentCoverageKpi.meta}
                                    available={assessmentCoverageKpi.available}
                                    tone="text-emerald-600"
                                />
                                <KpiCard
                                    testId="kpi-candidates-needing-assessment"
                                    title="Candidates Needing Assessment"
                                    value={needingAssessmentKpi.display}
                                    meta={needingAssessmentKpi.meta}
                                    available={needingAssessmentKpi.available}
                                    tone="text-amber-600"
                                />
                                <KpiCard
                                    testId="kpi-scoring-followup"
                                    title="Scoring Follow-up"
                                    value={scoringFollowupKpi.display}
                                    meta={scoringFollowupKpi.meta}
                                    available={scoringFollowupKpi.available}
                                    tone="text-rose-600"
                                />
                            </div>

                            {/* ── Assessment Completion & Scoring (real results) ── */}
                            <div className="space-y-6">
                                <h2 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                                    Assessment Completion & Scoring
                                </h2>

                                {/* A. Evidence coverage */}
                                <section id="assessment-coverage" className="glass-card rounded-2xl p-5" data-testid="assessment-coverage">
                                    <h4 className="text-sm font-bold text-slate-900 mb-1">Completion & Scoring Summary</h4>
<br></br>

                                    {evidenceSummary.denominator === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="assessment-coverage-empty">
                                            <p className="text-sm font-semibold text-slate-700">No completed assessment rounds in scope.</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                                Nothing is shown until real completed rounds exist.
                                            </p>
                                        </div>
                                    ) : (
                                        <>
                                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3">
                                                <p className="text-2xl font-black text-slate-900" data-testid="assessment-coverage-value">
                                                    {formatScore(evidenceSummary.value)}%
                                                    <span className="text-xs font-semibold text-slate-500 ml-2">
                                                        {evidenceSummary.numerator} of {evidenceSummary.denominator} completed round(s) with valid scores
                                                    </span>
                                                </p>
                                                <div className="text-xs text-slate-600">
                                                    Completed rounds: {evidenceSummary.denominator} · Rounds with valid scores: {evidenceSummary.numerator} · Completed rounds without usable scores: {Math.max(0, evidenceSummary.denominator - evidenceSummary.numerator)}
                                                </div>
                                            </div>
                                            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-4">
                                                <div className="h-2 bg-emerald-500" style={{ width: `${Math.max(0, Math.min(100, evidenceSummary.value || 0))}%` }} />
                                            </div>
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-left text-xs">
                                                    <thead>
                                                        <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                                                            <th className="py-2 pr-3">Assessment</th>
                                                            <th className="py-2 pr-3">Completed Rounds</th>
                                                            <th className="py-2 pr-3">Valid Scores</th>
                                                            <th className="py-2 pr-3">Score Coverage</th>
                                                            <th className="py-2 pr-3">Candidates Assessed</th>
                                                            <th className="py-2">Average Score</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {evidenceSummary.rows.map((row) => (
                                                            <tr key={row.key} className="border-b border-slate-100">
                                                                <td className="py-2 pr-3 font-semibold text-slate-800">{row.label}</td>
                                                                <td className="py-2 pr-3">{row.completed}</td>
                                                                <td className="py-2 pr-3">{row.valid}</td>
                                                                <td className="py-2 pr-3">{row.coveragePct != null ? `${formatScore(row.coveragePct)}%` : '—'}</td>
                                                                <td className="py-2 pr-3">{row.candidates}</td>
                                                                <td className="py-2">{row.avgScore != null ? formatScore(row.avgScore) : '—'}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </>
                                    )}
                                </section>

                                {/* B. Aptitude performance
                                <section className="glass-card rounded-2xl p-5" data-testid="aptitude-performance">
                                    <h4 className="text-sm font-bold text-slate-900 mb-1">Aptitude Performance (0–100 accuracy)</h4>

                                    {!aptitude.available ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="aptitude-performance-empty">
                                            <p className="text-sm font-semibold text-slate-700">No usable aptitude result in scope.</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                                {aptitude.reason || 'Completed aptitude rounds without graded responses are excluded, never counted as zero.'}
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4" data-testid="aptitude-performance-metrics">
                                            {[
                                                ['Mean per scored round', formatScore(aptitude.mean), `${aptitude.validRounds} scored round(s)`],
                                                ['Pooled accuracy', aptitude.pooled != null ? `${formatScore(aptitude.pooled)}%` : '—', `${aptitude.correct}/${aptitude.responses} graded response(s)`],
                                                ['Candidates with a score', String(aptitude.candidates), `${aptitude.completedRounds} completed round(s)`],
                                                ['Lowest scored round', formatScore(aptitude.min), 'minimum usable round'],
                                                ['Highest scored round', formatScore(aptitude.max), 'maximum usable round'],
                                            ].map(([label, value, hint]) => (
                                                <div key={label} className="rounded-xl border border-slate-200 bg-white/60 p-4 min-w-0">
                                                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</div>
                                                    <div className="text-2xl font-black mt-1 text-slate-900">{value}</div>
                                                    <div className="text-[11px] text-slate-400 mt-1">{hint}</div>
                                                </div>
                                            ))}
                                            <p className="col-span-full text-[11px] text-slate-400 leading-relaxed" data-testid="aptitude-sample-note">
                                            </p>
                                        </div>
                                    )}
                                </section> */}

                                {/* C. Consolidated Assessment Insights */}
                                <section className="glass-card rounded-2xl p-5" data-testid="assessment-insights">
                                    <h2 className="text-xl font-bold text-slate-900 mb-1">Assessment Insights</h2>
                                    <div className="mt-3 divide-y divide-slate-200/70">
                                        <div className="pb-5" data-testid="aptitude-assessment-insights">
                                            <br></br>
                                    <h5 className="text-l font-bold text-slate-900 mb-1"> 1. Aptitude Assessment Insights</h5>
                                    <p className="text-[11px] text-slate-400 mb-3">
                                    </p>
                                    {(() => {
                                        const aptComp = assessment?.components?.aptitude;
                                        const aptRow = evidenceRows.find((r) => r.type === 'aptitude') || null;
                                        const completed = aptComp?.completed_rounds ?? aptRow?.completed ?? 0;
                                        const withResults = aptComp?.rounds_with_results ?? aptRow?.withResults ?? 0;
                                        const valid = aptComp?.rounds_with_valid_scores ?? aptRow?.valid ?? 0;
                                        const candidates = aptComp?.candidates ?? aptRow?.candidates ?? 0;
                                        const coveragePct = aptRow?.coveragePct != null
                                            ? aptRow.coveragePct
                                            : (completed > 0 ? Math.round((valid / completed) * 1000) / 10 : null);
                                        const available = aptComp?.available === true || valid > 0;
                                        const needsReview = completed > 0 && valid === 0;
                                        return (
                                            <>
                                                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                                                    <div></div>
                                                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded self-start ${
                                                        valid > 0 ? 'bg-emerald-50 text-emerald-600' : needsReview ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'
                                                    }`}>
                                                        {valid > 0 ? 'Available' : needsReview ? 'Needs Review' : 'Unavailable'}
                                                    </span>
                                                </div>
                                                <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-3">
                                                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Completed Eligible Assessments</div>
                                                        <div className="text-lg font-black text-slate-900 mt-0.5">{completed}</div>
                                                    </div>
                                                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Assessments With Results</div>
                                                        <div className="text-lg font-black text-slate-900 mt-0.5">{withResults}</div>
                                                    </div>
                                                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Assessments With Valid Scores</div>
                                                        <div className="text-lg font-black text-slate-900 mt-0.5">{valid}</div>
                                                    </div>
                                                    <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Score Coverage</div>
                                                        <div className="text-lg font-black text-slate-900 mt-0.5">{coveragePct != null ? `${coveragePct.toFixed(1)}%` : '—'}</div>
                                                    </div>
                                                    <div className="rounded-lg border border-slate-200 bg-white p-3 col-span-2 lg:col-span-1">
                                                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Distinct Candidates With Valid Scores</div>
                                                        <div className="text-lg font-black text-slate-900 mt-0.5">{candidates}</div>
                                                    </div>
                                                </div>
                                                {completed === 0 ? (
                                                    <p className="text-xs text-slate-500 mt-2">No completed eligible aptitude assessments in scope.</p>
                                                ) : valid === 0 ? (
                                                    <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                                                        No usable aptitude scores available. {withResults > 0
                                                            ? 'Assessments have persisted results but no valid scores — review for follow-up.'
                                                            : 'Completed assessments currently have no persisted results — results may be pending or require follow-up.'}
                                                    </p>
                                                ) : (
                                                    <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                                                        Aptitude scores are available for {valid} of {completed} completed eligible assessments. Coverage is {coveragePct != null ? `${coveragePct.toFixed(1)}%` : '—'}. {candidates} distinct candidate(s) have valid scores.
                                                    </p>
                                                )}
                                                {aptComp?.reason && !available && completed > 0 && (
                                                    <p className="text-[11px] text-slate-500 mt-1">{aptComp.reason}</p>
                                                )}
                                            </>
                                        );
                                    })()}
                                        </div>

                                {/* Coding & Interview Assessment Insights */}
                                        <div className="pt-5" data-testid="assessment-type-status">
                                    <div className="space-y-4">
                                        {statusRows.map((row) => {
                                            const label = safeAssessmentLabel(row.label, row.type);
                                            const isCoding = row.type === 'coding';
                                            const isInterview = row.type === 'interview';
                                            const completed = row.completed || 0;
                                            const withResults = row.withResults || 0;
                                            const valid = row.valid || 0;
                                            const coveragePct = row.coveragePct != null ? row.coveragePct : (completed > 0 ? Math.round((valid / completed) * 1000) / 10 : null);
                                            const candidates = row.candidates || 0;
                                            const needsReview = completed > 0 && valid === 0;
                                            return (
                                                <div key={row.key} className="rounded-xl border border-slate-200 bg-white/60 p-4" data-testid={`assessment-type-${row.key}`}>
                                                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                                                        <div>
                                                            <h5 className="text-sm font-bold text-slate-800">{isCoding ? 'Coding Assessment Insights' : isInterview ? 'Interview Assessment Insights' : label}</h5>
                                                            <p className="text-[11px] text-slate-400 mt-0.5">

                                                            </p>
                                                        </div>
                                                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded self-start ${
                                                            valid > 0 ? 'bg-emerald-50 text-emerald-600' : needsReview ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-500'
                                                        }`}>
                                                            {valid > 0 ? 'Available' : needsReview ? 'Needs Review' : 'Unavailable'}
                                                        </span>
                                                    </div>
                                                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
                                                        <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                            <div className="text-[10px] uppercase tracking-wider text-slate-500">Completed Eligible Rounds</div>
                                                            <div className="text-lg font-black text-slate-900 mt-0.5">{completed}</div>
                                                        </div>
                                                        {(isCoding || isInterview) ? (
                                                            <>
                                                                <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Rounds With Results</div>
                                                                    <div className="text-lg font-black text-slate-900 mt-0.5">{withResults}</div>
                                                                </div>
                                                                <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Rounds With Valid Scores</div>
                                                                    <div className="text-lg font-black text-slate-900 mt-0.5">{valid}</div>
                                                                </div>
                                                            </>
                                                        ) : (
                                                            <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                                <div className="text-[10px] uppercase tracking-wider text-slate-500">Rounds With Valid Scores</div>
                                                                <div className="text-lg font-black text-slate-900 mt-0.5">{valid} / {completed}</div>
                                                            </div>
                                                        )}
                                                        <div className="rounded-lg border border-slate-200 bg-white p-3">
                                                            <div className="text-[10px] uppercase tracking-wider text-slate-500">Score Coverage</div>
                                                            <div className="text-lg font-black text-slate-900 mt-0.5">{coveragePct != null ? `${coveragePct.toFixed(1)}%` : '—'}</div>
                                                        </div>
                                                        <div className="rounded-lg border border-slate-200 bg-white p-3 col-span-2 lg:col-span-1">
                                                            <div className="text-[10px] uppercase tracking-wider text-slate-500">Distinct Candidates With Valid Scores</div>
                                                            <div className="text-lg font-black text-slate-900 mt-0.5">{candidates}</div>
                                                        </div>
                                                    </div>
                                                    {(isCoding || isInterview) && completed > 0 && (
                                                        <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                                                            {isCoding ? 'Coding' : 'Interview'} scores are available for {valid} of {completed} completed eligible rounds.
                                                            {coveragePct != null ? ` Coverage ${coveragePct.toFixed(1)}%.` : ''}
                                                            {candidates > 0 ? ` ${candidates} distinct candidate(s) have valid scores.` : ''}
                                                            {(withResults > 0 && valid === 0)
                                                                ? ' There are persisted results/turns but no usable scores — this can reflect pending scoring or sessions with turns but no usable final scores; review for follow-up.'
                                                                : (valid === 0 && withResults === 0)
                                                                    ? ' Completed rounds currently have no persisted results — results may be pending or require follow-up.'
                                                                    : ''}
                                                        </p>
                                                    )}
                                                    {!row.available && row.reason && (
                                                        <p className="text-[11px] text-slate-500 mt-1">{row.reason}</p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                        </div>
                                    </div>
                                </section>

                                {/* E. Evidence gaps
                                <section className="glass-card rounded-2xl p-5" data-testid="evidence-gaps">
                                    <h4 className="text-l font-bold text-slate-900 mb-1">Evidence Gaps</h4>
                                    <br></br>
                                    <p className="text-[11px] text-slate-400 mb-3">
                                    </p>
                                    {evidenceGaps.length === 0 ? (
                                        <p className="text-sm text-slate-500" data-testid="evidence-gaps-empty">No completed assessment rounds in scope.</p>
                                    ) : (
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-left text-xs">
                                                <thead>
                                                    <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                                                        <th className="py-2 pr-3">Assessment</th>
                                                        <th className="py-2 pr-3">Completed rounds</th>
                                                        <th className="py-2 pr-3">Usable scores</th>
                                                        <th className="py-2 pr-3">Missing evidence</th>
                                                        <th className="py-2">Missing %</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {evidenceGaps.map((row) => (
                                                        <tr key={row.key} className="border-b border-slate-100">
                                                            <td className="py-2 pr-3 font-semibold text-slate-800">{row.label}</td>
                                                            <td className="py-2 pr-3">{row.completed}</td>
                                                            <td className="py-2 pr-3">{row.valid}</td>
                                                            <td className="py-2 pr-3">{row.missing}</td>
                                                            <td className="py-2">{row.missingPct != null ? `${formatScore(row.missingPct)}%` : '—'}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </section> */}
                                {/* Recommended Actions
                                <section className="glass-card rounded-2xl p-5" data-testid="recommended-actions">
                                    <h4 className="text-sm font-bold text-slate-900 mb-1">Recommended Actions</h4>
                                    <p className="text-[11px] text-slate-400 mb-3">Actions supported by real assessment and scoring records in scope.</p>
                                    {recommendedActionList.length === 0 ? (
                                        <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2">
                                            <CheckCircle size={16} />
                                            <span className="text-sm font-medium">All clear — no follow-up actions identified in scope.</span>
                                        </div>
                                    ) : (
                                        <ul className="space-y-2">
                                            {recommendedActionList.map((a) => (
                                                <li key={a.key} className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white/60 px-3 py-2">
                                                    <span className="mt-0.5">
                                                        {a.tone === 'danger' ? (
                                                            <AlertTriangle size={14} className="text-rose-500" />
                                                        ) : a.tone === 'info' ? (
                                                            <Info size={14} className="text-sky-500" />
                                                        ) : (
                                                            <AlertTriangle size={14} className="text-amber-500" />
                                                        )}
                                                    </span>
                                                    <span className="text-xs text-slate-700 leading-relaxed">{a.text}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </section> */}
                            </div>

                            {hasScoredEvidence ? (
                            <>
                            {/* ── Cohort Outcomes ─────────────────────────── */}
                            <div className="space-y-6">
                                <br></br>
                                <h3 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                                    Cohort Outcomes
                                </h3>

                                {/* Department readiness */}
                                <section className="glass-card rounded-2xl p-5 min-w-0" data-testid="readiness-by-department">
                                    <h4 className="text-l font-bold text-slate-900 mb-1">Department Readiness</h4>
                                    <p className="text-[11px] text-slate-400 mb-3">
                                        
                                    </p>
                                    {deptBars.length === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="department-empty">
                                            <p className="text-sm font-semibold text-slate-700">No scored attempts by department.</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                                Department readiness uses eligible scored attempts on the 0–100 scale. Departments with
                                                no scored evidence are not shown and are never zeroed.
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="w-full min-w-0" style={{ height: Math.max(200, deptBars.length * 56) }} data-testid="department-chart">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart data={deptBars} layout="vertical" margin={{ top: 8, right: 32, bottom: 4, left: 8 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                                                    <YAxis type="category" dataKey="department" tick={{ fontSize: 11 }} width={120} />
                                                    <Tooltip
                                                        formatter={(value) => [formatScore(value), 'Avg readiness (0–100)']}
                                                        labelFormatter={(label, payload) => {
                                                            const p = payload?.[0]?.payload;
                                                            return p ? `${label} · ${p.candidates} candidate(s), ${p.attempts} attempt(s)` : label;
                                                        }}
                                                    />
                                                    <Bar dataKey="avg_readiness" name="Avg readiness (0–100)" fill="#0ea5e9" radius={[0, 6, 6, 0]}>
                                                        <LabelList dataKey="avg_readiness" position="right" fontSize={11} formatter={(v) => formatScore(v)} />
                                                    </Bar>
                                                </BarChart>
                                            </ResponsiveContainer>
                                        </div>
                                    )}
                                </section>
                            </div>

                            {/* ── Competency Skill Gaps ──────────────────────── */}
                            <div className="space-y-6 mt-6">
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div>
                                        <h3 className="text-sm font-extrabold text-slate-800 uppercase tracking-wider">
                                            Competency Skill Gaps
                                        </h3>
                                        <p className="text-xs text-slate-500 mt-1">
                                            Identify competencies that need improvement using mapped evidence from completed assessments.
                                        </p>
                                    </div>
                                    <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                                        Assessment
                                        <select
                                            aria-label="Filter competency gaps by assessment type"
                                            value={activeSkillGapType}
                                            onChange={(event) => setSkillGapAssessmentType(event.target.value)}
                                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                                        >
                                            <option value="all">All supported assessments</option>
                                            {availableSkillGapTypes.map((type) => (
                                                <option key={type} value={type}>
                                                    {type === 'aptitude' ? 'Aptitude' : 'Coding'}
                                                </option>
                                            ))}
                                        </select>
                                    </label>
                                </div>

                                <section className="space-y-4" data-testid="skill-gaps">
                                    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3" data-testid="skill-gap-summary">
                                        {[
                                            ['Competencies Assessed', activeSkillGaps?.summary?.competencies_assessed ?? 0, 'Competencies with countable mapped evidence'],
                                            ['Competencies Unassessed', activeSkillGaps?.summary?.competencies_unassessed ?? 0, 'Configured competencies with countable evidence'],
                                            ['Average Competency Score', formatScore(activeSkillGaps?.summary?.average_competency_score), activeSkillGaps?.summary?.average_competency_score == null ? 'No eligible competency scores in this scope' : 'Average across assessed competency scores'],
                                            ['Largest Competency Gap', formatScore(activeSkillGaps?.summary?.largest_competency_gap), activeSkillGaps?.summary?.largest_competency_gap == null ? 'No demonstrated gaps in this scope' : 'Largest 100 minus average score'],
                                        ].map(([label, value, description]) => (
                                            <div key={label} className="rounded-xl border border-slate-200 bg-white/70 p-4 min-w-0">
                                                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
                                                <p className="text-xl font-black text-slate-900 mt-1">{value}</p>
                                                <p className="text-[10px] text-slate-500 mt-1">{description}</p>
                                            </div>
                                        ))}
                                    </div>

                                    {activeSkillGaps?.summary?.configuration_known === true
                                        && activeSkillGaps?.summary?.configured_competencies === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="skill-gaps-empty">
                                            <p className="text-sm font-semibold text-slate-700">No competencies are configured for this assessment scope.</p>
                                        </div>
                                    ) : gapRows.length === 0 ? (
                                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4" data-testid="skill-gaps-empty">
                                            <p className="text-sm font-semibold text-slate-700">No demonstrated competency gaps yet</p>
                                            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                                No completed assessment in the selected scope has countable results explicitly mapped to a competency in its pinned blueprint. Configured competencies without evidence are listed below.
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="glass-card rounded-2xl p-5">
                                            <h4 className="text-sm font-bold text-slate-900 mb-3">Largest Demonstrated Competency Gaps</h4>
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-left text-xs">
                                                    <thead>
                                                        <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                                                            <th className="py-2 pr-3">Competency</th>
                                                            <th className="py-2 pr-3">Avg Score</th>
                                                            <th className="py-2 pr-3">Gap to 100</th>
                                                            <th className="py-2 pr-3">Assessed Attempts</th>
                                                            <th className="py-2 pr-3">Coverage</th>
                                                            <th className="py-2 pr-3">Evidence Items</th>
                                                            <th className="py-2">Evidence Sources</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {gapRows.map((c) => (
                                                            <tr key={c.competency_id} className="border-b border-slate-100">
                                                                <td className="py-2 pr-3 font-semibold text-slate-800">{c.competency_name}</td>
                                                                <td className="py-2 pr-3 font-bold text-slate-900">{formatScore(c.avg_score)} / 100</td>
                                                                <td className="py-2 pr-3">{formatScore(c.gap_to_100)}</td>
                                                                <td className="py-2 pr-3">{c.assessed_attempts} / {c.eligible_attempts}</td>
                                                                <td className="py-2 pr-3">{c.assessed_attempts} / {c.eligible_attempts} · {c.coverage_percent}%</td>
                                                                <td className="py-2 pr-3">{c.evidence_items}</td>
                                                                <td className="py-2">{(c.evidence_sources || []).map((type) => type === 'aptitude' ? 'Aptitude' : 'Coding').join(', ') || '—'}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    )}

                                </section>
                            </div>

                            </>
                            ) : (
                            <p className="text-xs text-slate-400 mt-6 leading-relaxed" data-testid="readiness-unavailable-summary">
                                Cohort readiness distribution, department readiness and skill gaps stay hidden until at
                                least one eligible scored attempt exists — see the competency-readiness status above.
                            </p>
                            )}
                        </section>

                        {/* ── E. Insights ─────────────────────────────── */}
                        <section className="mt-6 overflow-hidden rounded-2xl border border-slate-300 bg-white shadow-sm" data-testid="readiness-insights">
                            <header className="border-b border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
                                <h2 className="flex items-center gap-2 text-base font-bold text-slate-900">
                                    <Lightbulb size={17} className="text-amber-500" /> Readiness Intelligence
                                </h2>
                                <p className="mt-1 text-xs text-slate-500">
                                   
                                </p>
                            </header>
                            <div className="divide-y divide-slate-200 px-5 sm:px-6" data-testid="readiness-intelligence-content">
                                <article className="py-5 first:pt-4">
                                    <h3 className="text-sm font-semibold text-slate-900">Overall Scored Readiness</h3>
                                    <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                                        Summarizes the overall readiness of candidates based on completed assessments with valid competency evidence. Candidates without sufficient evidence are excluded from scoring.
                                    </p>
                                </article>
                                <article className="py-5">
                                    <h3 className="text-sm font-semibold text-slate-900">Competency Strengths and Development Areas</h3>
                                    <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                                        Highlights relative competency strengths and areas that may need improvement, based on normalized scores from eligible assessment evidence.
                                    </p>
                                </article>
                                <article className="py-5 last:pb-4">
                                    <h3 className="text-sm font-semibold text-slate-900">Assessment Evidence Coverage</h3>
                                    <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                                        Shows how effectively completed assessments contribute to readiness analysis. Missing or unmapped evidence is identified separately and is not treated as poor performance.
                                    </p>
                                </article>
                                <a
                                    className="inline-flex py-4 text-xs font-semibold text-blue-700 hover:text-blue-900"
                                    href="#assessment-coverage"
                                >
                                    Review evidence coverage →
                                </a>
                            </div>
                        </section>

                        {/* ── Evidence footer ──────────────────────────── */}

                    </>
                )}
            </main>
        </TPOLayout>
    );
}
