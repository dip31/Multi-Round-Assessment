import { useMemo, useState, useEffect } from 'react';
import { getProblems, startRound, runCode, submitCode } from '../services/codingService';
import useAdvancedProctoring from '../hooks/useAdvancedProctoring';

export default function CodingEditor({ sessionId }) {
  const [problems, setProblems] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python');
  const [output, setOutput] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('problem');
  const [busyAction, setBusyAction] = useState('');

  // Proctoring — single ownership via shared hook
  const { startMonitoring, stopMonitoring } = useAdvancedProctoring(sessionId ?? null, null);

  useEffect(() => {
    startMonitoring?.();
    return () => stopMonitoring?.();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Tab-visibility tracking (lightweight, hook-independent)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) console.warn('[Proctoring] TAB_SWITCH detected');
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadProblems = async () => {
      setLoading(true);
      setError('');

      try {
        const started = await startRound();
        if (cancelled) return;
        setProblems(Array.isArray(started) ? started : []);
      } catch (startError) {
        try {
          const fallback = await getProblems();
          if (cancelled) return;
          setProblems(Array.isArray(fallback) ? fallback : []);
          if (!fallback || fallback.length === 0) {
            setError('No coding problems are available right now.');
          }
        } catch (fallbackError) {
          if (cancelled) return;
          setProblems([]);
          setError('Unable to load coding problems. Please return to the dashboard and try again.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadProblems();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedIndex >= problems.length) {
      setSelectedIndex(0);
    }
  }, [problems, selectedIndex]);

  const current = useMemo(() => problems[selectedIndex] || null, [problems, selectedIndex]);

  useEffect(() => {
    if (current && !code) {
      setCode('// Write your solution here\n');
    }
  }, [current, code]);

  const languageOptions = [
    { value: 'python', label: 'Python 3' },
    { value: 'javascript', label: 'JavaScript' },
    { value: 'java', label: 'Java' },
    { value: 'cpp', label: 'C++' },
  ];

  // Render a multiline text field without literal \n characters
  const renderMultiline = (text) => {
    if (!text) return null;
    return text.split('\n').map((line, i) => (
      <p key={i} className="leading-6">{line || '\u00A0'}</p>
    ));
  };

  const normalizeProblemText = (text) => {
    if (!text) return '';
    return String(text)
      .replace(/<[^>]+>/g, '')
      .replace(/\r\n/g, '\n')
      .trim();
  };

  const renderOutput = () => {
    if (!output) {
      return <p className="text-sm text-slate-400">Run your code to see evaluation output here.</p>;
    }

    const raw = output.raw;
    const isRunResult = raw && Array.isArray(raw.test_case_results);
    const isSubmitResult = raw && typeof raw.submission_id !== 'undefined';

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-100">{output.heading}</h3>
          {raw?.status && (
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${
              raw.status === 'accepted'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                : 'border-red-400/30 bg-red-400/10 text-red-300'
            }`}>
              {raw.status}
            </span>
          )}
        </div>

        {/* Aggregate summary line */}
        {raw && (
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
            {typeof raw.test_cases_passed !== 'undefined' && (
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Tests passed: <span className="font-semibold text-white">{raw.test_cases_passed} / {raw.total_test_cases}</span>
              </div>
            )}
            {typeof raw.score !== 'undefined' && raw.score !== null && (
              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                Score: <span className="font-semibold text-white">{Math.round((raw.score ?? 0) * 100)}%</span>
              </div>
            )}
            {isSubmitResult && (
              <div className="col-span-2 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-3 py-2 text-emerald-200">
                Submission ID: <span className="font-semibold">{raw.submission_id}</span>
              </div>
            )}
          </div>
        )}

        {/* Compiler/Error output sections */}
        {raw?.compile_output && (
          <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3">
            <div className="text-xs font-semibold text-red-300 mb-1">Compilation Error</div>
            <pre className="text-xs text-red-200 font-mono whitespace-pre-wrap overflow-auto">{raw.compile_output}</pre>
          </div>
        )}
        {raw?.stderr && (
          <div className="rounded-xl border border-orange-400/30 bg-orange-400/10 p-3">
            <div className="text-xs font-semibold text-orange-300 mb-1">Runtime Error (stderr)</div>
            <pre className="text-xs text-orange-200 font-mono whitespace-pre-wrap overflow-auto">{raw.stderr}</pre>
          </div>
        )}
        {raw?.message && (
          <div className="rounded-xl border border-yellow-400/30 bg-yellow-400/10 p-3">
            <div className="text-xs font-semibold text-yellow-300 mb-1">Judge0 Message</div>
            <pre className="text-xs text-yellow-200 font-mono whitespace-pre-wrap overflow-auto">{raw.message}</pre>
          </div>
        )}

        {/* Per-case results table — only for /run (CodingRunResponse has test_case_results) */}
        {isRunResult && raw.test_case_results.length > 0 && (
          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="w-full text-xs text-slate-200">
              <thead className="border-b border-white/10 bg-white/5 text-[11px] uppercase tracking-[0.2em] text-slate-400">
                <tr>
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Input</th>
                  <th className="px-3 py-2 text-left">Expected</th>
                  <th className="px-3 py-2 text-left">Actual</th>
                  <th className="px-3 py-2 text-left">Result</th>
                </tr>
              </thead>
              <tbody>
                {raw.test_case_results.map((tc, idx) => (
                  <tr key={idx} className={`border-b border-white/5 ${tc.passed ? 'bg-emerald-950/20' : 'bg-red-950/20'}`}>
                    <td className="px-3 py-2 text-slate-400">{idx + 1}</td>
                    <td className="max-w-[120px] truncate px-3 py-2 font-mono">{tc.input_data}</td>
                    <td className="max-w-[120px] truncate px-3 py-2 font-mono">{tc.expected_output}</td>
                    <td className="max-w-[120px] truncate px-3 py-2 font-mono">{tc.actual_output}</td>
                    <td className="px-3 py-2">
                      {tc.passed
                        ? <span className="text-emerald-400 font-semibold">✓ Pass</span>
                        : <span className="text-red-400 font-semibold">✗ Fail</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] rounded-3xl border border-white/10 bg-slate-950/80 p-8 text-slate-100 shadow-2xl shadow-cyan-950/20">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 rounded bg-white/10" />
          <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)_320px]">
            <div className="h-[70vh] rounded-2xl bg-white/5" />
            <div className="h-[70vh] rounded-2xl bg-white/5" />
            <div className="h-[70vh] rounded-2xl bg-white/5" />
          </div>
        </div>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="rounded-3xl border border-white/10 bg-slate-950/80 p-8 text-slate-100 shadow-2xl shadow-cyan-950/20">
        <h2 className="text-2xl font-semibold">Coding Round</h2>
        <p className="mt-3 text-sm text-slate-300">{error || 'No coding problems are available right now.'}</p>
      </div>
    );
  }

  const handleRun = async () => {
    setBusyAction('run');
    setOutput({ heading: 'Running visible test cases...', raw: null });
    try {
      const res = await runCode({ problem_id: current.id, code, language });
      setOutput({ heading: 'Run complete', raw: res });
    } catch (e) {
      setOutput({ heading: 'Run failed', raw: e.response?.data || { detail: 'Error running code' } });
    } finally {
      setBusyAction('');
    }
  };

  const handleSubmit = async () => {
    setBusyAction('submit');
    setOutput({ heading: 'Submitting solution...', raw: null });
    try {
      const res = await submitCode({ problem_id: current.id, code, language });
      setOutput({ heading: 'Submission complete', raw: res });
    } catch (e) {
      setOutput({ heading: 'Submission failed', raw: e.response?.data || { detail: 'Error submitting code' } });
    } finally {
      setBusyAction('');
    }
  };

  return (
    <div className="min-h-[calc(100vh-3rem)] rounded-3xl border border-white/10 bg-slate-950/90 text-slate-100 shadow-2xl shadow-cyan-950/20 backdrop-blur">
      <div className="flex flex-col gap-4 border-b border-white/10 px-6 py-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300/70">Coding Round</p>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-white">HackerRank-style workspace</h2>
          <p className="mt-1 text-sm text-slate-400">Select a problem, write code, run visible tests, and submit from the same screen.</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Language</label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/20"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value} className="bg-slate-900">
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleRun}
            disabled={busyAction === 'run' || busyAction === 'submit'}
            className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyAction === 'run' ? 'Running...' : 'Run'}
          </button>
          <button
            onClick={handleSubmit}
            disabled={busyAction === 'run' || busyAction === 'submit'}
            className="rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busyAction === 'submit' ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>

      <div className="grid min-h-[calc(100vh-11rem)] grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)_320px]">
        <aside className="border-b border-white/10 lg:border-b-0 lg:border-r lg:border-white/10">
          <div className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Problems</h3>
              <span className="rounded-full bg-white/5 px-2 py-1 text-[11px] text-slate-300">{problems.length}</span>
            </div>
            <div className="space-y-2">
              {problems.map((problem, index) => {
                const isActive = index === selectedIndex;
                return (
                  <button
                    key={problem.id}
                    onClick={() => setSelectedIndex(index)}
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                      isActive
                        ? 'border-cyan-400/40 bg-cyan-400/10 text-white shadow-lg shadow-cyan-950/20'
                        : 'border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold leading-tight">{problem.title}</span>
                      <span className="rounded-full bg-white/10 px-2 py-1 text-[10px] uppercase tracking-[0.25em] text-slate-300">
                        {problem.difficulty || 'easy'}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">
                      {normalizeProblemText(problem.description)}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <main className="border-b border-white/10 lg:border-b-0 lg:border-r lg:border-white/10">
          <div className="flex h-full flex-col">
            <div className="border-b border-white/10 px-6 py-4">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-xl font-bold text-white">{current.title}</h3>
                <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.25em] text-emerald-200">
                  {current.difficulty || 'easy'}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-400">
                {(current.tags || []).map((tag) => (
                  <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid flex-1 gap-0 xl:grid-cols-[1fr_1.15fr]">
              <section className="border-b border-white/10 px-6 py-5 xl:border-b-0 xl:border-r xl:border-white/10">
                <div className="mb-5 flex items-center justify-between">
                  <h4 className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-400">Problem Statement</h4>
                  <button
                    onClick={() => setActiveTab(activeTab === 'problem' ? 'editor' : 'problem')}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300 xl:hidden"
                  >
                    {activeTab === 'problem' ? 'Show Editor' : 'Show Problem'}
                  </button>
                </div>

                <div className={`${activeTab === 'problem' ? 'block' : 'hidden'} space-y-5 xl:block`}>
                  <div className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
                    {renderMultiline(normalizeProblemText(current.description))}
                  </div>

                  {current.input_format ? (
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <h5 className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Input Format</h5>
                      <div className="text-sm leading-6 text-slate-200">
                        {renderMultiline(normalizeProblemText(current.input_format))}
                      </div>
                    </div>
                  ) : null}

                  {current.output_format ? (
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <h5 className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Output Format</h5>
                      <div className="text-sm leading-6 text-slate-200">
                        {renderMultiline(normalizeProblemText(current.output_format))}
                      </div>
                    </div>
                  ) : null}

                  {current.constraints ? (
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <h5 className="mb-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Constraints</h5>
                      <div className="text-sm leading-6 text-slate-200">
                        {renderMultiline(normalizeProblemText(current.constraints))}
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4">
                    <h5 className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-cyan-200">Visible Test Cases</h5>
                    <div className="space-y-3">
                      {current.test_cases.map((testCase, index) => (
                        <div key={testCase.id ?? `${current.id}-${index}`} className="rounded-xl border border-white/10 bg-slate-950/50 p-3">
                          <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.2em] text-slate-400">
                            <span>Case {index + 1}</span>
                            <span>{testCase.is_hidden ? 'Hidden' : 'Visible'}</span>
                          </div>
                          <div className="space-y-2 text-xs leading-6 text-slate-200">
                            <div>
                              <span className="text-slate-500 uppercase tracking-[0.15em]">Input:</span>
                              <pre className="mt-1 overflow-auto rounded bg-slate-950/60 px-2 py-1 font-mono">
                                {normalizeProblemText(testCase.input_data)}
                              </pre>
                            </div>
                            <div>
                              <span className="text-slate-500 uppercase tracking-[0.15em]">Expected:</span>
                              <pre className="mt-1 overflow-auto rounded bg-slate-950/60 px-2 py-1 font-mono">
                                {normalizeProblemText(testCase.expected_output)}
                              </pre>
                            </div>
                            {testCase.explanation ? (
                              <p className="text-slate-400 italic">{testCase.explanation}</p>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>

              <section className={`${activeTab === 'editor' ? 'block' : 'hidden'} flex flex-col xl:block`}>
                <div className="border-b border-white/10 px-6 py-4 xl:hidden">
                  <h4 className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-400">Editor</h4>
                </div>

                <div className="flex h-full flex-col px-4 py-4 sm:px-6">
                  <div className="mb-3 flex items-center justify-between gap-3 xl:hidden">
                    <button
                      onClick={() => setActiveTab('problem')}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] text-slate-300"
                    >
                      Problem
                    </button>
                    <button
                      onClick={() => setActiveTab('editor')}
                      className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-[11px] text-cyan-100"
                    >
                      Editor
                    </button>
                  </div>

                  <div className="flex items-center justify-between rounded-t-2xl border border-b-0 border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300">
                    <span className="font-semibold uppercase tracking-[0.25em] text-slate-400">Code</span>
                    <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-emerald-200">
                      Ready to run
                    </span>
                  </div>
                  <textarea
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    placeholder="Write your solution here..."
                    className="min-h-[360px] flex-1 rounded-b-2xl border border-white/10 bg-slate-950 px-4 py-4 font-mono text-sm leading-7 text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-400/40 focus:ring-2 focus:ring-cyan-400/20"
                    spellCheck={false}
                  />

                  <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <h4 className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Console</h4>
                        <span className="text-[11px] text-slate-500">Run / Submit output</span>
                      </div>
                      {renderOutput()}
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <h4 className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Quick Actions</h4>
                        <span className="text-[11px] text-slate-500">{busyAction ? 'Processing...' : 'Idle'}</span>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                        <button
                          onClick={handleRun}
                          disabled={busyAction === 'run' || busyAction === 'submit'}
                          className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {busyAction === 'run' ? 'Running...' : 'Run visible tests'}
                        </button>
                        <button
                          onClick={handleSubmit}
                          disabled={busyAction === 'run' || busyAction === 'submit'}
                          className="rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {busyAction === 'submit' ? 'Submitting...' : 'Submit solution'}
                        </button>
                      </div>
                      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs leading-6 text-slate-300">
                        Pick a problem on the left, edit your code in the center, then run visible tests before submitting.
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </main>

        <aside className="p-5">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Session</h3>
            <div className="mt-4 grid gap-3 text-sm text-slate-200">
              <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2">
                <span className="block text-[11px] uppercase tracking-[0.2em] text-slate-500">Current Problem</span>
                <span className="mt-1 block font-semibold">{current.title}</span>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2">
                <span className="block text-[11px] uppercase tracking-[0.2em] text-slate-500">Language</span>
                <span className="mt-1 block font-semibold capitalize">{language}</span>
              </div>
              <div className="rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2">
                <span className="block text-[11px] uppercase tracking-[0.2em] text-slate-500">Mode</span>
                <span className="mt-1 block font-semibold">HackerRank-style workspace</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
