import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import TPOLayout, { TPOMenuButton } from '../components/TPOLayout';
import CompanyPatternModal from '../components/CompanyPatternModal';
import { buildPlacementIntelligence, placementIntelligenceUnavailable } from '../utils/placementIntelligence';
import { candidateEligibility, summarizeEligibility } from '../utils/candidateEligibility';
import { Users, X, UserPlus, Download, Building2, CalendarX, TriangleAlert, ArrowRight, TrendingUp } from 'lucide-react';
import { CartesianGrid, XAxis, YAxis, Tooltip, Legend, BarChart, LineChart, Line, ResponsiveContainer } from 'recharts';

function csvEscape(v) {
    if (v === null || v === undefined) return '';
    const s = String(v);
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

function fmtRound(r) {
    return String(r).split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function driveRounds(d) {
    if (Array.isArray(d.rounds) && d.rounds.length) return d.rounds;
    const sr = d.selected_rounds || {};
    return Object.keys(sr).filter((k) => sr[k]);
}

const STATUS_BADGE = {
    active: { label: 'Active', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    published: { label: 'Published', cls: 'bg-sky-50 text-sky-700 border-sky-200' },
    draft: { label: 'Draft', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
    completed: { label: 'Completed', cls: 'bg-slate-100 text-slate-600 border-slate-200' },
};

export default function TPODashboard() {
    const [tpoUser, setTpoUser] = useState(null);
    const [students, setStudents] = useState([]);
    const [cohortStats, setCohortStats] = useState(null);
    const [drives, setDrives] = useState([]);
    const [rosters, setRosters] = useState({});
    const [attentionAvailability, setAttentionAvailability] = useState(null);
    const [placementReadiness, setPlacementReadiness] = useState(null);
    const [rosterSample, setRosterSample] = useState({ checked: 0, total: 0, failed: 0 });
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState(null);
    const [exporting, setExporting] = useState(false);
    const [studentModalOpen, setStudentModalOpen] = useState(false);
    const [studentForm, setStudentForm] = useState({ name: '', email: '', password: '' });
    const [studentSubmitting, setStudentSubmitting] = useState(false);
    const [studentError, setStudentError] = useState(null);
    const [companyModalOpen, setCompanyModalOpen] = useState(false);
    const addStudentBtnRef = useRef(null);

    const navigate = useNavigate();

    useEffect(() => {
        loadTPOData();
    }, []);

    useEffect(() => {
        if (!studentModalOpen) return;
        const onKeyDown = (e) => {
            if (e.key === 'Escape' && !studentSubmitting) closeStudentModal();
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [studentModalOpen, studentSubmitting]);

    const loadTPOData = async (opts = {}) => {
        const silent = opts.silent === true;
        if (!silent) setLoading(true);
        try {
            const [profRes, studentsRes, statsRes, drivesRes, readinessRes] = await Promise.all([
                api.get('/profile/me'),
                api.get('/profile/cohort/students').catch(() => ({ data: null, attentionUnavailable: true })),
                api.get('/report/admin/cohort-stats').catch(() => ({ data: null, attentionUnavailable: true })),
                api.get('/tpo/mock-drives').catch(() => ({ data: null, attentionUnavailable: true })),
                api.get('/report/admin/readiness/overview').catch(() => ({ data: null, attentionUnavailable: true })),
            ]);

            setTpoUser(profRes.data);
            const studentList = Array.isArray(studentsRes.data?.students) ? studentsRes.data.students : [];
            const studentsAvailable = !studentsRes.attentionUnavailable && Array.isArray(studentsRes.data?.students);
            setStudents(studentList);
            setCohortStats(statsRes.data);
            setPlacementReadiness(readinessRes.data);
            const drivesAvailable = !drivesRes.attentionUnavailable && Array.isArray(drivesRes.data);
            const driveList = drivesAvailable ? drivesRes.data : [];
            setDrives(driveList);

            const rosterTargets = driveList
                .filter((d) => d.status !== 'draft')
                .sort((a, b) => (b.id || 0) - (a.id || 0))
                .slice(0, 6);
            const rosterPairs = await Promise.all(
                rosterTargets.map((d) =>
                    api.get(`/tpo/mock-drives/${d.id}/roster`)
                        .then((r) => [d.id, r.data])
                        .catch(() => [d.id, null])
                )
            );
            const rostersAvailable = drivesAvailable && rosterPairs.every(([, data]) => data !== null);
            setRosterSample({
                checked: rosterTargets.length,
                total: driveList.filter((drive) => drive.status !== 'draft').length,
                failed: rosterPairs.filter(([, data]) => data === null).length,
            });
            setRosters(rosterPairs.reduce((acc, [id, data]) => {
                if (data) acc[id] = data;
                return acc;
            }, {}));
            setAttentionAvailability({
                students: studentsAvailable,
                drives: drivesAvailable,
                rosters: rostersAvailable,
                stats: !statsRes.attentionUnavailable && Boolean(statsRes.data),
                readiness: !readinessRes.attentionUnavailable && Boolean(readinessRes.data),
            });
        } catch (err) {
            setAttentionAvailability({ students: false, drives: false, rosters: false, stats: false, readiness: false });
            setToast({ type: 'error', message: 'Failed to load TPO dashboard data' });
        } finally {
            if (!silent) setLoading(false);
        }
    };

    const openStudentModal = () => {
        setStudentForm({ name: '', email: '', password: '' });
        setStudentError(null);
        setStudentModalOpen(true);
    };

    const closeStudentModal = () => {
        if (studentSubmitting) return;
        setStudentModalOpen(false);
        setStudentError(null);
        if (addStudentBtnRef.current) addStudentBtnRef.current.focus();
    };

    const submitStudent = async (e) => {
        e.preventDefault();
        const name = studentForm.name.trim();
        const email = studentForm.email.trim();
        if (!name) {
            setStudentError('Full name is required.');
            return;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            setStudentError('Enter a valid email address.');
            return;
        }
        if (studentForm.password.length < 8) {
            setStudentError('Password must be at least 8 characters.');
            return;
        }
        setStudentSubmitting(true);
        setStudentError(null);
        try {
            await api.post('/auth/register', {
                name,
                email,
                password: studentForm.password,
                role: 'student',
            });
            setStudentModalOpen(false);
            setStudentForm({ name: '', email: '', password: '' });
            setToast({ type: 'success', message: `Student account created for ${email}.` });
            loadTPOData({ silent: true });
        } catch (err) {
            const status = err?.response?.status;
            const detail = err?.response?.data?.detail;
            if (status === 409) {
                setStudentError('Email already registered. Use a different email address.');
            } else if (typeof detail === 'string' && detail.trim()) {
                setStudentError(detail);
            } else if (Array.isArray(detail) && detail.length) {
                setStudentError(detail.map((d) => d.msg).join('; '));
            } else {
                setStudentError('Could not create the student account. Check the connection and try again.');
            }
        } finally {
            setStudentSubmitting(false);
        }
    };

    const handleExport = async () => {
        if (exporting) return;
        setExporting(true);
        try {
            const res = await api.get('/profile/cohort/students');
            const list = Array.isArray(res.data?.students) ? res.data.students : [];
            if (!list.length) {
                setToast({ type: 'info', message: 'No candidate records to export.' });
                return;
            }
            const headers = ['Name', 'Email', 'Roll Number', 'Department', 'CGPA', 'Backlogs', 'Graduation Year', 'Target Role', 'Session Status', 'Aptitude', 'Coding', 'Interview', 'Overall Score'];
            const rows = list.map((s) => [
                s.name,
                s.email,
                s.roll_number,
                s.department,
                s.cgpa,
                s.backlogs_count,
                s.graduation_year,
                s.target_role,
                s.session_status,
                s.rounds?.aptitude?.status ?? '',
                s.rounds?.coding?.status ?? '',
                s.rounds?.interview?.status ?? '',
                s.overall_score,
            ]);
            const ts = new Date().toISOString();
            const metaCsv = `generated_at,${csvEscape(ts)}\r\nsource,${csvEscape('/profile/cohort/students')}\r\nscope,${csvEscape('complete authorized cohort — endpoint returns all students visible to this role; no server-side pagination')}\r\nrecord_count,${csvEscape(list.length)}\r\n`;
            downloadBlob('\uFEFF' + metaCsv + toCsv(headers, rows), `tpo-cohort-${ts.slice(0, 10)}.csv`, 'text/csv;charset=utf-8;');
            setToast({ type: 'success', message: `Exported ${list.length} candidate records.` });
        } catch (err) {
            setToast({ type: 'error', message: 'Export failed — could not fetch authorized candidate records.' });
        } finally {
            setExporting(false);
        }
    };

    const notifyUnavailable = (feature, reason) => {
        setToast({ type: 'info', message: `${feature} is unavailable — ${reason}` });
    };

    const eligibilitySummary = summarizeEligibility(students, { minimumCgpa: 7, maximumBacklogs: 0 });
    const placementInsights = buildPlacementIntelligence({
        drives,
        rosters,
        drivesAvailable: attentionAvailability?.drives === true,
        rostersAvailable: attentionAvailability?.rosters === true,
        readiness: placementReadiness,
        readinessAvailable: attentionAvailability?.readiness === true,
    });
    const placementIntelligenceUnavailableReasons = placementIntelligenceUnavailable({
        drives: attentionAvailability?.drives === true,
        rosters: attentionAvailability?.rosters === true,
        readiness: attentionAvailability?.readiness === true,
    });
    const placementIntelligenceChecksComplete = (
        attentionAvailability?.drives === true
        && attentionAvailability?.rosters === true
        && attentionAvailability?.readiness === true
    );
    const completedDriveCount = drives.filter((drive) => drive.status === 'completed').length;
    const benchmarkLabel = attentionAvailability?.stats && typeof cohortStats?.avg_overall_score === 'number'
        ? `${cohortStats.avg_overall_score.toFixed(1)}%`
        : '—';
    const eligibilityForDrive = (student, drive) => candidateEligibility(student, {
        minimumCgpa: drive.minimum_cgpa,
        maximumBacklogs: drive.maximum_backlogs,
        eligibleBranches: drive.eligible_branches,
    });

    const pipelineDrives = drives
        .filter((d) => d.status !== 'completed')
        .sort((a, b) => {
            const order = { active: 0, published: 1, draft: 2 };
            return (order[a.status] ?? 9) - (order[b.status] ?? 9) || (b.id || 0) - (a.id || 0);
        })
        .slice(0, 3);

    const activityRows = drives
        .map((d) => ({ drive: d, roster: rosters[d.id] }))
        .filter((x) => x.roster && (x.roster.total_participants || 0) > 0)
        .sort((a, b) => (b.roster.total_participants - a.roster.total_participants)
            || ((b.roster.completed_count || 0) - (a.roster.completed_count || 0)))
        .slice(0, 5);

    if (loading) {
        return <PageSkeleton variant="light" cardCount={4} />;
    }

    return (
        <TPOLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            {/* Main content */}
                <main
                    className="pt-8 pb-6 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full"
                >
                {/* Header Banner */}
                <div className="glass-card rounded-3xl p-8 mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-sky-50 text-sky-700 border border-sky-200">
                                Training & Placement Office
                            </span>
                            <span className="text-xs font-semibold text-slate-500">
                                {tpoUser?.tpo_profile?.institution || 'Engineering College'}
                            </span>
                        </div>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                            Corporate Recruitment & Placement Portal
                        </h1>
                        <br></br>
                        <p className="text-sm text-slate-500 mt-1">
                            Drive placement simulations, verify student eligibility criteria, and track multi-round hiring qualifications.
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/profile')}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                        >
                            TPO Profile
                        </button>
                        <TPOMenuButton />
                        <button
                            onClick={loadTPOData}
                            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all"
                        >
                            ↻ Refresh Roster
                        </button>
                    </div>
                </div>

                {/* KPIs */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8" data-testid="kpi-grid">
                    <div className="glass-card rounded-2xl p-6" data-testid="kpi-eligible-pool">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Eligible Candidate Pool</span>
                            <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">✓</span>
                        </div>
                        <div className="text-3xl font-black text-emerald-600">{attentionAvailability?.students ? eligibilitySummary.eligible : '—'}</div>
                        <br></br>
                        <div className="text-xs text-slate-500 mt-1 font-medium">
                            {attentionAvailability?.students
                                ? `${eligibilitySummary.ineligible} ineligible · ${eligibilitySummary.unknown} unknown · CGPA ≥ 7.0 and no backlogs`
                                : 'Candidate eligibility unavailable'}
                        </div>
                    </div>

                    <div className="glass-card rounded-2xl p-6" data-testid="kpi-registered-pool">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Registered Pool</span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">🎓</span>
                        </div>
                        <div className="text-3xl font-black text-slate-900">{attentionAvailability?.students ? students.length : '—'}</div>
                        <br></br>
                        <div className="text-xs text-slate-500 mt-1 font-medium">Candidates across all branches</div>
                    </div>

                    <div className="glass-card rounded-2xl p-6" data-testid="kpi-hiring-partners">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Placement Drives Completed</span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">🏢</span>
                        </div>
                        <div className="text-3xl font-black text-sky-600">{attentionAvailability?.drives ? completedDriveCount : '—'}</div>
                        <br></br>
                        <div className="text-xs text-slate-500 mt-1 font-medium">All-time drives marked completed</div>
                    </div>

                    <div className="glass-card rounded-2xl p-6" data-testid="kpi-benchmark">
                        <div className="flex items-center justify-between mb-3">

                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Institution-wide Assessment Average</span>
                            <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center font-bold text-sm">📊</span>
                        </div>
                        <div className="text-3xl font-black text-violet-600">{benchmarkLabel}</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">
                            <br></br>
                            <br></br>
                            {attentionAvailability?.stats && cohortStats
                                ? `Mean of ${cohortStats.completed_sessions ?? '—'} completed assessment sessions`
                                : 'Institution-wide statistics unavailable'}
                        </div>
                    </div>
                </div>

                {/* Recruitment Drives Pipeline */}
                <div className="mb-8" data-testid="pipeline">
                    <div className="flex items-center justify-between mb-4 gap-3">
                        <h2 className="text-lg font-bold text-slate-900">Active Placement Drives Pipeline</h2>
                        <a
                            href="/tpo/mock-drives"
                            className="text-xs font-semibold text-sky-600 hover:text-sky-700 inline-flex items-center gap-1 shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded px-1"
                        >
                            View all drives <ArrowRight size={14} />
                        </a>
                    </div>
                    {pipelineDrives.length === 0 ? (
                        <div className="glass-card rounded-2xl p-8 text-center">
                            <p className="text-sm font-bold text-slate-900">No active drives yet</p>
                            <p className="text-xs text-slate-500 mt-1">Create and publish a drive to start a placement pipeline.</p>
                            <a
                                href="/tpo/mock-drives"
                                className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded px-1"
                            >
                                Open drive management <ArrowRight size={13} />
                            </a>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                            {pipelineDrives.map((d) => {
                                const badge = STATUS_BADGE[d.status] || { label: d.status, cls: 'bg-slate-100 text-slate-600 border-slate-200' };
                                const branches = Array.isArray(d.eligible_branches) ? d.eligible_branches.filter(Boolean) : [];
                                const rounds = driveRounds(d);
                                return (
                                    <div key={d.id} className="glass-card rounded-2xl p-6 min-w-0">
                                        <div className="flex items-start justify-between gap-3 mb-4">
                                            <div className="min-w-0">
                                                <div className="text-base font-bold text-slate-900 truncate">{d.company_name}</div>
                                                <div className="text-xs text-slate-500 truncate">{d.target_role}</div>
                                            </div>
                                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border shrink-0 ${badge.cls}`}>
                                                {badge.label}
                                            </span>
                                        </div>
                                        <div className="space-y-2 text-xs text-slate-600 mb-4">
                                            <div className="flex justify-between gap-3">
                                                <span>Eligibility:</span>
                                                <span className="font-semibold text-slate-900 text-right">
                                                    CGPA ≥ {d.minimum_cgpa}, {d.maximum_backlogs === 0 ? '0 backlogs' : `≤ ${d.maximum_backlogs} backlogs`}
                                                </span>
                                            </div>
                                            {branches.length > 0 && (
                                                <div className="flex justify-between gap-3">
                                                    <span>Branches:</span>
                                                    <span className="min-w-0 font-medium text-slate-700 text-right break-words">{branches.join(', ')}</span>
                                                </div>
                                            )}
                                            <div className="flex justify-between gap-3">
                                                <span>Eligible Candidates:</span>
                                                <span
                                                    className="font-bold text-indigo-600"
                                                    title="Computed by applying this drive's CGPA, backlog, and branch criteria to the current cohort"
                                                >
                                                    {(() => {
                                                        const summary = summarizeEligibility(students, {
                                                            minimumCgpa: d.minimum_cgpa,
                                                            maximumBacklogs: d.maximum_backlogs,
                                                            eligibleBranches: d.eligible_branches,
                                                        });
                                                        return attentionAvailability?.students
                                                            ? `${summary.eligible} eligible · ${summary.ineligible} ineligible · ${summary.unknown} unknown`
                                                            : 'Unavailable';
                                                    })()}
                                                </span>
                                            </div>
                                            <div className="flex justify-between gap-3">
                                                <span>Stages:</span>
                                                <span className="font-medium text-slate-700 text-right">
                                                    {rounds.length ? rounds.map(fmtRound).join(' → ') : '—'}
                                                </span>
                                            </div>
                                        </div>
                                        <a
                                            href="/tpo/mock-drives"
                                            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded px-1"
                                        >
                                            Open roster <ArrowRight size={13} />
                                        </a>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Quick Actions */}
                <div className="glass-card rounded-2xl p-6 mb-8" data-testid="quick-actions">
                    <div className="flex items-center justify-between mb-4 gap-3">
                        <h2 className="text-base font-bold text-slate-900">Quick Actions</h2>
                        <span className="text-[11px] text-slate-500">Workflows backed by existing endpoints only</span>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <button
                            ref={addStudentBtnRef}
                            onClick={openStudentModal}
                            data-testid="qa-add-student"
                            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                        >
                            <UserPlus size={15} /> Add Student
                        </button>
                        <button
                            onClick={() => setCompanyModalOpen(true)}
                            data-testid="qa-add-company"
                            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                        >
                            <Building2 size={15} /> Add Company
                        </button>
                        <button
                            onClick={handleExport}
                            disabled={exporting}
                            data-testid="qa-export"
                            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                        >
                            <Download size={15} /> {exporting ? 'Exporting…' : 'Export Data'}
                        </button>
                        {/* <button
                            type="button"
                            aria-disabled="true"
                            data-testid="qa-invite-members"
                            onClick={() => notifyUnavailable('Invite Members', 'the backend has no invitation or members workflow endpoint')}
                            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-50 text-slate-400 text-xs font-semibold border border-dashed border-slate-300 cursor-not-allowed transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
                        >
                            <UserPlus size={15} /> Invite Members
                            <span className="text-[9px] uppercase tracking-wide bg-slate-200 text-slate-500 rounded-full px-1.5 py-0.5">Unavailable</span>
                        </button> */}

                    </div>
                  <br></br>
                </div>

                {/* Upcoming Deadlines + Most Active Drives */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                    <div className="glass-card rounded-2xl p-6" data-testid="deadlines">
                        <div className="flex items-center gap-2 mb-3">
                            <CalendarX size={18} className="text-slate-400" aria-hidden="true" />
                            <h2 className="text-base font-bold text-slate-900">Upcoming Deadlines</h2>
                        </div>
                        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4">
                            <p className="text-sm font-semibold text-slate-700">No upcoming deadlines to show.</p>

                        </div>
                        <br></br>
                        <a
                            href="/tpo/mock-drives"
                            className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-sky-600 hover:text-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded px-1"
                        >
                            Open drive management <ArrowRight size={13} />
                        </a>
                    </div>

                    <div className="glass-card rounded-2xl p-6 min-w-0" data-testid="most-active">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0" aria-hidden="true">
                                <TrendingUp size={15} />
                            </span>
                            <h2 className="text-base font-bold text-slate-900">Most Active Recruitment Drives</h2>
                        </div>
                        {attentionAvailability?.drives !== true ? (
                            <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Drive activity could not be loaded.</div>
                        ) : rosterSample.failed > 0 && activityRows.length === 0 ? (
                            <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Activity is unavailable for {rosterSample.failed} of {rosterSample.checked} checked drive rosters.</div>
                        ) : activityRows.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-4">
                                <p className="text-sm font-semibold text-slate-700">{rosterSample.total === 0 ? 'No non-draft drives are available to check.' : 'No candidate activity recorded in the checked drives.'}</p>
                                <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                                    Drives will appear here once candidates are enrolled or start assessments. Ranking uses recorded
                                    drive activity, not placement outcomes.
                                </p>
                            </div>
                        ) : (
                            <ol className="space-y-0" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                                {activityRows.map((row, i) => (
                                    <li
                                        key={row.drive.id}
                                        className="flex items-center gap-3 py-2.5 border-b border-slate-200/70 last:border-0"
                                    >
                                        <span className="w-6 h-6 rounded-lg bg-slate-100 text-slate-500 text-[10px] font-black flex items-center justify-center shrink-0">
                                            {i + 1}
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <div className="text-sm font-bold text-slate-900 truncate">{row.drive.company_name}</div>
                                            <div className="text-[11px] text-slate-500 truncate">{row.drive.target_role}</div>
                                        </div>
                                        <div className="text-right shrink-0">
                                            <div className="text-sm font-black text-indigo-600">{row.roster.total_participants}</div>
                                            <div className="text-[10px] text-slate-500">enrolled</div>
                                        </div>
                                        <div className="text-right shrink-0 w-16">
                                            <div className="text-sm font-black text-emerald-600">{row.roster.completed_count}</div>
                                            <div className="text-[10px] text-slate-500">completed</div>
                                        </div>
                                    </li>
                                ))}
                            </ol>
                        )}
                        <p className="text-[13px] text-slate-400 mt-3 leading-relaxed">
                            Ranked by enrolled candidates among the {rosterSample.checked} most recent non-draft drive rosters checked
                            ({rosterSample.total} non-draft drives exist). This is a recent sample, not an all-drive ranking.
                            {rosterSample.failed > 0 ? ` ${rosterSample.failed} roster request(s) failed; displayed results are partial.` : ''}
                        </p>
                    </div>
                </div>

                {/* Placement Intelligence */}
                <section className="mb-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" data-testid="placement-intelligence">
                    <header className="border-b border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
                        <h2 className="text-lg font-bold text-slate-900">Placement Intelligence</h2>
                    </header>
                    {placementIntelligenceUnavailableReasons.length > 0 && (
                        <div role="status" className="mx-5 mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 sm:mx-6">
                            <p className="font-semibold">Placement information could not be loaded.</p>
                            <p className="mt-1">{placementIntelligenceUnavailableReasons.join(' ')}</p>
                        </div>
                    )}
                    {placementInsights.length === 0 && placementIntelligenceChecksComplete ? (
                        <p className="px-5 py-5 text-sm text-slate-500 sm:px-6" data-testid="placement-intelligence-empty">
                            <span className="block font-semibold text-slate-700">Everything looks up to date</span>
                            <span className="mt-1 block">There are no new placement-related actions requiring attention right now. You can review your Mock Drives whenever you are ready.</span>
                        </p>
                    ) : placementInsights.length > 0 ? (
                        <ul className="divide-y divide-slate-200 px-5 sm:px-6" data-testid="placement-intelligence-list">
                            {placementInsights.map((item) => {
                                return (
                                    <li key={item.id} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 py-4 first:pt-5 last:pb-5 sm:gap-4">
                                        <span className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-rose-50 text-rose-700" aria-hidden="true">
                                            <TriangleAlert size={16} />
                                        </span>
                                        <div className="min-w-0">
                                            <h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>
                                            <p className="mt-1 text-sm leading-relaxed text-slate-600"><span className="font-semibold text-slate-700">What this means: </span>{item.meaning}</p>
                                            <p className="mt-1 text-sm leading-relaxed text-slate-600"><span className="font-semibold text-slate-700">Recommended action: </span>{item.action}</p>
                                            <div className="mt-2">
                                                <a
                                                    href={item.href}
                                                    className="shrink-0 text-xs font-semibold text-sky-700 hover:text-sky-800 inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 rounded"
                                                >
                                                    {item.linkText} <ArrowRight size={13} />
                                                </a>
                                            </div>
                                        </div>
                                    </li>
                                );
                            })}
                        </ul>
                    ) : null}
                </section>

            </main>

            {/* Add Student dialog */}
            {studentModalOpen && (
                <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
                        onClick={() => !studentSubmitting && closeStudentModal()}
                        aria-hidden="true"
                    />
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="add-student-title"
                        data-testid="add-student-dialog"
                        className="relative w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-xl p-6"
                    >
                        <div className="flex items-center justify-between mb-2">
                            <h3 id="add-student-title" className="text-base font-bold text-slate-900">Add Student</h3>
                            <button
                                onClick={closeStudentModal}
                                aria-label="Close add student dialog"
                                className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                            Creates a student account through the existing <span className="font-mono font-semibold">POST /auth/register</span>{' '}
                            workflow. The account then appears in the candidate pool on refresh.
                        </p>
                        <form onSubmit={submitStudent} className="space-y-3">
                            <div>
                                <label htmlFor="ns-name" className="block text-xs font-semibold text-slate-600 mb-1">Full name</label>
                                <input
                                    id="ns-name"
                                    type="text"
                                    value={studentForm.name}
                                    onChange={(e) => setStudentForm((f) => ({ ...f, name: e.target.value }))}
                                    required
                                    autoFocus
                                    autoComplete="name"
                                    maxLength={100}
                                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    placeholder="e.g. Priya Sharma"
                                />
                            </div>
                            <div>
                                <label htmlFor="ns-email" className="block text-xs font-semibold text-slate-600 mb-1">Email</label>
                                <input
                                    id="ns-email"
                                    type="email"
                                    value={studentForm.email}
                                    onChange={(e) => setStudentForm((f) => ({ ...f, email: e.target.value }))}
                                    required
                                    autoComplete="email"
                                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    placeholder="student@example.com"
                                />
                            </div>
                            <div>
                                <label htmlFor="ns-password" className="block text-xs font-semibold text-slate-600 mb-1">Initial password</label>
                                <input
                                    id="ns-password"
                                    type="password"
                                    value={studentForm.password}
                                    onChange={(e) => setStudentForm((f) => ({ ...f, password: e.target.value }))}
                                    required
                                    autoComplete="new-password"
                                    minLength={8}
                                    maxLength={128}
                                    className="w-full px-3 py-2 rounded-xl border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                                    placeholder="Minimum 8 characters"
                                />
                            </div>
                            {studentError && (
                                <div role="alert" data-testid="add-student-error" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700">
                                    {studentError}
                                </div>
                            )}
                            <div className="flex justify-end gap-2 pt-1">
                                <button
                                    type="button"
                                    onClick={closeStudentModal}
                                    disabled={studentSubmitting}
                                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-300 transition-all disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={studentSubmitting}
                                    data-testid="add-student-submit"
                                    className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 disabled:opacity-60 text-white text-xs font-semibold shadow-sm transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
                                >
                                    {studentSubmitting ? 'Creating…' : 'Create student'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Existing company management workflow */}
            <CompanyPatternModal
                isOpen={companyModalOpen}
                onClose={() => setCompanyModalOpen(false)}
                initialCompany=""
                initialRole=""
                existingDrives={drives}
                onToast={setToast}
            />
        </TPOLayout>
    );
}
