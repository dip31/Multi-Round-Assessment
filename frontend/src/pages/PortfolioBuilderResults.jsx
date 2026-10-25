import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getConsolidatedResults,
    getPortfolioBuilderProgress,
    STAGE_KEYS,
    STAGE_DISPLAY,
    STAGE_STATUS,
} from '../services/portfolioBuilderService';

export default function PortfolioBuilderResults() {
    const navigate = useNavigate();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchReport = useCallback(async () => {
        try {
            const data = await getConsolidatedResults();
            setReport(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load consolidated results:', err);
            setError(err.response?.data?.detail || 'Unable to load results. Please try again.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchReport();
    }, [fetchReport]);

    // Helper to get stage display
    const getStageDisplay = (stageKey) => {
        return STAGE_DISPLAY[stageKey] || { number: 0, title: stageKey, description: '', duration_minutes: 0, icon: '❓' };
    };

    // Helper to get status color
    const getStageStatusColor = (status) => {
        switch (status) {
            case STAGE_STATUS.COMPLETED:
                return 'text-green-600 bg-green-100';
            case STAGE_STATUS.IN_PROGRESS:
                return 'text-blue-600 bg-blue-100';
            case STAGE_STATUS.AVAILABLE:
                return 'text-yellow-600 bg-yellow-100';
            case STAGE_STATUS.LOCKED:
                return 'text-gray-600 bg-gray-100';
            case STAGE_STATUS.FAILED:
                return 'text-red-600 bg-red-100';
            default:
                return 'text-gray-600 bg-gray-100';
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-600 border-t-transparent"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="max-w-4xl mx-auto text-center py-12">
                <div className="text-red-600 mb-4">{error}</div>
                <button onClick={fetchReport} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
                    Retry
                </button>
                <button onClick={() => navigate('/portfolio-builder')} className="ml-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700">
                    Back to Overview
                </button>
            </div>
        );
    }

    if (!report) {
        return (
            <div className="max-w-4xl mx-auto text-center py-12">
                <div className="text-gray-600 mb-4">No report data available</div>
                <button onClick={() => navigate('/portfolio-builder')} className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700">
                    Back to Overview
                </button>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Consolidated Competency Results</h1>
                    <p className="text-gray-600 mt-1">
                        Evidence-backed competency profile from your Portfolio Builder journey
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStageStatusColor(report.overall_completion_status)}`}>
                        {report.overall_completion_status}
                    </span>
                    {report.completion_date && (
                        <span className="text-sm text-gray-500">
                            Completed: {new Date(report.completion_date).toLocaleDateString()}
                        </span>
                    )}
                </div>
            </div>

            {/* Error Toast */}
            {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">✕</button>
                </div>
            )}

            {/* Section A: Portfolio Builder Overview */}
            <section className="bg-white border border-gray-200 rounded-xl p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <span className="text-2xl">📋</span>
                    Section A: Portfolio Builder Overview
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-indigo-600">
                            {report.stages_completed?.length || 0} / 5
                        </div>
                        <div className="text-sm text-gray-500">Assessment Stages Completed</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-indigo-600">
                            {report.completion_date ? new Date(report.completion_date).toLocaleDateString() : '—'}
                        </div>
                        <div className="text-sm text-gray-500">Completion Date</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-indigo-600">
                            {report.total_duration_minutes ? `${report.total_duration_minutes} min` : '—'}
                        </div>
                        <div className="text-sm text-gray-500">Total Duration</div>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-indigo-600">
                            {report.evidence_sources_summary ? Object.keys(report.evidence_sources_summary).length : 0}
                        </div>
                        <div className="text-sm text-gray-500">Evidence Sources</div>
                    </div>
                </div>
                
                {report.missing_evidence_details?.length > 0 && (
                    <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                        <h4 className="font-semibold text-yellow-800 mb-2">⚠️ Missing Evidence</h4>
                        <ul className="text-yellow-700 space-y-1">
                            {report.missing_evidence_details.map((detail, i) => (
                                <li key={i}>• {detail}</li>
                            ))}
                        </ul>
                    </div>
                )}
            </section>

            {/* Section B: Aptitude & Logical Reasoning */}
            {report.aptitude_score !== null && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">🧮</span>
                        Section B: Aptitude & Logical Reasoning
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-blue-600">{report.aptitude_score}%</div>
                            <div className="text-sm text-gray-500">Score</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-blue-600">{report.aptitude_max_score}%</div>
                            <div className="text-sm text-gray-500">Max Score</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{report.aptitude_correct_count || 0}</div>
                            <div className="text-sm text-gray-500">Correct</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-red-600">{report.aptitude_incorrect_count || 0}</div>
                            <div className="text-sm text-gray-500">Incorrect</div>
                        </div>
                    </div>
                    {report.aptitude_topic_breakdown && Object.keys(report.aptitude_topic_breakdown).length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-700 mb-3">Topic Breakdown</h4>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(report.aptitude_topic_breakdown).map(([topic, score]) => (
                                    <span key={topic} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
                                        {topic}: {score}%
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Section C: Technical Knowledge */}
            {report.technical_score !== null && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">💻</span>
                        Section C: Technical Knowledge
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{report.technical_score}%</div>
                            <div className="text-sm text-gray-500">Score</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{report.technical_max_score}%</div>
                            <div className="text-sm text-gray-500">Max Score</div>
                        </div>
                    </div>
                    {report.technical_subject_breakdown && Object.keys(report.technical_subject_breakdown).length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-700 mb-3">Subject Breakdown</h4>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(report.technical_subject_breakdown).map(([subject, score]) => (
                                    <span key={subject} className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm">
                                        {subject}: {score}%
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Section D: Combined Assessment */}
            {report.combined_score !== null && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">🔄</span>
                        Section D: Combined Aptitude & Technical Assessment
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-purple-600">{report.combined_score}%</div>
                            <div className="text-sm text-gray-500">Score</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-purple-600">{report.combined_max_score}%</div>
                            <div className="text-sm text-gray-500">Max Score</div>
                        </div>
                    </div>
                    {report.combined_category_breakdown && Object.keys(report.combined_category_breakdown).length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-700 mb-3">Category Breakdown</h4>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(report.combined_category_breakdown).map(([category, score]) => (
                                    <span key={category} className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm">
                                        {category}: {score}%
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Section E: Coding Performance */}
            {report.coding_problems_attempted > 0 && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">👨‍💻</span>
                        Section E: Coding Performance
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-orange-600">{report.coding_problems_passed}</div>
                            <div className="text-sm text-gray-500">Problems Passed</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-orange-600">{report.coding_problems_attempted}</div>
                            <div className="text-sm text-gray-500">Problems Attempted</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-orange-600">{report.coding_languages_used?.join(', ') || '—'}</div>
                            <div className="text-sm text-gray-500">Languages</div>
                        </div>
                    </div>
                    {report.coding_competencies?.length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-700 mb-3">Demonstrated Competencies</h4>
                            <div className="flex flex-wrap gap-2">
                                {report.coding_competencies.map((comp, i) => (
                                    <span key={i} className="px-3 py-1 bg-orange-50 text-orange-700 rounded-full text-sm">
                                        {comp}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Section F: Interview Performance */}
            {report.interview_overall_score !== null && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">🎙️</span>
                        Section F: Interview Performance
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-pink-600">{report.interview_overall_score}%</div>
                            <div className="text-sm text-gray-500">Overall Score</div>
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg">
                            <div className="text-2xl font-bold text-pink-600">{report.interview_type || 'Technical'}</div>
                            <div className="text-sm text-gray-500">Interview Type</div>
                        </div>
                    </div>
                    {report.interview_dimension_scores && Object.keys(report.interview_dimension_scores).length > 0 && (
                        <div>
                            <h4 className="font-semibold text-gray-700 mb-3">Dimension Scores</h4>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(report.interview_dimension_scores).map(([dim, score]) => (
                                    <span key={dim} className="px-3 py-1 bg-pink-50 text-pink-700 rounded-full text-sm">
                                        {dim}: {score}%
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    {report.interview_competencies?.length > 0 && (
                        <div className="mt-4">
                            <h4 className="font-semibold text-gray-700 mb-3">Assessed Competencies</h4>
                            <div className="flex flex-wrap gap-2">
                                {report.interview_competencies.map((comp, i) => (
                                    <span key={i} className="px-3 py-1 bg-pink-50 text-pink-700 rounded-full text-sm">
                                        {comp}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {/* Section G: Competency Summary */}
            {report.competency_evidence?.length > 0 && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">📊</span>
                        Section G: Competency Summary
                    </h2>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-gray-50 text-left text-gray-500">
                                    <th className="p-3 font-semibold">Competency</th>
                                    <th className="p-3 font-semibold">Category</th>
                                    <th className="p-3 font-semibold">Evidence Sources</th>
                                    <th className="p-3 font-semibold">Score</th>
                                    <th className="p-3 font-semibold">Confidence</th>
                                    <th className="p-3 font-semibold">Evidence Count</th>
                                    <th className="p-3 font-semibold">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {report.competency_evidence.map((comp, i) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                        <td className="p-3 font-medium text-gray-900">{comp.competency_name}</td>
                                        <td className="p-3">
                                            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">{comp.category}</span>
                                        </td>
                                        <td className="p-3">
                                            <div className="flex flex-wrap gap-1">
                                                {comp.evidence_sources.map((src, j) => (
                                                    <span key={j} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded">{src}</span>
                                                ))}
                                            </div>
                                        </td>
                                        <td className="p-3">
                                            {comp.aggregated_score !== null ? (
                                                <span className={`font-mono ${comp.aggregated_score >= 70 ? 'text-green-600' : comp.aggregated_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                                                    {comp.aggregated_score}%
                                                </span>
                                            ) : (
                                                <span className="text-gray-400">—</span>
                                            )}
                                        </td>
                                        <td className="p-3">
                                            {comp.confidence !== null ? (
                                                <span className={`${comp.confidence >= 0.7 ? 'text-green-600' : comp.confidence >= 0.4 ? 'text-yellow-600' : 'text-red-600'}`}>
                                                    {(comp.confidence * 100).toFixed(0)}%
                                                </span>
                                            ) : (
                                                <span className="text-gray-400">—</span>
                                            )}
                                        </td>
                                        <td className="p-3 text-center">{comp.evidence_count}</td>
                                        <td className="p-3">
                                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${comp.evidence_sufficient ? 'text-green-600 bg-green-100' : 'text-yellow-600 bg-yellow-100'}`}>
                                                {comp.evidence_sufficient ? 'Sufficient' : 'Insufficient'}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}

            {/* Section H: Improvement Recommendations */}
            {report.recommendations?.length > 0 && (
                <section className="bg-white border border-gray-200 rounded-xl p-6">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <span className="text-2xl">💡</span>
                        Section H: Improvement Recommendations
                    </h2>
                    <div className="space-y-3">
                        {report.recommendations.map((rec, i) => (
                            <div key={i} className="p-4 bg-gray-50 rounded-lg border-l-4 border-indigo-500">
                                <div className="flex items-start gap-3">
                                    <span className="text-indigo-600 font-bold">{i + 1}.</span>
                                    <div className="flex-1">
                                        <h4 className="font-semibold text-gray-900">{rec.title}</h4>
                                        <p className="text-gray-600 text-sm mt-1">{rec.description}</p>
                                        {rec.competency && (
                                            <span className="inline-block mt-2 px-2 py-0.5 text-xs bg-indigo-100 text-indigo-700 rounded">
                                                Focus: {rec.competency} ({rec.category})
                                            </span>
                                        )}
                                    </div>
                                    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                                        rec.priority === 'high' ? 'bg-red-100 text-red-700' :
                                        rec.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                        'bg-green-100 text-green-700'
                                    }`}>
                                        {rec.priority}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* Footer Actions */}
            <div className="flex justify-center gap-4 pt-6 border-t">
                <button 
                    onClick={() => navigate('/portfolio-builder')}
                    className="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                >
                    Back to Overview
                </button>
                <button 
                    onClick={() => window.print()}
                    className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                    Print / Save as PDF
                </button>
            </div>
        </div>
    );
}