import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { getPracticeRoundResult, getPracticeRoundReview } from '../services/practiceResultService';
import { startPractice } from '../services/sessionService';

const ROUND_LABELS = {
    aptitude: 'MCQ Round',
    mcq: 'MCQ Round',
    technical: 'Technical MCQ',
    combined: 'Combined MCQ',
    coding: 'Coding Challenge',
    interview: 'Interview Round',
};

const ROUND_COLORS = {
    aptitude: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', accent: 'bg-indigo-600' },
    mcq: { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200', accent: 'bg-indigo-600' },
    technical: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', accent: 'bg-blue-600' },
    combined: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', accent: 'bg-purple-600' },
    coding: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', accent: 'bg-emerald-600' },
    interview: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', accent: 'bg-amber-600' },
};

function getPercentageColor(pct) {
    if (pct >= 75) return 'text-emerald-600';
    if (pct >= 50) return 'text-indigo-600';
    return 'text-amber-600';
}

function getPercentageBadge(pct) {
    if (pct >= 75) return { label: 'Excellent', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
    if (pct >= 50) return { label: 'Good', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200' };
    return { label: 'Needs Practice', cls: 'bg-amber-50 text-amber-700 border-amber-200' };
}

export default function PracticeResultDashboard() {
    const { sessionId, roundId } = useParams();
    const navigate = useNavigate();
    
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [summary, setSummary] = useState(null);
    const [review, setReview] = useState(null);
    const [startingAgain, setStartingAgain] = useState(false);
    
    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                const [summaryData, reviewData] = await Promise.all([
                    getPracticeRoundResult(sessionId, roundId),
                    getPracticeRoundReview(sessionId, roundId),
                ]);
                setSummary(summaryData);
                setReview(reviewData);
            } catch (err) {
                console.error(err);
                setError(err?.response?.data?.detail || 'Failed to load result data.');
            } finally {
                setLoading(false);
            }
        };
        
        if (sessionId && roundId) {
            loadData();
        }
    }, [sessionId, roundId]);
    
    const handlePracticeAgain = async () => {
        setStartingAgain(true);
        try {
            // M2-E: Use the authoritative Practice flow (POST /practice/start).
            // The roundType from the completed summary is the correct backend round_type.
            const apiRoundType = summary?.round_type || 'aptitude';
            const practiceType = summary?.practice_type || null;
            await startPractice(apiRoundType, practiceType);

            // Restore practice config in localStorage for the assessment page
            const practiceTypeForConfig = practiceType || apiRoundType;
            const config = { practice_type: practiceTypeForConfig, subject: null };
            localStorage.setItem('edi5_practice_config', JSON.stringify(config));

            if (apiRoundType === 'coding') {
                navigate('/coding');
            } else if (apiRoundType === 'interview') {
                navigate('/resume-upload');
            } else {
                navigate('/aptitude');
            }
        } catch (err) {
            console.error('Failed to start practice session:', err);
            if (err.response?.status === 409) {
                alert(err.response.data?.detail || 'An active practice session is already in progress. Please complete it first.');
            } else {
                alert('Failed to start a new practice session.');
            }
        } finally {
            setStartingAgain(false);
        }
    };
    
    if (loading) {
        return (
            <StudentModeLayout>
                <div className="flex items-center justify-center min-h-[calc(100vh-80px)]">
                    <div className="text-center">
                        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-slate-500 text-sm font-semibold">Loading results...</p>
                    </div>
                </div>
            </StudentModeLayout>
        );
    }
    
    if (error) {
        return (
            <StudentModeLayout>
                <div className="flex items-center justify-center min-h-[calc(100vh-80px)] p-6">
                    <div className="bg-white border border-slate-200 rounded-3xl p-8 max-w-md w-full text-center shadow-sm">
                        <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl font-bold">⚠️</div>
                        <h2 className="text-xl font-bold text-slate-900 mb-2">Unable to Load Results</h2>
                        <p className="text-slate-500 text-xs mb-6 leading-relaxed">{error}</p>
                        <button
                            onClick={() => navigate('/analytics')}
                            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 rounded-xl text-xs uppercase tracking-wider transition-all shadow-sm cursor-pointer"
                        >
                            Return to Analytics
                        </button>
                    </div>
                </div>
            </StudentModeLayout>
        );
    }
    
    const roundType = summary?.round_type || 'aptitude';
    const colors = ROUND_COLORS[roundType] || ROUND_COLORS.aptitude;
    const badge = getPercentageBadge(summary?.percentage || 0);
    
    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-6 py-8">
                {/* Header */}
                <div className="mb-8 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
                    <div>
                        <Link to="/analytics" className="text-xs font-medium text-indigo-600 hover:text-indigo-800 mb-2 inline-flex items-center gap-1">
                            ← Back to Analytics
                        </Link>
                        <h1 className="text-3xl font-black text-slate-900 tracking-tight mt-1">
                            {ROUND_LABELS[roundType] || roundType} — Results
                        </h1>
                        <p className="text-slate-500 text-sm mt-1">
                            Completed {summary?.completed_at ? new Date(summary.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'recently'}
                        </p>
                    </div>
                    <div className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold ${badge.cls}`}>
                        {badge.label}
                    </div>
                </div>
                
                {/* Score Summary Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
                    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Score</span>
                        <span className={`text-3xl font-black ${getPercentageColor(summary?.percentage || 0)}`}>
                            {summary?.percentage || 0}%
                        </span>
                        <span className="text-xs text-slate-500 block mt-1">
                            {summary?.score} / {summary?.max_score}
                        </span>
                    </div>
                    
                    {summary?.correct_count !== undefined && (
                        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Correct</span>
                            <span className="text-3xl font-black text-emerald-600">{summary.correct_count}</span>
                            <span className="text-xs text-slate-500 block mt-1">out of {summary.max_score} questions</span>
                        </div>
                    )}
                    
                    {summary?.incorrect_count !== undefined && (
                        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Incorrect</span>
                            <span className="text-3xl font-black text-rose-600">{summary.incorrect_count}</span>
                            <span className="text-xs text-slate-500 block mt-1">{summary.skipped_count > 0 ? `+ ${summary.skipped_count} skipped` : 'answers'}</span>
                        </div>
                    )}
                    
                    {summary?.problems_solved !== undefined && (
                        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Problems Solved</span>
                            <span className="text-3xl font-black text-emerald-600">{summary.problems_solved}</span>
                            <span className="text-xs text-slate-500 block mt-1">of {summary.problems_attempted} attempted</span>
                        </div>
                    )}
                    
                    {summary?.average_final_score !== undefined && (
                        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Avg Score</span>
                            <span className="text-3xl font-black text-amber-600">{summary.average_final_score}</span>
                            <span className="text-xs text-slate-500 block mt-1">out of 10 ({summary.total_turns} turns)</span>
                        </div>
                    )}
                </div>
                
                {/* Detailed Review Section */}
                <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm mb-8">
                    <h2 className="text-lg font-bold text-slate-900 mb-6">
                        {roundType === 'interview' ? 'Turn-by-Turn Review' : roundType === 'coding' ? 'Problem-by-Problem Review' : 'Question-by-Question Review'}
                    </h2>
                    
                    <div className="space-y-4">
                        {review?.items?.map((item, idx) => (
                            <div key={idx} className="rounded-2xl border border-slate-100 bg-slate-50/50 p-5">
                                {/* Aptitude-style review */}
                                {item.options && (
                                    <>
                                        <div className="flex items-start justify-between mb-3">
                                            <div className="flex-1">
                                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider mr-2 ${item.is_correct ? 'bg-emerald-100 text-emerald-700' : item.selected_option ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-500'}`}>
                                                    {item.is_correct ? '✓ Correct' : item.selected_option ? '✗ Wrong' : '— Skipped'}
                                                </span>
                                                {item.topic && (
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">{item.topic}</span>
                                                )}
                                                {item.difficulty && (
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ml-1 ${item.difficulty === 'hard' ? 'bg-rose-50 text-rose-600' : item.difficulty === 'medium' ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'}`}>
                                                        {item.difficulty}
                                                    </span>
                                                )}
                                            </div>
                                            {item.response_time !== null && item.response_time !== undefined && (
                                                <span className="text-[10px] text-slate-400 font-medium">{item.response_time.toFixed(1)}s</span>
                                            )}
                                        </div>
                                        <h3 className="font-semibold text-sm text-slate-900 mb-3">Q{item.sequence}. {item.question_text}</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {Object.entries(item.options).map(([k, v]) => {
                                                const isSelected = item.selected_option === k;
                                                const isCorrect = item.correct_option === k;
                                                let cls = 'border-slate-200 bg-white';
                                                if (isSelected && item.is_correct) cls = 'border-emerald-300 bg-emerald-50';
                                                else if (isSelected && !item.is_correct) cls = 'border-rose-300 bg-rose-50';
                                                else if (isCorrect) cls = 'border-emerald-300 bg-emerald-50/50 border-dashed';
                                                
                                                return (
                                                    <div key={k} className={`p-3 rounded-xl border text-xs ${cls}`}>
                                                        <span className="font-bold mr-1.5">{k}.</span>
                                                        {v}
                                                        {isSelected && <span className="ml-2 text-[10px] font-bold">(Your answer)</span>}
                                                        {isCorrect && !isSelected && <span className="ml-2 text-[10px] font-bold text-emerald-600">(Correct)</span>}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </>
                                )}
                                
                                {/* Coding-style review */}
                                {item.problem_title && !item.options && (
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h3 className="font-semibold text-sm text-slate-900">
                                                #{item.sequence}. {item.problem_title}
                                            </h3>
                                            <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                                                {item.problem_difficulty && (
                                                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium ${item.problem_difficulty === 'hard' ? 'bg-rose-50 text-rose-600' : item.problem_difficulty === 'medium' ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'}`}>
                                                        {item.problem_difficulty}
                                                    </span>
                                                )}
                                                <span>{item.submission_count} submission{item.submission_count !== 1 ? 's' : ''}</span>
                                                {item.language && <span>• {item.language}</span>}
                                                {item.execution_time !== null && <span>• {item.execution_time.toFixed(2)}s</span>}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <span className={`text-2xl font-black ${item.best_score >= 1.0 ? 'text-emerald-600' : item.best_score > 0 ? 'text-amber-600' : 'text-rose-600'}`}>
                                                {Math.round(item.best_score * 100)}%
                                            </span>
                                            <span className={`block text-[10px] font-bold uppercase tracking-wider mt-0.5 ${item.best_status === 'accepted' ? 'text-emerald-600' : 'text-slate-500'}`}>
                                                {item.best_status}
                                            </span>
                                        </div>
                                    </div>
                                )}
                                
                                {/* Interview-style review */}
                                {item.candidate_response !== undefined && !item.options && !item.problem_title && (
                                    <div>
                                        <div className="flex items-start justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Turn {item.sequence}</span>
                                                {item.is_followup && <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-medium">Follow-up</span>}
                                                {item.question_difficulty && (
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${item.question_difficulty === 'hard' ? 'bg-rose-50 text-rose-600' : item.question_difficulty === 'medium' ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'}`}>
                                                        {item.question_difficulty}
                                                    </span>
                                                )}
                                            </div>
                                            {item.final_score !== null && (
                                                <span className={`text-lg font-black ${item.final_score >= 7 ? 'text-emerald-600' : item.final_score >= 4 ? 'text-amber-600' : 'text-rose-600'}`}>
                                                    {item.final_score}/10
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm font-semibold text-slate-900 mb-2">{item.question_text}</p>
                                        {item.candidate_response && (
                                            <div className="bg-white border border-slate-200 rounded-xl p-3 text-xs text-slate-700 leading-relaxed mt-2">
                                                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Your Response</span>
                                                {item.candidate_response}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                        
                        {(!review?.items || review.items.length === 0) && (
                            <div className="py-12 text-center text-xs text-slate-400 italic">
                                No detailed review data available for this round.
                            </div>
                        )}
                    </div>
                </div>
                
                {/* Actions */}
                <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                            <h2 className="text-lg font-bold text-slate-900">What's next?</h2>
                            <p className="text-sm text-slate-500">Practice again with a fresh session, or return to analytics.</p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <button
                                onClick={handlePracticeAgain}
                                disabled={startingAgain}
                                className={`rounded-xl ${colors.accent} px-6 py-3 text-sm font-semibold text-white transition hover:opacity-90 shadow-sm disabled:opacity-50`}
                            >
                                {startingAgain ? 'Starting...' : `Practice ${ROUND_LABELS[roundType] || 'Again'} →`}
                            </button>
                            <button
                                onClick={() => navigate('/analytics')}
                                className="rounded-xl bg-slate-100 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 shadow-sm"
                            >
                                Analytics Dashboard
                            </button>
                            <button
                                onClick={() => navigate('/practice')}
                                className="rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 shadow-sm"
                            >
                                Practice Overview
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </StudentModeLayout>
    );
}
