import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import TPOLayout, { TPOMenuButton } from '../components/TPOLayout';
import { ClipboardList, Search, SlidersHorizontal, X } from 'lucide-react';
import { candidateEligibility, filterAndSortCandidates, summarizeCandidates } from '../utils/candidatePool';

export default function TPOStudentsPage() {
    const [tpoUser,          setTpoUser]          = useState(null);
    const [students,         setStudents]          = useState([]);
    // eslint-disable-next-line no-unused-vars -- preserved verbatim from TPODashboard load contract
    const [cohortStats,      setCohortStats]       = useState(null);
    const [loading,          setLoading]           = useState(true);
    const [searchTerm,       setSearchTerm]        = useState('');
    const [deptFilter,       setDeptFilter]        = useState('');
    const [eligibilityFilter,setEligibilityFilter] = useState('');
    const [minCgpa,           setMinCgpa]           = useState('');
    const [maxCgpa,           setMaxCgpa]           = useState('');
    const [backlogFilter,     setBacklogFilter]     = useState('');
    const [sortField,         setSortField]         = useState('name');
    const [sortDirection,     setSortDirection]     = useState('asc');
    const [pageSize,          setPageSize]          = useState(10);
    const [page,              setPage]              = useState(1);
    const [filtersOpen,       setFiltersOpen]       = useState(false);
    const [selectedStudent,  setSelectedStudent]   = useState(null);
    const [toast,            setToast]             = useState(null);

    const navigate = useNavigate();

    const loadTPOData = useCallback(async () => {
        setLoading(true);
        try {
            const [profRes, studentsRes, statsRes] = await Promise.all([
                api.get('/profile/me'),
                api.get('/profile/cohort/students').catch(() => ({ data: { students: [] } })),
                api.get('/report/admin/cohort-stats').catch(() => ({ data: null })),
            ]);
            setTpoUser(profRes.data);
            setStudents(studentsRes.data?.students || []);
            setCohortStats(statsRes.data);
            setPage(1);
        } catch {
            setToast({ type: 'error', message: 'Failed to load TPO dashboard data' });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadTPOData(); }, [loadTPOData]);

    const filteredStudents = filterAndSortCandidates(students, {
        search: searchTerm, department: deptFilter, eligibility: eligibilityFilter,
        minCgpa, maxCgpa, backlogs: backlogFilter, sort: sortField, direction: sortDirection,
    });
    const representativeStudents = [];
    const repeatedNameStudents = [];
    const seenDisplayNames = new Set();
    filteredStudents.forEach(student => {
        const normalizedName = (student.full_name || student.name || '')
            .trim()
            .replace(/\s+/g, ' ')
            .toLocaleLowerCase();
        if (!normalizedName || !seenDisplayNames.has(normalizedName)) {
            representativeStudents.push(student);
            if (normalizedName) seenDisplayNames.add(normalizedName);
        } else {
            repeatedNameStudents.push(student);
        }
    });
    const orderedStudents = [...representativeStudents, ...repeatedNameStudents];
    const summary = summarizeCandidates(students);
    const departments = [...new Set(students.map(student => student.department).filter(value => typeof value === 'string' && value.trim()))]
        .sort((a, b) => a.localeCompare(b));
    const eligibilityOptions = [...new Set(students.map(candidateEligibility))];
    const pageCount = Math.max(1, Math.ceil(filteredStudents.length / pageSize));
    const visibleStudents = orderedStudents.slice((page - 1) * pageSize, page * pageSize);
    const clearFilters = () => {
        setSearchTerm(''); setDeptFilter(''); setEligibilityFilter('');
        setMinCgpa(''); setMaxCgpa(''); setBacklogFilter('');
        setSortField('name'); setSortDirection('asc'); setPageSize(10); setPage(1);
    };

    if (loading) return <PageSkeleton variant="light" cardCount={4} />;

    return (
        <TPOLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-6 py-10 space-y-10">

                {/* ── 1. HEADER ──────────────────────────────────────────── */}
                <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
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

                <section>
                    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                        <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-sky-700">Student directory</p>
                            <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Candidate Pool</h2>
                            <p className="mt-1 text-sm text-slate-500">Summary and filters cover the {students.length} candidates returned for your current access scope.</p>
                        </div>
                        <button type="button" onClick={() => setFiltersOpen(value => !value)} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm lg:hidden" aria-expanded={filtersOpen}>
                            <SlidersHorizontal size={16} /> Filters
                        </button>
                    </div>

                    <div className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
                        {[
                            ['Total candidates', summary.total, 'Loaded cohort'],
                            ['Eligible', summary.eligible, 'Based on current roster rule'],
                            ['Conditional', summary.conditional, 'Based on current roster rule'],
                            ['With backlogs', summary.withBacklogs, 'Known backlog count above zero'],
                        ].map(([label, value, note]) => <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                            <div className="text-xs font-semibold text-slate-500">{label}</div>
                            <div className="mt-1 text-2xl font-bold text-slate-900">{value}</div>
                            <div className="mt-1 text-[11px] text-slate-400">{note}</div>
                        </div>)}
                    </div>

                    <div className="grid gap-4 lg:grid-cols-[250px_minmax(0,1fr)]">
                        <aside className={`${filtersOpen ? 'block' : 'hidden'} h-fit rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-5 lg:block`} aria-label="Candidate filters">
                            <div className="mb-4 flex items-center justify-between"><h3 className="font-bold text-slate-900">Filters</h3><button type="button" className="text-xs font-semibold text-sky-700 hover:text-sky-900" onClick={clearFilters}>Clear all</button></div>
                            <label className="mb-4 block text-xs font-semibold text-slate-600">Search candidates
                                <span className="relative mt-1.5 block"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input value={searchTerm} onChange={event => { setSearchTerm(event.target.value); setPage(1); }} placeholder="Name, email, or roll number" className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-9 pr-3 text-sm font-normal text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500" /></span>
                            </label>
                            <label className="mb-4 block text-xs font-semibold text-slate-600">Department<select value={deptFilter} onChange={event => { setDeptFilter(event.target.value); setPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="">All departments</option>{departments.map(department => <option key={department} value={department}>{department}</option>)}</select></label>
                            <label className="mb-4 block text-xs font-semibold text-slate-600">Eligibility status<select value={eligibilityFilter} onChange={event => { setEligibilityFilter(event.target.value); setPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="">All statuses</option>{eligibilityOptions.map(status => <option key={status} value={status}>{status === 'eligible' ? 'Eligible' : status === 'conditional' ? 'Conditional' : 'Unknown'}</option>)}</select></label>
                            <div className="mb-4 text-xs font-semibold text-slate-600">CGPA range<div className="mt-1.5 grid grid-cols-2 gap-2"><input aria-label="Minimum CGPA" type="number" min="0" max="10" step="0.01" value={minCgpa} onChange={event => { setMinCgpa(event.target.value); setPage(1); }} placeholder="Min" className="min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900" /><input aria-label="Maximum CGPA" type="number" min="0" max="10" step="0.01" value={maxCgpa} onChange={event => { setMaxCgpa(event.target.value); setPage(1); }} placeholder="Max" className="min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900" /></div></div>
                            <label className="mb-4 block text-xs font-semibold text-slate-600">Backlogs<select value={backlogFilter} onChange={event => { setBacklogFilter(event.target.value); setPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="">Any backlog count</option><option value="none">No backlogs</option><option value="has">Has backlogs</option><option value="unknown">Unknown</option></select></label>
                            <label className="mb-2 block text-xs font-semibold text-slate-600">Sort by<select value={sortField} onChange={event => { setSortField(event.target.value); setPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="name">Student name</option><option value="department">Department</option><option value="target_role">Target role</option><option value="cgpa">CGPA</option><option value="backlogs">Backlogs</option></select></label>
                            <div className="mt-2 flex rounded-xl bg-slate-100 p-1 text-xs"><button type="button" onClick={() => setSortDirection('asc')} className={`flex-1 rounded-lg py-2 font-semibold ${sortDirection === 'asc' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}>A–Z / Low</button><button type="button" onClick={() => setSortDirection('desc')} className={`flex-1 rounded-lg py-2 font-semibold ${sortDirection === 'desc' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}>Z–A / High</button></div>
                        </aside>

                        <div className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:px-5">
                                <div><h3 className="font-bold text-slate-900">Candidates</h3><p className="mt-0.5 text-xs text-slate-500">Showing {filteredStudents.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredStudents.length)} of {filteredStudents.length} filtered</p></div>
                                <label className="flex items-center gap-2 text-xs text-slate-500">Rows<select value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-slate-800"><option value={10}>10</option><option value={25}>25</option><option value={50}>50</option></select></label>
                            </div>
                            {filteredStudents.length === 0 ? <div className="px-5 py-16 text-center"><ClipboardList size={34} className="mx-auto mb-3 text-slate-300" /><h3 className="font-bold text-slate-800">No candidates found</h3><p className="mt-1 text-sm text-slate-500">Try changing or clearing your filters.</p></div> : <div className="overflow-x-auto">
                                <table className="w-full min-w-[760px] text-left text-xs">
                                    <thead><tr className="border-b border-slate-200 bg-slate-50 text-[10px] font-bold uppercase tracking-wider text-slate-500"><th className="px-4 py-3">Student</th><th className="px-4 py-3">Department</th><th className="px-4 py-3 text-right">CGPA</th><th className="px-4 py-3 text-right">Backlogs</th><th className="px-4 py-3">Target role</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Action</th></tr></thead>
                                    <tbody className="divide-y divide-slate-100">{visibleStudents.map(student => {
                                        const status = candidateEligibility(student);
                                        const badgeClass = status === 'eligible' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : status === 'conditional' ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-slate-200 bg-slate-50 text-slate-600';
                                        return <tr key={student.user_id} className="hover:bg-slate-50/80"><td className="px-4 py-3"><div className="font-semibold text-slate-900">{student.full_name || student.name || 'Unnamed candidate'}</div><div className="mt-0.5 text-[11px] text-slate-500">{student.email || 'No email'}{student.roll_number ? ` · ${student.roll_number}` : ''}</div></td><td className="px-4 py-3 text-slate-700">{student.department || '—'}</td><td className="px-4 py-3 text-right font-semibold text-slate-800">{student.cgpa ?? '—'}</td><td className="px-4 py-3 text-right font-semibold text-slate-800">{student.backlogs_count ?? '—'}</td><td className="px-4 py-3 text-slate-700">{student.target_role || '—'}</td><td className="px-4 py-3"><span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${badgeClass}`}>{status === 'eligible' ? 'Eligible' : status === 'conditional' ? 'Conditional' : 'Unknown'}</span></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => setSelectedStudent(student)} className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 font-semibold text-sky-700 hover:bg-sky-100">View</button></td></tr>;
                                    })}</tbody>
                                </table>
                            </div>}
                            {filteredStudents.length > 0 && <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3"><span className="text-xs text-slate-500">Page {page} of {pageCount}</span><div className="flex gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40">Previous</button><button type="button" disabled={page >= pageCount} onClick={() => setPage(value => Math.min(pageCount, value + 1))} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40">Next</button></div></div>}
                        </div>
                    </div>
                </section>

            </main>

            {/* Existing candidate review details, presented as a responsive side drawer. */}
            {selectedStudent && (
                <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm" onMouseDown={event => { if (event.target === event.currentTarget) setSelectedStudent(null); }}>
                    <aside role="dialog" aria-modal="true" aria-label={`${selectedStudent.name || 'Candidate'} details`} className="h-full w-full max-w-lg overflow-y-auto border-l border-slate-200 bg-white p-5 shadow-2xl sm:p-8">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
                            <div>
                                <h3 className="text-xl font-bold text-slate-900">{selectedStudent.name}</h3>
                                <p className="text-xs text-slate-500">{selectedStudent.email} | {selectedStudent.department}</p>
                            </div>
                            <button aria-label="Close candidate details" onClick={() => setSelectedStudent(null)} className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"><X size={16} /></button>
                        </div>
                        <div className="space-y-4 text-xs">
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-slate-50 rounded-2xl border border-slate-200">
                                {[
                                    ['CGPA',             <span className="font-bold text-indigo-600">{selectedStudent.cgpa} / 10.0</span>],
                                    ['10th Marks',       <span className="font-bold text-slate-900">{selectedStudent.tenth_marks ? `${selectedStudent.tenth_marks}%` : 'Not Set'}</span>],
                                    ['12th Marks',       <span className="font-bold text-slate-900">{selectedStudent.twelfth_marks ? `${selectedStudent.twelfth_marks}%` : 'Not Set'}</span>],
                                    ['Active Backlogs',  <span className={`font-bold ${selectedStudent.backlogs_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{selectedStudent.backlogs_count}</span>],
                                    ['Gender & Nationality', <span className="font-bold text-slate-900">{selectedStudent.gender || 'Male'} | {selectedStudent.nationality || 'Indian'}</span>],
                                    ['Date of Birth',    <span className="font-bold text-slate-900">{selectedStudent.date_of_birth || 'Not Set'}</span>],
                                    ['Graduation Year',  <span className="font-bold text-slate-900">{selectedStudent.graduation_year}</span>],
                                    ['Mobile No.',       <span className="font-mono text-slate-800">{selectedStudent.mobile_no || 'Not Set'}</span>],
                                ].map(([label, val]) => (
                                    <div key={label}><div className="text-slate-400 font-medium">{label}</div>{val}</div>
                                ))}
                                <div className="sm:col-span-3">
                                    <div className="text-slate-400 font-medium">College Email ID</div>
                                    <div className="font-mono text-slate-800">{selectedStudent.college_email_id || selectedStudent.email}</div>
                                </div>
                            </div>
                            <div className="p-4 bg-sky-50/60 rounded-2xl border border-sky-100">
                                <h4 className="font-bold text-slate-800 mb-2">Drive Eligibility Check</h4>
                                <div className="space-y-1.5 text-slate-700">
                                    {[
                                        ['Google SDE (CGPA ≥ 8.0, 0 Backlogs)',   selectedStudent.cgpa >= 8.0 && selectedStudent.backlogs_count === 0],
                                        ['Amazon SDE (CGPA ≥ 7.5, 0 Backlogs)',   selectedStudent.cgpa >= 7.5 && selectedStudent.backlogs_count === 0],
                                        ['TCS Prime (CGPA ≥ 6.5, ≤1 Backlog)',    selectedStudent.cgpa >= 6.5 && selectedStudent.backlogs_count <= 1],
                                    ].map(([label, ok]) => (
                                        <div key={label} className="flex items-center justify-between">
                                            <span>{label}:</span>
                                            <span className="font-bold">{ok ? '✓ Yes' : '✕ No'}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                        <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
                            <button onClick={() => setSelectedStudent(null)} className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all">Done</button>
                        </div>
                    </aside>
                </div>
            )}
        </TPOLayout>
    );
}
