import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getReport } from '../services/interviewService';
import { Toast } from '../components/Toast';
import Navbar from '../components/Navbar';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function InterviewReport() {
    const { interviewId } = useParams();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState(null);
    const [expandedTurns, setExpandedTurns] = useState({});

    const navigate = useNavigate();

    useEffect(() => {
        const fetchReport = async () => {
            try {
                const data = await getReport(interviewId || localStorage.getItem('interview_id'));
                setReport(data);
            } catch (error) {
                setToast({ type: 'error', message: 'Failed to load report' });
            } finally {
                setLoading(false);
            }
        };
        fetchReport();
    }, [interviewId]);

    const toggleExpand = (turnNum) => {
        setExpandedTurns(prev => ({ ...prev, [turnNum]: !prev[turnNum] }));
    };

    if (loading) {
        return <PageSkeleton variant="light" cardCount={4} />;
    }

    if (!report) {
        return (
            <div className="min-h-screen bg-slate-50">
                <Navbar />
                <div className="mx-auto max-w-5xl px-6 py-16 text-center">
                    <p className="text-slate-700 text-lg">Report not found</p>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-xl transition-all"
                    >
                        Back to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    const getScoreColor = (score) => {
        if (score >= 0.7) return 'text-green-600 border-green-300 bg-green-50';
        if (score >= 0.4) return 'text-amber-600 border-amber-300 bg-amber-50';
        return 'text-red-600 border-red-300 bg-red-50';
    };

    const getScoreBarColor = (score) => {
        if (score >= 0.7) return 'bg-green-500';
        if (score >= 0.4) return 'bg-amber-500';
        return 'bg-red-500';
    };

    const getDifficultyColor = (d) => {
        if (d === 'EASY') return 'bg-green-100 text-green-700';
        if (d === 'HARD') return 'bg-red-100 text-red-700';
        return 'bg-amber-100 text-amber-700';
    };

    const getIntentColor = (intent) => {
        if (intent === 'POSITIVE') return 'bg-green-100 text-green-700';
        if (intent === 'NEGATIVE') return 'bg-red-100 text-red-700';
        return 'bg-slate-100 text-slate-600';
    };

    const getFollowupRateColor = (rate) => {
        if (rate < 30) return 'text-green-600';
        if (rate <= 60) return 'text-amber-600';
        return 'text-red-600';
    };

    return (
        <div className="min-h-screen bg-slate-50">
            <Navbar />

            <main className="mx-auto max-w-5xl px-6 py-12">
                {/* Header */}
                <div className="mb-12">
                    <div className="flex items-center gap-4 mb-4">
                        <button
                            onClick={() => navigate('/dashboard')}
                            className="text-slate-600 hover:text-slate-900 text-sm font-medium flex items-center gap-1 transition-colors"
                        >
                            <span>←</span> Back
                        </button>
                    </div>
                    <h1 className="text-4xl font-bold text-slate-900 mb-2">Interview Assessment Report</h1>
                    <p className="text-slate-600">
                        {report.total_turns} questions answered
                    </p>
                </div>

                {/* Score Cards Grid */}
                <div className="grid grid-cols-4 gap-6 mb-12">
                    {/* Overall */}
                    <div className={`rounded-2xl border-4 p-6 text-center ${getScoreColor(report.overall_score)}`}>
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Overall</p>
                        <div className="text-4xl font-bold mb-1">{Math.round(report.overall_score * 100)}%</div>
                        <div className="text-xs font-medium">
                            {report.overall_score >= 0.7 ? '✓ Excellent' : report.overall_score >= 0.4 ? '◐ Moderate' : '✕ Needs Work'}
                        </div>
                    </div>

                    {/* Content */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm text-center">
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Content</p>
                        <div className="text-4xl font-bold text-blue-600 mb-1">{Math.round(report.content_score * 100)}%</div>
                        <p className="text-xs text-slate-500">Knowledge accuracy</p>
                    </div>

                    {/* Behavior */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm text-center">
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Behavior</p>
                        <div className="text-4xl font-bold text-purple-600 mb-1">{Math.round(report.behavior_score * 100)}%</div>
                        <p className="text-xs text-slate-500">Eye contact & stability</p>
                    </div>

                    {/* Follow-up Rate */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm text-center">
                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Follow-up Rate</p>
                        <div className={`text-4xl font-bold mb-1 ${getFollowupRateColor(report.followup_rate)}`}>
                            {report.followup_rate.toFixed(0)}%
                        </div>
                        <p className="text-xs text-slate-500">{report.followup_interpretation}</p>
                    </div>
                </div>

                {/* AI Feedback */}
                <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm mb-12">
                    <div className="flex items-start gap-4">
                        <div className="text-3xl flex-shrink-0">✨</div>
                        <div>
                            <h2 className="text-lg font-bold text-slate-900 mb-3">AI Feedback & Insights</h2>
                            <p className="text-slate-700 leading-relaxed text-base">{report.feedback_summary}</p>
                        </div>
                    </div>
                </div>

                {/* Turn Breakdown */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm mb-12 overflow-hidden">
                    <div className="px-8 py-6 border-b border-slate-200 bg-slate-50">
                        <h2 className="text-lg font-bold text-slate-900">Question-by-Question Breakdown</h2>
                    </div>

                    <div className="divide-y divide-slate-100">
                        {report.turn_reviews.map((turn) => (
                            <div key={turn.turn_number}>
                                {/* Main turn row */}
                                <div
                                    className={`px-8 py-5 hover:bg-slate-50 transition-colors ${turn.followups?.length > 0 ? 'cursor-pointer' : ''}`}
                                    onClick={() => turn.followups?.length > 0 && toggleExpand(turn.turn_number)}
                                >
                                    <div className="flex items-center gap-4">
                                        {/* Turn badge */}
                                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                                            <span className="text-sm font-bold text-blue-700">Q{turn.turn_number}</span>
                                        </div>

                                        {/* Question text */}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-semibold text-slate-900 truncate">
                                                {turn.question_text?.substring(0, 80)}{turn.question_text?.length > 80 ? '...' : ''}
                                            </p>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${getDifficultyColor(turn.difficulty)}`}>
                                                    {turn.difficulty || 'MEDIUM'}
                                                </span>
                                                {turn.intent && (
                                                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${getIntentColor(turn.intent)}`}>
                                                        {turn.intent}
                                                    </span>
                                                )}
                                                {turn.response_time_sec != null && (
                                                    <span className="text-[10px] text-slate-400">
                                                        {Math.round(turn.response_time_sec)}s
                                                    </span>
                                                )}
                                                {turn.followups?.length > 0 && (
                                                    <span className="text-[10px] text-amber-600 font-medium">
                                                        {turn.followups.length} follow-up{turn.followups.length > 1 ? 's' : ''}
                                                    </span>
                                                )}
                                            </div>
                                        </div>

                                        {/* Score */}
                                        <div className="flex items-center gap-3 flex-shrink-0">
                                            <div className="w-20 h-2 bg-slate-200 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all ${getScoreBarColor(turn.final_score || 0)}`}
                                                    style={{ width: `${(turn.final_score || 0) * 100}%` }}
                                                ></div>
                                            </div>
                                            <span className={`text-sm font-bold w-12 text-right ${
                                                (turn.final_score || 0) >= 0.7 ? 'text-green-600' :
                                                (turn.final_score || 0) >= 0.4 ? 'text-amber-600' : 'text-red-600'
                                            }`}>
                                                {Math.round((turn.final_score || 0) * 100)}%
                                            </span>

                                            {/* Expand indicator */}
                                            {turn.followups?.length > 0 && (
                                                <span className={`text-slate-400 text-xs transition-transform ${expandedTurns[turn.turn_number] ? 'rotate-90' : ''}`}>
                                                    ▸
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Follow-up sub-rows (expandable) */}
                                {expandedTurns[turn.turn_number] && turn.followups?.map((fu, idx) => (
                                    <div key={idx} className="pl-16 pr-8 py-3 bg-amber-50/50 border-l-2 border-amber-300 ml-8 mr-8 mb-1 rounded-r-lg">
                                        <div className="flex items-center gap-3">
                                            <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-[10px] font-semibold">
                                                Follow-up {fu.followup_number}
                                            </span>
                                            <p className="text-sm text-slate-700 flex-1 truncate">
                                                {fu.question_text?.substring(0, 60)}
                                            </p>
                                            {fu.content_score != null && (
                                                <span className={`text-sm font-bold ${
                                                    fu.content_score >= 0.7 ? 'text-green-600' :
                                                    fu.content_score >= 0.4 ? 'text-amber-600' : 'text-red-600'
                                                }`}>
                                                    {Math.round(fu.content_score * 100)}%
                                                </span>
                                            )}
                                            {fu.intent && (
                                                <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${getIntentColor(fu.intent)}`}>
                                                    {fu.intent}
                                                </span>
                                            )}
                                        </div>
                                        {fu.candidate_response && (
                                            <p className="text-xs text-slate-500 mt-1 truncate pl-1">
                                                📝 {fu.candidate_response.substring(0, 100)}
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-center gap-4">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="px-8 py-3 bg-white border border-slate-300 hover:bg-slate-50 text-slate-900 font-semibold rounded-xl transition-all active:scale-[0.98]"
                    >
                        Back to Dashboard
                    </button>
                    <button
                        onClick={() => setToast({ type: 'success', message: 'Report download starting...' })}
                        className="px-8 py-3 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold rounded-xl transition-all flex items-center gap-2"
                    >
                        <span>📥</span> Download Report
                    </button>
                </div>
            </main>

            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
        </div>
    );
}
