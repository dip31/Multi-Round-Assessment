import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { getPracticeRoundResult } from '../services/practiceResultService';
import api from '../services/api';

const ROUND_LABELS = {
    aptitude: 'MCQ Round',
    mcq: 'MCQ Round',
    technical: 'Technical MCQ',
    combined: 'Combined MCQ',
    coding: 'Coding Challenge',
    interview: 'Interview Round',
};

const ROUND_ICONS = {
    aptitude: '📝',
    mcq: '📝',
    technical: '💻',
    combined: '📚',
    coding: '⌨️',
    interview: '🎤',
};

function getPercentageColor(pct) {
    if (pct >= 75) return 'text-emerald-600';
    if (pct >= 50) return 'text-indigo-600';
    return 'text-amber-600';
}

function getPerformanceMessage(pct, roundType) {
    if (pct >= 75) {
        return roundType === 'interview' 
            ? "Outstanding performance! You're interview ready." 
            : "Excellent work! You've mastered this round.";
    }
    if (pct >= 50) {
        return 'Good effort! Keep practicing to improve further.';
    }
    return 'Keep going! Practice makes perfect.';
}

export default function PracticeSummary() {
    const { sessionId, roundId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [summary, setSummary] = useState(null);
    const [isInterviewRound, setIsInterviewRound] = useState(false);
    const [interviewId, setInterviewId] = useState(null);
    
    useEffect(() => {
        const loadData = async () => {
            try {
                setLoading(true);
                
                // Check if this is an interview round by trying to get interview data
                try {
                    const interviewData = await api.get(`/interview/session/${sessionId}/status`);
                    if (interviewData.data && interviewData.data.status === 'completed') {
                        setIsInterviewRound(true);
                        setInterviewId(sessionId);
                        // Create a summary object from interview data
                        setSummary({
                            round_type: 'interview',
                            percentage: interviewData.data.average_score * 10, // Convert 0-10 scale to percentage
                            score: Math.round(interviewData.data.average_score * 10),
                            max_score: 100,
                            total_turns: interviewData.data.total_questions || 0,
                            average_final_score: interviewData.data.average_score,
                            completed_at: interviewData.data.end_time,
                        });
                        setLoading(false);
                        return;
                    }
                } catch (interviewErr) {
                    // Not an interview round, proceed with normal practice round
                }
                
                // Load regular practice round data
                const summaryData = await getPracticeRoundResult(sessionId, roundId);
                setSummary(summaryData);
            } catch (err) {
                console.error(err);
                setError(err?.response?.data?.detail || 'Failed to load result summary.');
            } finally {
                setLoading(false);
            }
        };
        
        if (sessionId && roundId) {
            loadData();
        } else if (sessionId) {
            // Try loading as interview
            loadData();
        } else {
            setError('Invalid session or round ID');
            setLoading(false);
        }
    }, [sessionId, roundId]);
    
    const handleViewDetailedResult = () => {
        if (isInterviewRound) {
            navigate(`/interview/report/${interviewId}`);
        } else {
            navigate(`/practice/result/${sessionId}/${roundId}`);
        }
    };
    
    if (loading) {
        return (
            <StudentModeLayout>
                <div className="flex items-center justify-center min-h-[calc(100vh-80px)]">
                    <div className="text-center">
                        <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-slate-500 text-base font-semibold">Loading your results...</p>
                    </div>
                </div>
            </StudentModeLayout>
        );
    }
    
    if (error || !summary) {
        return (
            <StudentModeLayout>
                <div className="flex items-center justify-center min-h-[calc(100vh-80px)] p-6">
                    <div className="bg-white border border-slate-200 rounded-3xl p-10 max-w-lg w-full text-center shadow-lg">
                        <div className="w-16 h-16 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl">
                            ⚠️
                        </div>
                        <h2 className="text-2xl font-bold text-slate-900 mb-3">Unable to Load Results</h2>
                        <p className="text-slate-500 text-sm mb-8 leading-relaxed">{error || 'Unknown error occurred'}</p>
                        <button
                            onClick={() => navigate('/practice')}
                            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl text-sm uppercase tracking-wider transition-all shadow-sm"
                        >
                            Back to Practice
                        </button>
                    </div>
                </div>
            </StudentModeLayout>
        );
    }
    
    const roundType = summary?.round_type || 'aptitude';
    const percentage = summary?.percentage || 0;
    const performanceMessage = getPerformanceMessage(percentage, roundType);
    
    return (
        <StudentModeLayout>
            <div className="max-w-4xl mx-auto px-6 py-12">
                {/* Success Animation */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-24 h-24 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-full mb-6 animate-bounce shadow-xl">
                        <span className="text-5xl">✓</span>
                    </div>
                    <h1 className="text-4xl font-black text-slate-900 tracking-tight mb-3">
                        Assessment Complete!
                    </h1>
                    <p className="text-slate-600 text-lg">
                        {performanceMessage}
                    </p>
                </div>
                
                {/* Score Card */}
                <div className="bg-gradient-to-br from-white to-slate-50 border-2 border-slate-200 rounded-3xl p-10 mb-8 shadow-xl">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <span className="text-4xl">{ROUND_ICONS[roundType] || '📝'}</span>
                            <div>
                                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
                                    {ROUND_LABELS[roundType] || roundType}
                                </h2>
                                <p className="text-xs text-slate-400 mt-0.5">
                                    Completed {summary?.completed_at 
                                        ? new Date(summary.completed_at).toLocaleString('en-US', { 
                                            month: 'short', 
                                            day: 'numeric', 
                                            hour: '2-digit', 
                                            minute: '2-digit' 
                                        }) 
                                        : 'just now'}
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    {/* Large Score Display */}
                    <div className="text-center py-8 border-t border-b border-slate-200 my-6">
                        <p className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-3">Your Score</p>
                        <p className={`text-7xl font-black ${getPercentageColor(percentage)} mb-2`}>
                            {Math.round(percentage)}%
                        </p>
                        <p className="text-slate-500 text-base">
                            {summary?.score} out of {summary?.max_score} {roundType === 'coding' ? 'points' : 'questions'}
                        </p>
                    </div>
                    
                    {/* Quick Stats Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6">
                        {summary?.correct_count !== undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-emerald-600">{summary.correct_count}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Correct</p>
                            </div>
                        )}
                        
                        {summary?.incorrect_count !== undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-rose-600">{summary.incorrect_count}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Incorrect</p>
                            </div>
                        )}
                        
                        {summary?.problems_solved !== undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-indigo-600">{summary.problems_solved}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Solved</p>
                            </div>
                        )}
                        
                        {summary?.problems_attempted !== undefined && summary.problems_solved === undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-indigo-600">{summary.problems_attempted}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Attempted</p>
                            </div>
                        )}
                        
                        {summary?.total_turns !== undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-amber-600">{summary.total_turns}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Turns</p>
                            </div>
                        )}
                        
                        {summary?.average_final_score !== undefined && (
                            <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                                <p className="text-2xl font-black text-purple-600">{summary.average_final_score}</p>
                                <p className="text-xs text-slate-500 mt-1 font-medium">Avg Score</p>
                            </div>
                        )}
                    </div>
                </div>
                
                {/* Action Buttons */}
                <div className="space-y-4">
                    <button
                        onClick={handleViewDetailedResult}
                        className="w-full bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 text-white font-bold py-5 rounded-2xl text-base uppercase tracking-wider transition-all shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                    >
                        View Detailed Results →
                    </button>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <button
                            onClick={() => navigate('/practice')}
                            className="w-full bg-white hover:bg-slate-50 border-2 border-slate-300 text-slate-700 font-bold py-4 rounded-xl text-sm uppercase tracking-wider transition-all shadow-sm"
                        >
                            Practice Again
                        </button>
                        <button
                            onClick={() => navigate('/analytics')}
                            className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-4 rounded-xl text-sm uppercase tracking-wider transition-all shadow-sm"
                        >
                            View Analytics
                        </button>
                    </div>
                </div>
            </div>
        </StudentModeLayout>
    );
}
