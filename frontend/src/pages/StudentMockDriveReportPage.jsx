import { createElement, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpenCheck, Check, ChevronDown, Download, FileQuestion, Flag, Gauge, Layers3, ListChecks, Target, Timer } from 'lucide-react';
import StudentModeLayout from '../components/StudentModeLayout';
import api from '../services/api';
import { getStudentMockDriveImprovementPlan } from '../utils/studentMockDriveImprovementPlan';

const ROUND_NAMES = { aptitude: 'Aptitude', coding: 'Coding', technical_interview: 'Technical interview', hr_interview: 'HR interview' };
const card = 'rounded-2xl border border-slate-200 bg-white shadow-sm';
const label = 'text-xs font-semibold uppercase tracking-wide text-slate-500';
const EMPTY_QUESTIONS = [];

function getRoundState(round) {
  if (round.evaluation_status === 'pending') return 'Completed - awaiting evaluation';
  if (round.evaluation_status === 'evaluated') return 'Completed and evaluated';
  if (['completed', 'expired'].includes(round.status)) return 'Completed - evaluation unavailable';
  if (['active', 'in_progress'].includes(round.status)) return 'In progress';
  return 'Not started';
}

function getScore(round) {
  if (round.score == null) return 'Unavailable';
  if (round.max_score === 100) return `${round.score}%`;
  if (round.max_score === 1) return `${round.score} / 1.00`;
  return `${round.score}${round.max_score == null ? '' : ` / ${round.max_score}`}`;
}

function Stat({ title, value, note, icon: Icon }) {
  return <div className={`${card} p-4`}><div className="flex items-start justify-between gap-2"><p className={label}>{title}</p>{createElement(Icon, { 'aria-hidden': true, className: 'h-4 w-4 text-blue-600' })}</div><p className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{value}</p><p className="mt-1 text-xs text-slate-500">{note}</p></div>;
}

function AptitudeDetails({ details }) {
  const questions = details?.questions ?? EMPTY_QUESTIONS;
  const [openQuestion, setOpenQuestion] = useState(null);
  const [filter, setFilter] = useState('all');
  const topicStats = useMemo(() => {
    const topics = new Map();
    questions.forEach((question) => {
      if (!question.topic || question.is_correct == null) return;
      const value = topics.get(question.topic) || { correct: 0, graded: 0 };
      value.graded += 1;
      if (question.is_correct === true) value.correct += 1;
      topics.set(question.topic, value);
    });
    return [...topics].map(([name, value]) => ({ name, ...value, accuracy: value.correct / value.graded * 100 }));
  }, [questions]);
  const graded = questions.filter((q) => q.is_correct != null);
  const correct = graded.filter((q) => q.is_correct === true).length;
  const answered = questions.filter((q) => q.selected_option != null && q.selected_option !== '').length;
  const timed = questions.map((q) => q.response_time).filter((time) => Number.isFinite(time) && time >= 0);
  const averageSeconds = timed.length ? timed.reduce((sum, time) => sum + time, 0) / timed.length : null;
  const strongest = topicStats.filter((topic) => topic.graded >= 2).sort((a, b) => b.accuracy - a.accuracy)[0];
  const focus = topicStats.filter((topic) => topic.graded >= 2).sort((a, b) => a.accuracy - b.accuracy)[0];
  const visibleQuestions = questions.filter((q) => filter === 'all' || (filter === 'unanswered' ? q.response_status === 'unanswered' : filter === 'ungraded' ? q.response_status === 'ungraded' : q.is_correct === (filter === 'correct')));
  return <div className="mt-5 space-y-5">
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{[['Total questions', details?.total_questions ?? 'Unavailable'], ['Answered', answered], ['Correct', correct], ['Incorrect', graded.length - correct], ['Unanswered', details?.unanswered_count ?? 'Unavailable'], ['Accuracy', graded.length ? `${Math.round(correct / graded.length * 100)}%` : 'Unavailable']].map(([title, value]) => <div key={title} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{title}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}</div>
    {details?.question_set_complete === false && <p className="text-xs text-slate-500">The complete assigned question set is unavailable for this legacy round, so total and unanswered counts cannot be calculated reliably.</p>}
    {!!topicStats.length && <div className="grid gap-3 md:grid-cols-2">{topicStats.map((topic) => <div key={topic.name} className="rounded-xl border border-slate-200 p-4"><div className="flex justify-between gap-2 text-sm"><span className="font-medium text-slate-800">{topic.name}</span><span className="text-slate-600">{topic.correct}/{topic.graded} · {Math.round(topic.accuracy)}%</span></div><div className="mt-3 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-600" style={{ width: `${topic.accuracy}%` }} /></div></div>)}</div>}
    {averageSeconds != null && <p className="flex items-center gap-2 text-sm text-slate-600"><Timer className="h-4 w-4" />Average recorded response time: <strong className="text-slate-900">{Math.round(averageSeconds)} seconds</strong> across {timed.length} questions with valid durations.</p>}
    {strongest && focus && strongest.name !== focus.name && <p className="text-sm text-slate-600">Strongest topic: <strong>{strongest.name}</strong>. Topic to review: <strong>{focus.name}</strong>. Each has at least two graded responses; accuracy excludes unanswered and ungraded questions.</p>}
    <section aria-label="Aptitude question review"><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold text-slate-900">Question review</h3><label className="flex items-center gap-2 text-sm text-slate-600 print:hidden">Filter<select value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2"><option value="all">All</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option><option value="unanswered">Unanswered</option><option value="ungraded">Ungraded</option></select></label></div>
      <ol className="mt-3 space-y-2">{visibleQuestions.map((q, index) => { const questionKey = `${q.question_id}-${index}`; const expanded = openQuestion === questionKey; const status = q.response_status === 'unanswered' ? 'Unanswered' : q.response_status === 'ungraded' ? 'Evaluation unavailable' : q.is_correct === true ? 'Correct' : q.is_correct === false ? 'Incorrect' : 'Evaluation unavailable'; return <li key={questionKey} className="rounded-xl border border-slate-200"><button type="button" aria-expanded={expanded} onClick={() => setOpenQuestion(expanded ? null : questionKey)} className="flex w-full items-center gap-3 p-4 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 print-hidden"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-slate-100 text-sm font-bold text-slate-700">{index + 1}</span><span className="min-w-0 flex-1"><span className="block font-medium text-slate-900">{q.text || `Question ${index + 1}`}</span><span className="mt-1 block text-xs text-slate-500">{q.topic || 'Topic unavailable'} · {q.difficulty || 'Difficulty unavailable'} · {status}</span></span><ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`} /></button><div className={`${expanded ? 'block' : 'hidden print:block'} border-t border-slate-100 bg-slate-50 px-4 py-3 text-sm`}><p className="hidden print:block font-medium text-slate-900">Q{index + 1}. {q.text || 'Question text unavailable'} · {status}</p><p className="text-slate-600">Selected answer: {q.selected_option || 'No recorded answer'}</p>{q.response_time != null && Number.isFinite(q.response_time) && q.response_time >= 0 && <p className="mt-1 text-xs text-slate-500">Recorded response time: {q.response_time}s</p>}</div></li>; })}</ol>
      {!visibleQuestions.length && <p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No persisted question details match this filter.</p>}
      <p className="mt-3 text-xs text-slate-500">Accuracy = correct divided by graded responses. Each assigned question is represented once using its latest persisted attempt.</p>
    </section>
  </div>;
}

function CodingDetails({ details }) {
  const problems = details?.problems || [];
  const attempted = problems.filter((problem) => problem.attempted).length;
  const solved = problems.filter((problem) => problem.status === 'accepted' || problem.status === 'solved').length;
  return <div className="mt-5 space-y-4"><div className="grid grid-cols-3 gap-3">{[['Assigned', problems.length], ['Attempted', attempted], ['Solved', solved]].map(([name, value]) => <div key={name} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{name}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}</div><p className="text-xs text-slate-500">Problem-level persisted scores use the normalized 0–1 scale. Per-test-case outcomes are not available in this report.</p>{problems.length ? <div className="space-y-2">{problems.map((problem) => <article key={problem.problem_id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold text-slate-900">{problem.title || 'Assigned problem'}</h3><span className="text-sm text-slate-600">{problem.score == null ? 'Score unavailable' : `${Math.round(problem.score * 100)}% finalized best score`}</span></div><p className="mt-1 text-sm text-slate-500">{problem.difficulty || 'Difficulty unavailable'} · {problem.attempted ? 'Attempted' : 'Not attempted'} · {problem.evaluation_status === 'pending' ? 'Evaluation pending' : problem.evaluation_status === 'unavailable' && problem.attempted ? 'Evaluation unavailable' : problem.status || 'Not attempted'}</p>{problem.tags?.length > 0 && <p className="mt-1 text-xs text-slate-500">Topics: {problem.tags.join(', ')}</p>}</article>)}</div> : <p className="text-sm text-slate-600">No assigned problem details are available.</p>}</div>;
}

function InterviewDetails({ details }) {
  const turns = details?.turns || [];
  const evaluated = turns.filter((turn) => turn.score != null).length;
  return <div className="mt-5 space-y-4"><div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Persisted turns</p><p className="mt-1 font-semibold">{turns.length}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Evaluated turns</p><p className="mt-1 font-semibold">{evaluated}</p></div></div>{turns.length ? turns.map((turn, index) => <article key={`${turn.turn_number}-${index}`} className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{turn.is_followup ? `Follow-up ${turn.followup_number || ''}` : `Question ${turn.turn_number}`}</p><p className="mt-1 font-medium text-slate-900">{turn.question || 'Question unavailable'}</p><p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{turn.response || 'No response was persisted.'}</p><p className="mt-2 text-sm text-slate-600">{turn.score == null ? 'Evaluation unavailable' : `Persisted score: ${turn.score} / 1.00`}</p></article>) : <p className="text-sm text-slate-600">No persisted interview turns are available.</p>}</div>;
}

function RoundCard({ round, index }) {
  const [open, setOpen] = useState(index === 0);
  const name = ROUND_NAMES[round.round_type] || round.round_type || 'Assessment round';
  return <article className={`${card} overflow-hidden`}><button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)} className="flex w-full items-center gap-4 p-4 text-left sm:p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600 print-hidden"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-sm font-bold text-blue-800">{String(index + 1).padStart(2, '0')}</span><span className="min-w-0 flex-1"><span className="block font-semibold text-slate-900">{name}</span><span className="mt-1 block text-sm text-slate-500">{name} assessment · {getRoundState(round)}</span></span><span className="text-right"><span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Round score</span><span className="mt-1 block font-semibold text-slate-900">{getScore(round)}</span></span><ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} /></button><div className={`${open ? 'block' : 'hidden print:block'} border-t border-slate-200 px-4 pb-5 sm:px-5`}><div className="hidden print:block pt-4 font-semibold text-slate-900">{String(index + 1).padStart(2, '0')} · {name} · {getRoundState(round)} · {getScore(round)}</div>{round.round_type === 'aptitude' ? <AptitudeDetails details={round.details} /> : round.round_type === 'coding' ? <CodingDetails details={round.details} /> : <InterviewDetails details={round.details} />}</div></article>;
}

function formatDate(value) {
  if (!value) return 'Information unavailable';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Information unavailable' : date.toLocaleDateString();
}

export default function StudentMockDriveReportPage() {
  const { mockDriveId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => {
      if (active) { setLoading(true); setError(''); setReport(null); }
      return api.get(`/mock-drives/${encodeURIComponent(mockDriveId)}/result`);
    }).then(({ data }) => { if (active) setReport(data); }).catch((err) => {
      if (!active) return;
      setError(err.response?.status === 404 ? 'No report is available for this mock drive.' : [401, 403].includes(err.response?.status) ? 'You are not authorized to view this mock drive report.' : 'Unable to load this report. Please try again.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [mockDriveId]);

  const rounds = report?.rounds || [];
  const completed = rounds.filter((round) => ['completed', 'expired'].includes(round.status)).length;
  const results = rounds.filter((round) => round.evaluation_status === 'evaluated').length;
  const completion = rounds.length ? completed / rounds.length * 100 : 0;
  const insights = useMemo(() => {
    const items = [];
    for (const round of report?.rounds || []) {
      if (round.evaluation_status !== 'evaluated') continue;
      if (round.round_type === 'aptitude') {
        const topics = new Map();
        for (const q of round.details?.questions || []) {
          if (!q.topic || q.is_correct == null) continue;
          const tally = topics.get(q.topic) || { correct: 0, graded: 0 };
          tally.graded += 1;
          if (q.is_correct === true) tally.correct += 1;
          topics.set(q.topic, tally);
        }
        for (const [topic, tally] of topics) if (tally.graded >= 2 && tally.correct < tally.graded) items.push({ key: `apt-${topic}`, round: ROUND_NAMES.aptitude, topic, evidence: `${tally.correct} of ${tally.graded} graded responses were correct.`, meaning: 'Some graded responses in this topic were missed.', action: `Review the missed graded questions in ${topic}.` });
        const strong = [...topics].filter(([, tally]) => tally.graded >= 2 && tally.correct === tally.graded);
        for (const [topic, tally] of strong) items.push({ key: `strong-${topic}`, round: ROUND_NAMES.aptitude, topic, evidence: `${tally.correct} of ${tally.graded} graded responses were correct.`, meaning: 'All recorded graded responses in this topic were correct.' });
      }
      if (round.round_type === 'coding') for (const problem of round.details?.problems || []) if (problem.score != null && problem.score < 1) items.push({ key: `coding-${problem.problem_id}`, round: ROUND_NAMES.coding, topic: problem.title, evidence: `Finalized best submission score: ${Math.round(problem.score * 100)}% on the persisted normalized scale.`, meaning: 'The evaluated submission did not reach the full normalized score.', action: `Review the solution approach for ${problem.title || 'this problem'}.` });
      if (['technical_interview', 'hr_interview'].includes(round.round_type)) {
        const evaluatedTurns = (round.details?.turns || []).filter((turn) => turn.score != null);
        if (evaluatedTurns.length) items.push({ key: `interview-${round.round_type}`, round: ROUND_NAMES[round.round_type], evidence: `${evaluatedTurns.length} persisted interview turn(s) have evaluation scores.`, meaning: 'Scores are available for the evaluated turns in this interview phase.' });
      }
    }
    return items;
  }, [report]);
  const recommendations = useMemo(() => getStudentMockDriveImprovementPlan(report, insights), [report, insights]);
  const driveStatus = report?.status === 'completed' ? 'Completed' : report?.status === 'in_progress' ? 'In Progress' : 'Awaiting Evaluation';
  return <StudentModeLayout><style>{`@media print { @page { margin: 14mm; } body:has(.mock-drive-report) aside, body:has(.mock-drive-report) button[aria-label="Open menu"], .mock-drive-report .print-hidden { display:none !important; } .mock-drive-report { padding:0 !important; background:#fff !important; } .mock-drive-report article, .mock-drive-report section { break-inside:avoid; box-shadow:none !important; } }`}</style>
    <main className="mock-drive-report min-h-screen bg-slate-50 px-4 py-6 sm:px-6 lg:px-10 lg:py-8"><div className="mx-auto max-w-6xl space-y-6">
      <nav aria-label="Breadcrumb" className="text-sm text-slate-500 print-hidden"><Link to="/home" className="hover:text-blue-700">Student Dashboard</Link><span className="px-2">/</span><Link to="/mock-drive/results" className="hover:text-blue-700">Mock Drives</Link><span className="px-2">/</span><span className="text-slate-800">Performance Report</span></nav>
      <div className="flex flex-wrap items-start justify-between gap-4"><div><Link to="/mock-drive/results" className="mb-3 inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 hover:bg-white print-hidden"><ArrowLeft className="h-4 w-4" />Back to Results</Link><h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Mock Drive Performance Report</h1>{report && <><p className="mt-2 text-lg font-semibold text-slate-800">{report.company_name || 'Information unavailable'} · {report.target_role || 'Information unavailable'}</p><p className="mt-1 text-sm text-slate-500">Completed on: {formatDate(report.completed_at)}</p></>}</div><button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 print-hidden"><Download className="h-4 w-4" />Print / Save Report</button></div>
      {loading ? <p role="status" className={`${card} p-6 text-slate-600`}>Loading mock drive report…</p> : error ? <section role="alert" className={`${card} p-6 text-slate-700`}><h2 className="text-xl font-bold">Report unavailable</h2><p className="mt-2">{error}</p></section> : report && <>
        <div className="flex items-center gap-2"><span className={`rounded-full border px-3 py-1 text-xs font-semibold ${report.status === 'completed' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>{driveStatus}</span><span className="text-sm text-slate-600">Drive {report.mock_drive_id}</span></div>
        <section aria-labelledby="summary-title"><div className="mb-3 flex items-center gap-2"><Layers3 className="h-5 w-5 text-blue-700" /><h2 id="summary-title" className="text-lg font-bold text-slate-900">Performance Summary</h2></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat title="Rounds configured" value={rounds.length} note="Enabled for this drive" icon={Layers3} /><Stat title="Rounds completed" value={completed} note="Based on persisted round status" icon={Check} /><Stat title="Results available" value={results} note="Finalized evaluations" icon={FileQuestion} /><Stat title="Overall drive status" value={driveStatus} note="Persisted lifecycle status" icon={Gauge} /></div><div className="mt-4 rounded-xl border border-slate-200 bg-white p-4"><div className="flex justify-between gap-3 text-sm"><span className="font-medium text-slate-700">Round completion</span><span className="text-slate-600">{completed} of {rounds.length} complete</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${Math.round(completion)}% of configured rounds completed`}><div className="h-full rounded-full bg-blue-700" style={{ width: `${completion}%` }} /></div><p className="mt-2 text-xs text-slate-500">Completion follows round lifecycle status. Results count finalized evaluations. Different round score scales are not combined into an overall score.</p></div></section>
        <section className={`${card} p-5 sm:p-6`}><div className="flex items-center gap-2"><Target className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-bold text-slate-900">Key Insights</h2></div>{insights.length ? <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.map((item) => <article key={item.key} className="rounded-xl border border-blue-200 bg-blue-50/40 p-4"><p className="font-semibold text-slate-900">{item.topic || item.round}</p><p className="mt-1 text-xs font-medium text-slate-500">{item.round}{item.topic ? ` · ${item.topic}` : ''}</p><p className="mt-2 text-sm text-slate-700"><strong>Evidence:</strong> {item.evidence}</p><p className="mt-2 text-sm text-slate-600">{item.meaning}</p>{item.action && <p className="mt-2 text-sm text-slate-700"><strong>Recommended action:</strong> {item.action}</p>}</article>)}</div> : <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">Not enough evaluated evidence to generate insights yet.</p>}</section>
        <section aria-labelledby="rounds-title"><div className="mb-3 flex items-center gap-2"><BookOpenCheck className="h-5 w-5 text-blue-700" /><h2 id="rounds-title" className="text-lg font-bold text-slate-900">Round-by-round performance</h2></div><p className="mb-4 text-sm text-slate-500">Rounds are shown in this drive’s configured order.</p>{rounds.length ? <div className="space-y-3">{rounds.map((round, index) => <RoundCard key={`${round.round_type}-${index}`} round={round} index={index} />)}</div> : <p className={`${card} p-5 text-sm text-slate-600`}>No configured assessment rounds are available.</p>}</section>
        <section className={`${card} p-5 sm:p-6`}><div className="flex items-center gap-2"><Flag className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-bold text-slate-900">Improvement Plan</h2></div><p className="mt-1 text-sm text-slate-500">Recommendations based on persisted, evaluated evidence.</p>{recommendations.length ? <ol className="mt-4 space-y-3">{recommendations.map((item) => <li key={item.key} className="flex gap-3 text-sm text-slate-700"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-800"><ListChecks className="h-3.5 w-3.5" /></span><span><strong className="text-slate-900">{item.action}</strong><span className="mt-0.5 block text-xs text-slate-500">{item.round}{item.topic ? ` · ${item.topic}` : ''}</span></span></li>)}</ol> : <p className="mt-4 text-sm text-slate-600">No evidence-based recommendations are available yet.</p>}</section>
        <section className={`${card} p-5 sm:p-6`}><h2 className="text-lg font-bold text-slate-900">Competency Results</h2>{report.competency_scoring?.overall_score_status && report.competency_scoring.overall_score_status !== 'unavailable' ? <><p className="mt-2 text-sm text-slate-600">Competency score: {report.competency_scoring.overall_score ?? 'Unavailable'} / 100 ({report.competency_scoring.overall_score_status}) · evidence coverage {report.competency_scoring.evidence_coverage == null ? 'unavailable' : `${Math.round(report.competency_scoring.evidence_coverage * 100)}%`}.</p><ul className="mt-3 space-y-2">{report.competency_scoring.competencies.map((item) => <li key={item.competency_id} className="flex justify-between gap-3 rounded-lg bg-slate-50 p-3 text-sm"><span>{item.competency_name} · {item.status === 'assessed' ? `${item.evidence_count} evidence item(s)` : 'Not assessed'}</span><strong>{item.normalized_score == null ? 'Unavailable' : `${item.normalized_score}%`}</strong></li>)}</ul></> : <p className="mt-2 text-sm text-slate-600">Competency scoring is unavailable for this drive or its pinned blueprint.</p>}</section>
      </>}
      <p className="pb-3 text-center text-xs text-slate-500">Report data comes from persisted records for this mock drive.</p>
    </div></main>
  </StudentModeLayout>;
}
