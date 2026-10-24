import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis,
    CartesianGrid, Tooltip, Legend, LabelList,
} from 'recharts';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import TPOLayout, { TPOMenuButton } from '../components/TPOLayout';
import {
    AlertCircle, ArrowLeft, RefreshCw, Download, TrendingUp,
    Filter, FileText, BarChart3,
} from 'lucide-react';

const PERIODS = [
    { value: '7', label: 'Last 7 days' },
    { value: '30', label: 'Last 30 days' },
    { value: '90', label: 'Last 90 days' },
    { value: 'all', label: 'All time' },
];

const EXPORT_TYPES = [
    { value: 'drive', label: 'Drive Report' },
    { value: 'candidate', label: 'Candidate List' },
    { value: 'summary', label: 'Summary Report' },
    { value: 'competency', label: 'Competency Report' },
];

function buildQuery(filters) {
    const params = new URLSearchParams();
    if (filters.period && filters.period !== 'all') params.set('period', filters.period);
    if (filters.company) params.set('company', filters.company);
    if (filters.role) params.set('role', filters.role);
    if (filters.drive_status) params.set('drive_status', filters.drive_status);
    const qs = params.toString();
    return qs ? `?${qs}` : '';
}

function csvEscape(v) {
    if (v === null || v === undefined) return '';
    const s = String(v);
    // Guard against spreadsheet formula injection.
    const guarded = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
    if (/[",\n\r]/.test(guarded)) {
        return `"${guarded.replace(/"/g, '""')}"`;
    }
    return guarded;
}

function toCsv(headers, rows) {
    const lines = [headers.map(csvEscape).join(',')];
    for (const r of rows) lines.push(r.map(csvEscape).join(','));
    return lines.join('\r\n');
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

export default function TPOAnalyticsPage() {
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [toast, setToast] = useState(null);

    const [filters, setFilters] = useState({
        period: 'all', company: '', role: '', drive_status: '',
    });
    const [compMode, setCompMode] = useState('weight'); // 'weight' | 'score'
    const [driveSort, setDriveSort] = useState({ key: 'company_name', dir: 'asc' });
    const [drivePage, setDrivePage] = useState(1);
    const [exportType, setExportType] = useState('drive');
    const [exportFormat, setExportFormat] = useState('csv');
    const DRIVE_PAGE_SIZE = 8;

    const fetchAnalytics = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get(`/report/admin/analytics/overview${buildQuery(filters)}`);
            setData(res.data);
        } catch (err) {
            setError(err?.response?.data?.detail || err?.message || 'Failed to load analytics data');
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => {
        fetchAnalytics();
    }, [fetchAnalytics]);

    const setFilter = (key, value) => {
        setFilters((f) => ({ ...f, [key]: value }));
        setDrivePage(1);
    };

    const kpis = data?.kpis;
    const trend = data?.activity_trend || [];
    const rounds = data?.round_performance || [];
    const funnel = data?.funnel?.stages || [];
    const compByDept = data?.competency_by_department || { departments: [], available: false };
    const insights = data?.competency_insights || [];
    const competencyCoverage = data?.competency_coverage;
    const drives = data?.drives || [];
    const filterOptions = data?.filters || {};

    // ── Competency by department dataset (Weight vs Average Score) ──────
    const compChartData = useMemo(() => {
        if (!compByDept.available || !compByDept.departments.length) return [];
        // Collect all competency names across departments.
        const names = [];
        const seen = new Set();
        for (const d of compByDept.departments) {
            for (const c of d.competencies) {
                if (!seen.has(c.competency_name)) {
                    seen.add(c.competency_name);
                    names.push(c.competency_name);
                }
            }
        }
        return compByDept.departments.map((d) => {
            const row = { department: d.department };
            for (const name of names) {
                const comp = d.competencies.find((c) => c.competency_name === name);
                if (compMode === 'weight') {
                    row[name] = comp && comp.weight_pct != null ? comp.weight_pct : null;
                } else {
                    row[name] = comp && comp.avg_score != null ? comp.avg_score : null;
                }
            }
            return row;
        });
    }, [compByDept, compMode]);

    const compNames = useMemo(() => {
        const seen = new Set();
        const out = [];
        for (const d of compByDept.departments || []) {
            for (const c of d.competencies) {
                if (!seen.has(c.competency_name)) {
                    seen.add(c.competency_name);
                    out.push(c.competency_name);
                }
            }
        }
        return out;
    }, [compByDept]);

    const COMP_COLORS = ['#0ea5e9', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#14b8a6'];

    // ── Drive table: sort + paginate ───────────────────────────────────
    const sortedDrives = useMemo(() => {
        const arr = [...drives];
        const { key, dir } = driveSort;
        arr.sort((a, b) => {
            const av = a[key];
            const bv = b[key];
            if (typeof av === 'number' && typeof bv === 'number') {
                return dir === 'asc' ? av - bv : bv - av;
            }
            return dir === 'asc'
                ? String(av).localeCompare(String(bv))
                : String(bv).localeCompare(String(av));
        });
        return arr;
    }, [drives, driveSort]);

    const drivePages = Math.max(1, Math.ceil(sortedDrives.length / DRIVE_PAGE_SIZE));
    const pagedDrives = sortedDrives.slice(
        (drivePage - 1) * DRIVE_PAGE_SIZE,
        drivePage * DRIVE_PAGE_SIZE,
    );

    const toggleDriveSort = (key) => {
        setDriveSort((s) =>
            s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }
        );
    };

    // ── Exports (client-side from already-filtered data) ───────────────
    const exportPreviewCount = useMemo(() => {
        if (exportType === 'drive') return drives.length;
        if (exportType === 'competency') return insights.length;
        if (exportType === 'summary') return 1;
        return kpis ? kpis.enrolled_candidates : 0;
    }, [exportType, drives.length, insights.length, kpis]);

    const handleExport = () => {
        if (!data) return;
        const ts = data.generated_at || new Date().toISOString();
        const meta = {
            generated_at: ts,
            filters: {
                period: filters.period || 'all',
                company: filters.company || null,
                role: filters.role || null,
                drive_status: filters.drive_status || null,
            },
        };

        if (exportFormat === 'json') {
            let payload;
            if (exportType === 'drive') payload = { ...meta, drives };
            else if (exportType === 'competency') payload = { ...meta, competencies: insights };
            else if (exportType === 'summary') payload = { ...meta, kpis, activity_trend: trend, round_performance: rounds, funnel };
            else payload = { ...meta, kpis };
            downloadBlob(JSON.stringify(payload, null, 2), `analytics-${exportType}.json`, 'application/json');
            setToast({ type: 'success', message: 'JSON export downloaded' });
            return;
        }

        // CSV
        let headers, rows, name;
        if (exportType === 'drive') {
            headers = ['drive_id', 'company_name', 'target_role', 'status', 'enrolled', 'completed', 'completion_rate'];
            rows = drives.map((d) => [d.drive_id, d.company_name, d.target_role, d.status, d.enrolled, d.completed, d.completion_rate]);
            name = 'drive-report';
        } else if (exportType === 'competency') {
            headers = ['competency_id', 'competency_name', 'avg_score', 'evidence_count', 'coverage_rate', 'top_department'];
            rows = insights.map((c) => [c.competency_id, c.competency_name, c.avg_score, c.evidence_count, c.coverage_rate, c.top_department]);
            name = 'competency-report';
        } else if (exportType === 'summary') {
            headers = ['metric', 'value'];
            rows = [
                ['total_drives', kpis?.total_drives],
                ['enrolled_candidates', kpis?.enrolled_candidates],
                ['completion_rate', kpis?.completion_rate],
                ['passed_candidates', kpis?.passed_candidates ?? 'unavailable'],
            ];
            name = 'summary-report';
        } else {
            headers = ['drive_id', 'company_name', 'target_role', 'enrolled', 'completed', 'completion_rate'];
            rows = drives.map((d) => [d.drive_id, d.company_name, d.target_role, d.enrolled, d.completed, d.completion_rate]);
            name = 'candidate-list';
        }
        const csv = toCsv(headers, rows);
        // Prepend metadata as comment lines is not standard CSV; include as a header row set instead.
        const metaCsv = `generated_at,${csvEscape(ts)}\r\nfilters,${csvEscape(JSON.stringify(meta.filters))}\r\n`;
        downloadBlob('\uFEFF' + metaCsv + csv, `${name}.csv`, 'text/csv;charset=utf-8;');
        setToast({ type: 'success', message: 'CSV export downloaded' });
    };

    if (loading && !data) return <PageSkeleton variant="light" cardCount={4} />;

    const passedUnavailable = kpis && kpis.passed_candidates == null;

    return (
        <TPOLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
                    <div>
                        <h1 className="text-xl font-bold text-slate-900">TPO Analytics</h1>
                        <p className="text-sm text-slate-500">
                            Recruitment performance, candidate progress and competency insights
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={fetchAnalytics}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
                        >
                            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                            Refresh
                        </button>
                        <button
                            onClick={() => navigate('/tpo/dashboard')}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
                        >
                            <ArrowLeft size={15} />
                            Dashboard
                        </button>
                        <TPOMenuButton />
                    </div>
                </div>

                {/* Filters */}
                <section className="glass-card rounded-2xl p-4 mb-6">
                    <div className="flex items-center gap-2 mb-3">
                        <Filter size={15} className="text-slate-400" />
                        <span className="text-sm font-semibold text-slate-700">Filters</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
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
                        <div className="flex items-end">
                            <span className="text-xs text-slate-400 pb-2">
                                Filters apply to KPIs, charts, tables and exports.
                            </span>
                        </div>
                    </div>
                </section>

                {/* Error state */}
                {error && (
                    <div className="bg-white rounded-2xl p-6 border border-red-200 shadow-xs mb-6">
                        <div className="flex items-center gap-2 text-red-600 mb-2">
                            <AlertCircle size={18} />
                            <span className="font-semibold text-sm">Failed to load analytics</span>
                        </div>
                        <p className="text-sm text-slate-600 mb-3">{error}</p>
                        <button
                            onClick={fetchAnalytics}
                            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {/* Empty state */}
                {!error && !data && (
                    <div className="glass-card rounded-2xl p-8">
                        <p className="text-sm text-slate-500 text-center">No analytics data available.</p>
                    </div>
                )}

                {data && (
                    <>
                        {/* KPI cards */}
                        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                            <div className="p-4 rounded-2xl glass-card">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Total Drives</span>
                                <span className="text-2xl font-bold text-sky-600">{kpis?.total_drives ?? 0}</span>
                            </div>
                            <div className="p-4 rounded-2xl glass-card">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Enrolled Candidates</span>
                                <span className="text-2xl font-bold text-violet-600">{kpis?.enrolled_candidates ?? 0}</span>
                            </div>
                            <div className="p-4 rounded-2xl glass-card">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Candidate Completion Rate</span>
                                <span className="text-2xl font-bold text-emerald-600">
                                    {kpis?.completion_rate != null ? `${kpis.completion_rate}%` : '—'}
                                </span>
                            </div>
                            <div className="p-4 rounded-2xl glass-card">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Passed Candidates</span>
                                {passedUnavailable ? (
                                    <span className="text-sm font-medium text-slate-400">Not tracked</span>
                                ) : (
                                    <span className="text-2xl font-bold text-emerald-600">{kpis?.passed_candidates}</span>
                                )}
                            </div>
                        </section>

                        {/* Activity trend */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <h2 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
                                <TrendingUp size={15} className="text-sky-500" /> Recruitment Activity Trend
                            </h2>
                            {trend.length === 0 ? (
                                <p className="text-sm text-slate-500 py-6 text-center">
                                    No historical activity in the selected period.
                                </p>
                            ) : (
                                <ResponsiveContainer width="100%" height={260}>
                                    <LineChart data={trend}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                                        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                                        <Tooltip />
                                        <Legend />
                                        <Line type="monotone" dataKey="enrolled" name="Enrolled" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                                        <Line type="monotone" dataKey="completed" name="Completed" stroke="#10b981" strokeWidth={2} dot={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                            )}
                        </section>

                        {/* Round-wise performance */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <h2 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
                                <BarChart3 size={15} className="text-violet-500" /> Round-wise Performance
                            </h2>
                            {rounds.length === 0 ? (
                                <p className="text-sm text-slate-500 py-6 text-center">No round data available.</p>
                            ) : (
                                <>
                                    <ResponsiveContainer width="100%" height={240}>
                                        <BarChart data={rounds}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                            <XAxis dataKey="round_label" tick={{ fontSize: 12 }} />
                                            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                                            <Tooltip />
                                            <Legend />
                                            <Bar dataKey="enrolled" name="Enrolled" fill="#0ea5e9" />
                                            <Bar dataKey="completed" name="Completed" fill="#10b981" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                    <table className="w-full text-left mt-3 text-sm">
                                        <thead>
                                            <tr className="text-xs text-slate-500 uppercase border-b border-slate-200">
                                                <th className="py-2">Round</th>
                                                <th className="py-2">Completed</th>
                                                <th className="py-2">Avg Score</th>
                                                <th className="py-2">Scored candidates</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {rounds.map((r) => (
                                                <tr key={r.round_type} className="border-b border-slate-100">
                                                    <td className="py-2 font-medium">{r.round_label}</td>
                                                    <td className="py-2">{r.completed} / {r.enrolled}</td>
                                                    <td className="py-2">
                                                        {r.avg_score != null ? r.avg_score : <span className="text-slate-400">No scores</span>}
                                                    </td>
                                                    <td className="py-2">{r.score_count}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </>
                            )}
                        </section>

                        {/* Conversion funnel */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <h2 className="text-sm font-bold text-slate-900 mb-3">Candidate Conversion Funnel</h2>
                            {funnel.length === 0 ? (
                                <p className="text-sm text-slate-500 py-4 text-center">No funnel data available.</p>
                            ) : (
                                <div className="space-y-2">
                                    {funnel.map((stage, i) => {
                                        const pct = stage.conversion || 0;
                                        return (
                                            <div key={stage.stage}>
                                                <div className="flex justify-between text-xs text-slate-600 mb-1">
                                                    <span>{stage.stage}</span>
                                                    <span>{stage.count} ({pct}%)</span>
                                                </div>
                                                <div className="h-6 bg-slate-100 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full rounded-full transition-all"
                                                        style={{
                                                            width: `${Math.max(pct, 2)}%`,
                                                            backgroundColor: COMP_COLORS[i % COMP_COLORS.length],
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                    <p className="text-[11px] text-slate-400 pt-1">
                                    </p>
                                </div>
                            )}
                        </section>

                        {/* Competency weight by department */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <div className="flex items-center justify-between mb-2">
                                <h2 className="text-sm font-bold text-slate-900">Competency by Department</h2>
                                <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                                    <button
                                        onClick={() => setCompMode('weight')}
                                        className={`px-3 py-1 text-xs font-semibold ${compMode === 'weight' ? 'bg-sky-600 text-white' : 'bg-white text-slate-600'}`}
                                    >Weight</button>
                                    <button
                                        onClick={() => setCompMode('score')}
                                        className={`px-3 py-1 text-xs font-semibold ${compMode === 'score' ? 'bg-sky-600 text-white' : 'bg-white text-slate-600'}`}
                                    >Average Score</button>
                                </div>
                            </div>
                            {!compByDept.available || compChartData.length === 0 ? (
                                <p className="text-sm text-slate-500 py-6 text-center">
                                    No department-linked competency data configured or scored yet.
                                </p>
                            ) : (
                                <ResponsiveContainer width="100%" height={Math.max(180, compChartData.length * 60)}>
                                    <BarChart data={compChartData} layout="vertical" stackOffset="sign">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                        <XAxis type="number" tick={{ fontSize: 11 }} />
                                        <YAxis type="category" dataKey="department" tick={{ fontSize: 11 }} width={110} />
                                        <Tooltip />
                                        <Legend />
                                        {compNames.map((name, i) => (
                                            <Bar
                                                key={name}
                                                dataKey={name}
                                                stackId="comp"
                                                fill={COMP_COLORS[i % COMP_COLORS.length]}
                                            />
                                        ))}
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </section>

                        {/* Competency evidence coverage and supported reasons */}
                        <section className="glass-card rounded-2xl p-5 mb-6" data-testid="competency-coverage">
                            <h2 className="text-sm font-bold text-slate-900">Competency Evidence Coverage</h2>
                            <p className="mt-1 text-xs text-slate-500"></p>
                            {!competencyCoverage ? (
                                <p className="py-4 text-sm text-slate-500">Coverage details are unavailable from this response.</p>
                            ) : competencyCoverage.eligible_contexts === 0 ? (
                                <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600" data-testid="competency-coverage-empty">
                                    No eligible assessment contexts match the current filters.
                                </p>
                            ) : (
                                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                                    {[
                                        ['Eligible contexts', competencyCoverage.eligible_contexts],
                                        ['No session found', competencyCoverage.contexts_without_session],
                                        ['Missing pinned snapshot', competencyCoverage.contexts_without_snapshot],
                                        ['No competency configuration', competencyCoverage.contexts_without_competencies],
                                        ['Mapping pending', competencyCoverage.mapping_statuses?.pending],
                                        ['Mapping failed', competencyCoverage.mapping_statuses?.failed],
                                        ['No countable mapped evidence', competencyCoverage.contexts_without_countable_evidence],
                                        ['Final scores available', competencyCoverage.final_scored_contexts],
                                        ['Provisional scores available', competencyCoverage.provisional_scored_contexts],
                                        ['Scoring errors', competencyCoverage.scoring_errors],
                                    ].map(([label, value]) => (
                                        <div key={label} className="rounded-xl border border-slate-200 bg-white/70 p-3">
                                            <div className="text-[11px] font-semibold text-slate-500">{label}</div>
                                            <div className="mt-1 text-xl font-bold text-slate-900">{value ?? 'Unavailable'}</div>
                                        </div>
                                    ))}
                                    <p className="col-span-full text-[11px] leading-relaxed text-slate-500">
                                       
                                    </p>
                                </div>
                            )}
                        </section>

                        {/* Competency insights */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <h2 className="text-sm font-bold text-slate-900 mb-3">Competency Insights</h2>
                            {insights.length === 0 ? (
                                <p className="text-sm text-slate-500 py-4 text-center">No competency insights available.</p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left text-sm">
                                        <thead>
                                            <tr className="text-xs text-slate-500 uppercase border-b border-slate-200">
                                                <th className="py-2">Competency</th>
                                                <th className="py-2">Avg Score</th>
                                                <th className="py-2">Evidence Coverage</th>
                                                <th className="py-2">Assessed</th>
                                                <th className="py-2">Top Department</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {insights.map((c) => (
                                                <tr key={c.competency_id} className="border-b border-slate-100">
                                                    <td className="py-2 font-medium">{c.competency_name}</td>
                                                    <td className="py-2">
                                                        {c.avg_score != null ? c.avg_score : <span className="text-slate-400">Unavailable</span>}
                                                    </td>
                                                    <td className="py-2">{c.coverage_rate}%</td>
                                                    <td className="py-2">{c.assessed} / {c.total}</td>
                                                    <td className="py-2">{c.top_department || <span className="text-slate-400">—</span>}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </section>

                        {/* Drive performance comparison */}
                        <section className="glass-card rounded-2xl p-5 mb-6">
                            <h2 className="text-sm font-bold text-slate-900 mb-3">Drive Performance Comparison</h2>
                            {drives.length === 0 ? (
                                <p className="text-sm text-slate-500 py-4 text-center">No drives match the current filters.</p>
                            ) : (
                                <>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-left text-sm">
                                            <thead>
                                                <tr className="text-xs text-slate-500 uppercase border-b border-slate-200">
                                                    {[
                                                        ['company_name', 'Company'], ['target_role', 'Role'],
                                                        ['enrolled', 'Enrolled'], ['completed', 'Completed'],
                                                        ['completion_rate', 'Completion Rate'], ['status', 'Status'],
                                                    ].map(([key, label]) => (
                                                        <th
                                                            key={key}
                                                            className="py-2 cursor-pointer select-none"
                                                            onClick={() => toggleDriveSort(key)}
                                                        >
                                                            {label} {driveSort.key === key ? (driveSort.dir === 'asc' ? '↑' : '↓') : ''}
                                                        </th>
                                                    ))}
                                                    <th className="py-2">Details</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {pagedDrives.map((d) => (
                                                    <tr key={d.drive_id} className="border-b border-slate-100 hover:bg-slate-50/50">
                                                        <td className="py-2 font-medium">{d.company_name}</td>
                                                        <td className="py-2">{d.target_role}</td>
                                                        <td className="py-2">{d.enrolled}</td>
                                                        <td className="py-2">{d.completed}</td>
                                                        <td className="py-2">{d.completion_rate}%</td>
                                                        <td className="py-2">
                                                            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${d.status === 'completed' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{d.status}</span>
                                                        </td>
                                                        <td className="py-2">
                                                            <button
                                                                onClick={() => navigate(`/tpo/mock-drives?drive=${d.drive_id}`)}
                                                                className="text-sky-600 hover:text-sky-700 text-xs font-semibold"
                                                            >View</button>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    {drivePages > 1 && (
                                        <div className="flex items-center justify-between mt-3">
                                            <span className="text-xs text-slate-500">Page {drivePage} of {drivePages}</span>
                                            <div className="flex gap-2">
                                                <button
                                                    disabled={drivePage <= 1}
                                                    onClick={() => setDrivePage((p) => p - 1)}
                                                    className="px-3 py-1 rounded border border-slate-200 text-xs disabled:opacity-40"
                                                >Prev</button>
                                                <button
                                                    disabled={drivePage >= drivePages}
                                                    onClick={() => setDrivePage((p) => p + 1)}
                                                    className="px-3 py-1 rounded border border-slate-200 text-xs disabled:opacity-40"
                                                >Next</button>
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                        </section>

                        {/* Reports & exports */}
                        <section className="glass-card rounded-2xl p-5">
                            <h2 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
                                <Download size={15} className="text-emerald-500" /> Reports &amp; Exports
                            </h2>
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs font-medium text-slate-500">Report type</span>
                                    <select
                                        value={exportType}
                                        onChange={(e) => setExportType(e.target.value)}
                                        className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white"
                                    >
                                        {EXPORT_TYPES.map((t) => (
                                            <option key={t.value} value={t.value}>{t.label}</option>
                                        ))}
                                    </select>
                                </label>
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs font-medium text-slate-500">Format</span>
                                    <select
                                        value={exportFormat}
                                        onChange={(e) => setExportFormat(e.target.value)}
                                        className="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white"
                                    >
                                        <option value="csv">CSV</option>
                                        <option value="json">JSON</option>
                                    </select>
                                </label>
                                <div className="flex items-end">
                                    <button
                                        onClick={handleExport}
                                        disabled={exportPreviewCount === 0}
                                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold disabled:opacity-40 transition-colors"
                                    >
                                        <FileText size={15} /> Export {exportPreviewCount} row{exportPreviewCount === 1 ? '' : 's'}
                                    </button>
                                </div>
                            </div>
                            <p className="text-[11px] text-slate-400">
                            </p>
                        </section>
                    </>
                )}
            </div>
        </TPOLayout>
    );
}
