import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, ClipboardList, LoaderCircle, Plus, RefreshCw, Search, Users } from 'lucide-react';
import api from '../services/api';
import FacultyPracticeAssessmentDialog from './FacultyPracticeAssessmentDialog';
import { formatAvailabilityDate, localDateTimeToUtcIso } from '../utils/assignedAssessmentAvailability';

const TABS = ['Create Assessment', 'Assigned Assessments', 'Review Results'];
const ROUND_OPTIONS = [
    { round_type: 'aptitude', practice_type: 'mcq', label: 'Aptitude Assessment · MCQ' },
    { round_type: 'aptitude', practice_type: 'technical', label: 'Aptitude Assessment · Technical MCQ' },
    { round_type: 'aptitude', practice_type: 'combined', label: 'Aptitude Assessment · Combined MCQ' },
    { round_type: 'coding', practice_type: 'coding', label: 'Coding Assessment' },
    { round_type: 'interview', practice_type: 'interview', label: 'Interview Assessment' },
];
const labels = { aptitude: 'Aptitude', coding: 'Coding', interview: 'Interview' };
const statusLabel = (value) => ({ not_started: 'Not started', in_progress: 'In progress', attempt_completed: 'Attempt completed', evaluation_pending: 'Evaluation pending', evaluated: 'Evaluated', failed: 'Failed', unavailable: 'Unavailable' }[value] || value);
const dateTime = (value) => value ? new Date(value).toLocaleString() : 'No limit';
const makeRequestKey = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;

function Notice({ error, onRetry }) {
    return error ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><p>{error}</p>{onRetry && <button type="button" onClick={onRetry} className="mt-2 font-semibold underline">Retry</button>}</div> : null;
}

export default function FacultyPracticeAssessmentWorkspace({ initialTab = TABS[0], monitoringOnly = false }) {
    const [tab, setTab] = useState(initialTab);
    const [assessments, setAssessments] = useState([]);
    const [students, setStudents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [rosterError, setRosterError] = useState(null);
    const [saving, setSaving] = useState(false);
    const [formError, setFormError] = useState(null);
    const [notice, setNotice] = useState(null);
    const [step, setStep] = useState(0);
    const [studentSearch, setStudentSearch] = useState('');
    const [selectedIds, setSelectedIds] = useState([]);
    const [selectedAssessmentId, setSelectedAssessmentId] = useState('');
    const [assessmentDetail, setAssessmentDetail] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState(null);
    const [practiceReportDialog, setPracticeReportDialog] = useState(null);
    const [reportLoading, setReportLoading] = useState(false);
    const [selectedStudentId, setSelectedStudentId] = useState('');
    const [form, setForm] = useState({ title: '', description: '', instructions: '', availability_start: '', availability_end: '', rounds: [] });
    const [requestKey, setRequestKey] = useState(makeRequestKey);
    const detailRequestId = useRef(0);

    const loadAssessments = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get('/faculty/practice-assessments');
            setAssessments(Array.isArray(response.data) ? response.data : []);
        } catch (cause) {
            setError(cause?.response?.status === 403 ? 'Faculty assessment management is not available for this account.' : 'Assigned assessments could not be loaded.');
        } finally { setLoading(false); }
    }, []);
    const loadRoster = useCallback(async () => {
        setRosterError(null);
        try {
            const response = await api.get('/faculty/practice-assessments/roster');
            setStudents(Array.isArray(response.data) ? response.data : []);
        } catch (cause) {
            setRosterError(cause?.response?.status === 403 ? 'The authorized faculty roster is unavailable for this account.' : 'The authorized student roster could not be loaded.');
        }
    }, []);
    useEffect(() => { loadAssessments(); if (!monitoringOnly) loadRoster(); }, [loadAssessments, loadRoster, monitoringOnly]);

    const loadAssessmentDetail = useCallback(async (assessmentId) => {
        const current = ++detailRequestId.current;
        if (!assessmentId) { setAssessmentDetail(null); setDetailError(null); return; }
        setDetailLoading(true);
        setDetailError(null);
        try {
            const response = await api.get(`/faculty/practice-assessments/${assessmentId}`);
            if (current === detailRequestId.current) setAssessmentDetail(response.data);
        } catch (cause) {
            if (current === detailRequestId.current) setDetailError(cause?.response?.data?.detail || 'Assessment results could not be loaded.');
        } finally {
            if (current === detailRequestId.current) setDetailLoading(false);
        }
    }, []);
    useEffect(() => { loadAssessmentDetail(selectedAssessmentId); }, [selectedAssessmentId, loadAssessmentDetail]);

    const filteredStudents = useMemo(() => {
        const term = studentSearch.trim().toLocaleLowerCase();
        return students.filter((student) => !term || `${student.name} ${student.roll_number || ''} ${student.id}`.toLocaleLowerCase().includes(term));
    }, [students, studentSearch]);
    const selectedAssessment = assessmentDetail && String(assessmentDetail.id) === String(selectedAssessmentId) ? assessmentDetail : null;
    const selectedResultStudent = selectedAssessment?.students?.find((item) => String(item.student?.id) === String(selectedStudentId)) || null;

    const openConsolidatedReport = async (student) => {
        setReportLoading(true);
        setPracticeReportDialog({ loading: true, error: null, payload: null, record: { student: { user_id: student.id, name: student.name, roll_number: student.roll_number }, assessment_name: 'Practice Assessment', session_name: 'Student practice history', round_name: 'Practice history' } });
        try {
            const response = await api.get(`/profile/cohort/practice-assessment-activity/students/${student.id}/report`);
            setPracticeReportDialog((current) => ({ ...current, loading: false, payload: response.data }));
        } catch (cause) {
            setPracticeReportDialog((current) => ({ ...current, loading: false, error: cause?.response?.status === 403 || cause?.response?.status === 404 ? 'This student report is outside your authorized faculty scope.' : 'The student practice report could not be loaded.' }));
        } finally { setReportLoading(false); }
    };

    const changeRound = (index, key, value) => setForm((current) => ({ ...current, rounds: current.rounds.map((round, at) => at === index ? { ...round, [key]: value } : round) }));
    const moveRound = (index, direction) => setForm((current) => {
        const rounds = [...current.rounds];
        const target = index + direction;
        if (target < 0 || target >= rounds.length) return current;
        [rounds[index], rounds[target]] = [rounds[target], rounds[index]];
        return { ...current, rounds };
    });
    const addRound = () => setForm((current) => ({ ...current, rounds: [...current.rounds, { round_type: 'aptitude', practice_type: 'mcq' }] }));
    const removeRound = (index) => setForm((current) => ({ ...current, rounds: current.rounds.filter((_, at) => at !== index) }));
    const toggleStudent = (id) => setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
    const selectFiltered = () => setSelectedIds((current) => [...new Set([...current, ...filteredStudents.map((student) => student.id)])]);
    const cancelAssignedAssessment = async (assessmentId) => {
        if (!window.confirm('Cancel this assessment for future rounds? Existing attempts and results will remain available.')) return;
        try {
            await api.post(`/faculty/practice-assessments/${assessmentId}/cancel`);
            setNotice('Assessment cancelled. Existing attempt records remain available.');
            await loadAssessments();
            if (selectedAssessmentId === String(assessmentId)) await loadAssessmentDetail(selectedAssessmentId);
        } catch (cause) {
            setError(cause?.response?.data?.detail || 'Assessment could not be cancelled.');
        }
    };

    const submit = async () => {
        setFormError(null);
        if (!form.title.trim() || !form.rounds.length || !selectedIds.length) {
            setFormError('Enter a title, add at least one round, and select at least one student.');
            return;
        }
        if (form.availability_start && form.availability_end && new Date(form.availability_end) <= new Date(form.availability_start)) {
            setFormError('The availability end must be later than its start.');
            return;
        }
        setSaving(true);
        try {
            await api.post('/faculty/practice-assessments', {
                title: form.title.trim(), description: form.description.trim(), instructions: form.instructions.trim(),
                availability_start: localDateTimeToUtcIso(form.availability_start),
                availability_end: localDateTimeToUtcIso(form.availability_end),
                rounds: form.rounds, student_ids: selectedIds,
            }, { headers: { 'Idempotency-Key': requestKey } });
            setForm({ title: '', description: '', instructions: '', availability_start: '', availability_end: '', rounds: [] });
            setSelectedIds([]);
            setRequestKey(makeRequestKey());
            setStep(0);
            setNotice('Assessment assigned successfully.');
            await loadAssessments();
            setTab('Assigned Assessments');
        } catch (cause) {
            setFormError(cause?.response?.data?.detail || 'Assessment could not be assigned. Your entries are saved here; retry to safely submit again.');
        } finally { setSaving(false); }
    };

    const stepContent = () => {
        if (step === 0) return <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Assessment title<input value={form.title} maxLength={200} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" /></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Description<textarea value={form.description} maxLength={2000} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} rows={2} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" /></label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Student instructions<textarea value={form.instructions} maxLength={5000} onChange={(event) => setForm((current) => ({ ...current, instructions: event.target.value }))} rows={3} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" /></label>
            <label className="text-sm font-medium text-slate-700">Available from<input type="datetime-local" value={form.availability_start} onChange={(event) => setForm((current) => ({ ...current, availability_start: event.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" /></label>
            <label className="text-sm font-medium text-slate-700">Available until<input type="datetime-local" value={form.availability_end} onChange={(event) => setForm((current) => ({ ...current, availability_end: event.target.value }))} className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2.5" /></label>
            <p className="text-xs leading-5 text-slate-500 sm:col-span-2">Assessment time limits and attempt limits follow each existing practice engine’s current settings.</p>
        </div>;
        if (step === 1) return <div className="space-y-3">
            {form.rounds.map((round, index) => <div key={`${index}-${round.round_type}`} className="grid items-end gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-[1fr_auto_auto_auto]">
                <label className="text-sm font-medium text-slate-700">Round {index + 1}<select value={`${round.round_type}:${round.practice_type}`} onChange={(event) => { const [round_type, practice_type] = event.target.value.split(':'); changeRound(index, 'round_type', round_type); changeRound(index, 'practice_type', practice_type); }} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2">{ROUND_OPTIONS.map((option) => <option key={`${option.round_type}:${option.practice_type}`} value={`${option.round_type}:${option.practice_type}`}>{option.label}</option>)}</select></label>
                <button type="button" aria-label={`Move round ${index + 1} up`} disabled={index === 0} onClick={() => moveRound(index, -1)} className="rounded-lg border border-slate-300 p-2 disabled:opacity-40"><ArrowUp size={16} /></button>
                <button type="button" aria-label={`Move round ${index + 1} down`} disabled={index === form.rounds.length - 1} onClick={() => moveRound(index, 1)} className="rounded-lg border border-slate-300 p-2 disabled:opacity-40"><ArrowDown size={16} /></button>
                <button type="button" onClick={() => removeRound(index)} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700">Remove</button>
            </div>)}
            {form.rounds.length < 10 && <button type="button" onClick={addRound} className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 px-3 py-2 text-sm font-semibold text-indigo-700"><Plus size={16} />Add round</button>}
            <p className="text-xs text-slate-500">Rounds run in the order shown. Aptitude uses the existing MCQ practice modes; Coding and Interview use their existing practice engines.</p>
        </div>;
        if (step === 2) return rosterError ? <Notice error={rosterError} onRetry={loadRoster} /> : <div>
            <div className="flex flex-wrap items-center justify-between gap-3"><label className="relative min-w-[230px] flex-1"><span className="sr-only">Search authorized students</span><Search size={16} className="absolute left-3 top-3 text-slate-400" /><input value={studentSearch} onChange={(event) => setStudentSearch(event.target.value)} placeholder="Search name or student ID" className="w-full rounded-xl border border-slate-300 py-2.5 pl-9 pr-3" /></label><button type="button" onClick={selectFiltered} disabled={!filteredStudents.length} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50">Select filtered ({filteredStudents.length})</button></div>
            <p className="mt-3 text-sm font-semibold text-indigo-800">{selectedIds.length} selected · authorized roster only</p>
            <div className="mt-3 max-h-72 overflow-y-auto rounded-xl border border-slate-200">{filteredStudents.map((student) => <label key={student.id} className="flex cursor-pointer items-center gap-3 border-b border-slate-100 px-3 py-2.5 last:border-0 hover:bg-slate-50"><input type="checkbox" checked={selectedIds.includes(student.id)} onChange={() => toggleStudent(student.id)} className="h-4 w-4 rounded border-slate-300 text-indigo-600" /><span className="min-w-0"><span className="block text-sm font-medium text-slate-900">{student.name}</span><span className="text-xs text-slate-500">{student.roll_number || `Student ${student.id}`} · {student.department}</span></span></label>)}{!filteredStudents.length && <p className="p-5 text-sm text-slate-500">No students match this search.</p>}</div>
            {!!selectedIds.length && <div className="mt-3 flex flex-wrap gap-2">{selectedIds.map((id) => { const student = students.find((item) => item.id === id); return <button key={id} type="button" onClick={() => toggleStudent(id)} className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-800">{student?.name || `Student ${id}`} ×</button>; })}</div>}
        </div>;
        return <div className="space-y-4 text-sm">
            <div><h3 className="font-semibold text-slate-900">{form.title || 'Untitled assessment'}</h3><p className="mt-1 text-slate-600">{form.description || 'No description provided.'}</p><p className="mt-1 text-xs text-slate-500">{dateTime(form.availability_start)} – {dateTime(form.availability_end)}</p></div>
            <div><h4 className="font-semibold text-slate-800">Round sequence</h4><ol className="mt-2 list-inside list-decimal space-y-1 text-slate-700">{form.rounds.map((round, index) => <li key={`${index}-${round.round_type}`}>{index + 1}. {ROUND_OPTIONS.find((item) => item.round_type === round.round_type && item.practice_type === round.practice_type)?.label}</li>)}</ol></div>
            <div><h4 className="font-semibold text-slate-800">Assigned students ({selectedIds.length})</h4><ul className="mt-2 flex flex-wrap gap-2">{selectedIds.map((id) => { const student = students.find((item) => item.id === id); return <li key={id} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{student?.name || `Student ${id}`} ({student?.roll_number || id})</li>; })}</ul></div>
        </div>;
    };

    return <div className="space-y-4">
        {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}<button type="button" onClick={() => setNotice(null)} className="ml-3 font-semibold underline">Dismiss</button></div>}
        {!monitoringOnly && <nav aria-label="Practice assessment workspace views" className="flex gap-2 overflow-x-auto rounded-2xl glass-card p-2 shadow-sm">{TABS.map((item) => <button key={item} type="button" aria-current={tab === item ? 'page' : undefined} onClick={() => { setTab(item); setFormError(null); }} className={`shrink-0 rounded-xl px-3 py-2 text-sm font-semibold ${tab === item ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{item}</button>)}</nav>}
        {tab === 'Create Assessment' && <section className="rounded-2xl glass-card p-4 shadow-sm sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold text-slate-900">Create and assign an assessment</h2><p className="mt-1 text-sm text-slate-500">Step {step + 1} of 4 · {['Assessment details', 'Configure rounds', 'Select students', 'Review and assign'][step]}</p></div><span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800">Sequential execution</span></div>
            <div className="mt-5">{stepContent()}</div>
            {formError && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{formError}</p>}
            <div className="mt-6 flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-4"><button type="button" onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0 || saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40">Back</button><div className="flex gap-2">{step < 3 ? <button type="button" onClick={() => { if (step === 0 && !form.title.trim()) return setFormError('Enter an assessment title before continuing.'); if (step === 1 && !form.rounds.length) return setFormError('Add at least one round before continuing.'); if (step === 2 && !selectedIds.length) return setFormError('Select at least one authorized student.'); setFormError(null); setStep((value) => value + 1); }} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Continue</button> : <button type="button" onClick={submit} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving && <LoaderCircle size={16} className="animate-spin" />}Assign Assessment</button>}</div></div>
        </section>}
        {tab === 'Assigned Assessments' && <section data-testid="assessment-monitoring" className="overflow-hidden rounded-2xl glass-card shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4"><div><h2 className="font-bold text-slate-900">Assessment Monitoring</h2><p className="mt-1 text-sm text-slate-500">Track faculty-created assessments and their assigned students using saved assignment and round results.</p></div><div className="flex gap-2">{!monitoringOnly && <button type="button" onClick={() => setTab('Create Assessment')} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white"><Plus size={15} />Create assessment</button>}<button type="button" onClick={() => { loadAssessments(); if (selectedAssessmentId) loadAssessmentDetail(selectedAssessmentId); }} disabled={loading || detailLoading} aria-label="Refresh assigned assessments" className="rounded-lg border border-slate-300 p-2"><RefreshCw size={16} className={loading || detailLoading ? 'animate-spin' : ''} /></button></div></div>
            {error ? <div className="p-4"><Notice error={error} onRetry={loadAssessments} /></div> : loading ? <p className="p-8 text-center text-sm text-slate-500">Loading assessments…</p> : !assessments.length ? <div className="p-10 text-center"><ClipboardList className="mx-auto h-8 w-8 text-slate-400" /><h3 className="mt-3 font-semibold text-slate-900">No assessments assigned yet</h3><p className="mt-1 text-sm text-slate-500">Create an assessment and assign it to students in your authorized roster.</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[820px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Assessment', 'Rounds', 'Assigned students', 'Availability', 'Progress', 'Status', 'Action'].map((label) => <th key={label} className="px-6 py-4">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{assessments.map((item) => <Fragment key={item.id}><tr><td className="px-6 py-4"><p className="font-semibold text-slate-900">{item.title}</p>{item.description?.trim() && <p className="text-xs text-slate-500">{item.description}</p>}</td><td className="px-6 py-4">{item.rounds.map((round) => labels[round.round_type]).join(' → ')}</td><td className="px-6 py-4">{item.assigned_students}</td><td className="px-6 py-4 text-xs text-slate-600 space-y-2"><span className="block"><span className="font-semibold text-slate-700">Start date and time:</span> {formatAvailabilityDate(item.availability_start)}</span><span className="block"><span className="font-semibold text-slate-700">End date and time:</span> {formatAvailabilityDate(item.availability_end)}</span></td><td className="px-6 py-4"><span className="block">{item.rounds_started || 0} / {item.rounds_total || 0} student-round opportunities started</span><span className="mt-1 block text-xs text-slate-500">{item.rounds_attempt_completed || 0} attempts completed · {item.rounds_evaluated || 0} evaluated · {item.rounds_evaluation_pending || 0} pending evaluation · {item.rounds_failed || 0} failed</span></td><td className="px-6 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.status === 'cancelled' ? 'bg-rose-50 text-rose-800' : 'bg-emerald-50 text-emerald-800'}`}>{item.status}</span></td><td className="px-6 py-4"><div className="flex flex-col items-start gap-2"><button type="button" onClick={() => { setSelectedAssessmentId((current) => current === String(item.id) ? '' : String(item.id)); setSelectedStudentId(''); }} className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100">{selectedAssessmentId === String(item.id) ? 'Hide Students' : 'View Students'}</button>{item.status === 'published' && <button type="button" onClick={() => cancelAssignedAssessment(item.id)} className="inline-flex items-center rounded-md border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50">Cancel</button>}</div></td></tr>{selectedAssessmentId === String(item.id) && <tr><td colSpan={7} className="bg-slate-50/70 p-4">{detailLoading ? <p className="text-sm text-slate-600">Loading assigned-student progress…</p> : detailError ? <Notice error={detailError} onRetry={() => loadAssessmentDetail(String(item.id))} /> : selectedAssessment ? <div className="space-y-3">{!selectedAssessment.students?.length ? <p className="text-sm text-slate-600">No students in this assessment’s current authorized scope.</p> : selectedAssessment.students.map((assignedStudent) => <article key={assignedStudent.assignment_id} className="rounded-xl glass-card p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-900">{assignedStudent.student.name}</h3><p className="text-xs text-slate-500">{assignedStudent.student.roll_number || 'No student identifier'} · {statusLabel(assignedStudent.status)} · {assignedStudent.progress}/{assignedStudent.round_count} rounds started</p></div><button type="button" onClick={() => { setSelectedStudentId(String(assignedStudent.student.id)); setTab('Review Results'); }} className="text-xs font-semibold text-indigo-700 hover:underline">Review results</button></div><ol className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{assignedStudent.rounds.map((round) => <li key={round.id} className="rounded-lg border border-slate-100 bg-slate-50 p-3"><p className="text-xs font-semibold text-slate-700">{round.sequence}. {labels[round.round_type]}{round.practice_type !== round.round_type && ` · ${round.practice_type}`}</p><p className="mt-1 text-xs text-slate-600">{statusLabel(round.status)}</p><p className="mt-1 text-xs text-slate-500">{round.score === null || round.score === undefined ? 'Score unavailable' : `Score ${round.score}`}</p></li>)}</ol></article>)}</div> : <p className="text-sm text-slate-600">Assessment details are not available.</p>}</td></tr>}</Fragment>)}</tbody></table></div>}
        </section>}
        {tab === 'Review Results' && <section className="rounded-2xl glass-card p-4 shadow-sm sm:p-6"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-bold text-slate-900">Review results</h2><button type="button" disabled={!selectedAssessmentId || detailLoading} onClick={() => loadAssessmentDetail(selectedAssessmentId)} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50"><RefreshCw size={14} className={detailLoading ? 'animate-spin' : ''} />Refresh</button></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium text-slate-700">Assessment<select value={selectedAssessmentId} onChange={(event) => { setSelectedAssessmentId(event.target.value); setSelectedStudentId(''); }} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="">Select assessment</option>{assessments.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label className="text-sm font-medium text-slate-700">Assigned student<select value={selectedStudentId} onChange={(event) => setSelectedStudentId(event.target.value)} disabled={!selectedAssessment} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="">Select assigned student</option>{(selectedAssessment?.students || []).map((item) => <option key={item.assignment_id} value={item.student.id}>{item.student.name} · {item.student.roll_number || item.student.id}</option>)}</select></label></div>
            {!selectedAssessmentId && <p className="mt-5 rounded-xl bg-slate-50 p-5 text-sm text-slate-600">Select an assessment to see its assigned students and progress.</p>}
            {selectedAssessmentId && detailLoading && <p className="mt-5 rounded-xl bg-slate-50 p-5 text-sm text-slate-600">Loading assigned students and results…</p>}
            {selectedAssessmentId && detailError && <div className="mt-5"><Notice error={detailError} onRetry={() => loadAssessmentDetail(selectedAssessmentId)} /></div>}
            {selectedAssessment && !selectedResultStudent && !detailLoading && <p className="mt-5 rounded-xl bg-slate-50 p-5 text-sm text-slate-600"><Users className="mr-2 inline h-4 w-4" />Select a student assigned to this assessment.</p>}
            {selectedResultStudent && <><div className="mt-5 rounded-xl bg-indigo-50 p-4"><p className="font-semibold text-indigo-950">{selectedResultStudent.student.name}</p><p className="mt-1 text-sm text-indigo-800">{selectedAssessment.title} · {statusLabel(selectedResultStudent.status)} · {selectedResultStudent.progress}/{selectedResultStudent.round_count} rounds started</p>{selectedAssessment.instructions && <p className="mt-2 text-sm text-slate-700">Instructions: {selectedAssessment.instructions}</p>}</div><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-3 py-2">Order</th><th className="px-3 py-2">Round</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Persisted result</th><th className="px-3 py-2">Evaluation evidence</th></tr></thead><tbody className="divide-y divide-slate-100">{selectedResultStudent.rounds.map((round) => <tr key={round.id}><td className="px-3 py-3">{round.sequence}</td><td className="px-3 py-3">{labels[round.round_type]}{round.practice_type !== round.round_type && ` · ${round.practice_type}`}</td><td className="px-3 py-3">{statusLabel(round.status)}</td><td className="px-3 py-3">{round.score === null || round.score === undefined ? 'Not available' : round.round_type === 'interview' ? `${round.score.toFixed(2)} / 10` : round.round_type === 'aptitude' ? `${round.score} / ${round.evidence?.evaluated_questions ?? '—'} correct` : `${round.score} / ${round.evidence?.score_max ?? '—'} points`}</td><td className="px-3 py-3 text-xs text-slate-600">{round.round_type === 'aptitude' && round.evidence?.evaluated_questions !== undefined ? `${round.evidence.correct}/${round.evidence.evaluated_questions} answers evaluated` : round.round_type === 'coding' && round.evidence?.submission_count !== undefined ? `${round.evidence.evaluated_submissions} of ${round.evidence.submission_count} submissions evaluated` : round.round_type === 'interview' && round.evidence?.evaluated_turns !== undefined ? `${round.evidence.evaluated_turns} interview turns scored; turn-level feedback is not persisted in the current engine` : 'Evaluation details unavailable'}</td></tr>)}</tbody></table></div><p className="mt-3 text-xs text-slate-500">Scores and evidence come from linked engine records. Feedback is shown only where persisted by the existing engine; missing feedback is not inferred.</p><button type="button" disabled={reportLoading} onClick={() => openConsolidatedReport(selectedResultStudent.student)} className="mt-3 rounded-lg border border-indigo-200 px-3 py-2 text-xs font-semibold text-indigo-700 disabled:opacity-50">{reportLoading ? 'Loading student report…' : 'Open consolidated student practice report'}</button></>}
        </section>}
        {practiceReportDialog && <FacultyPracticeAssessmentDialog {...practiceReportDialog} mode="report" onClose={() => setPracticeReportDialog(null)} />}
    </div>;
}
