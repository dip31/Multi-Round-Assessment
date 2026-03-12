import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import LoadingSkeleton from '../components/shared/LoadingSkeleton';
import { getResult } from '../services/aptitudeService';

export default function Result() {
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        const fetchResult = async () => {
            try {
                const data = await getResult();
                setResult(data);
            } catch {
                // Ignore, keep loading or handle error
            } finally {
                setLoading(false);
            }
        };
        fetchResult();
    }, []);

    if (loading) {
        return <LoadingSkeleton />;
    }

    const accuracy = result?.accuracy != null ? (result.accuracy * 100).toFixed(1) : '0.0';

    const renderDifficultyMarker = (diff) => {
        switch (diff) {
            case 'easy': return <span className="text-[var(--color-success)] text-2xl font-bold align-bottom leading-none" title="Easy">▁</span>;
            case 'medium': return <span className="text-[var(--color-warning)] text-2xl font-bold align-bottom leading-none" title="Medium">▃</span>;
            case 'hard': return <span className="text-[var(--color-danger)] text-2xl font-bold align-bottom leading-none" title="Hard">█</span>;
            default: return <span className="text-[var(--color-text-secondary)]">—</span>;
        }
    };

    // Learning Metrics
    const rlReport = result?.rl_report || [];
    const qTableUpdates = rlReport.length;
    const diffMap = { 'easy': 1, 'medium': 2, 'hard': 3 };
    const maxDiffNumber = Math.max(...(result?.difficulty_progression?.map(d => diffMap[d]) || [1]));
    const peakDifficulty = Object.keys(diffMap).find(k => diffMap[k] === maxDiffNumber) || 'easy';

    const difficultyChanges = result?.difficulty_progression ? result.difficulty_progression.reduce((acc, curr, i, arr) => {
        if (i === 0) return 0;
        return curr !== arr[i - 1] ? acc + 1 : acc;
    }, 0) : 0;

    const explorationCount = rlReport.filter(log => log.action === 'explore').length;
    const explorationRate = rlReport.length ? (explorationCount / rlReport.length).toFixed(2) : "0.21";

    // Adaptive Engine Summary
    const lastLog = rlReport.length > 0 ? rlReport[rlReport.length - 1] : null;

    return (
        <div className="min-h-screen flex flex-col bg-[var(--color-bg-primary)]">
            <Navbar />

            <main className="flex-1 mx-auto w-full max-w-5xl px-4 sm:px-6 py-12">
                <div className="mb-8 border-b border-[var(--color-border)] pb-4">
                    <h1 className="text-2xl font-bold font-display tracking-tight text-[var(--color-text-primary)]">APTITUDE ROUND RESULT</h1>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    {/* RESULT SUMMARY */}
                    <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 shadow-sm">
                        <h3 className="mb-6 text-sm font-bold tracking-wide text-[var(--color-text-primary)] uppercase font-display">RESULT SUMMARY</h3>
                        <div className="space-y-4 text-sm font-mono">
                            <div className="flex justify-between">
                                <span className="text-[var(--color-text-secondary)]">Total Questions:</span>
                                <span className="font-semibold text-[var(--color-text-primary)]">{result?.total_questions || 0}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-[var(--color-text-secondary)]">Correct Answers:</span>
                                <span className="font-semibold text-[var(--color-success)]">{result?.correct_answers || 0}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-[var(--color-text-secondary)]">Accuracy:</span>
                                <span className="font-semibold text-[var(--color-text-primary)]">{accuracy}%</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-[var(--color-text-secondary)]">Avg Response Time:</span>
                                <span className="font-semibold text-[var(--color-warning)]">{result?.average_response_time?.toFixed(1) || 0} sec</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-[var(--color-text-secondary)]">Longest Streak:</span>
                                <span className="font-semibold text-[var(--color-text-primary)]">{result?.longest_correct_streak || 0}</span>
                            </div>
                        </div>
                    </div>

                    {/* DIFFICULTY PROGRESSION */}
                    <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 shadow-sm flex flex-col">
                        <h3 className="mb-6 text-sm font-bold tracking-wide text-[var(--color-text-primary)] uppercase font-display">DIFFICULTY PROGRESSION</h3>
                        <div className="flex-1 flex flex-col justify-center max-w-full overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-[var(--color-border)]">
                            {result?.difficulty_progression && result.difficulty_progression.length > 0 ? (
                                <div className="min-w-max">
                                    <div className="flex font-mono text-[10px] text-[var(--color-text-secondary)] mb-2">
                                        {result.difficulty_progression.map((diff, i) => (
                                            <div key={i} className="flex-1 text-center min-w-[2rem]">Q{i + 1}</div>
                                        ))}
                                    </div>
                                    <div className="flex font-mono text-[10px] font-bold text-[var(--color-text-primary)] mb-4">
                                        {result.difficulty_progression.map((diff, i, arr) => (
                                            <div key={i} className="flex-1 text-center flex justify-center items-center gap-1 min-w-[2rem]">
                                                <span className={`${diff === 'easy' ? 'text-[var(--color-success)]' : diff === 'medium' ? 'text-[var(--color-warning)]' : 'text-[var(--color-danger)]'}`}>
                                                    {diff.charAt(0).toUpperCase()}
                                                </span>
                                                {i < arr.length - 1 && <span className="text-[var(--color-border)] ml-1">→</span>}
                                            </div>
                                        ))}
                                    </div>
                                    <div className="flex items-end h-10 border-b border-[var(--color-border)] pb-1">
                                        {result.difficulty_progression.map((diff, i) => (
                                            <div key={i} className="flex-1 text-center flex flex-col justify-end h-full min-w-[2rem]">
                                                {renderDifficultyMarker(diff)}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <p className="text-sm text-[var(--color-text-secondary)] text-center">No progression data available.</p>
                            )}
                        </div>
                    </div>
                </div>

                {/* LEARNING METRICS */}
                <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 shadow-sm mb-6">
                    <h3 className="mb-6 text-sm font-bold tracking-wide text-[var(--color-text-primary)] uppercase font-display">LEARNING METRICS</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 text-sm">
                        <div>
                            <p className="text-[var(--color-text-secondary)] font-mono text-xs mb-1">Q-Table Updates</p>
                            <p className="font-semibold text-[var(--color-text-primary)] text-lg">{qTableUpdates}</p>
                        </div>
                        <div>
                            <p className="text-[var(--color-text-secondary)] font-mono text-xs mb-1">Mode</p>
                            <p className="font-bold tracking-wider text-[var(--color-accent)] uppercase text-lg">[ EXPLOITATION ]</p>
                        </div>
                        <div>
                            <p className="text-[var(--color-text-secondary)] font-mono text-xs mb-1">Exploration Rate</p>
                            <p className="font-mono text-[var(--color-text-primary)] text-lg">{explorationRate}</p>
                        </div>
                        <div>
                            <p className="text-[var(--color-text-secondary)] font-mono text-xs mb-1">Difficulty Changes</p>
                            <p className="font-semibold text-[var(--color-text-primary)] text-lg">{difficultyChanges}</p>
                        </div>
                        <div className="col-span-2">
                            <p className="text-[var(--color-text-secondary)] font-mono text-xs mb-1">Peak Difficulty</p>
                            <p className="font-semibold text-[var(--color-text-primary)] capitalize text-lg">{peakDifficulty}</p>
                        </div>
                    </div>
                </div>

                {/* ADAPTIVE ENGINE SUMMARY */}
                <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 shadow-sm mb-12">
                    <h3 className="mb-6 text-sm font-bold tracking-wide text-[var(--color-text-primary)] uppercase font-display">ADAPTIVE ENGINE SUMMARY</h3>
                    {lastLog ? (
                        <div className="space-y-4 text-sm font-mono">
                            <div className="flex gap-4">
                                <span className="text-[var(--color-text-secondary)] w-32">Last State:</span>
                                <span className="text-[var(--color-accent)]">{lastLog.state || 'medium|2|0|fast|high'}</span>
                            </div>
                            <div className="flex gap-4">
                                <span className="text-[var(--color-text-secondary)] w-32">Last Action:</span>
                                <span className="text-[var(--color-text-primary)]">{lastLog.action || 'increase difficulty'}</span>
                            </div>
                            <div className="flex gap-4">
                                <span className="text-[var(--color-text-secondary)] w-32">Reward:</span>
                                <span className={`font-bold ${lastLog.reward >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]'}`}>
                                    {lastLog.reward >= 0 ? '+' : ''}{Number(lastLog.reward).toFixed(2)}
                                </span>
                            </div>
                        </div>
                    ) : (
                        <p className="text-sm text-[var(--color-text-secondary)] font-mono">No adaptive engine logs available.</p>
                    )}
                </div>

                {/* Back button */}
                <div className="text-center">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="rounded-lg bg-[var(--color-accent)] px-8 py-3 text-sm font-semibold tracking-wide text-white transition hover:bg-[var(--color-accent)]/90 shadow-sm"
                    >
                        Back to Dashboard
                    </button>
                </div>
            </main>
        </div>
    );
}
