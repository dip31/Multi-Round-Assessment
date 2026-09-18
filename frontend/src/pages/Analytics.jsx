import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { getStudentAnalytics, getAnalytics } from '../services/reportService';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    BarChart,
    Bar,
    Cell,
} from 'recharts';

export default function Analytics() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const res = await getStudentAnalytics();
                setData(res);
            } catch (err) {
                console.warn('Student analytics error, attempting fallback:', err);
                try {
                    const fallback = await getAnalytics();
                    setData(fallback);
                } catch (fallbackErr) {
                    if (fallbackErr?.response?.status === 401) {
                        navigate('/login');
                        return;
                    }
                    setError(fallbackErr?.response?.data?.detail || 'Failed to load analytics');
                }
            } finally {
                setLoading(false);
            }
        };

        fetchAnalytics();
    }, [navigate]);

    if (loading) {
        return (
            <div className="bg-slate-50 text-slate-900 font-['Inter'] min-h-screen flex items-center justify-center antialiased">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-500 text-sm font-semibold">Loading student analytics...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-slate-50 text-slate-900 font-['Inter'] min-h-screen flex items-center justify-center p-6 antialiased">
                <div className="bg-white border border-slate-200 rounded-3xl p-8 max-w-md w-full text-center shadow-sm">
                    <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                        ⚠️
                    </div>
                    <h2 className="text-xl font-bold text-slate-900 mb-2">Unable to Load Analytics</h2>
                    <p className="text-slate-500 text-xs mb-6 leading-relaxed">{error}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all shadow-sm cursor-pointer"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    const overview = data?.overview || {};
    const summary = data?.summary || {};
    const trend = Array.isArray(data?.trend) ? data.trend : [];
    const subjects = Array.isArray(data?.subjects) ? data.subjects : [];
    const topics = Array.isArray(data?.topics) ? data.topics : [];
    const rounds = Array.isArray(data?.rounds) ? data.rounds : [];
    const difficulty = Array.isArray(data?.difficulty) ? data.difficulty : [];
    const coding = data?.coding || {};
    const interviews = data?.interviews || {};
    const strengths = Array.isArray(data?.strengths) ? data.strengths : [];
    const focusAreas = Array.isArray(data?.focus_areas) ? data.focus_areas : [];
    const recommendation = data?.recommendation;
    const consistency = data?.consistency || {};

    const hasAnyAttempts = (summary.questions_attempted || 0) > 0 || trend.length > 0;

    return (
        <div className="bg-slate-50 text-slate-900 font-['Inter'] antialiased min-h-screen">
            <Navbar position="sticky" />

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
                {/* Header Strip */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                                Student Performance Analytics
                            </h1>
                            <span className="text-[10px] font-bold bg-indigo-50 text-indigo-700 px-2.5 py-0.5 rounded-full border border-indigo-200 uppercase tracking-wider">
                                Real DB Data
                            </span>
                        </div>
                        <p className="text-xs text-slate-500 font-medium mt-1">
                            Comprehensive readiness evaluation across Aptitude, Technical, Coding, and Interview dimensions
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/dashboard')}
                            className="px-4 py-2 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-xs font-bold text-slate-700 shadow-2xs transition-all cursor-pointer"
                        >
                            ← Back to Dashboard
                        </button>
                    </div>
                </div>

                {/* 1. OVERALL READINESS SCORECARD */}
                <section className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
                        <div className="md:col-span-1 p-6 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white text-center shadow-md">
                            <span className="text-[11px] font-bold uppercase tracking-wider opacity-90 block mb-1">
                                Overall Placement Readiness
                            </span>
                            <div className="text-5xl font-black my-2 tracking-tight">
                                {overview.overall_readiness !== undefined ? `${overview.overall_readiness}%` : '0%'}
                            </div>
                            <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-white/20 backdrop-blur-xs mt-1">
                                {overview.readiness_tier || 'Foundational'}
                            </span>
                        </div>

                        <div className="md:col-span-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                                    Questions Attempted
                                </span>
                                <span className="text-2xl font-black text-slate-900">
                                    {summary.questions_attempted || 0}
                                </span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">Across all rounds</span>
                            </div>
                            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                                    Overall Accuracy
                                </span>
                                <span className="text-2xl font-black text-emerald-600">
                                    {summary.overall_accuracy !== undefined ? `${summary.overall_accuracy}%` : '0%'}
                                </span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">MCQ + Technical</span>
                            </div>
                            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                                    Coding Challenges
                                </span>
                                <span className="text-2xl font-black text-indigo-600">
                                    {coding.problems_solved || 0} Solved
                                </span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">
                                    Best: {coding.best_score || 0}%
                                </span>
                            </div>
                            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/70">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                                    Interview Average
                                </span>
                                <span className="text-2xl font-black text-violet-600">
                                    {interviews.avg_score !== undefined ? `${interviews.avg_score}%` : 'N/A'}
                                </span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">AI mock rounds</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* 2. CHRONOLOGICAL PERFORMANCE TREND */}
                <section className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 tracking-tight">
                                Chronological Progression Trend
                            </h2>
                            <p className="text-xs text-slate-500">Session-by-session performance trajectory</p>
                        </div>
                        <span className="text-xs text-slate-500 font-medium">
                            {trend.length} Historical Sessions
                        </span>
                    </div>

                    {trend.length > 0 ? (
                        <div className="h-64 w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={trend} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                    <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
                                    <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} unit="%" />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: '#ffffff',
                                            borderRadius: '12px',
                                            border: '1px solid #e2e8f0',
                                            fontSize: '12px',
                                            fontWeight: 'bold',
                                        }}
                                    />
                                    <Legend wrapperStyle={{ fontSize: '11px' }} />
                                    <Line
                                        type="monotone"
                                        dataKey="score"
                                        name="Score %"
                                        stroke="#4f46e5"
                                        strokeWidth={3}
                                        dot={{ r: 4, fill: '#4f46e5' }}
                                        activeDot={{ r: 6 }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div className="py-12 text-center text-xs text-slate-400 italic">
                            No historical sessions completed yet. Practice rounds will populate your progression chart.
                        </div>
                    )}
                </section>

                {/* 3. TECHNICAL SUBJECT PERFORMANCE (OS, CN, OOPS, DBMS, DSA) */}
                <section className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                    <div className="mb-6">
                        <h2 className="text-base font-bold text-slate-900 tracking-tight">
                            Core Technical Subjects Breakdown
                        </h2>
                        <p className="text-xs text-slate-500">
                            Evaluated against standard Computer Science placement subjects: OS, CN, OOPS, DBMS, and DSA
                        </p>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
                        <div className="lg:col-span-2 h-64">
                            {subjects.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={subjects} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                        <XAxis dataKey="subject" stroke="#64748b" fontSize={10} />
                                        <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} unit="%" />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: '#ffffff',
                                                borderRadius: '12px',
                                                border: '1px solid #e2e8f0',
                                                fontSize: '11px',
                                            }}
                                        />
                                        <Bar dataKey="score" name="Accuracy %" radius={[6, 6, 0, 0]}>
                                            {subjects.map((entry, index) => (
                                                <Cell
                                                    key={`cell-${index}`}
                                                    fill={entry.score >= 75 ? '#10b981' : entry.score >= 50 ? '#6366f1' : '#f59e0b'}
                                                />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full flex items-center justify-center text-xs text-slate-400 italic">
                                    No technical subject questions attempted yet.
                                </div>
                            )}
                        </div>

                        <div className="space-y-2">
                            {subjects.map((s) => (
                                <div
                                    key={s.subject}
                                    className="p-3 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
                                >
                                    <div>
                                        <h4 className="font-bold text-slate-900">{s.subject}</h4>
                                        <span className="text-[10px] text-slate-500">
                                            {s.correct || 0} / {s.attempted || 0} Correct
                                        </span>
                                    </div>
                                    <span
                                        className={`font-black text-sm ${
                                            (s.score || 0) >= 75
                                                ? 'text-emerald-600'
                                                : (s.score || 0) >= 50
                                                ? 'text-indigo-600'
                                                : 'text-amber-600'
                                        }`}
                                    >
                                        {s.score !== null ? `${s.score}%` : 'N/A'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* 4. PRACTICE ROUNDS & COMBINED ROUND SPLIT */}
                <section className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                    <div className="mb-6">
                        <h2 className="text-base font-bold text-slate-900 tracking-tight">
                            Practice Rounds & Assessment Breakdown
                        </h2>
                        <p className="text-xs text-slate-500">
                            Including MCQ Round, Technical Round, Combined Round (with 50/50 split), Coding, and Interview
                        </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
                        {rounds.map((r, idx) => (
                            <div key={idx} className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200 flex flex-col justify-between">
                                <div>
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                                        {r.label}
                                    </span>
                                    <span className="text-2xl font-black text-slate-900 block my-1">
                                        {r.best_score !== null && r.best_score !== undefined ? `${r.best_score}%` : '—'}
                                    </span>
                                    {r.sub_breakdown && (
                                        <div className="mt-2 pt-2 border-t border-slate-200 text-[10px] space-y-0.5 text-slate-600">
                                            <div className="flex justify-between">
                                                <span>Aptitude (50%):</span>
                                                <strong className="text-slate-900">{r.sub_breakdown.aptitude_score || 0}%</strong>
                                            </div>
                                            <div className="flex justify-between">
                                                <span>Technical (50%):</span>
                                                <strong className="text-slate-900">{r.sub_breakdown.technical_score || 0}%</strong>
                                            </div>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-3 text-[10px] text-slate-500 flex justify-between">
                                    <span>Attempts: {r.attempts || 0}</span>
                                    <span>Avg: {r.avg_score || 0}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>

                {/* 5. STRENGTHS, FOCUS AREAS & NEXT PRACTICE */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Strengths */}
                    <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-lg">💪</span>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Key Strengths
                            </h3>
                        </div>
                        {strengths.length > 0 ? (
                            <div className="space-y-2">
                                {strengths.map((str, idx) => (
                                    <div
                                        key={idx}
                                        className="p-3 rounded-2xl bg-emerald-50/70 border border-emerald-100 flex items-center justify-between text-xs"
                                    >
                                        <span className="font-bold text-emerald-950">{str.name}</span>
                                        <span className="font-black text-emerald-700">{str.score}%</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-400 italic p-3">Complete more practice rounds to identify dominant skills.</p>
                        )}
                    </div>

                    {/* Focus Areas */}
                    <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs">
                        <div className="flex items-center gap-2 mb-4">
                            <span className="text-lg">🎯</span>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Focus Areas / Weaknesses
                            </h3>
                        </div>
                        {focusAreas.length > 0 ? (
                            <div className="space-y-2">
                                {focusAreas.map((foc, idx) => (
                                    <div
                                        key={idx}
                                        className="p-3 rounded-2xl bg-amber-50/70 border border-amber-200/70 flex items-center justify-between text-xs"
                                    >
                                        <span className="font-bold text-amber-950">{foc.name}</span>
                                        <span className="font-black text-amber-700">{foc.score}%</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-400 italic p-3">No low-performing domains detected. Great consistency!</p>
                        )}
                    </div>

                    {/* Deterministic Next Practice Recommendation */}
                    <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs flex flex-col justify-between">
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <span className="text-lg">🚀</span>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    Recommended Next Practice
                                </h3>
                            </div>
                            <div className="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 text-xs">
                                <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-wider block mb-1">
                                    Algorithm Suggested Round
                                </span>
                                <h4 className="text-sm font-black text-indigo-950">
                                    {recommendation?.title || 'Technical Round — Operating Systems'}
                                </h4>
                                <p className="text-indigo-800/80 text-[11px] mt-1 leading-relaxed">
                                    {recommendation?.reason ||
                                        'Reinforce foundational technical concepts to boost your overall placement readiness.'}
                                </p>
                            </div>
                        </div>

                        <button
                            onClick={() => navigate('/dashboard')}
                            className="w-full mt-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
                        >
                            Launch Recommended Practice →
                        </button>
                    </div>
                </div>

                {/* 6. CONSISTENCY & DIFFICULTY ANALYTICS */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    {/* Consistency Summary */}
                    <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Score Consistency & Distribution
                        </h3>
                        <div className="grid grid-cols-2 gap-3 text-xs">
                            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200">
                                <span className="text-slate-500 block mb-1">Best Score</span>
                                <strong className="text-lg font-black text-emerald-600">
                                    {consistency.best_score ? `${consistency.best_score}%` : 'N/A'}
                                </strong>
                            </div>
                            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200">
                                <span className="text-slate-500 block mb-1">Average Score</span>
                                <strong className="text-lg font-black text-slate-900">
                                    {consistency.avg_score ? `${consistency.avg_score}%` : 'N/A'}
                                </strong>
                            </div>
                            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200">
                                <span className="text-slate-500 block mb-1">Lowest Score</span>
                                <strong className="text-lg font-black text-amber-600">
                                    {consistency.lowest_score ? `${consistency.lowest_score}%` : 'N/A'}
                                </strong>
                            </div>
                            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200">
                                <span className="text-slate-500 block mb-1">Latest Score</span>
                                <strong className="text-lg font-black text-indigo-600">
                                    {consistency.latest_score ? `${consistency.latest_score}%` : 'N/A'}
                                </strong>
                            </div>
                        </div>
                    </div>

                    {/* Difficulty Distribution */}
                    <div className="bg-white rounded-3xl p-6 border border-slate-200 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Difficulty Tier Performance
                        </h3>
                        <div className="space-y-3">
                            {difficulty.map((d) => (
                                <div key={d.level} className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-xs">
                                    <div className="flex items-center justify-between mb-1.5">
                                        <span className="font-bold text-slate-800 capitalize">{d.level} Questions</span>
                                        <span className="font-black text-indigo-600">
                                            {d.accuracy !== null ? `${d.accuracy}%` : 'N/A'}
                                        </span>
                                    </div>
                                    <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                                        <div
                                            className="bg-indigo-600 h-full rounded-full transition-all duration-500"
                                            style={{ width: `${d.accuracy || 0}%` }}
                                        ></div>
                                    </div>
                                    <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                                        <span>Attempted: {d.attempted}</span>
                                        <span>Correct: {d.correct}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
