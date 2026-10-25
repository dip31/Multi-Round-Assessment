import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getOrInitializePortfolioBuilder,
    getPortfolioBuilderProgress,
    startStage,
    STAGE_KEYS,
    STAGE_ORDER,
    STAGE_DISPLAY,
    STAGE_STATUS,
    getStageDisplay,
    getStageActionText,
    getStageActionVariant,
    getStageStatusColor,
} from '../services/portfolioBuilderService';

export default function PortfolioBuilderOverview() {
    const navigate = useNavigate();
    const [attempt, setAttempt] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [initializing, setInitializing] = useState(false);
    const [actionLoading, setActionLoading] = useState(null);

    const fetchProgress = useCallback(async () => {
        try {
            const data = await getPortfolioBuilderProgress();
            setAttempt(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load portfolio builder progress:', err);
            if (!attempt) { // Only set error if we don't have existing data
                setError(err.response?.data?.detail || 'Unable to load progress. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    }, [attempt]);

    const initialize = useCallback(async () => {
        setInitializing(true);
        setError(null);
        try {
            const data = await getOrInitializePortfolioBuilder();
            setAttempt(data.attempt);
            setError(null);
        } catch (err) {
            console.error('Failed to initialize portfolio builder:', err);
            setError(err.response?.data?.detail || 'Unable to initialize Portfolio Builder. Please try again.');
        } finally {
            setInitializing(false);
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        initialize();
    }, [initialize]);

    // Poll for progress updates when a stage is in progress
    useEffect(() => {
        if (!attempt) return;
        
        const hasInProgress = attempt.stages?.some(s => s.status === STAGE_STATUS.IN_PROGRESS);
        if (!hasInProgress) return;

        const interval = setInterval(fetchProgress, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, [attempt, fetchProgress]);

    const handleStageAction = async (stageKey, status) => {
        if (status === STAGE_STATUS.LOCKED) {
            return; // Do nothing for locked stages
        }

        // Find stage data to check for existing score
        const stage = attempt.stages?.find(s => s.stage_key === stageKey);
        const hasScore = stage && typeof stage.score === 'number' && stage.score > 0;

        const slugMap = {
            [STAGE_KEYS.APTITUDE]: 'aptitude',
            [STAGE_KEYS.TECHNICAL_MCQ]: 'technical-mcq',
            [STAGE_KEYS.COMBINED_MCQ]: 'combined-mcq',
            [STAGE_KEYS.DSA_CODING]: 'dsa-coding',
            [STAGE_KEYS.RESUME_INTERVIEW]: 'resume-interview',
            [STAGE_KEYS.COMPETENCY_RESULTS]: 'results',
        };

        // Treat as completed if backend says COMPLETED or we already have a score
        if (status === STAGE_STATUS.COMPLETED || hasScore) {
            if (stageKey === STAGE_KEYS.COMPETENCY_RESULTS) {
                navigate('/portfolio-builder/results');
            } else {
                navigate(`/portfolio-builder/stage/${slugMap[stageKey] || stageKey}`);
            }
            return;
        }

        // Set up configuration for this assessment stage
        let config = {};
        switch (stageKey) {
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
            default:
                config = { is_portfolio_builder: true };
        }

        if (Object.keys(config).length) {
            localStorage.setItem('edi5_practice_config', JSON.stringify(config));
        }

        try {
            setActionLoading(stageKey);
            const result = await startStage(stageKey);
            
            // Navigate to the appropriate stage or round page
            if (result.redirect_url) {
                navigate(result.redirect_url, { state: { practice_config: config } });
            } else {
                navigate(`/portfolio-builder/stage/${slugMap[stageKey] || stageKey}`, { state: { practice_config: config } });
            }
        } catch (err) {
            console.error(`Failed to ${status === STAGE_STATUS.AVAILABLE ? 'start' : 'resume'} stage:`, err);
            setError(err.response?.data?.detail || 'Failed to start stage. Please try again.');
        } finally {
            setActionLoading(null);
        }
    };

    const getPrerequisiteText = (stageKey) => {
        const currentIndex = STAGE_ORDER.indexOf(stageKey);
        if (currentIndex === 0) return null;
        
        const prerequisites = STAGE_ORDER.slice(0, currentIndex);
        return prerequisites.map(k => STAGE_DISPLAY[k].title).join(', ');
    };

    if (loading && !attempt) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
            </div>
        );
    }

    if (error && !attempt) {
        return (
            <div className="text-center py-12">
                <div className="text-red-600 mb-4">{error}</div>
                <button 
                    onClick={initialize}
                    disabled={initializing}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                    {initializing ? 'Initializing...' : 'Retry'}
                </button>
            </div>
        );
    }

    if (!attempt) {
        return (
            <div className="text-center py-12">
                <button 
                    onClick={initialize}
                    disabled={initializing}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                    {initializing ? 'Initializing...' : 'Start Portfolio Builder'}
                </button>
            </div>
        );
    }

    const currentStage = attempt.stages?.find(s => s.stage_key === attempt.current_stage);
    const completedStages = attempt.stages?.filter(s => s.status === STAGE_STATUS.COMPLETED).length || 0;
    const totalStages = STAGE_ORDER.length - 1; // Exclude results stage from progress

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">Portfolio Builder Assessment</h1>
                    <p className="text-gray-600 mt-1">
                        Complete 6 structured stages to build your evidence-backed placement readiness profile.
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="text-right">
                        <div className="text-2xl font-bold text-blue-600">{completedStages} / {totalStages}</div>
                        <div className="text-sm text-gray-500">Stages Completed</div>
                    </div>
                    <div className="w-32 h-4 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-blue-600 rounded-full transition-all duration-300"
                            style={{ width: `${(completedStages / totalStages) * 100}%` }}
                        ></div>
                    </div>
                </div>
            </div>

            {/* Error Toast */}
            {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center justify-between">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">✕</button>
                </div>
            )}

            {/* Stage Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {STAGE_ORDER.map((stageKey) => {
                    const stage = attempt.stages?.find(s => s.stage_key === stageKey);
                    const display = getStageDisplay(stageKey);
                    const isCurrentStage = stageKey === attempt.current_stage;
                    const stageStatus = stage?.status || STAGE_STATUS.LOCKED;
                    const prerequisites = getPrerequisiteText(stageKey);

                    return (
                        <div 
                            key={stageKey} 
                            className={`relative p-6 rounded-xl border transition-all duration-200 ${
                                isCurrentStage 
                                    ? 'border-blue-300 bg-blue-50 shadow-lg ring-2 ring-blue-200' 
                                    : 'border-gray-200 bg-white hover:shadow-md'
                            }`}
                        >
                            {/* Stage Number Badge */}
                            <div className="absolute -top-3 -right-3 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
                                {display.number}
                            </div>

                            {/* Icon */}
                            <div className="text-4xl mb-3">{display.icon}</div>

                            {/* Title */}
                            <h3 className="text-xl font-semibold text-gray-900 mb-1">{display.title}</h3>

                            {/* Description */}
                            <p className="text-gray-600 text-sm mb-4">{display.description}</p>

                            {/* Duration */}
                            {display.duration_minutes > 0 && (
                                <div className="flex items-center text-sm text-gray-500 mb-3">
                                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <span>{display.duration_minutes} min</span>
                                </div>
                            )}

                            {/* Status Badge */}
                            {stage && (
                                <div className="mb-4">
                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStageStatusColor(stageStatus)}`}>
                                        {stageStatus}
                                    </span>
                                </div>
                            )}

                            {/* Score/Progress for completed stages */}
                            {stage && stageStatus === STAGE_STATUS.COMPLETED && stage.score !== null && (
                                <div className="mb-4 p-3 bg-green-50 rounded-lg">
                                    <div className="text-sm font-medium text-green-700">Score: {stage.score}%</div>
                                    {stage.max_score && <div className="text-xs text-green-600">Max: {stage.max_score}%</div>}
                                    <div className="text-xs text-green-600 mt-1">
                                        {stage.passed ? '✓ Passed' : '✗ Not Passed'}
                                    </div>
                                    {stage.completed_at && (
                                        <div className="text-xs text-green-500 mt-1">
                                            Completed: {new Date(stage.completed_at).toLocaleDateString()}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Prerequisite notice for locked stages */}
                            {stage && stageStatus === STAGE_STATUS.LOCKED && prerequisites && (
                                <div className="mb-4 p-3 bg-yellow-50 rounded-lg text-sm text-yellow-700">
                                    🔒 Complete first: {prerequisites}
                                </div>
                            )}

                            {/* Action Button */}
                            {/* Determine effective status for UI: treat as completed if we already have a score */}
                            {(() => {
                                const hasScore = stage && typeof stage.score === 'number' && stage.score > 0;
                                const effectiveStatus = hasScore ? STAGE_STATUS.COMPLETED : stageStatus;
                                return (
                                    <button
                                        onClick={() => handleStageAction(stageKey, stageStatus)}
                                        disabled={stageStatus === STAGE_STATUS.LOCKED || actionLoading !== null || hasScore}
                                        className={`w-full px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
                                            getStageActionVariant(effectiveStatus) === 'primary' 
                                                ? 'bg-blue-600 text-white hover:bg-blue-700' 
                                                : getStageActionVariant(effectiveStatus) === 'secondary'
                                                ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                                                : getStageActionVariant(effectiveStatus) === 'success'
                                                ? 'bg-green-100 text-green-700 hover:bg-green-200'
                                                : getStageActionVariant(effectiveStatus) === 'danger'
                                                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                : 'bg-gray-100 text-gray-500 cursor-not-allowed'
                                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                                    >
                                        {actionLoading === stageKey ? 'Starting...' : getStageActionText(effectiveStatus)}
                                    </button>
                                );
                            })()}
                        </div>
                    );
                })}
            </div>

            {/* Journey Info */}
            <div className="bg-gray-50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h3>
                <div className="space-y-3 text-sm text-gray-600">
                    <p>• Stages must be completed in order — you cannot skip ahead.</p>
                    <p>• Progress is saved automatically — you can resume anytime.</p>
                    <p>• Each stage uses the actual EDI5 assessment engine — no simulated scores.</p>
                    <p>• Final results aggregate evidence from all stages into a competency profile.</p>
                </div>
            </div>
        </div>
    );
}