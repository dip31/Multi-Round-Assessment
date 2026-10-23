import React, { useState } from 'react';

// Question-wise Analysis Component for EDI5 scored interviews
const QuestionWiseAnalysis = ({ analysis }) => {
    if (!analysis || !analysis.questions || analysis.questions.length === 0) return null;
    
    const getScoreColor = (score) => {
        if (score >= 7) return 'text-green-600 border-green-300 bg-green-50';
        if (score >= 4) return 'text-amber-600 border-amber-300 bg-amber-50';
        return 'text-red-600 border-red-300 bg-red-50';
    };
    
    const getScoreBarColor = (score) => {
        if (score >= 7) return 'bg-green-500';
        if (score >= 4) return 'bg-amber-500';
        return 'bg-red-500';
    };
    
    const getDepthColor = (depth) => {
        switch (depth) {
            case 'Expert': return 'text-purple-600 bg-purple-50 border-purple-200';
            case 'Strong': return 'text-blue-600 bg-blue-50 border-blue-200';
            case 'Good': return 'text-green-600 bg-green-50 border-green-200';
            case 'Basic': return 'text-amber-600 bg-amber-50 border-amber-200';
            default: return 'text-slate-600 bg-slate-50 border-slate-200';
        }
    };

    return (
        <section className="mb-8 rounded-2xl border border-indigo-200 bg-indigo-50 p-6">
            <div className="flex items-center gap-3 mb-4">
                <div className="text-3xl">[Target]</div>
                <div>
                    <h2 className="text-lg font-bold text-indigo-950">Question-wise Analysis</h2>
                    <p className="text-sm text-indigo-700">Detailed per-question evaluation with concept coverage and gap analysis</p>
                </div>
            </div>
            
            {/* Overall Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">{analysis.questions.length}</div>
                    <div className="text-xs text-slate-500">Questions Analyzed</div>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                    <div className="text-2xl font-bold text-slate-600">{analysis.overall_score} / 10</div>
                    <div className="text-xs text-slate-500">Overall Score</div>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{analysis.strong_areas?.length || 0}</div>
                    <div className="text-xs text-slate-500">Strengths</div>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
                    <div className="text-2xl font-bold text-amber-600">{analysis.improvement_areas?.length || 0}</div>
                    <div className="text-xs text-slate-500">Areas to Improve</div>
                </div>
            </div>
            
            {/* Confidence Meter */}
            <div className="mb-6 bg-white rounded-xl border border-slate-200 p-4">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-bold text-slate-900">Evaluation Confidence</h4>
                    <span className="text-sm font-bold text-purple-600">
                        {Math.round((analysis.confidence || 0.8) * 100)}%
                    </span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                        className="h-full rounded-full bg-gradient-to-r from-purple-500 to-purple-400 transition-all"
                        style={{ width: `${(analysis.confidence || 0.8) * 100}%` }}
                    ></div>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                    Higher confidence means more reliable evaluation (based on answer depth and concept clarity)
                </p>
            </div>
            
            {/* Strengths & Improvement Areas */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div className="bg-white rounded-xl border border-green-200 p-4">
                    <h4 className="text-sm font-bold text-green-800 mb-2 flex items-center gap-2">
                        <span className="text-green-600"></span> Strengths
                    </h4>
                    <ul className="space-y-1">
                        {(analysis.strong_areas || []).map((area, idx) => (
                            <li key={idx} className="text-sm text-green-700 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                {area}
                            </li>
                        ))}
                        {(analysis.strong_areas?.length || 0) === 0 && (
                            <p className="text-sm text-slate-500">No strong areas identified yet</p>
                        )}
                    </ul>
                </div>
                
                <div className="bg-white rounded-xl border border-amber-200 p-4">
                    <h4 className="text-sm font-bold text-amber-800 mb-2 flex items-center gap-2">
                        <span className="text-amber-600"></span> Areas for Improvement
                    </h4>
                    <ul className="space-y-1">
                        {(analysis.improvement_areas || []).map((area, idx) => (
                            <li key={idx} className="text-sm text-amber-700 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                                {area}
                            </li>
                        ))}
                        {(analysis.improvement_areas?.length || 0) === 0 && (
                            <p className="text-sm text-slate-500">No major improvement areas</p>
                        )}
                    </ul>
                </div>
            </div>
            
            {/* Recurring Gaps */}
            {(analysis.recurring_gaps?.length || 0) > 0 && (
                <div className="bg-white rounded-xl border border-red-200 p-4 mb-4">
                    <h4 className="text-sm font-bold text-red-800 mb-2 flex items-center gap-2">
                        <span className="text-red-600"></span> Recurring Gaps
                    </h4>
                    <p className="text-sm text-red-700 mb-2">
                        These concepts were missed across multiple questions:
                    </p>
                    <div className="flex flex-wrap gap-2">
                        {(analysis.recurring_gaps || []).map((gap, idx) => (
                            <span key={idx} className="px-2 py-1 bg-red-50 text-red-700 text-xs font-medium rounded-full">
                                {gap}
                            </span>
                        ))}
                    </div>
                </div>
            )}
            
            {/* Pattern Summary */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6">
                <h4 className="text-sm font-bold text-slate-900 mb-2">Interview Pattern Summary</h4>
                <p className="text-sm text-slate-700 leading-relaxed">{analysis.pattern_summary}</p>
            </div>
            
            {/* Competency Changes */}
            {(analysis.competency_changes?.length || 0) > 0 && (
                <div className="bg-white rounded-xl border border-blue-200 p-4 mb-6">
                    <h4 className="text-sm font-bold text-blue-800 mb-3 flex items-center gap-2">
                        <span className="text-blue-600"></span> Competency Profile Updates
                    </h4>
                    <div className="space-y-2">
                        {(analysis.competency_changes || []).map((change, idx) => (
                            <div key={idx} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-100">
                                <div>
                                    <p className="text-sm font-medium text-blue-900">{change.skill}</p>
                                    <p className="text-xs text-blue-700">
                                        {change.previous_score.toFixed(1)}% → {change.new_score.toFixed(1)}% 
                                        (Confidence: {Math.round(change.previous_confidence * 100)}% → {Math.round(change.new_confidence * 100)}%)
                                    </p>
                                </div>
                                <span className={`text-sm font-bold ${change.new_score >= change.previous_score ? 'text-green-600' : 'text-red-600'}`}>
                                    {change.new_score >= change.previous_score ? '+' : ''}{(change.new_score - change.previous_score).toFixed(1)}%
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
            
            {/* Question Breakdown */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200 bg-slate-50">
                    <h3 className="text-sm font-bold text-slate-900">Question-by-Question Breakdown</h3>
                </div>
                <div className="divide-y divide-slate-100">
                    {(analysis.questions || []).map((q, idx) => (
                        <QuestionAnalysisCard 
                            key={q.question_id || idx} 
                            question={q} 
                            index={idx}
                        />
                    ))}
                </div>
            </div>
        </section>
    );
};

// Individual Question Analysis Card Component
const QuestionAnalysisCard = ({ question, index }) => {
    const [expanded, setExpanded] = useState(false);
    
    const getScoreColor = (score) => {
        if (score >= 7) return 'text-green-600';
        if (score >= 4) return 'text-amber-600';
        return 'text-red-600';
    };
    
    const getScoreBarColor = (score) => {
        if (score >= 7) return 'bg-green-500';
        if (score >= 4) return 'bg-amber-500';
        return 'bg-red-500';
    };
    
    const getDepthColor = (depth) => {
        switch (depth) {
            case 'Expert': return 'text-purple-600 bg-purple-50 border-purple-200';
            case 'Strong': return 'text-blue-600 bg-blue-50 border-blue-200';
            case 'Good': return 'text-green-600 bg-green-50 border-green-200';
            case 'Basic': return 'text-amber-600 bg-amber-50 border-amber-200';
            default: return 'text-slate-600 bg-slate-50 border-slate-200';
        }
    };
    
    const scorePercent = Math.round((question.score / (question.max_score || 10)) * 100);
    
    return (
        <div className="group">
            {}
            <div 
                className={`px-6 py-4 hover:bg-slate-50 transition-colors cursor-pointer flex items-center gap-4`}
                onClick={() => setExpanded(!expanded)}
            >
                {}
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                    <span className="text-sm font-bold text-purple-700">Q{question.question_number || index + 1}</span>
                </div>
                
                {}
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-900 truncate mb-1">
                        {question.question_text?.substring(0, 100)}{question.question_text?.length > 100 ? '...' : ''}
                    </p>
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${getDepthColor(question.depth_level || 'Basic')}`}>
                            {question.depth_level || 'Basic'}
                        </span>
                        {question.question_type && (
                            <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-100">
                                {question.question_type}
                            </span>
                        )}
                    </div>
                </div>
                
                {}
                <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="w-20 h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full transition-all ${getScoreBarColor(question.score || 0)}`}
                            style={{ width: `${Math.round((question.score / (question.max_score || 10)) * 100)}%` }}
                        ></div>
                    </div>
                    <span className={`text-sm font-bold w-10 text-right ${getScoreColor(question.score || 0)}`}>
                        {Math.round(question.score)}%
                    </span>
                </div>
                
                {}
                <span className={`text-slate-400 text-xs transition-transform ${expanded ? 'rotate-90' : ''}`}>
                    
                </span>
            </div>
            
            {}
            {expanded && (
                <div className="px-6 pb-4 bg-slate-50 bg-opacity-50 border-t border-slate-100 animate-slide-down">
                    <div className="space-y-4 pt-4">
                        {}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="bg-white rounded-lg border border-green-200 p-4">
                                <h5 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                                    Covered Concepts ({question.covered_concepts?.length || 0})
                                </h5>
                                <div className="flex flex-wrap gap-1">
                                    {question.covered_concepts?.length > 0 ? (
                                        question.covered_concepts.map((c, i) => (
                                            <span key={i} className="px-2 py-1 bg-green-50 text-green-700 text-xs rounded-full border border-green-200">
                                                {c}
                                            </span>
                                        ))
                                    ) : (
                                        <p className="text-xs text-slate-400">None covered</p>
                                    )}
                                </div>
                            </div>
                            
                            <div className="bg-white rounded-lg border border-red-200 p-4">
                                <h5 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                                    Missing Concepts ({question.missing_concepts?.length || 0})
                                </h5>
                                <div className="flex flex-wrap gap-1">
                                    {question.missing_concepts?.length > 0 ? (
                                        question.missing_concepts.map((c, i) => (
                                            <span key={i} className="px-2 py-1 bg-red-50 text-red-700 text-xs rounded-full border border-red-200">
                                                {c}
                                            </span>
                                        ))
                                    ) : (
                                        <p className="text-xs text-green-600">All concepts covered!</p>
                                    )}
                                </div>
                            </div>
                        </div>
                        
                        {}
                        {question.incorrect_concepts?.length > 0 && (
                            <div className="bg-white rounded-lg border border-red-200 p-4">
                                <h5 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                                    Incorrect Statements ({question.incorrect_concepts.length})
                                </h5>
                                <div className="flex flex-wrap gap-1">
                                    {question.incorrect_concepts.map((c, i) => (
                                        <span key={i} className="px-2 py-1 bg-red-50 text-red-700 text-xs rounded-full border border-red-200">
                                            {c}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {question.strengths?.length > 0 && (
                                <div className="bg-white rounded-lg border border-green-200 p-4">
                                    <h5 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2">Strengths</h5>
                                    <ul className="space-y-1">
                                        {question.strengths.map((s, i) => (
                                            <li key={i} className="text-xs text-green-700 flex items-center gap-1">
                                                <span className="w-1 h-1 rounded-full bg-green-500"></span>
                                                {s}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {question.gaps?.length > 0 && (
                                <div className="bg-white rounded-lg border border-amber-200 p-4">
                                    <h5 className="text-xs font-bold text-amber-700 uppercase tracking-wider mb-2">Gaps</h5>
                                    <ul className="space-y-1">
                                        {question.gaps.map((g, i) => (
                                            <li key={i} className="text-xs text-amber-700 flex items-center gap-1">
                                                <span className="w-1 h-1 rounded-full bg-amber-500"></span>
                                                {g}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                        
                        {}
                        <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600">
                            <p><span className="font-medium">Question ID:</span> {question.question_id}</p>
                            <p><span className="font-medium">Confidence:</span> {Math.round((question.confidence || 0.8) * 100)}%</p>
</div>
                    </div>
                </div>
            )}
        </div>
    );
};

export { QuestionWiseAnalysis, QuestionAnalysisCard };