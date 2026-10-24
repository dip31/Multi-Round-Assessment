import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownToLine, ClipboardList, FileText, LoaderCircle, Search } from 'lucide-react';
import api from '../services/api';
import FacultyPracticeAssessmentDialog from './FacultyPracticeAssessmentDialog';
import {
    ASSESSMENT_FILTER_DEFAULTS,
    assessmentCsv,
    assessmentStatusLabel,
    buildAssessmentActivityParams,
    filterAssessmentGroups,
    groupAssessmentActivity,
} from '../utils/facultyAssessmentActivity';
import { facultyStudentDisplayIdentity } from '../utils/facultyDemoIdentity';

const PAGE_SIZE = 20;
const badgeStyles = {
    completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    in_progress: 'border-blue-200 bg-blue-50 text-blue-800',
    evaluation_in_progress: 'border-blue-200 bg-blue-50 text-blue-800',
    not_started: 'border-slate-200 bg-slate-100 text-slate-700',
    awaiting_evaluation: 'border-amber-200 bg-amber-50 text-amber-800',
    failed: 'border-rose-200 bg-rose-50 text-rose-800',
    unavailable: 'border-slate-200 bg-slate-100 text-slate-600',
};
const dateLabel = (value) => value && !Number.isNaN(new Date(value).getTime())
    ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : 'Not available';
function StatusBadge({ value }) {
    const label = ({ completed: 'Completed', in_progress: 'In Progress', not_started: 'Not Started', failed: 'Needs Attention' })[value] || assessmentStatusLabel(value);
    return <span className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeStyles[value] || badgeStyles.unavailable}`}>{label}</span>;
}

function StudentIdentityCell({ record, assignments }) {
    const identity = facultyStudentDisplayIdentity(record, {
        isDevelopment: import.meta.env.DEV,
        assignments,
    });
    return <td className="min-w-[150px] px-4 py-3"><span className="font-semibold text-slate-900">{identity.name}</span>{record.student.roll_number && <p className="mt-0.5 text-xs text-slate-500">Roll number: {record.student.roll_number}</p>}</td>;
}

function saveTextFile(name, content) {
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
}

export default function FacultyAssessmentsSection({ onOpenAssignment }) {
    const [filters, setFilters] = useState(ASSESSMENT_FILTER_DEFAULTS);
    const [page, setPage] = useState(1);
    const [data, setData] = useState({ records: [], total: 0, pages: 1, filters: {} });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [selected, setSelected] = useState(null);
    const [reportPickerOpen, setReportPickerOpen] = useState(false);
    const [reportStudentId, setReportStudentId] = useState('');
    const requestId = useRef(0);
    const tableRef = useRef(null);
    const demoIdentityAssignments = useRef(new Map());

    const load = useCallback(async () => {
        const current = ++requestId.current;
        setLoading(true);
        setError(null);
        try {
            const first = await api.get('/profile/cohort/practice-assessment-activity', {
                params: buildAssessmentActivityParams(ASSESSMENT_FILTER_DEFAULTS, 1, 100),
            });
            const all = [...(first.data?.records || [])];
            for (let nextPage = 2; nextPage <= (first.data?.pages || 1); nextPage += 1) {
                const next = await api.get('/profile/cohort/practice-assessment-activity', {
                    params: buildAssessmentActivityParams(ASSESSMENT_FILTER_DEFAULTS, nextPage, 100),
                });
                all.push(...(next.data?.records || []));
            }
            if (current === requestId.current) setData({ ...first.data, records: all, total: all.length });
        } catch (cause) {
            if (current === requestId.current) {
                setData({ records: [], total: 0, pages: 1, filters: {} });
                setError(cause?.response?.status === 403
                    ? 'Practice Assessment activity is unavailable for your faculty scope.'
                    : 'Practice Assessment activity could not be loaded. Retry the request.');
            }
        } finally {
            if (current === requestId.current) setLoading(false);
        }
    }, [filters, page]);
    useEffect(() => { load(); }, [load]);

    const filterOptions = data.filters || {};
    const groupedRecords = useMemo(() => groupAssessmentActivity(data.records), [data.records]);
    const filteredRecords = useMemo(() => filterAssessmentGroups(groupedRecords, filters), [groupedRecords, filters]);
    const totalPages = Math.max(1, Math.ceil(filteredRecords.length / PAGE_SIZE));
    const pageRecords = filteredRecords.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    const updateFilter = (key, value) => {
        setPage(1);
        setFilters((current) => ({ ...current, [key]: value }));
    };
    const hasFilters = Object.entries(filters).some(([key, value]) => value !== ASSESSMENT_FILTER_DEFAULTS[key]);
    const reset = () => {
        setFilters(ASSESSMENT_FILTER_DEFAULTS);
        setPage(1);
        setReportPickerOpen(false);
        setActionError(null);
    };

    const openView = async (record, mode) => {
        const displayIdentity = mode === 'report'
            ? facultyStudentDisplayIdentity(record, {
                isDevelopment: import.meta.env.DEV,
                assignments: demoIdentityAssignments.current,
            })
            : null;
        setSelected({
            record,
            mode,
            displayStudentName: displayIdentity?.isDemo ? displayIdentity.name : null,
            payload: null,
            loading: true,
            error: null,
        });
        const endpoint = mode === 'report'
            ? `/profile/cohort/practice-assessment-activity/students/${record.student.user_id}/report`
            : `/profile/cohort/practice-assessment-activity/students/${record.student.user_id}/sessions/${record.session_id}/rounds/${record.round_id}`;
        try {
            const response = await api.get(endpoint);
            setSelected((current) => current?.record === record
                ? { ...current, payload: response.data, loading: false }
                : current);
        } catch (cause) {
            const message = cause?.response?.status === 403 || cause?.response?.status === 404
                ? 'This practice record is not available in your authorized faculty scope.'
                : 'Practice details could not be loaded. Retry from the table.';
            setSelected((current) => current?.record === record
                ? { ...current, loading: false, error: message }
                : current);
        }
    };

    const openStudentReport = async () => {
        const target = (filterOptions.students || []).find((item) => String(item.id) === String(reportStudentId));
        if (!target) return;
        const representative = {
            student: { user_id: target.id, name: target.name, roll_number: target.roll_number },
            assessment_name: 'Practice Assessment',
            session_name: 'Practice history',
            round_name: 'Student report',
        };
        setReportPickerOpen(false);
        await openView(representative, 'report');
    };

    const exportAll = async () => {
        setActionError(null);
        try {
            const first = await api.get('/profile/cohort/practice-assessment-activity', {
                params: buildAssessmentActivityParams(ASSESSMENT_FILTER_DEFAULTS, 1, 100),
            });
            const all = [...(first.data?.records || [])];
            for (let nextPage = 2; nextPage <= (first.data?.pages || 1); nextPage += 1) {
                const next = await api.get('/profile/cohort/practice-assessment-activity', {
                    params: buildAssessmentActivityParams(ASSESSMENT_FILTER_DEFAULTS, nextPage, 100),
                });
                all.push(...(next.data?.records || []));
            }
            saveTextFile('practice-assessment-results.csv', assessmentCsv(filterAssessmentGroups(groupAssessmentActivity(all), filters)));
        } catch {
            setActionError('Authorized practice results could not be exported.');
        }
    };

    const evaluationOptions = useMemo(() => [
        ['in_progress', 'In progress'], ['evaluation_in_progress', 'Evaluation in progress'],
        ['not_started', 'Not available'], ['awaiting_evaluation', 'Awaiting evaluation'],
        ['completed', 'Results available'], ['failed', 'Evaluation failed'], ['unavailable', 'Unavailable'],
    ], []);
    return <div className="space-y-4">
        <section aria-label="Practice Assessment search and filters" className="rounded-2xl glass-card p-4 shadow-sm">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <label className="relative block sm:col-span-2 xl:col-span-1"><span className="sr-only">Search student, session, or round</span><Search aria-hidden="true" className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input value={filters.search} onChange={(event) => updateFilter('search', event.target.value)} placeholder="Search student or session" className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600" /></label>
                <label className="text-xs font-medium text-slate-600">Assessment session<select value={filters.session_id} onChange={(event) => updateFilter('session_id', event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All practice sessions</option>{(filterOptions.sessions || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                <label className="text-xs font-medium text-slate-600">Round<select value={filters.round_type} onChange={(event) => updateFilter('round_type', event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All rounds</option>{(filterOptions.round_types || []).map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
                <label className="text-xs font-medium text-slate-600">Evaluation status<select value={filters.evaluation_status} onChange={(event) => updateFilter('evaluation_status', event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">All evaluation states</option>{evaluationOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                <label className="text-xs font-medium text-slate-600">From date<input type="date" value={filters.date_from} onChange={(event) => updateFilter('date_from', event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" /></label>
                <label className="text-xs font-medium text-slate-600">To date<input type="date" value={filters.date_to} onChange={(event) => updateFilter('date_to', event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" /></label>
                <label className="flex items-end gap-2 pb-2 text-sm text-slate-700"><input type="checkbox" checked={filters.needs_attention} onChange={(event) => updateFilter('needs_attention', event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-indigo-600" />Needs attention</label>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3"><p className="text-xs text-slate-500">{loading ? 'Updating results...' : `${filteredRecords.length} practice session${filteredRecords.length === 1 ? '' : 's'} match`}</p><div className="flex items-center gap-2"><button type="button" disabled={!hasFilters} onClick={reset} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-40">Reset filters</button><button type="button" onClick={exportAll} disabled={!data.records.length || loading} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"><ArrowDownToLine className="h-4 w-4" />Export filtered results</button></div></div>
            {actionError && <p role="alert" className="mt-2 text-sm text-rose-700">{actionError}</p>}
        </section>

        <section ref={tableRef} aria-label="Practice Assessment results" className="overflow-hidden rounded-2xl glass-card shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 p-4"><div><h2 className="font-semibold text-slate-900">Practice Assessment activity</h2><p className="mt-1 text-sm text-slate-500"></p></div><button type="button" onClick={load} disabled={loading} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50">Refresh</button></div>
            {error ? <div role="alert" className="p-6 text-center"><p className="font-semibold text-rose-800">Practice data unavailable</p><p className="mt-1 text-sm text-slate-600">{error}</p><button type="button" onClick={load} className="mt-3 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white">Retry</button></div> : loading ? <div className="flex items-center justify-center gap-2 p-12 text-sm text-slate-600"><LoaderCircle className="h-5 w-5 animate-spin" />Loading authorized practice activity...</div> : filteredRecords.length === 0 ? <div className="p-10 text-center"><ClipboardList className="mx-auto h-8 w-8 text-slate-400" /><h3 className="mt-3 font-semibold text-slate-900">{hasFilters ? 'No practice records match these filters' : 'No practice assessment records are available'}</h3><p className="mt-1 text-sm text-slate-500">{hasFilters ? 'Reset the filters to see all authorized practice activity.' : 'Practice sessions will appear here when authorized students start an assessment.'}</p>{hasFilters && <button type="button" onClick={reset} className="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Reset filters</button>}</div> : <div className="overflow-x-auto"><table className="w-full min-w-[1050px] table-fixed text-left text-sm"><colgroup><col className="w-[17%]"/><col className="w-[22%]"/><col className="w-[25%]"/><col className="w-[13%]"/><col className="w-[13%]"/><col className="w-[10%]"/></colgroup><thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600"><tr>{['Student', 'Assessment / Session', 'Activity', 'Assessment Status', 'Last Activity', 'Actions'].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{pageRecords.map((record) => <tr key={`${record.student?.user_id}-${record.assessment_source}-${record.assessment_id || ''}-${record.session_id}`} className="align-top hover:bg-slate-50/70"><StudentIdentityCell record={record} assignments={demoIdentityAssignments.current} /><td className="break-words px-4 py-4"><span className="font-semibold text-slate-800">{record.assessment_name}</span><p className="mt-0.5 text-xs text-slate-500">{record.assessment_source === 'faculty_assignment' ? 'Faculty assignment' : 'Independent practice'} · {record.session_name}</p><p className="mt-1 text-xs text-slate-500">{record.round_names.join(', ')}</p></td><td className="break-words px-4 py-4 text-slate-700">{record.activity}</td><td className="px-4 py-4"><StatusBadge value={record.assessment_status} />{record.evaluation_statuses.some((status) => ['awaiting_evaluation', 'evaluation_in_progress'].includes(status)) && <p className="mt-1 text-xs text-amber-700">Evaluation pending</p>}</td><td className="whitespace-normal px-4 py-4 text-xs text-slate-600">{dateLabel(record.last_activity)}</td><td className="px-4 py-4"><div className="flex flex-col items-start gap-2">{record.assessment_source === 'faculty_assignment' && record.assessment_id && onOpenAssignment && <button type="button" onClick={() => onOpenAssignment(record.assessment_id)} className="text-left text-xs font-semibold text-indigo-700 hover:underline">View assigned assessment</button>}<button type="button" onClick={() => openView(record, 'report')} className="text-left text-xs font-semibold text-indigo-700 hover:underline">View full student report</button>{record.has_submission_details && <button type="button" onClick={() => openView(record.details_record, 'details')} className="text-left text-xs font-semibold text-slate-700 hover:underline">Submission details</button>}</div></td></tr>)}</tbody></table></div>}
            {!loading && !error && filteredRecords.length > 0 && <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs text-slate-500">Showing {Math.min((page - 1) * PAGE_SIZE + 1, filteredRecords.length)} to {Math.min(page * PAGE_SIZE, filteredRecords.length)} of {filteredRecords.length} sessions</p><div className="flex items-center gap-2"><button type="button" aria-label="Previous assessment page" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded-lg border border-slate-300 px-3 py-2 text-xs disabled:opacity-40">Previous</button><span aria-live="polite" className="text-xs text-slate-600">Page {page} of {totalPages}</span><button type="button" aria-label="Next assessment page" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded-lg border border-slate-300 px-3 py-2 text-xs disabled:opacity-40">Next</button></div></div>}
        </section>

        <section className="rounded-2xl glass-card p-4 shadow-sm"><h2 className="font-semibold text-slate-900">Assessment Tools</h2><p className="mt-1 text-sm text-slate-500">Tools use Practice Assessment records in your authorized faculty scope.</p><ul className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><li><button type="button" onClick={() => { updateFilter('needs_attention', true); tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} className="text-left"><span className="text-sm font-semibold text-indigo-700">Evaluation follow-up</span><span className="mt-1 block text-xs text-slate-500">Filter practice rounds awaiting or undergoing evaluation, or with failures.</span></button></li><li><button type="button" onClick={() => { reset(); tableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} className="text-left"><span className="text-sm font-semibold text-indigo-700">Assessment history</span><span className="mt-1 block text-xs text-slate-500">Show previous practice sessions and persisted rounds.</span></button></li><li><button type="button" onClick={() => setReportPickerOpen((value) => !value)} disabled={!filterOptions.students?.length} className="text-left disabled:opacity-50"><span className="text-sm font-semibold text-indigo-700">Student performance reports</span><span className="mt-1 block text-xs text-slate-500">Choose an authorized practice participant and open their history.</span></button></li><li><button type="button" disabled={!data.total || loading} onClick={exportAll} className="text-left disabled:opacity-50"><span className="text-sm font-semibold text-indigo-700">Export assessment results</span><span className="mt-1 block text-xs text-slate-500">Download filtered practice round activity.</span></button></li></ul>
            {reportPickerOpen && <div className="mt-4 flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-3"><label className="min-w-56 flex-1 text-xs font-medium text-slate-600">Authorized practice student<select value={reportStudentId} onChange={(event) => setReportStudentId(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Select a student</option>{(filterOptions.students || []).map((item) => <option key={item.id} value={item.id}>{item.name}{item.roll_number ? ` · ${item.roll_number}` : ''}</option>)}</select></label><button type="button" disabled={!reportStudentId} onClick={openStudentReport} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Open report</button><button type="button" onClick={() => setReportPickerOpen(false)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Cancel</button></div>}
        </section>
        {selected && <FacultyPracticeAssessmentDialog {...selected} onClose={() => setSelected(null)} />}
    </div>;
}
