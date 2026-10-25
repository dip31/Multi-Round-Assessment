import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    getPortfolioBuilderProgress,
    completeStage,
    getStageResults,
    startStage,
    STAGE_KEYS,
    STAGE_ORDER,
    STAGE_DISPLAY,
    STAGE_STATUS,
    getStageDisplay,
    getStageStatusColor,
} from '../services/portfolioBuilderService';

export default function PortfolioBuilderStage() {
    const { stageKey } = useParams();
    const navigate = useNavigate();
    const [stage, setStage] = useState(null);
    const [attempt, setAttempt] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [completing, setCompleting] = useState(false);

    // Map URL param to stage key
    const stageKeyMap = {
        'aptitude': STAGE_KEYS.APTITUDE,
        'technical-mcq': STAGE_KEYS.TECHNICAL_MCQ,
        'combined-mcq': STAGE_KEYS.COMBINED_MCQ,
        'dsa-coding': STAGE_KEYS.DSA_CODING,
        'resume-interview': STAGE_KEYS.RESUME_INTERVIEW,
        'results': STAGE_KEYS.COMPETENCY_RESULTS,
    };

    const canonicalStageKey = stageKeyMap[stageKey] || stageKey;

    const fetchProgress = useCallback(async () => {
        try {
            const data = await getPortfolioBuilderProgress();
            setAttempt(data);
            const stageData = data.stages?.find(s => s.stage_key === canonicalStageKey);
            setStage(stageData);
            setError(null);
        } catch (err) {
            console.error('Failed to load stage:', err);
            setError(err.response?.data?.detail || 'Unable to load stage. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [canonicalStageKey]);

    useEffect(() => {
        fetchProgress();
    }, [fetchProgress]);

    // Auto-complete stage if underlying assessment round is completed
    useEffect(() => {
        if (stage && stage.status === STAGE_STATUS.IN_PROGRESS && !completing) {
            // Attempt to complete the stage; backend will validate round completion
            const tryComplete = async () => {
                try {
                    setCompleting(true);
                    const result = await completeStage(canonicalStageKey);
                    if (result.next_stage_key && result.next_stage_available) {
                        navigate('/portfolio-builder');
                    } else {
                        fetchProgress();
                    }
                } catch (err) {
                    // Ignore errors (e.g., round not completed yet)
                    console.debug('Auto-complete not ready:', err.message);
                } finally {
                    setCompleting(false);
                }
            };
            tryComplete();
        }
    }, [stage, canonicalStageKey, completing, navigate, fetchProgress]);

    // Redirect locked stages to overview
    useEffect(() => {
        if (stage && stage.status === STAGE_STATUS.LOCKED) {
            navigate('/portfolio-builder');
        }
    }, [stage, navigate]);

    const display = STAGE_DISPLAY[canonicalStageKey] || { number: 0, title: canonicalStageKey, description: '', duration_minutes: 0, icon: '❓' };
    const [startingAssessment, setStartingAssessment] = useState(false);

    const launchAssessment = async () => {
        // Prevent launching if stage already completed (has a score)
        if (isCompleted) {
            // Redirect to overview to see updated progress
            navigate('/portfolio-builder');
            return;
        }
        try {
            setStartingAssessment(true);
            setError(null);

            // Determine practice config for the stage
            let config = {};
            switch (canonicalStageKey) {
                case STAGE_KEYS.APTITUDE:
                    config = { practice_type: 'mcq', subject: null, is_portfolio_builder: true };
                    break;
                case STAGE_KEYS.TECHNICAL_MCQ:
                    config = { practice_type: 'technical', subject: null, is_portfolio_builder: true };
                    break;
                case STAGE_KEYS.COMBINED_MCQ:
                    config = { practice_type: 'combined', subject: null, is_portfolio_builder: true };
                    break;
                case STAGE_KEYS.DSA_CODING:
                    config = { practice_type: 'coding', is_portfolio_builder: true };
                    break;
                case STAGE_KEYS.RESUME_INTERVIEW:
                    config = { practice_type: 'interview', is_portfolio_builder: true };
                    break;
                case STAGE_KEYS.COMPETENCY_RESULTS:
                    config = {};
                    break;
                default:
                    config = {};
            }

            // Store config for the assessment page
            if (Object.keys(config).length) {
                localStorage.setItem('edi5_practice_config', JSON.stringify(config));
            }

            // Start or resume the stage via backend to get the proper redirect URL with round/session IDs
            const result = await startStage(canonicalStageKey);
            if (result.redirect_url) {
                navigate(result.redirect_url, { state: { practice_config: config } });
            } else if (canonicalStageKey === STAGE_KEYS.COMPETENCY_RESULTS) {
                navigate('/portfolio-builder/results');
            }
        } catch (err) {
            console.error('Failed to launch assessment:', err);
            setError(err.response?.data?.detail || 'Failed to launch assessment. Please try again.');
        } finally {
            setStartingAssessment(false);
        }
    };

    const handleComplete = async () => {
        if (!stage || stage.status !== STAGE_STATUS.IN_PROGRESS) return;

        setCompleting(true);
        try {
            const result = await completeStage(canonicalStageKey);
            if (result.next_stage_key && result.next_stage_available) {
                // Navigate to overview to see updated progress
                navigate('/portfolio-builder');
            } else if (canonicalStageKey === STAGE_KEYS.COMPETENCY_RESULTS) {
                navigate('/portfolio-builder/results');
            } else {
                // Refresh progress
                fetchProgress();
            }
        } catch (err) {
            console.error('Failed to complete stage:', err);
            setError(err.response?.data?.detail || 'Failed to complete stage. Please try again.');
        } finally {
            setCompleting(false);
        }
    };

    const handleViewResults = async () => {
        if (canonicalStageKey === STAGE_KEYS.COMPETENCY_RESULTS) {
            navigate('/portfolio-builder/results');
        } else {
            try {
                const results = await getStageResults(canonicalStageKey);
                // Could open a modal or navigate to results page
                console.log('Stage results:', results);
                alert(`Stage completed with score: ${results.score}%`);
            } catch (err) {
                console.error('Failed to load results:', err);
            }
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center py-12">
                <div className="text-red-600 mb-4">{error}</div>
                <button onClick={fetchProgress} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Retry
                </button>
            </div>
        );
    }

    if (!stage) {
        return (
            <div className="text-center py-12">
                <div className="text-red-600 mb-4">Stage not found</div>
                <button onClick={() => navigate('/portfolio-builder')} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Back to Overview
                </button>
            </div>
        );
    }

    const hasScore = typeof stage.score === 'number' && stage.score > 0;
    const isCompleted = stage.status === STAGE_STATUS.COMPLETED || hasScore;
    const isInProgress = stage.status === STAGE_STATUS.IN_PROGRESS && !hasScore;
    const isAvailable = stage.status === STAGE_STATUS.AVAILABLE && !hasScore;
    const isLocked = stage.status === STAGE_STATUS.LOCKED;

    // Render stage-specific content
    const renderStageContent = () => {
        switch (canonicalStageKey) {
            case STAGE_KEYS.APTITUDE:
            case STAGE_KEYS.TECHNICAL_MCQ:
            case STAGE_KEYS.COMBINED_MCQ:
                return renderMCQStage();
            case STAGE_KEYS.DSA_CODING:
                return renderCodingStage();
            case STAGE_KEYS.RESUME_INTERVIEW:
                return renderInterviewStage();
            case STAGE_KEYS.COMPETENCY_RESULTS:
                return renderResultsStage();
            default:
                return <div>Unknown stage</div>;
        }
    };

    const renderMCQStage = () => (
        <div className="space-y-6">
            <div className="bg-blue-50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-blue-900 mb-2">MCQ Assessment</h3>
                <p className="text-blue-700">
                    This stage uses the EDI5 adaptive MCQ engine with RL-driven difficulty adaptation.
                    Questions are selected based on your performance in real-time.
                </p>
            </div>

            {isInProgress && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                    <h4 className="font-semibold text-yellow-800 mb-3">Assessment In Progress</h4>
                    <div className="space-y-3">
                        <p className="text-yellow-700">
                            You have an active assessment round. Continue where you left off.
                        </p>
                        <button 
                            onClick={launchAssessment}
                            disabled={startingAssessment}
                            className="inline-flex items-center px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors disabled:opacity-50"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            {startingAssessment ? 'Launching...' : 'Continue Assessment'}
                        </button>
                    </div>
                </div>
            )}

            {isCompleted && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                    <h4 className="font-semibold text-green-800 mb-3">✅ Assessment Completed</h4>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.score}%</div>
                            <div className="text-sm text-gray-500">Score</div>
                        </div>
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.max_score}%</div>
                            <div className="text-sm text-gray-500">Max Score</div>
                        </div>
                    </div>
                    <button 
                        onClick={handleViewResults}
                        className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                        View Detailed Results
                    </button>
                </div>
            )}

            {isAvailable && (
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center">
                    <p className="text-blue-700 mb-4">
                        Ready to start the {display.title} assessment?
                    </p>
                    <button 
                        onClick={launchAssessment}
                        disabled={startingAssessment}
                        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-lg disabled:opacity-50"
                    >
                        {startingAssessment ? 'Launching...' : 'Start Assessment'}
                    </button>
                </div>
            )}

            {isLocked && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
                    <div className="text-gray-500 mb-2">🔒 Locked</div>
                    <p className="text-gray-600">Complete previous stages to unlock.</p>
                </div>
            )}
        </div>
    );

    const renderCodingStage = () => (
        <div className="space-y-6">
            <div className="bg-green-50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-green-900 mb-2">DSA Coding Assessment</h3>
                <p className="text-green-700">
                    Solve coding problems with automated evaluation via Judge0. 
                    Supports Python, JavaScript, Java, and C++.
                </p>
            </div>

            {isInProgress && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                    <h4 className="font-semibold text-yellow-800 mb-3">Coding Round In Progress</h4>
                    <div className="space-y-3">
                        <p className="text-yellow-700">
                            You have an active coding round. Continue solving problems.
                        </p>
                        <button 
                            onClick={launchAssessment}
                            disabled={startingAssessment}
                            className="inline-flex items-center px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors disabled:opacity-50"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 16l4-16M6 9a3 3 0 00-3 3v10a3 3 0 003 3h12a3 3 0 003-3v-2.667" />
                            </svg>
                            {startingAssessment ? 'Launching...' : 'Continue Coding'}
                        </button>
                    </div>
                </div>
            )}

            {isCompleted && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                    <h4 className="font-semibold text-green-800 mb-3">✅ Coding Assessment Completed</h4>
                    <div className="grid grid-cols-3 gap-4 mb-4">
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.score}%</div>
                            <div className="text-sm text-gray-500">Best Score</div>
                        </div>
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.detail?.problems_passed || 0}</div>
                            <div className="text-sm text-gray-500">Problems Passed</div>
                        </div>
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.detail?.problems_attempted || 0}</div>
                            <div className="text-sm text-gray-500">Problems Attempted</div>
                        </div>
                    </div>
                    <button 
                        onClick={handleViewResults}
                        className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                        View Detailed Results
                    </button>
                </div>
            )}

            {isAvailable && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
                    <p className="text-green-700 mb-4">Ready to start the DSA Coding Assessment?</p>
                    <button 
                        onClick={launchAssessment}
                        disabled={startingAssessment}
                        className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-lg disabled:opacity-50"
                    >
                        {startingAssessment ? 'Launching...' : 'Start Coding Assessment'}
                    </button>
                </div>
            )}

            {isLocked && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
                    <div className="text-gray-500 mb-2">🔒 Locked</div>
                    <p className="text-gray-600">Complete previous stages to unlock.</p>
                </div>
            )}
        </div>
    );

    const renderInterviewStage = () => (
        <div className="space-y-6">
            <div className="bg-purple-50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-purple-900 mb-2">Resume-Based Interview</h3>
                <p className="text-purple-700">
                    AI-powered technical interview grounded in your resume, projects, and experience.
                    Questions are personalized based on your background.
                </p>
            </div>

            {isInProgress && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                    <h4 className="font-semibold text-yellow-800 mb-3">Interview In Progress</h4>
                    <div className="space-y-3">
                        <p className="text-yellow-700">
                            You have an active interview session. Continue the conversation.
                        </p>
                        <button 
                            onClick={launchAssessment}
                            disabled={startingAssessment}
                            className="inline-flex items-center px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors disabled:opacity-50"
                        >
                            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                            {startingAssessment ? 'Launching...' : 'Continue Interview'}
                        </button>
                    </div>
                </div>
            )}

            {isCompleted && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                    <h4 className="font-semibold text-green-800 mb-3">✅ Interview Completed</h4>
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.score}%</div>
                            <div className="text-sm text-gray-500">Overall Score</div>
                        </div>
                        <div className="bg-white p-4 rounded-lg">
                            <div className="text-2xl font-bold text-green-600">{stage.detail?.scored_turns || 0}</div>
                            <div className="text-sm text-gray-500">Turns Completed</div>
                        </div>
                    </div>
                    <button 
                        onClick={handleViewResults}
                        className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                        View Interview Report
                    </button>
                </div>
            )}

            {isAvailable && (
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-6 text-center">
                    <p className="text-purple-700 mb-4">Ready for your Resume-Based Interview?</p>
                    <button 
                        onClick={launchAssessment}
                        disabled={startingAssessment}
                        className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-lg disabled:opacity-50"
                    >
                        {startingAssessment ? 'Launching...' : 'Start Interview'}
                    </button>
                </div>
            )}

            {isLocked && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
                    <div className="text-gray-500 mb-2">🔒 Locked</div>
                    <p className="text-gray-600">Complete previous stages to unlock.</p>
                </div>
            )}
        </div>
    );

    const renderResultsStage = () => (
        <div className="space-y-6">
            <div className="bg-indigo-50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-indigo-900 mb-2">Consolidated Competency Results</h3>
                <p className="text-indigo-700">
                    Your evidence-backed competency profile aggregated from all completed stages.
                </p>
            </div>

            {isInProgress && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                    <h4 className="font-semibold text-yellow-800 mb-3">Generating Report</h4>
                    <p className="text-yellow-700">Compiling evidence from all stages...</p>
                </div>
            )}

            {isCompleted && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                    <h4 className="font-semibold text-green-800 mb-3">✅ Consolidated Report Ready</h4>
                    <p className="text-green-700 mb-4">Your competency profile has been generated.</p>
                    <a 
                        href="/portfolio-builder/results"
                        className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        View Full Report
                    </a>
                </div>
            )}

            {isAvailable && (
                <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6 text-center">
                    <p className="text-indigo-700 mb-4">All assessment stages completed. Generate your competency report?</p>
                    <button 
                        onClick={handleComplete}
                        disabled={completing}
                        className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-lg"
                    >
                        {completing ? 'Generating...' : 'Generate Report'}
                    </button>
                </div>
            )}

            {isLocked && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
                    <div className="text-gray-500 mb-2">🔒 Locked</div>
                    <p className="text-gray-600">Complete all 5 assessment stages to unlock.</p>
                </div>
            )}
        </div>
    );

    return (
        <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <button 
                    onClick={() => navigate('/portfolio-builder')}
                    className="mb-4 inline-flex items-center text-gray-500 hover:text-gray-700 transition-colors"
                >
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                    <span>Back to Portfolio Builder</span>
                </button>
                
                <div className="flex items-start gap-4">
                    <div className="w-16 h-16 rounded-xl bg-blue-100 flex items-center justify-center text-3xl">
                        {display.icon}
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-blue-600 bg-blue-100 px-3 py-1 rounded-full">
                                Stage {display.number} of 6
                            </span>
                            {stage && (
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStageStatusColor(stage.status)}`}>
                                    {stage.status}
                                </span>
                            )}
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900 mt-2">{display.title}</h1>
                        <p className="text-gray-600 mt-1">{display.description}</p>
                        {display.duration_minutes > 0 && (
                            <div className="flex items-center text-sm text-gray-500 mt-2">
                                <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <span>Duration: ~{display.duration_minutes} minutes</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Stage Content */}
            {renderStageContent()}

            {/* Progress Bar */}
            {attempt && (
                <div className="mt-8 pt-6 border-t">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">Overall Progress</span>
                        <span className="text-sm text-gray-500">
                            {attempt.stages?.filter(s => s.status === STAGE_STATUS.COMPLETED).length || 0} / {STAGE_ORDER.length - 1} stages completed
                        </span>
                    </div>
                    <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-blue-600 rounded-full transition-all duration-300"
                            style={{ width: `${((attempt.stages?.filter(s => s.status === STAGE_STATUS.COMPLETED).length || 0) / (STAGE_ORDER.length - 1)) * 100}%` }}
                        ></div>
                    </div>
                </div>
            )}
        </div>
    );
}