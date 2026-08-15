import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

/**
 * CodingResultPage — dedicated result page for the coding round.
 * Fetches per-problem submission data and renders a summary.
 * Route: /coding/result
 */
export default function CodingResultPage() {
  const navigate = useNavigate();
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get('/coding/results');
        setSubmissions(Array.isArray(res.data) ? res.data : []);
      } catch (e) {
        // Fallback: try to pull from localStorage if API not available
        const stored = localStorage.getItem('coding_submissions');
        if (stored) {
          try { setSubmissions(JSON.parse(stored)); } catch (_) {}
        } else {
          setError(e.response?.data?.detail || 'Could not load coding results.');
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const overallScore = submissions.length
    ? submissions.reduce((sum, s) => sum + (s.score ?? 0), 0) / submissions.length
    : 0;

  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-emerald-400';
    if (score >= 0.5) return 'text-amber-400';
    return 'text-red-400';
  };

  const getStatusBadge = (status) => {
    const map = {
      accepted: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
      wrong_answer: 'border-red-400/30 bg-red-400/10 text-red-300',
      runtime_error: 'border-orange-400/30 bg-orange-400/10 text-orange-300',
      time_limit_exceeded: 'border-yellow-400/30 bg-yellow-400/10 text-yellow-300',
      compilation_error: 'border-purple-400/30 bg-purple-400/10 text-purple-300',
    };
    return map[status] ?? 'border-white/10 bg-white/5 text-slate-300';
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-cyan-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950 px-4 py-10 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl space-y-8">

        {/* Header */}
        <div className="text-center">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-300/70">Coding Round Complete</p>
          <h1 className="mt-2 text-4xl font-black tracking-tight">Your Results</h1>
        </div>

        {/* Overall score card */}
        <div className="rounded-3xl border border-white/10 bg-white/5 p-8 text-center">
          <p className="text-sm uppercase tracking-[0.25em] text-slate-400">Overall Score</p>
          <p className={`mt-2 text-6xl font-black ${getScoreColor(overallScore)}`}>
            {Math.round(overallScore * 100)}%
          </p>
          <p className="mt-2 text-sm text-slate-400">
            {submissions.length} problem{submissions.length !== 1 ? 's' : ''} attempted
          </p>
        </div>

        {/* Error state */}
        {error && (
          <div className="rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Per-problem breakdown */}
        {submissions.length > 0 ? (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-400">Problem Breakdown</h2>
            {submissions.map((sub, idx) => (
              <div
                key={sub.submission_id ?? idx}
                className="rounded-2xl border border-white/10 bg-white/5 p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <p className="font-semibold text-white">{sub.title ?? `Problem ${idx + 1}`}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Language: <span className="capitalize text-slate-300">{sub.language ?? '—'}</span>
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${getStatusBadge(sub.status)}`}>
                      {sub.status?.replace(/_/g, ' ') ?? 'unknown'}
                    </span>
                    <span className={`text-2xl font-black ${getScoreColor(sub.score ?? 0)}`}>
                      {Math.round((sub.score ?? 0) * 100)}%
                    </span>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs text-slate-300">
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="uppercase tracking-[0.15em] text-slate-500">Tests Passed</p>
                    <p className="mt-1 font-semibold text-white">
                      {sub.test_cases_passed ?? '—'} / {sub.total_test_cases ?? '—'}
                    </p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="uppercase tracking-[0.15em] text-slate-500">Exec Time</p>
                    <p className="mt-1 font-semibold text-white">
                      {sub.execution_time != null ? `${sub.execution_time.toFixed(2)}s` : '—'}
                    </p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="uppercase tracking-[0.15em] text-slate-500">Submission ID</p>
                    <p className="mt-1 font-semibold text-white">{sub.submission_id ?? '—'}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
                    <p className="uppercase tracking-[0.15em] text-slate-500">Submitted At</p>
                    <p className="mt-1 font-semibold text-white">
                      {sub.submitted_at
                        ? new Date(sub.submitted_at).toLocaleTimeString()
                        : '—'}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : !error ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center text-sm text-slate-400">
            No submissions found for this round.
          </div>
        ) : null}

        {/* Actions */}
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
          >
            Back to Dashboard
          </button>
          <button
            onClick={() => navigate('/interview')}
            className="flex-1 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-500 px-6 py-4 text-sm font-semibold text-white transition hover:opacity-90"
          >
            Continue to Interview Round →
          </button>
        </div>

      </div>
    </div>
  );
}
