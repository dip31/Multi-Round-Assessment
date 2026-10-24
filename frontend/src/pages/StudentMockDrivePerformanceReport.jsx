import { createElement, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, BookOpenCheck, Check, ChevronDown, CircleAlert, Download, FileQuestion, Flag, Gauge, Layers3, ListChecks, Target, Timer } from 'lucide-react';
import StudentModeLayout from '../components/StudentModeLayout';
import { getAptitudeStats, getCodingStats, getRoundSummary, getScenario, getScenarioInsights, REPORT_SCENARIOS } from '../utils/studentMockDriveReportPreview';

const card = 'rounded-2xl border border-slate-200 bg-white shadow-sm';
const label = 'text-xs font-semibold uppercase tracking-wide text-slate-500';

function Stat({ title, value, note, icon: Icon }) {
  return <div className={`${card} p-4 sm:p-5`}><div className="flex items-start justify-between gap-2"><p className={label}>{title}</p>{createElement(Icon, { 'aria-hidden': true, className: 'h-4 w-4 text-blue-600' })}</div><p className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{value}</p><p className="mt-1 text-xs text-slate-500">{note}</p></div>;
}

function StatusPill({ round }) {
  const text = round.status === 'completed' && round.evaluated ? 'Completed - evaluated' : round.status === 'evaluation-pending' ? 'Attempted - results pending' : round.status === 'completed' ? 'Completed - evaluation unavailable' : 'Pending';
  const tone = round.status === 'completed' && round.evaluated ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : round.status === 'evaluation-pending' || round.status === 'completed' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-slate-200 bg-slate-100 text-slate-700';
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${tone}`}>{text}</span>;
}

function AptitudeReport({ round }) {
  const [filter, setFilter] = useState('all');
  const [openQuestion, setOpenQuestion] = useState(null);
  const stats = getAptitudeStats(round);
  const questions = round.questions.filter((question) => filter === 'all' || question.state === filter);
  const strongest = [...stats.topicStats].filter((topic) => topic.accuracy !== null).sort((a, b) => b.accuracy - a.accuracy)[0];
  const focus = [...stats.topicStats].filter((topic) => topic.accuracy !== null).sort((a, b) => a.accuracy - b.accuracy)[0];
  return <div className="mt-5 space-y-5">
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {[['Total questions', stats.total], ['Answered', stats.answered], ['Correct', stats.correct], ['Incorrect', stats.incorrect], ['Unanswered', stats.unanswered], ['Accuracy¹', stats.accuracy === null ? 'N/A' : `${Math.round(stats.accuracy)}%`]].map(([name, value]) => <div key={name} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{name}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}
    </div>
    <div className="grid gap-3 md:grid-cols-2">
      {stats.topicStats.map((topic) => <div key={topic.name} className="rounded-xl border border-slate-200 p-4"><div className="flex justify-between gap-2 text-sm"><span className="font-medium text-slate-800">{topic.name}</span><span className="text-slate-600">{topic.accuracy === null ? 'N/A' : `${topic.correct}/${topic.answered} · ${Math.round(topic.accuracy)}%`}</span></div><div className="mt-3 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-600" style={{ width: `${topic.accuracy || 0}%` }} /></div></div>)}
    </div>
    {stats.averageSeconds !== null && <p className="flex items-center gap-2 text-sm text-slate-600"><Timer className="h-4 w-4" />Average recorded question time: <strong className="text-slate-900">{Math.round(stats.averageSeconds)} seconds</strong> across {round.questions.filter((question) => Number.isFinite(question.seconds)).length} timed questions.</p>}
    {strongest && focus && strongest.name !== focus.name && <p className="text-sm text-slate-600">Strongest topic: <strong className="text-slate-900">{strongest.name}</strong>. Focus area: <strong className="text-slate-900">{focus.name}</strong>. Accuracy uses answered and graded questions only; unanswered questions are excluded.</p>}
    <section aria-label="Aptitude question review">
      <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold text-slate-900">Question review <span className="font-normal text-slate-500">(illustrative preview questions)</span></h3><label className="flex items-center gap-2 text-sm text-slate-600 print:hidden">Filter questions<select value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"><option value="all">All questions</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option><option value="unanswered">Unanswered</option></select></label></div>
      <div className="mt-3 space-y-2">{questions.map((question) => <div key={question.number} className="rounded-xl border border-slate-200">
        <button type="button" aria-expanded={openQuestion === question.number} onClick={() => setOpenQuestion(openQuestion === question.number ? null : question.number)} className="flex w-full items-center gap-3 p-4 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">
          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-bold ${question.state === 'correct' ? 'bg-emerald-100 text-emerald-800' : question.state === 'incorrect' ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-700'}`}>{question.state === 'correct' ? <Check className="h-4 w-4" /> : question.number}</span>
          <span className="min-w-0 flex-1"><span className="block font-medium text-slate-900">Q{question.number}. {question.text}</span><span className="mt-1 block text-xs text-slate-500">{question.topic} · {question.difficulty} · {question.state}</span></span><ChevronDown className={`h-4 w-4 text-slate-500 transition-transform ${openQuestion === question.number ? 'rotate-180' : ''}`} />
        </button>
        <div className={`${openQuestion === question.number ? 'block' : 'hidden print:block'} grid gap-2 border-t border-slate-100 bg-slate-50 px-4 py-3 text-sm sm:grid-cols-2`}><p><span className="text-slate-500">Your answer:</span> {question.selected ?? 'No answer selected'}</p>{question.correct && <p><span className="text-slate-500">Correct answer:</span> {question.correct}</p>}<p className="sm:col-span-2"><span className="text-slate-500">Illustrative explanation:</span> {question.explanation}</p>{Number.isFinite(question.seconds) && <p><span className="text-slate-500">Time:</span> {question.seconds}s</p>}</div>
      </div>)}{questions.length === 0 && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No questions match this filter.</p>}</div>
      <p className="mt-3 text-xs text-slate-500">¹ Accuracy = correct ÷ answered. Unanswered items are excluded from the denominator.</p>
    </section>
  </div>;
}

function CodingReport({ round }) {
  const [open, setOpen] = useState(null);
  const stats = getCodingStats(round);
  return <div className="mt-5 space-y-4">
    {round.problems.length ? <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{[['Assigned', stats.assigned], ['Attempted', stats.attempted], ['Solved', stats.solved], ['Tests passed', stats.passed], ['Tests failed', stats.failed], ['Pass rate²', stats.passRate === null ? 'N/A' : `${Math.round(stats.passRate)}%`]].map(([name, value]) => <div key={name} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{name}</p><p className="mt-1 font-semibold text-slate-900">{value}</p></div>)}</div>
      <p className="text-xs text-slate-500">Pass rate uses test cases with a reported outcome ({stats.passed} passed, {stats.failed} failed of {stats.total} recorded). It is not an overall coding score. Runtime, memory, language, and submission history are not included in this preview.</p>
      <div className="space-y-2">{round.problems.map((problem) => <div key={problem.title} className="rounded-xl border border-slate-200">
        <button type="button" aria-expanded={open === problem.title} onClick={() => setOpen(open === problem.title ? null : problem.title)} className="flex w-full items-center gap-3 p-4 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"><span className={`grid h-9 w-9 place-items-center rounded-xl ${problem.solved ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}><ListChecks className="h-4 w-4" /></span><span className="min-w-0 flex-1"><span className="block font-semibold text-slate-900">{problem.title}</span><span className="text-xs text-slate-500">{problem.difficulty} · {problem.attempted ? problem.solved ? 'Solved' : 'Partially solved' : 'Not attempted'}</span></span><span className="text-sm text-slate-600">{problem.passed}/{problem.total} passed</span><ChevronDown className={`h-4 w-4 text-slate-500 ${open === problem.title ? 'rotate-180' : ''}`} /></button>
        <div className={`${open === problem.title ? 'block' : 'hidden print:block'} space-y-2 border-t border-slate-100 bg-slate-50 px-4 py-4 text-sm`}><p>{problem.description}</p><p className="text-slate-600">Test cases: <strong>{problem.passed} passed</strong>, <strong>{problem.failed} failed</strong> of {problem.total} recorded sample cases. Hidden test-case details are not shown.</p><p><span className="text-slate-500">Recommended practice:</span> {problem.practice}</p><p className="text-slate-500">Submission/evaluation: {problem.attempted ? 'Attempt recorded; evaluated sample outcomes shown above.' : 'Not attempted in this preview.'}</p></div>
      </div>)}</div>
    </> : <Unavailable text={round.status === 'evaluation-pending' ? 'Results not available yet. This attempted round is awaiting evaluation.' : 'No evaluated problem details are available in this preview.'} />}
  </div>;
}

function InterviewReport({ round }) {
  if (!round.evaluated) return <Unavailable text="This round is configured but has not been evaluated. No scores or feedback are shown." />;
  const strengths = (round.rubric || []).filter((item) => item.outOf > 0 && item.score / item.outOf >= 0.8);
  const improvements = (round.rubric || []).filter((item) => item.outOf > 0 && item.score / item.outOf < 0.8);
  return <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
    <section><h3 className="font-semibold text-slate-900">{round.name} rubric <span className="font-normal text-slate-500">(illustrative)</span></h3><div className="mt-3 grid gap-2 sm:grid-cols-2">{strengths.length > 0 && <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Strengths</p><p className="mt-1 text-sm text-slate-700">{strengths.map((item) => item.name).join(', ')}</p></div>}{improvements.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Areas to develop</p><p className="mt-1 text-sm text-slate-700">{improvements.map((item) => item.name).join(', ')}</p></div>}</div><div className="mt-3 space-y-3">{round.rubric?.length ? round.rubric.map((item) => <div key={item.name} className="rounded-xl border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><span className="font-medium text-slate-800">{item.name}</span><span className="rounded-full bg-blue-50 px-2.5 py-1 text-sm font-semibold text-blue-800">{item.score}/{item.outOf}</span></div><p className="mt-2 text-sm text-slate-600">{item.note}</p></div>) : <Unavailable text="No interview rubric scores are included in this scenario." />}</div></section>
    <section><h3 className="font-semibold text-slate-900">Question-level feedback <span className="font-normal text-slate-500">(illustrative)</span></h3><div className="mt-3 space-y-3">{round.questions?.length ? round.questions.map((item, index) => <div key={item.prompt} className="rounded-xl bg-slate-50 p-4"><p className="text-sm font-medium text-slate-900">Q{index + 1}. {item.prompt}</p><p className="mt-2 text-sm text-slate-600">{item.feedback}</p></div>) : <Unavailable text="No question-level interview feedback is included in this scenario." />}</div></section>
  </div>;
}

function Unavailable({ text }) {
  return <div className="mt-5 flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600"><CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />{text}</div>;
}

function RoundPanel({ round, index, open, onToggle }) {
  const roundSummary = round.type === 'aptitude'
    ? (() => { const stats = getAptitudeStats(round); return `${stats.total} questions · ${stats.correct} correct · ${stats.accuracy === null ? 'accuracy unavailable' : `${Math.round(stats.accuracy)}% accuracy`}`; })()
    : round.type === 'coding'
      ? (() => { const stats = getCodingStats(round); return `${stats.assigned} problems · ${stats.attempted} attempted · ${stats.solved} solved · ${stats.evaluated} test cases evaluated`; })()
      : round.evaluated ? `${round.rubric?.length || 0} rubric dimensions evaluated` : 'No evaluated result is available';
  return <article className={`${card} overflow-hidden`}>
    <button type="button" aria-expanded={open} onClick={onToggle} className="flex w-full items-center gap-4 p-4 text-left sm:p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-sm font-bold text-blue-800">{String(index + 1).padStart(2, '0')}</span>
      <span className="min-w-0 flex-1"><span className="block font-semibold text-slate-900">{round.name}</span><span className="mt-1 block text-sm text-slate-500">{round.type === 'aptitude' ? 'Aptitude assessment' : round.type === 'coding' ? 'Coding assessment' : `${round.name} · interview evaluation`}</span><span className="mt-1 block text-xs text-slate-600">{roundSummary}</span></span>
      <StatusPill round={round} /><ChevronDown aria-hidden="true" className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
    </button>
    <div className={`${open ? 'block' : 'hidden print:block'} border-t border-slate-200 px-4 pb-5 sm:px-5`}>{round.evaluated ? round.type === 'aptitude' ? <AptitudeReport round={round} /> : round.type === 'coding' ? <CodingReport round={round} /> : <InterviewReport round={round} /> : round.type === 'coding' ? <CodingReport round={round} /> : <InterviewReport round={round} />}</div>
  </article>;
}

export default function StudentMockDrivePerformanceReport() {
  const [scenarioId, setScenarioId] = useState(REPORT_SCENARIOS[0].id);
  const [openRounds, setOpenRounds] = useState({ aptitude: true });
  const scenario = getScenario(scenarioId);
  const summary = useMemo(() => getRoundSummary(scenario.rounds), [scenario]);
  const insights = useMemo(() => getScenarioInsights(scenario), [scenario]);
  const recommendations = useMemo(() => {
    const seen = new Set();
    return insights.filter((item) => {
      const key = item.action.trim().toLocaleLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [insights]);
  const selectScenario = (event) => { setScenarioId(event.target.value); setOpenRounds({}); };

  return <StudentModeLayout>
    <style>{`@media print { @page { margin: 14mm; } body:has(.mock-drive-report-preview) { background: #fff !important; } body:has(.mock-drive-report-preview) aside, body:has(.mock-drive-report-preview) button[aria-label="Open menu"] { display: none !important; } .mock-drive-report-preview { padding: 0 !important; background: #fff !important; } .mock-drive-report-preview section, .mock-drive-report-preview article { break-inside: avoid; box-shadow: none !important; } }`}</style>
    <div className="mock-drive-report-preview min-h-screen bg-slate-50 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <nav aria-label="Breadcrumb" className="text-sm text-slate-500 print:hidden"><Link to="/home" className="hover:text-blue-700">Student Dashboard</Link><span className="px-2">/</span><Link to="/mock-drive/results" className="hover:text-blue-700">Mock Drives</Link><span className="px-2">/</span><span className="text-slate-800">Performance Report</span></nav>
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
          <div><Link to="/mock-drive/results" className="mb-4 inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 hover:bg-white hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 print:hidden"><ArrowLeft className="h-4 w-4" />Back to Mock Drives</Link>
            <div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">Preview data · not connected to live results</span><span className={`rounded-full border px-3 py-1 text-xs font-semibold ${summary.status === 'Completed' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>{summary.status}</span></div>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Mock Drive Performance Report</h1>
            <p className="mt-2 text-lg font-semibold text-slate-800">{scenario.company} <span className="font-normal text-slate-400">·</span> {scenario.role}</p>
            <p className="mt-1 text-sm text-slate-500">{scenario.drive} · {scenario.date} <span className="text-slate-400">(fictional preview date)</span></p>
          </div>
          <button type="button" onClick={() => window.print()} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 print:hidden"><Download className="h-4 w-4" />Print / save report</button>
        </div>

        <section className={`${card} flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5 print:hidden`} aria-label="Preview scenario selector"><div><h2 className="font-semibold text-slate-900">Explore report scenarios</h2><p className="mt-1 text-sm text-slate-500">Fictional preview only. Changing this selection does not modify a drive.</p></div><label className="flex flex-col gap-1.5 text-sm font-medium text-slate-700 sm:min-w-72">Preview drive configuration<select value={scenarioId} onChange={selectScenario} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600">{REPORT_SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></section>

        <section aria-labelledby="summary-heading"><div className="mb-3 flex items-center gap-2"><Layers3 className="h-5 w-5 text-blue-700" /><h2 id="summary-heading" className="text-lg font-bold text-slate-900">Performance summary</h2></div><div className="grid grid-cols-2 gap-3 lg:grid-cols-4"><Stat title="Rounds configured" value={summary.configured} note="Included in this drive" icon={Layers3} /><Stat title="Rounds completed" value={summary.completed} note="Marked complete" icon={Check} /><Stat title="Results available" value={summary.results} note="Evaluated rounds" icon={FileQuestion} /><Stat title="Overall drive status" value={summary.status} note="Based on this preview scenario" icon={Gauge} /></div><div className="mt-4 rounded-xl border border-slate-200 bg-white p-4"><div className="flex items-center justify-between gap-3 text-sm"><span className="font-medium text-slate-700">Round completion</span><span className="text-slate-600">{summary.completed} of {summary.configured} complete</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${Math.round(summary.completionPercent)}% of configured rounds completed`}><div className="h-full rounded-full bg-blue-700" style={{ width: `${summary.completionPercent}%` }} /></div><p className="mt-2 text-xs text-slate-500">Completion tracks round status only; results count only evaluated rounds. Scores from different round types are not combined.</p></div></section>

        <section aria-labelledby="insights-heading" className={`${card} p-5 sm:p-6`}><div className="flex items-center gap-2"><Target className="h-5 w-5 text-blue-700" /><h2 id="insights-heading" className="text-lg font-bold text-slate-900">Key insights</h2></div>{insights.length ? <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.map((insight) => <article key={`${insight.round}-${insight.title}`} className={`rounded-xl border p-4 ${insight.tone === 'opportunity' || insight.tone === 'amber' ? 'border-amber-200 bg-amber-50/50' : insight.tone === 'strength' ? 'border-emerald-200 bg-emerald-50/50' : 'border-blue-200 bg-blue-50/40'}`}><p className="font-semibold text-slate-900">{insight.title}</p><p className="mt-1 text-xs font-medium text-slate-500">{insight.round}{insight.topic ? ` | ${insight.topic}` : ''}</p><p className="mt-2 text-sm text-slate-700"><strong>Evidence:</strong> {insight.evidence}</p>{insight.why && <p className="mt-2 text-sm text-slate-600"><strong>Why it matters:</strong> {insight.why}</p>}<p className="mt-2 text-sm text-slate-700"><strong>Recommended action:</strong> {insight.action}</p></article>)}</div> : <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">There is not enough evaluated response data in this scenario to generate reliable performance insights yet. Pending rounds are excluded.</p>}</section>

        <section aria-labelledby="rounds-heading"><div className="mb-3 flex items-center gap-2"><BookOpenCheck className="h-5 w-5 text-blue-700" /><h2 id="rounds-heading" className="text-lg font-bold text-slate-900">Round-by-round performance</h2></div><p className="mb-4 text-sm text-slate-500">Only rounds configured for this preview drive are shown.</p><div className="space-y-3">{scenario.rounds.map((round, index) => <RoundPanel key={`${scenarioId}-${round.id}`} round={round} index={index} open={Boolean(openRounds[round.id])} onToggle={() => setOpenRounds((current) => ({ ...current, [round.id]: !current[round.id] }))} />)}</div></section>

        <section className={`${card} p-5 sm:p-6`}><div className="flex items-center gap-2"><Flag className="h-5 w-5 text-blue-700" /><h2 className="text-lg font-bold text-slate-900">Improvement plan</h2></div><p className="mt-1 text-sm text-slate-500">Next steps based only on evidence available in this preview scenario.</p>{recommendations.length ? <ol className="mt-4 space-y-3">{recommendations.map((item, index) => <li key={item.action} className="flex gap-3 text-sm text-slate-700"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-800">{index + 1}</span><span><span className="block font-medium text-slate-900">{item.action}</span><span className="mt-0.5 block text-xs text-slate-500">{item.round}{item.topic ? ` | ${item.topic}` : ''}</span></span></li>)}</ol> : <Unavailable text="No evaluated findings are available to support a specific practice recommendation in this scenario." />}</section>

        <div className="flex justify-end print:hidden"><button type="button" onClick={() => window.print()} className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"><Download className="h-4 w-4" />Print / save report</button></div>

        <p className="pb-3 text-center text-xs text-slate-500">All companies, dates, questions, scores and feedback on this page are fictional preview data. No live student records are shown.</p>
      </div>
    </div>
  </StudentModeLayout>;
}
