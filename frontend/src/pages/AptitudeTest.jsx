import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import QuestionCard from '../components/QuestionCard';
import Timer from '../components/Timer';
import Toast from '../components/shared/Toast';
import ProctoringWarning from '../components/ProctoringWarning';
import { getNextQuestion, submitAnswer } from '../services/aptitudeService';
import { getSessionStatus, completeSession } from '../services/sessionService';
import { useAdvancedProctoring } from '../hooks/useAdvancedProctoring';

const MAX_QUESTIONS = 10;

export default function AptitudeTest() {
    const [question, setQuestion] = useState(null);
    const [selectedOption, setSelectedOption] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [questionCount, setQuestionCount] = useState(0);
    const [answersHistory, setAnswersHistory] = useState([]); // 'answered' | 'skipped'

    const [timeRemaining, setTimeRemaining] = useState(null);
    const [showSubmitModal, setShowSubmitModal] = useState(false);
    const [toast, setToast] = useState(null);
    const [networkOffline, setNetworkOffline] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const [proctoringWarnings, setProctoringWarnings] = useState([]);
    const [proctoringBlocked, setProctoringBlocked] = useState(false);
    const [testTerminated, setTestTerminated] = useState(false);

    const startTimeRef = useRef(null);
    const navigate = useNavigate();
    const retryTimeoutRef = useRef(null);
    const questionCountRef = useRef(0);
    const noFaceTimeoutRef = useRef(null);

    const finalizeAndGoToResult = useCallback(async () => {
        try {
            await completeSession();
        } catch {
            // Ignore session finalization errors and continue to the result page.
        } finally {
            navigate('/result');
        }
    }, [navigate]);

    // Initialize advanced proctoring hook
    const { videoRef, isMonitoring, enterFullscreen, detectionResults } = useAdvancedProctoring(
        sessionId,
        (violation) => {
            if (violation.terminate) {
                setTestTerminated(true);
                setProctoringBlocked(true);
                setToast({
                    type: 'error',
                    message: 'Test terminated due to multiple proctoring violations.',
                    duration: 5000
                });
                setTimeout(() => {
                    finalizeAndGoToResult();
                }, 3000);
            } else {
                const warning = {
                    type: violation.eventType,
                    message: `Proctoring violation detected: ${violation.eventType}`,
                    count: violation.violationCount,
                    severity: 'high',
                };

                if (violation.eventType === 'FACE_NOT_VISIBLE') {
                    warning.type = 'face_not_visible';
                    warning.message = 'Face not detected. Keep your face visible in the camera to continue the test.';
                    warning.blocking = true;
                    setProctoringBlocked(true);
                }

                setProctoringWarnings(prev => [...prev, warning]);
                setTimeout(() => {
                    setProctoringWarnings(prev => prev.filter(w => w !== warning));
                }, 5000);
            }
        }
    );

    useEffect(() => {
        if (!isMonitoring || testTerminated) return;

        if (detectionResults?.faceVisible) {
            if (noFaceTimeoutRef.current) {
                clearTimeout(noFaceTimeoutRef.current);
                noFaceTimeoutRef.current = null;
            }
            if (proctoringBlocked) {
                setProctoringBlocked(false);
            }
            return;
        }

        if (!noFaceTimeoutRef.current) {
            noFaceTimeoutRef.current = setTimeout(() => {
                setProctoringBlocked(true);
                setProctoringWarnings(prev => {
                    const alreadyExists = prev.some(w => w.type === 'face_not_visible' && w.blocking);
                    if (alreadyExists) return prev;
                    return [...prev, {
                        type: 'face_not_visible',
                        message: 'Face is not visible for more than 6 seconds. Please face the camera to continue.',
                        severity: 'high',
                        blocking: true,
                        count: 1,
                    }];
                });
            }, 6000);
        }

        return () => {
            if (noFaceTimeoutRef.current && detectionResults?.faceVisible) {
                clearTimeout(noFaceTimeoutRef.current);
                noFaceTimeoutRef.current = null;
            }
        };
    }, [detectionResults?.faceVisible, isMonitoring, proctoringBlocked, testTerminated]);

    useEffect(() => {
        if (testTerminated) {
            // Unconditionally finalize question gracefully
            if (question && !submitting) {
                const endTime = Date.now();
                const responseTime = (endTime - startTimeRef.current) / 1000;
                submitAnswer(question.question_id, null, responseTime).catch(() => {});
            }
            // Navigate after 5 seconds to let user read the warning
            const tm = setTimeout(() => {
                finalizeAndGoToResult();
            }, 5000);
            return () => clearTimeout(tm);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [testTerminated, finalizeAndGoToResult]);

    // Keep a ref so logic can read the latest count without creating effect loops.
    useEffect(() => {
        questionCountRef.current = questionCount;
    }, [questionCount]);

    const fetchQuestion = useCallback(async () => {
        console.log('🔍 DEBUG: fetchQuestion called, questionCount:', questionCountRef.current);
        
        if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);

        if (questionCountRef.current >= MAX_QUESTIONS) {
            console.log('🔍 DEBUG: Max questions reached, navigating to result');
            await finalizeAndGoToResult();
            return;
        }

        console.log('🔍 DEBUG: Setting loading to true');
        setLoading(true);
        setSelectedOption(null);
        setToast(null);
        try {
            console.log('🔍 DEBUG: Calling getNextQuestion...');
            const data = await getNextQuestion();
            console.log('🔍 DEBUG: Received question data:', data);
            setQuestion(data);
            startTimeRef.current = Date.now();
            setQuestionCount(prev => prev + 1);
            console.log('🔍 DEBUG: Question set, new count:', questionCountRef.current + 1);
        } catch (err) {
            console.error('🔍 DEBUG: Error in fetchQuestion:', err);
            if (err.response?.status === 404) {
                await finalizeAndGoToResult();
            } else if (!err.response) {
                setNetworkOffline(true);
                setToast({
                    message: "Failed to load question. Please try again.",
                    onRetry: fetchQuestion
                });
            } else {
                // Auto retry every 10 seconds for GET
                retryTimeoutRef.current = setTimeout(fetchQuestion, 10000);
            }
        } finally {
            console.log('🔍 DEBUG: Setting loading to false');
            setLoading(false);
        }
    }, [navigate, finalizeAndGoToResult]);

    const isInitialized = useRef(false);

    useEffect(() => {
        if (isInitialized.current) return;
        isInitialized.current = true;

        const initSession = async () => {
        try {
            const status = await getSessionStatus();
            setSessionId(status.id);
            setTimeRemaining(status.time_remaining_seconds ?? 1800);
        } catch (err) {
            if (!err.response) {
                console.error("Failed to restore session", err);
                navigate('/dashboard');
            }
        }
    };
        initSession();
        return () => {
            clearTimeout(retryTimeoutRef.current);
            if (noFaceTimeoutRef.current) {
                clearTimeout(noFaceTimeoutRef.current);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const didStartTestRef = useRef(false);
    useEffect(() => {
        console.log('🔍 DEBUG: Session effect triggered, sessionId:', sessionId);
        if (sessionId && !didStartTestRef.current) {
            didStartTestRef.current = true;
            console.log('🔍 DEBUG: Calling fetchQuestion...');
            fetchQuestion();
        }
    }, [sessionId, fetchQuestion]);

    const handleSubmission = async (optionToSubmit) => {
        if (submitting || !question) return;

        setSubmitting(true);
        setToast(null);

        const endTime = Date.now();
        const responseTime = (endTime - startTimeRef.current) / 1000;

        try {
            await submitAnswer(
                question.question_id,
                optionToSubmit, // null if skipped
                responseTime
            );

            // Record history
            setAnswersHistory(prev => [...prev, optionToSubmit ? 'answered' : 'skipped']);

            await fetchQuestion();
        } catch (err) {
            if (err.response?.status === 404) {
                await finalizeAndGoToResult();
            } else if (!err.response) {
                setNetworkOffline(true);
            } else {
                setToast({
                    message: "Answer submission failed. Please try again.",
                    onRetry: () => handleSubmission(optionToSubmit)
                });
            }
        } finally {
            setSubmitting(false);
        }
    };

    const handleTimerExpire = useCallback(() => {
        handleSubmission(selectedOption || null);
    }, [selectedOption, question]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleWarningDismiss = (warningIndex) => {
        setProctoringWarnings(prev => prev.filter((_, index) => index !== warningIndex));
    };

    const handleWarningRetry = async () => {
        if (!detectionResults?.faceVisible) {
            setToast({
                type: 'error',
                message: 'Face is still not visible. Please face the camera clearly and try again.',
                duration: 3000,
            });
            setProctoringBlocked(true);
            return;
        }

        setProctoringWarnings(prev => prev.filter(w => !w.blocking));
        setProctoringBlocked(false);
        if (sessionId) {
            await enterFullscreen();
        }
    };

    if (networkOffline) {
        return (
            <div className="flex h-screen flex-col items-center justify-center bg-[var(--color-bg-primary)] p-4 text-center">
                <div className="rounded-[12px] border border-[var(--color-danger)]/50 bg-[var(--color-bg-surface)] p-8 shadow-lg max-w-md w-full">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[var(--color-danger)]/10 text-[var(--color-danger)] mb-6">
                        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <h2 className="mb-4 text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">Connection Lost</h2>
                    <p className="mb-8 text-sm text-[var(--color-text-secondary)]">
                        The assessment backend server appears to be offline or unreachable. Please verify your connection and try again.
                    </p>
                    <button
                        onClick={() => window.location.reload()}
                        className="w-full rounded-lg bg-[var(--color-accent)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--color-accent)]/90"
                    >
                        Retry Connection
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="mt-4 w-full rounded-lg bg-transparent px-5 py-3 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]"
                    >
                        Return to Dashboard
                    </button>
                </div>
            </div>
        );
    }

    if (loading && timeRemaining === null) {
        return (
            <div className="flex h-screen flex-col overflow-hidden bg-[var(--color-bg-primary)]">
                <div className="mx-auto w-full max-w-6xl px-4 pt-6 sm:px-6 animate-pulse">
                    <div className="h-16 rounded-xl border border-[var(--color-border)] bg-white" />
                </div>
                <div className="mx-auto flex w-full max-w-6xl flex-1 items-start justify-center gap-8 overflow-hidden px-4 py-8 sm:px-6">
                    <div className="flex h-full w-full md:w-[70%] max-w-3xl flex-col overflow-hidden rounded-[12px] border border-[var(--color-border)] bg-white shadow-sm">
                        <div className="flex-1 p-6 sm:p-8 animate-pulse">
                            <div className="h-6 w-32 bg-[var(--color-border)] rounded mb-8"></div>
                            <div className="h-4 w-3/4 bg-[var(--color-border)] rounded mb-4"></div>
                            <div className="h-4 w-1/2 bg-[var(--color-border)] rounded mb-8"></div>
                            <div className="space-y-4">
                                {[1, 2, 3, 4].map(i => <div key={i} className="h-14 bg-[var(--color-bg-primary)] rounded-xl border border-[var(--color-border)]"></div>)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const answeredCount = answersHistory.filter(s => s === 'answered').length;
    const skippedCount = answersHistory.filter(s => s === 'skipped').length;
    const displayCount = questionCount || 1;

    return (
        <div className="flex h-screen flex-col overflow-hidden bg-[var(--color-bg-primary)]">
            <div className="mx-auto w-full max-w-6xl px-4 pt-4 sm:px-6">
                <div className="rounded-xl border border-[var(--color-border)] bg-white px-4 py-3 shadow-sm flex items-center justify-between">
                    <div>
                        <p className="text-xs uppercase tracking-wider text-[var(--color-text-secondary)] font-semibold">Assessment In Progress</p>
                        <p className="text-sm font-bold text-[var(--color-text-primary)]">Aptitude Test</p>
                    </div>
                    {timeRemaining !== null && (
                        <div className="flex items-center gap-3">
                            <Timer
                                initialSeconds={timeRemaining}
                                onExpire={handleTimerExpire}
                            />
                            <button
                                onClick={() => setShowSubmitModal(true)}
                                className="hidden md:block rounded-lg px-5 py-2.5 text-sm font-semibold tracking-wide text-white transition bg-[var(--color-accent)] hover:bg-[var(--color-accent)]/90 shadow-sm"
                            >
                                Submit Test
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Proctoring Warnings */}
            {proctoringWarnings.length > 0 && !testTerminated && (
                <div className="max-w-6xl mx-auto w-full px-4 pt-4 space-y-2">
                    {proctoringWarnings.map((warning, index) => (
                        <ProctoringWarning
                            key={index}
                            warning={warning}
                            onDismiss={() => handleWarningDismiss(index)}
                            onRetry={handleWarningRetry}
                        />
                    ))}
                </div>
            )}

            {/* Test Terminated Overlay */}
            {testTerminated && (
                <div className="fixed inset-0 bg-black/95 z-[150] flex items-center justify-center">
                    <div className="bg-white rounded-3xl p-8 max-w-lg mx-4 text-center shadow-2xl">
                        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-[var(--color-danger)]/10 text-[var(--color-danger)] mb-6">
                            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <h3 className="text-3xl font-black tracking-tight mb-4 text-[var(--color-danger)]">Test Terminated</h3>
                        <p className="text-[var(--color-text-secondary)] text-base mb-8 leading-relaxed">
                            You have exceeded the maximum limit for proctoring violations. Your test session has been immediately halted and finalized.
                        </p>
                        <div className="animate-pulse text-sm font-semibold text-[var(--color-text-primary)]">
                            Redirecting to results...
                        </div>
                    </div>
                </div>
            )}

            {/* Proctoring Blocked Overlay */}
            {proctoringBlocked && !testTerminated && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
                    <div className="bg-white rounded-lg p-6 max-w-md mx-4">
                        <h3 className="text-lg font-semibold mb-2">Proctoring Requirements</h3>
                        <p className="text-gray-600 mb-4">
                            Please meet all proctoring requirements to continue with the test.
                        </p>
                        <button
                            onClick={handleWarningRetry}
                            className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                        >
                            Retry Setup
                        </button>
                    </div>
                </div>
            )}

            {/* (mobile-specific top question container removed to avoid extra spacing;
                main question card is rendered in the central panel below) */}
            <div className="md:hidden border-b border-[var(--color-border)] bg-[var(--color-bg-surface)] px-4 py-3">
                <div className="flex justify-between text-sm text-[var(--color-text-secondary)] font-medium mb-2">
                    <span>Question {displayCount} of {MAX_QUESTIONS}</span>
                </div>
                <div className="h-1.5 w-full bg-[var(--color-bg-elevated)] overflow-hidden rounded-full">
                    <div
                        className="h-full bg-[var(--color-accent)] transition-all duration-300"
                        style={{ width: `${(displayCount / MAX_QUESTIONS) * 100}%` }}
                    />
                </div>
            </div>

            <div className="mx-auto flex w-full max-w-6xl flex-1 items-start justify-center gap-8 overflow-hidden px-4 py-8 sm:px-6">

                {/* Left Column: Question Panel */}
                <div className="flex h-full w-full md:w-[70%] max-w-3xl flex-col overflow-hidden rounded-[12px] border border-[var(--color-border)] bg-white shadow-sm">
                    {loading ? (
                        <div className="flex-1 p-6 sm:p-8 animate-pulse">
                            <div className="h-6 w-32 bg-[var(--color-border)] rounded mb-8"></div>
                            <div className="h-4 w-3/4 bg-[var(--color-border)] rounded mb-4"></div>
                            <div className="h-4 w-1/2 bg-[var(--color-border)] rounded mb-8"></div>
                            <div className="space-y-4">
                                {[1, 2, 3, 4].map(i => <div key={i} className="h-14 bg-[var(--color-bg-primary)] rounded-xl border border-[var(--color-border)]"></div>)}
                            </div>
                        </div>
                    ) : (
                        <div className="flex-1 overflow-y-auto p-6 sm:p-8">
                            <div className="mb-6 flex items-center justify-between">
                                <span className="text-sm font-semibold tracking-wide text-[var(--color-text-secondary)] uppercase">
                                    Question {displayCount} of {MAX_QUESTIONS}
                                </span>
                            </div>
                            <QuestionCard
                                question={question}
                                selectedOption={selectedOption}
                                onOptionSelect={setSelectedOption}
                                disabled={submitting}
                            />
                        </div>
                    )}

                    {/* Fixed Footer */}
                    <div className="shrink-0 border-t border-[var(--color-border)] bg-white p-6 flex items-center justify-end rounded-b-[12px]">
                        <button
                            onClick={() => handleSubmission(selectedOption)}
                            disabled={submitting || loading || proctoringBlocked || testTerminated}
                            className={`flex items-center gap-2 rounded-lg px-8 py-3 text-sm font-semibold transition disabled:opacity-40 shadow-sm ${selectedOption ? 'bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent)]/90' : 'bg-[#E5E7EB] text-[var(--color-text-secondary)] hover:bg-[#D1D5DB]'}`}
                        >
                            {selectedOption ? 'Next Question →' : 'Skip Question →'}
                        </button>
                    </div>
                </div>

                {/* Right Column: Test Progress (Hidden on mobile) */}
                <div className="hidden md:flex w-[30%] max-w-sm flex-col gap-6 shrink-0 h-full overflow-y-auto pb-8">
                    <div className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 shadow-sm">
                        <h3 className="mb-6 text-[15px] font-bold tracking-wide text-[var(--color-text-primary)] font-display uppercase">
                            TEST PROGRESS
                        </h3>
                        <div className="grid grid-cols-5 gap-3 mb-8">
                            {Array.from({ length: MAX_QUESTIONS }).map((_, i) => {
                                const num = i + 1;
                                let stateCls = "border-[var(--color-progress-not-visited)] bg-transparent text-[var(--color-text-secondary)]";

                                if (num < displayCount) {
                                    const status = answersHistory[i];
                                    if (status === 'answered') stateCls = "bg-[var(--color-success)] border-[var(--color-success)] text-white";
                                    else if (status === 'skipped') stateCls = "bg-[var(--color-danger)] border-[var(--color-danger)] text-white";
                                } else if (num === displayCount) {
                                    stateCls = "bg-white border-[var(--color-accent)] border-[2px] text-[var(--color-accent)] shadow-sm";
                                }

                                return (
                                    <div
                                        key={num}
                                        tabIndex={-1}
                                        aria-hidden="true"
                                        className={`flex h-[2.75rem] w-[2.75rem] items-center justify-center rounded-[8px] border font-mono text-sm font-bold transition-colors ${stateCls}`}
                                    >
                                        {num}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Legend */}
                        <div className="space-y-3 pt-6 border-t border-[var(--color-border)]">
                            <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-4">Legend</h4>
                            <div className="flex items-center gap-3 text-sm text-[var(--color-text-primary)]">
                                <div className="h-3 w-3 rounded-full bg-[var(--color-success)]" /> Answered
                            </div>
                            <div className="flex items-center gap-3 text-sm text-[var(--color-text-primary)]">
                                <div className="h-3 w-3 rounded-full bg-[var(--color-accent)]" /> Current
                            </div>
                            <div className="flex items-center gap-3 text-sm text-[var(--color-text-primary)]">
                                <div className="h-3 w-3 rounded-full bg-[var(--color-bg-elevated)] border border-[var(--color-border)]" /> Not Visited
                            </div>
                            <div className="flex items-center gap-3 text-sm text-[var(--color-text-primary)]">
                                <div className="h-3 w-3 rounded-full bg-[var(--color-danger)]" /> Skipped
                            </div>
                        </div>

                        {/* Progress Completion Bar */}
                        <div className="mt-8 pt-6 border-t border-[var(--color-border)]">
                            <div className="flex justify-between text-xs text-[var(--color-text-secondary)] tracking-wider font-mono mb-2">
                                <span>COMPLETION</span>
                                <span>{displayCount - 1}/{MAX_QUESTIONS}</span>
                            </div>
                            <div className="h-2 w-full bg-[var(--color-bg-primary)] overflow-hidden rounded-full border border-[var(--color-border)]/50">
                                <div
                                    className="h-full bg-[var(--color-text-secondary)] opacity-50 transition-all duration-300"
                                    style={{ width: `${((displayCount - 1) / MAX_QUESTIONS) * 100}%` }}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Toast for Submit Error */}
            <Toast
                message={toast?.message}
                onRetry={toast?.onRetry}
                onClose={() => setToast(null)}
            />

            {/* Submit Modal */}
            {showSubmitModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#0F172A]/80 backdrop-blur-sm p-4">
                    <div className="w-full max-w-sm rounded-3xl border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-8 shadow-2xl">
                        <h3 className="mb-2 text-2xl font-bold tracking-tight text-white">Submit Test?</h3>
                        <p className="mb-8 text-sm leading-relaxed text-[var(--color-text-secondary)]">Are you sure you want to end the assessment early? Unanswered questions may affect your score.</p>

                        <div className="mb-8 space-y-3 rounded-2xl bg-[var(--color-bg-primary)] p-5 text-sm font-medium border border-[var(--color-border)]/50">
                            <div className="flex justify-between items-center">
                                <span className="text-[var(--color-text-secondary)]">Answered</span>
                                <span className="font-bold text-[var(--color-success)] text-base">{answeredCount}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-[var(--color-text-secondary)]">Skipped</span>
                                <span className="font-bold text-[var(--color-danger)] text-base">{skippedCount}</span>
                            </div>
                        </div>

                        <div className="flex gap-3">
                            <button onClick={() => setShowSubmitModal(false)} className="flex-1 rounded-xl bg-[var(--color-bg-elevated)] py-3.5 font-bold text-[var(--color-text-primary)] hover:bg-[var(--color-border)] transition-colors">
                                Cancel
                            </button>
                            <button onClick={finalizeAndGoToResult} className="flex-1 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-surface)] py-3.5 font-bold text-white hover:bg-[var(--color-bg-elevated)] transition-colors">
                                Submit Test
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {/* Camera Preview */}
            {/* Always mount <video> so proctoring can attach stream.
                Only show the floating preview once monitoring is active. */}
            <div
                className={`fixed bottom-6 right-6 z-[90] overflow-hidden rounded-xl border border-[var(--color-border)] shadow-2xl bg-black h-36 w-48 transition-all hover:scale-105 ${
                    isMonitoring && !testTerminated ? 'opacity-100' : 'opacity-0 pointer-events-none'
                }`}
                aria-hidden={!isMonitoring || testTerminated}
            >
                <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    className="h-full w-full object-cover scale-x-[-1]"
                />
                {isMonitoring && !testTerminated && (
                    <div className="absolute top-3 right-3 flex items-center gap-2 rounded-md bg-black/60 px-2 py-1 backdrop-blur-md">
                        <div className="h-2 w-2 rounded-full bg-[var(--color-danger)] animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                        <span className="text-[10px] font-bold tracking-wider text-white uppercase">Rec</span>
                    </div>
                )}

                {isMonitoring && !testTerminated && (
                    <div className="absolute bottom-3 left-3 rounded-md bg-black/65 px-2 py-1 backdrop-blur-md">
                        <p className="text-[10px] font-semibold text-white tracking-wide">DEBUG</p>
                        <p className="text-[10px] text-white/90">Face: {detectionResults?.faceCount ?? 0}</p>
                        <p className="text-[10px] text-white/90">
                            Visibility: {Math.round((detectionResults?.visibilityRatio ?? 0) * 100)}%
                        </p>
                        <p className={`text-[10px] font-semibold ${detectionResults?.faceVisible ? 'text-emerald-300' : 'text-amber-300'}`}>
                            {detectionResults?.faceVisible ? 'Visible' : 'Not Visible'}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
