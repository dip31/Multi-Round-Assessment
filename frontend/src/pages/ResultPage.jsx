import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { getResult } from '../services/aptitudeService';
import ScoreCards from '../components/result-dashboard/ScoreCards';
import ProgressionChart from '../components/result-dashboard/ProgressionChart';
import PerformanceChart from '../components/result-dashboard/PerformanceChart';
import ResponseTimeChart from '../components/result-dashboard/ResponseTimeChart';
import ImprovementInsights from '../components/result-dashboard/ImprovementInsights';

const difficultyOrder = {
    easy: 1,
    medium: 2,
    hard: 3,
};

const readinessMap = [
    { min: 75, label: 'Interview Ready', tone: 'border-emerald-500/30 bg-emerald-50 text-emerald-700' },
    { min: 55, label: 'Needs Practice', tone: 'border-amber-500/30 bg-amber-50 text-amber-700' },
    { min: 0, label: 'Foundational Work Needed', tone: 'border-rose-500/30 bg-rose-50 text-rose-700' },
];

function formatSeconds(value) {
    return `${Number(value || 0).toFixed(1)}s`;
}

function getReadiness(accuracy) {
    return readinessMap.find((item) => accuracy >= item.min) || readinessMap[readinessMap.length - 1];
}

function getResponseTimeFill(value) {
    if (value < 5) return '#10b981';
    if (value <= 15) return '#3b82f6';
    return '#ef4444';
}

function buildSkeleton() {
    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <Navbar />
            <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
                <div className="mb-8 space-y-3">
                    <div className="h-8 w-72 animate-pulse rounded-lg bg-slate-200" />
                    <div className="h-4 w-96 animate-pulse rounded-lg bg-slate-200" />
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    {Array.from({ length: 5 }).map((_, index) => (
                        <div key={index} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                            <div className="h-3 w-24 animate-pulse rounded-lg bg-slate-200" />
                            <div className="mt-5 h-9 w-28 animate-pulse rounded-lg bg-slate-200" />
                            <div className="mt-4 h-4 w-40 animate-pulse rounded-lg bg-slate-200" />
                        </div>
                    ))}
                </div>

                <div className="mt-6 grid gap-6 lg:grid-cols-2">
                    <div className="lg:col-span-2 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                        <div className="h-6 w-56 animate-pulse rounded-lg bg-slate-200" />
                        <div className="mt-5 h-[300px] animate-pulse rounded-2xl bg-slate-100" />
                    </div>
                    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                        <div className="h-6 w-48 animate-pulse rounded-lg bg-slate-200" />
                        <div className="mt-5 h-[280px] animate-pulse rounded-2xl bg-slate-100" />
                    </div>
                    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                        <div className="h-6 w-40 animate-pulse rounded-lg bg-slate-200" />
                        <div className="mt-5 h-[280px] animate-pulse rounded-2xl bg-slate-100" />
                    </div>
                    <div className="lg:col-span-2 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                        <div className="h-6 w-52 animate-pulse rounded-lg bg-slate-200" />
                        <div className="mt-5 h-[180px] animate-pulse rounded-2xl bg-slate-100" />
                    </div>
                </div>
            </main>
        </div>
    );
}

function buildErrorState(navigate) {
    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <Navbar />
            <main className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-3xl items-center justify-center px-4 py-10 sm:px-6">
                <div className="w-full rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-sm">
                    <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full border border-slate-200 bg-slate-100 text-2xl text-slate-500">
                        !
                    </div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900">No results found</h1>
                    <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-slate-600">
                        Complete the aptitude assessment to see your results.
                    </p>
                    <button
                        onClick={() => navigate('/aptitude')}
                        className="mt-8 rounded-full bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 shadow-sm"
                    >
                        Go to aptitude
                    </button>
                </div>
            </main>
        </div>
    );
}

export default function ResultPage() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [userName, setUserName] = useState('Candidate');

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        if (!storedUser) return;

        try {
            const parsed = JSON.parse(storedUser);
            setUserName(parsed.full_name || parsed.name || parsed.username || 'Candidate');
        } catch {
            setUserName('Candidate');
        }
    }, []);

    useEffect(() => {
        const loadResult = async () => {
            try {
                const response = await getResult();
                setData(response);
            } catch (err) {
                setError(err?.response?.data?.detail || 'Unable to load aptitude results');
            } finally {
                setLoading(false);
            }
        };

        loadResult();
    }, []);

    const transformed = useMemo(() => {
        if (!data) {
            return null;
        }

        const progression = Array.isArray(data.progression) ? data.progression : [];
        const difficultyStats = data.difficulty_stats || { easy: { correct: 0, total: 0 }, medium: { correct: 0, total: 0 }, hard: { correct: 0, total: 0 } };
        const responseTimes = Array.isArray(data.response_times) ? data.response_times : [];
        const topicStats = Array.isArray(data.topic_stats) ? data.topic_stats : [];

        const progressionData = progression.map((item) => ({
            questionLabel: `Q${item.question}`,
            difficultyValue: difficultyOrder[item.difficulty] || 2,
            performanceValue: item.correct ? 1 : 0,
            difficulty: item.difficulty,
            correct: item.correct,
        }));

        const performanceData = ['easy', 'medium', 'hard'].map((key) => {
            const bucket = difficultyStats[key] || { correct: 0, total: 0 };
            const total = bucket.total || 0;
            const correct = bucket.correct || 0;
            return {
                label: key.charAt(0).toUpperCase() + key.slice(1),
                correct,
                incorrect: Math.max(total - correct, 0),
                total,
            };
        });

        const responseTimeData = responseTimes.map((item) => ({
            questionLabel: `Q${item.question}`,
            question: item.question,
            time: Number(item.time || 0),
            fill: getResponseTimeFill(Number(item.time || 0)),
        }));

        return {
            progressionData,
            performanceData,
            responseTimeData,
            topicStats,
            difficultyStats,
        };
    }, [data]);

    if (loading) {
        return buildSkeleton();
    }

    if (error || !data || !transformed) {
        return buildErrorState(navigate);
    }

    const readiness = getReadiness(data.accuracy || 0);
    const scoreCards = [
        {
            label: 'Score',
            value: `${Math.round(data.score || 0)}`,
            subtext: `Out of ${data.total_questions || 0} questions`,
            badge: `${Math.round(data.percentile || 0)}th`,
            badgeClassName: 'border-sky-500/30 bg-sky-50 text-sky-700',
        },
        {
            label: 'Accuracy',
            value: `${Number(data.accuracy || 0).toFixed(1)}%`,
            subtext: 'Correct answers across the completed session',
            badge: readiness.label,
            badgeClassName: readiness.tone,
        },
        {
            label: 'Avg Response Time',
            value: formatSeconds(data.avg_response_time),
            subtext: 'Mean time per question',
            badge: data.avg_response_time < 5 ? 'Fast' : data.avg_response_time <= 15 ? 'Balanced' : 'Slow',
            badgeClassName: data.avg_response_time < 5 ? 'border-emerald-500/30 bg-emerald-50 text-emerald-700' : data.avg_response_time <= 15 ? 'border-sky-500/30 bg-sky-50 text-sky-700' : 'border-rose-500/30 bg-rose-50 text-rose-700',
        },
        {
            label: 'Questions Attempted',
            value: `${data.total_questions || 0}`,
            subtext: data.has_multiple_rounds ? 'Combined round summary available' : 'Single aptitude round summary',
            badge: data.has_multiple_rounds ? 'Multi-round' : 'Single round',
            badgeClassName: 'border-violet-500/30 bg-violet-50 text-violet-700',
        },
        {
            label: 'Percentile',
            value: `${Number(data.percentile || 0).toFixed(1)}%`,
            subtext: 'Compared against other completed aptitude sessions',
            badge: data.percentile >= 75 ? 'Top tier' : data.percentile >= 50 ? 'Solid' : 'Needs lift',
            badgeClassName: data.percentile >= 75 ? 'border-emerald-500/30 bg-emerald-50 text-emerald-700' : data.percentile >= 50 ? 'border-sky-500/30 bg-sky-50 text-sky-700' : 'border-amber-500/30 bg-amber-50 text-amber-700',
        },
    ];

    const fallbackInsights = [
        'Performance drops with higher difficulty',
        'Response time increases with difficulty',
    ];

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter']">
            <Navbar
                rightContent={
                    <button onClick={() => navigate('/profile')} className="flex items-center gap-2 transition-opacity hover:opacity-80">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-50 border border-indigo-200 text-sm font-bold text-indigo-700">
                            {userName?.charAt(0) || 'C'}
                        </div>
                    </button>
                }
            />

            <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
                <header className="mb-8 flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.24em] text-indigo-600">Performance Analytics</p>
                        <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">Practice Result Dashboard</h1>
                        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                            Adaptive difficulty is analyzed here as a performance story, not a static quiz score. The progression chart shows how the system responded to your answers in real time.
                        </p>
                    </div>
                    <div className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold ${readiness.tone}`}>
                        {readiness.label}
                    </div>
                </header>

                <ScoreCards cards={scoreCards} />

                <section className="mt-6 grid gap-6 lg:grid-cols-2">
                    <div className="lg:col-span-2">
                        <ProgressionChart data={transformed.progressionData} />
                    </div>
                    <PerformanceChart data={transformed.performanceData} />
                    <ResponseTimeChart data={transformed.responseTimeData} />
                    <div className="lg:col-span-2">
                        <ImprovementInsights topicStats={transformed.topicStats} fallbackInsights={fallbackInsights} />
                    </div>
                </section>

                <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900">Next action</h2>
                            <p className="text-sm text-slate-500">Move to another round, review the summary, or retry the assessment flow.</p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <button
                                onClick={() => navigate('/dashboard')}
                                className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 shadow-sm"
                            >
                                Retake Test
                            </button>
                            <button
                                onClick={() => navigate('/dashboard')}
                                className="rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 shadow-sm"
                            >
                                Go to Dashboard
                            </button>
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}