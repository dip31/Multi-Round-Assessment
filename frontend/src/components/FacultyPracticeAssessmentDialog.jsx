import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, Printer, X } from 'lucide-react';
import { assessmentStatusLabel } from '../utils/facultyAssessmentActivity';
import { buildPracticeReportText, escapePracticeReportHtml } from '../utils/facultyPracticeReport';

const dateLabel = (value) => value && !Number.isNaN(new Date(value).getTime())
    ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : 'Not available';
const roundNameLabel = (value) => {
    const title = String(value || 'Assessment round').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
    if (title === 'No Round Recorded') return 'No round recorded';
    return /\bassessment\b/i.test(title) ? title : `${title} Assessment`;
};
const roundStatusLabel = (value) => ({ active: 'In progress', in_progress: 'In progress', completed: 'Completed', pending: 'Not started', not_started: 'Not started', terminated: 'Incomplete', expired: 'Expired' }[value] || String(value || 'Not available').replaceAll('_', ' '));
const scoreLabel = (item) => item.score === null || item.score === undefined
    ? (['awaiting_evaluation', 'evaluation_in_progress'].includes(item.evaluation_status) ? 'Not evaluated' : 'Not available')
    : item.score_max !== null && item.score_max !== undefined
        ? `${item.score} / ${item.score_max}`
        : `${item.score} ${item.score_scale || ''}`;
const summaryLabels = {
    practice_sessions: 'Practice sessions',
    rounds_with_participation: 'Rounds with attempts or submissions',
    completed_rounds: 'Completed rounds',
    question_attempts: 'Question attempts',
    correct_answers: 'Correct answers',
    coding_submissions: 'Coding submissions',
    interview_responses: 'Interview responses',
    evaluated_round_results: 'Evaluated round results',
    pending_evaluations: 'Pending evaluations',
};

export default function FacultyPracticeAssessmentDialog({ record, mode, payload, loading, error, onClose, displayStudentName }) {
    const dialogRef = useRef(null);
    const [selectedEvidenceId, setSelectedEvidenceId] = useState(null);
    useEffect(() => {
        const previousFocus = document.activeElement;
        dialogRef.current?.focus();
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                event.preventDefault();
                onClose();
            }
        };
        document.addEventListener('keydown', onKeyDown);
        return () => {
            document.removeEventListener('keydown', onKeyDown);
            previousFocus?.focus?.();
        };
    }, [onClose]);

    const activeEvidenceId = selectedEvidenceId || (payload?.answers?.[0]
        ? `attempt:${payload.answers[0].attempt_id ?? payload.answers[0].sequence}`
        : payload?.submissions?.[0] ? `submission:${payload.submissions[0].id}` : '');
    const selectedAnswer = payload?.answers?.find((item) => `attempt:${item.attempt_id ?? item.sequence}` === activeEvidenceId);
    const selectedSubmission = payload?.submissions?.find((item) => `submission:${item.id}` === activeEvidenceId);
    const text = buildPracticeReportText({ mode, record, payload, selectedEvidenceId: activeEvidenceId, dateLabel });
    const print = () => {
        const printWindow = window.open('', '_blank');
        if (!printWindow) return;
        printWindow.document.write(`<!doctype html><html><head><title>Practice Assessment report</title><meta charset="utf-8"><style>body{font:14px Arial,sans-serif;color:#172033;margin:36px}pre{white-space:pre-wrap;line-height:1.6;font-family:Arial,sans-serif}</style></head><body><pre>${escapePracticeReportHtml(text)}</pre></body></html>`);
        printWindow.document.close();
        printWindow.focus();
        printWindow.print();
    };
    const download = () => {
        const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = mode === 'report' ? 'practice-assessment-report.txt' : 'practice-assessment-submission.txt';
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    const student = payload?.student || record?.student || {};
    const visibleStudentName = displayStudentName || student.name || 'Student name unavailable';

    return <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/50 p-3 sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
        <section ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="practice-detail-title" className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl focus:outline-none sm:p-7">
            <header className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
                <div>
                    <h2 id="practice-detail-title" className="text-xl font-bold text-slate-950">{mode === 'report' ? 'Student Performance Report' : 'Submission Details'}</h2>
                </div>
                <button type="button" aria-label="Close practice assessment details" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
            </header>

            {loading ? <p className="flex items-center gap-2 py-12 text-sm text-slate-600"><span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />Loading authorized practice records...</p> : error ? <div role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div> : <>
                <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {[
                        ['Student name', visibleStudentName],
                        ...(student.roll_number ? [['Roll number', student.roll_number]] : []),
                        ['Department', student.department || 'Not available'],
                        ['Assessment type', payload?.assessment_name || record?.assessment_name || 'Practice Assessment'],
                        ...(mode === 'details' ? [['Session', payload?.session_name || record?.session_name || 'Not available']] : []),
                    ].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-semibold text-slate-900">{value}</dd></div>)}
                </dl>

                {mode === 'report' && payload && <>
                    <section className="mt-5">
                        <h3 className="font-semibold text-slate-900">Overall practice activity</h3>
                        <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(payload.summary || {}).map(([key, value]) => <div key={key} className="rounded-xl border border-slate-200 p-3"><dt className="text-xs text-slate-500">{summaryLabels[key] || key.replaceAll('_', ' ')}</dt><dd className="mt-1 text-lg font-bold text-slate-900">{value}</dd></div>)}</dl>
                        {(payload.data_notes || []).length > 0 && <div className="mt-3 rounded-xl bg-slate-50 p-3"><h4 className="text-xs font-semibold text-slate-700">Data notes</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">{payload.data_notes.map((note) => <li key={note}>{note}</li>)}</ul></div>}
                    </section>
                    <section className="mt-6">
                        <h3 className="font-semibold text-slate-900">Assessment history</h3>
                        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200"><table className="w-full min-w-[1080px] text-left text-sm"><thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600"><tr>{['Assessment type', 'Session', 'Round', 'Date', 'Round status', 'Evaluation', 'Activity', 'Score'].map((item) => <th key={item} className="px-3 py-3">{item}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{(payload.history || []).map((item) => <tr key={`${item.session_id}-${item.round_id}`} className="align-top"><td className="px-3 py-3 font-medium">{item.assessment_name}</td><td className="px-3 py-3 text-slate-700">{item.session_name}</td><td className="px-3 py-3 font-medium">{roundNameLabel(item.round_name)}</td><td className="px-3 py-3 whitespace-nowrap">{dateLabel(item.date)}</td><td className="px-3 py-3">{item.round_status ? roundStatusLabel(item.round_status) : 'Not available'}</td><td className="px-3 py-3"><span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold">{assessmentStatusLabel(item.evaluation_status)}</span></td><td className="min-w-48 px-3 py-3">{item.activity_label}</td><td className="px-3 py-3 font-semibold whitespace-nowrap">{scoreLabel(item)}</td></tr>)}</tbody></table></div>
                        <p className="mt-3 text-xs text-slate-500">Interview response details appear once below, under the session where they were recorded.</p>
                    </section>
                    <section className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4"><h3 className="font-semibold text-slate-900">Progress interpretation</h3><p className="mt-1 text-sm text-slate-700">{payload.progress_message}</p>{payload.comparisons?.map((item) => <p key={`${item.round_type}-${item.score_scale}`} className="mt-2 text-sm text-slate-700">{item.round_type.replaceAll('_', ' ')}: {item.first_score} to {item.latest_score} ({item.change > 0 ? '+' : ''}{item.change} {item.score_scale}); {dateLabel(item.first_date)} to {dateLabel(item.latest_date)}.</p>)}</section>
                    {(payload.session_level_interviews || []).length > 0 && <section className="mt-5"><h3 className="font-semibold text-slate-900">Session-level interview results</h3><p className="mt-1 text-xs text-slate-500">Interview turns are linked to the practice session, not to a specific interview round.</p><div className="mt-3 space-y-3">{payload.session_level_interviews.map((interview, index) => <details key={`${interview.session_id}-${interview.phase}-${index}`} className="rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-semibold text-slate-800">{interview.phase || 'Interview'} | {interview.response_count} responses | {interview.evaluated_response_count} evaluated</summary><ul className="mt-3 space-y-2">{interview.turns.map((turn) => <li key={`${turn.turn_number}-${turn.created_at}`} className="rounded-lg bg-slate-50 p-3 text-sm"><p className="font-medium text-slate-800">Turn {turn.turn_number}{turn.is_followup ? ' | Follow-up' : ''}</p><p className="mt-1 text-slate-600">Question: {turn.question_text}</p><p className="mt-1 whitespace-pre-wrap text-slate-700">Response: {turn.candidate_response || 'No response persisted'}</p><p className="mt-1 text-xs text-slate-500">Content score: {turn.content_score === null || turn.content_score === undefined ? 'Not available' : `${turn.content_score} / 1`} | Final score: {turn.final_score === null || turn.final_score === undefined ? 'Not available' : `${turn.final_score} / 1`} | {dateLabel(turn.created_at)}</p></li>)}</ul></details>)}</div></section>}
                </>}

                {mode === 'details' && payload && <>
                    <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[
                        ['Round', roundNameLabel(payload.round_name)],
                        ['Round status', roundStatusLabel(payload.round_status)], ['Evaluation status', assessmentStatusLabel(payload.evaluation_status)],
                        ...(payload.round_type?.toLowerCase().includes('aptitude') || ['mcq', 'combined', 'technical'].includes(payload.round_type?.toLowerCase()) ? [['Question attempts', payload.question_attempts], ['Correct answers', payload.correct_answers], ['Evaluated answers', payload.evaluated_answers]] : payload.round_type === 'coding' ? [['Coding submissions', payload.attempt_count], ['Evaluated problem results', payload.evaluated_answers]] : []),
                        ['Score', scoreLabel(payload)],
                        ['Started', dateLabel(payload.started_at)], ['Completed', dateLabel(payload.completed_at)], ['Last submission', dateLabel(payload.last_activity)],
                    ].filter(([, value]) => value !== null && value !== undefined).map(([label, value]) => <div key={label} className="rounded-xl bg-slate-50 p-3"><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 text-sm font-semibold text-slate-900">{value}</dd></div>)}</dl>
                    {payload.detail_note && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{payload.detail_note}</p>}
                    {(payload.answers || []).length > 0 && <section className="mt-5"><h3 className="font-semibold text-slate-900">Selected persisted question attempt</h3>{payload.answers.length > 1 && <label className="mt-2 block max-w-md text-xs font-medium text-slate-600">Choose one question attempt<select value={activeEvidenceId} onChange={(event) => setSelectedEvidenceId(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">{payload.answers.map((answer) => <option key={answer.attempt_id || answer.sequence} value={`attempt:${answer.attempt_id || answer.sequence}`}>Attempt {answer.sequence} - {dateLabel(answer.attempted_at)}</option>)}</select></label>}{selectedAnswer && <article className="mt-3 rounded-xl border border-slate-200 p-4"><p className="text-sm font-semibold text-slate-900">Attempt {selectedAnswer.sequence}: {selectedAnswer.question_text}</p><p className="mt-2 text-sm text-slate-700">Selected answer: {selectedAnswer.selected_option || 'Not answered'}; {selectedAnswer.is_correct === null || selectedAnswer.is_correct === undefined ? 'Not evaluated' : selectedAnswer.is_correct ? 'Correct' : 'Incorrect'}</p><p className="mt-1 text-xs text-slate-500">Topic: {selectedAnswer.topic || 'Not recorded'}; Attempted: {dateLabel(selectedAnswer.attempted_at)}</p></article>}</section>}
                    {(payload.submissions || []).length > 0 && <section className="mt-5"><h3 className="font-semibold text-slate-900">Selected persisted coding submission</h3>{payload.submissions.length > 1 && <label className="mt-2 block max-w-md text-xs font-medium text-slate-600">Choose one submission<select value={activeEvidenceId} onChange={(event) => setSelectedEvidenceId(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">{payload.submissions.map((submission) => <option key={submission.id} value={`submission:${submission.id}`}>Submission {submission.id} - {dateLabel(submission.submitted_at)}</option>)}</select></label>}{selectedSubmission && <article className="mt-3 rounded-xl border border-slate-200 p-4"><p className="text-sm font-semibold text-slate-800">Submission {selectedSubmission.id}; {selectedSubmission.status}; {dateLabel(selectedSubmission.submitted_at)}</p><p className="mt-2 text-sm">Language: {selectedSubmission.language || 'Not available'}; Score: {selectedSubmission.score === null || selectedSubmission.score === undefined ? 'Not evaluated' : `${selectedSubmission.score} (scale unavailable)`}</p><pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">{selectedSubmission.code || 'No code persisted'}</pre></article>}</section>}
                    {!payload.answers?.length && !payload.submissions?.length && <p className="mt-5 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">This round has no separately persisted submission record.</p>}
                </>}
            </>}

            {!loading && !error && <div className="mt-6 flex flex-wrap justify-end gap-2"><button type="button" onClick={print} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><Printer className="h-4 w-4" />Print</button><button type="button" onClick={download} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><ArrowDownToLine className="h-4 w-4" />Download</button><button type="button" onClick={onClose} className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200">Close</button></div>}
        </section>
    </div>;
}
