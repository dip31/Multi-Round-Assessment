import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    uploadResumeAsync,
    pollResumeProcessing,
    startInterview,
} from '../services/interviewService';
import { Toast } from '../components/Toast';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

// ── Stage 6B async state machine ──────────────────────────────────────
// Frontend-only lifecycle labels — DO NOT use these as wire-level enums.
// The wire-level status sent by the backend is one of:
//   PENDING | PROCESSING | COMPLETED | FAILED
// The UI states here map those onto user-facing progress copy without
// exposing Celery/Redis/MinIO or any other infrastructure term.
const UI_STATES = {
    IDLE: 'idle',
    UPLOADING: 'uploading',
    PROCESSING: 'processing',
    COMPLETED: 'completed',
    FAILED: 'failed',
};

// sessionStorage key for active job_id recovery across refresh.
// Bound to this assessment instance — values are scoped user-side.
const ACTIVE_JOB_KEY = 'stage6b_active_resume_job';

// Polling/timing knobs. Tuned so a normal resume parse completes within
// the timeout but a truly wedged worker does not leave the candidate
// waiting indefinitely.
const POLL_INTERVAL_MS = 1500;          // ~1.5s
const POLL_TIMEOUT_MS = 5 * 60 * 1000;  // 5 minutes max

// User-facing progress copy by backend status/progress_step.
// NEVER expose Celery/Redis/MinIO/stack traces here — only safe phrasing.
const PROGRESS_COPY = {
    PENDING:    'Uploading resume...',
    PROCESSING: 'Processing resume...',
    // Backend progress_step is more granular than the wire status; map the
    // known ones (claiming, parsing_resume, generating_pool, done) to
    // candidate-facing language. Unknown steps degrade gracefully to
    // the coarse "Processing resume..." copy.
    PROGRESS_STEPS: {
        uploaded:        'Uploading resume...',
        claiming:        'Processing resume...',
        parsing_resume:  'Analyzing resume...',
        generating_pool: 'Preparing personalized interview...',
        done:            'Resume processing completed.',
        // Failure-step keys are emitted as failed:<reason> by the worker.
        // We treat any progress_step starting with "failed" as FAILED.
    },
}

function storeActiveJobId(jobId) {
    if (jobId == null) {
        sessionStorage.removeItem(ACTIVE_JOB_KEY);
        return;
    }
    sessionStorage.setItem(ACTIVE_JOB_KEY, String(jobId));
}

function readActiveJobId() {
    const v = sessionStorage.getItem(ACTIVE_JOB_KEY);
    if (!v) return null;
    const n = parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : null;
}

function clearActiveJobId() {
    sessionStorage.removeItem(ACTIVE_JOB_KEY);
}

export default function ResumeUpload() {
    const [uiState, setUiState] = useState(UI_STATES.IDLE);
    const [selectedFile, setSelectedFile] = useState(null);
    const [jobId, setJobId] = useState(null);
    const [_statusPayload, setStatusPayload] = useState(null);
    const [poolId, setPoolId] = useState(null);
    const [interviewId, setInterviewId] = useState(null);
    const [detectedRole, setDetectedRole] = useState(null);
    const [toast, setToast] = useState(null);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [progressCopy, setProgressCopy] = useState('');
    const [fatalErrorMsg, setFatalErrorMsg] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const navigate = useNavigate();

    // Poll-cancel ref so a re-mount / state-change can halt an active loop.
    const cancelPollRef = useRef(false);
    // The polling helper uses a Promise that we resolve/reject from outside,
    // but we also need to short-circuit cleanly when the component unmounts.
    const unmountedRef = useRef(false);

    useEffect(() => {
        unmountedRef.current = false;
        return () => {
            unmountedRef.current = true;
            cancelPollRef.current = true;
        };
    }, []);

    // ── Recovery: if a job_id is stored in sessionStorage on mount, resume
    //    polling without re-uploading. We are deliberately tolerant of the
    //    job already being in a terminal state — the status endpoint will
    //    return COMPLETED or FAILED and we'll display the right UI.
    useEffect(() => {
        const stored = readActiveJobId();
        if (!stored) return;
        setJobId(stored);
        setUiState(UI_STATES.PROCESSING);
        setProgressCopy(PROGRESS_COPY.PROCESSING);
        pollLoopForJob(stored);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const startInterviewSession = useCallback(async (poolIdArg) => {
        try {
            const res = await startInterview(poolIdArg);
            if (res && res.interview_id) {
                setInterviewId(res.interview_id);
                localStorage.setItem('interview_id', res.interview_id);
            } else {
                setToast({ type: 'error', message: 'Failed to get interview ID' });
            }
        } catch (error) {
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to start interview',
            });
        }
    }, []);

    // ── Polling loop: held outside the JSX so the recovery useEffect and
    //    handleUpload can both start one. Returns nothing; relies on React
    //    state transitions. Idempotent thanks to cancelPollRef guarding
    //    against overlapping polls (component-width singleton).
    const pollLoopForJob = useCallback(async (jid) => {
        cancelPollRef.current = false;
        try {
            const status = await pollResumeProcessing(jid, {
                intervalMs: POLL_INTERVAL_MS,
                timeoutMs: POLL_TIMEOUT_MS,
            });
            if (unmountedRef.current) return;
            setStatusPayload(status);
            setPoolId(status.pool_id ?? null);
            setDetectedRole(status.detected_role ?? null);
            setProgressCopy(PROGRESS_COPY.PROGRESS_STEPS.done);
            setUiState(UI_STATES.COMPLETED);
            clearActiveJobId();
            // Auto-start the interview session row so the candidate can
            // proceed immediately to the InterviewRoom. The next-step
            // button is gated by uiState === COMPLETED + poolId.
            if (status.pool_id) {
                startInterviewSession(status.pool_id);
            }
        } catch (err) {
            if (unmountedRef.current) return;
            // Map structured poll errors to safe UI copy.
            if (err?.reason === 'timeout') {
                setFatalErrorMsg(
                    'Resume processing is taking longer than expected. Please try again.'
                );
            } else if (err?.reason === 'failed') {
                setFatalErrorMsg(
                    err?.error_message ||
                    'We couldn\'t process your resume. Please try again.'
                );
            } else if (err?.reason === 'not_found') {
                setFatalErrorMsg(
                    'We couldn\'t find your resume processing job. Please upload again.'
                );
            } else if (err?.reason === 'network') {
                setFatalErrorMsg(
                    'We couldn\'t reach the server. Check your connection and try again.'
                );
            } else if (err?.reason === 'cancelled') {
                return; // quiet
            } else {
                setFatalErrorMsg(
                    'Something went wrong while processing your resume. Please try again.'
                );
            }
            setUiState(UI_STATES.FAILED);
            clearActiveJobId();
        }
    }, [startInterviewSession]);

    // ── Handlers
    const handleFileSelect = (e) => {
        if (isSubmitting) return;
        const file = e.target.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            setToast(null);
        } else {
            setToast({ type: 'error', message: 'Please select a valid PDF file' });
        }
    };

    const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation(); };
    const handleDrop = (e) => {
        if (isSubmitting) return;
        e.preventDefault(); e.stopPropagation();
        const file = e.dataTransfer.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
        } else {
            setToast({ type: 'error', message: 'Please select a valid PDF file' });
        }
    };

    /**
     * Begin an ASYNC upload — debounced via isSubmitting so double-clicks
     * cannot produce two active jobs. Sets sessionStorage.job_id as soon
     * as the backend returns one. If the upload itself errors, we surface
     * a safe FAILED state and clear the stored job_id.
     */
    const handleUpload = async () => {
        if (isSubmitting) return;         // duplicate-click prevention
        if (!selectedFile) {
            setToast({ type: 'error', message: 'Please select a file first' });
            return;
        }
        setIsSubmitting(true);
        setUiState(UI_STATES.UPLOADING);
        setUploadProgress(10);
        setProgressCopy(PROGRESS_COPY.PENDING);
        setFatalErrorMsg('');
        try {
            const res = await uploadResumeAsync(selectedFile);
            setUploadProgress(100);
            setJobId(res.job_id);
            storeActiveJobId(res.job_id);
            setUiState(UI_STATES.PROCESSING);
            setProgressCopy(PROGRESS_COPY.PROCESSING);
            // Begin polling. The poll loop will drive the rest of state.
            pollLoopForJob(res.job_id);
        } catch (error) {
            const detail = error?.response?.data?.detail;
            const msg = typeof detail === 'string'
                ? detail
                : (Array.isArray(detail)
                    ? (detail[0]?.msg || 'Upload failed')
                    : 'Upload failed');
            setFatalErrorMsg(msg);
            setUiState(UI_STATES.FAILED);
            clearActiveJobId();
        } finally {
            // Keep isSubmitting true until COMPLETED/FAILED so a) the file
            // input can't be changed mid-processing and b) the Upload
            // button cannot be double-fired. Reset on FAILED (so retry
            // works) and on COMPLETED (so restart is possible if needed).
        }
    };

    // Reset to IDLE after FAILED so the candidate can re-upload.
    // Also clears isSubmitting so the "Try Again" button works.
    const handleRetry = () => {
        cancelPollRef.current = true;
        clearActiveJobId();
        setIsSubmitting(false);
        setUiState(UI_STATES.IDLE);
        setSelectedFile(null);
        setJobId(null);
        setStatusPayload(null);
        setPoolId(null);
        setDetectedRole(null);
        setFatalErrorMsg('');
        setProgressCopy('');
        setUploadProgress(0);
    };

    // ── Interview-start guard: only permitted when uiState === COMPLETED
    //    AND we have a poolId. Backend enforces the same via the status
    //    endpoint and sync interview router; this is defense-in-depth.
    const handleStartInterview = () => {
        if (uiState !== UI_STATES.COMPLETED || !poolId) {
            setToast({
                type: 'error',
                message: 'Interview can only start after resume processing completes.',
            });
            return;
        }
        const storedInterviewId = localStorage.getItem('interview_id');
        if (interviewId || storedInterviewId) {
            navigate('/interview');
        } else {
            setToast({
                type: 'error',
                message: 'Interview ID not found. Please re-upload your resume.',
            });
        }
    };

    // Derived: disable the upload button while any processing is active.
    const uploadDisabled = isSubmitting && uiState !== UI_STATES.FAILED;

    // ── Stepper
    const steps = [
        { label: 'Upload Resume',
          completed: [UI_STATES.UPLOADING, UI_STATES.PROCESSING, UI_STATES.COMPLETED].includes(uiState) },
        { label: 'AI Processing',
          completed: [UI_STATES.PROCESSING, UI_STATES.COMPLETED].includes(uiState) },
        { label: 'Ready for Interview',
          completed: uiState === UI_STATES.COMPLETED },
        { label: 'Start Interview', completed: false },
    ];

    const whatHappensNext = [
        { num: 1, text: 'Our AI will analyze your resume and experience' },
        { num: 2, text: 'A personalized interview question pool will be prepared' },
        { num: 3, text: 'You\'ll proceed directly to the interview' },
    ];

    return (
        <div className="min-h-screen bg-background text-on-surface font-body selection:bg-primary/30 antialiased">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="mx-auto max-w-3xl px-6 py-12 pt-24">
                {/* Back link */}
                <div className="mb-12">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="text-on-surface-variant hover:text-on-surface text-sm font-medium flex items-center gap-1 transition-colors"
                    >
                        <span>←</span> Back to Dashboard
                    </button>
                </div>

                {/* Header */}
                <div className="mb-12">
                    <h1 className="text-4xl font-headline font-black tracking-tighter text-on-surface mb-2">Resume Upload</h1>
                    <p className="text-on-surface-variant">Upload your resume to begin the interview process</p>
                </div>

                {/* Progress Stepper */}
                <div className="mb-12 bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                    <div className="flex items-center justify-between">
                        {steps.map((step, idx) => (
                            <div key={idx} className="flex flex-col items-center flex-1">
                                <div
                                    className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 font-semibold text-sm transition-all ${
                                        step.completed
                                            ? 'bg-emerald-500/20 text-emerald-400 border-2 border-emerald-500/30'
                                            : idx === 0 && uiState !== UI_STATES.IDLE
                                            ? 'bg-primary/20 text-primary border-2 border-primary/30'
                                            : 'bg-surface-container-highest text-on-surface-variant border-2 border-outline-variant/30'
                                    }`}
                                >
                                    {step.completed ? '✓' : idx + 1}
                                </div>
                                <p className={`text-xs font-label uppercase tracking-widest text-center ${
                                    step.completed ? 'text-emerald-400' : 'text-on-surface-variant'
                                }`}>
                                    {step.label}
                                </p>
                                {idx < steps.length - 1 && (
                                    <div
                                        className={`absolute w-12 h-1 -ml-6 mt-6 ${
                                            steps[idx + 1].completed ? 'bg-emerald-500/30' : 'bg-outline-variant/30'
                                        }`}
                                        style={{
                                            left: `calc(${(idx + 1) * (100 / steps.length)}% - 24px)`,
                                            top: '51px'
                                        }}
                                    ></div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Main Content Card */}
                {uiState === UI_STATES.IDLE && (
                    <div className="mb-12">
                        <div
                            onDragOver={handleDragOver}
                            onDrop={handleDrop}
                            className="bg-surface-container rounded-2xl border-2 border-dashed border-outline-variant/50 hover:border-primary/50 p-12 text-center transition-colors shadow-lg shadow-primary/5"
                        >
                            <input
                                type="file"
                                accept=".pdf"
                                onChange={handleFileSelect}
                                className="hidden"
                                id="file-input"
                                disabled={uploadDisabled}
                            />
                            <div className="text-5xl mb-4">☁️</div>
                            <h2 className="text-xl font-headline font-bold text-on-surface mb-2">
                                {selectedFile ? 'File Selected' : 'Drag & drop your resume'}
                            </h2>
                            <p className="text-on-surface-variant text-sm mb-6">
                                {selectedFile
                                    ? selectedFile.name
                                    : 'or click below to browse. PDF format, max 10MB'}
                            </p>
                            <label
                                htmlFor="file-input"
                                className={`inline-flex items-center justify-center bg-primary hover:bg-primary/90 active:scale-95 text-on-primary-container font-semibold py-3 px-8 rounded-xl transition-all duration-150 shadow-lg shadow-primary/20 cursor-pointer ${
                                    uploadDisabled ? 'opacity-50 pointer-events-none' : ''
                                }`}
                            >
                                {selectedFile ? 'Change File' : 'Select Resume'}
                            </label>
                            {selectedFile && (
                                <div className="mt-6">
                                    <button
                                        onClick={handleUpload}
                                        disabled={uploadDisabled}
                                        className="w-full hero-gradient hover:shadow-lg text-on-primary-container font-semibold py-3 rounded-xl transition-all duration-150 shadow-lg shadow-primary/20 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        Upload & Process
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="mt-12 bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                            <h3 className="text-lg font-headline font-bold text-on-surface mb-6">What happens next?</h3>
                            <div className="space-y-4">
                                {whatHappensNext.map((item) => (
                                    <div key={item.num} className="flex items-start gap-4">
                                        <div className="flex-shrink-0 w-8 h-8 bg-primary/20 text-primary rounded-full flex items-center justify-center font-bold text-sm font-label">
                                            {item.num}
                                        </div>
                                        <p className="text-on-surface text-sm font-medium pt-1">{item.text}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {(uiState === UI_STATES.UPLOADING || uiState === UI_STATES.PROCESSING) && (
                    <div className="bg-surface-container rounded-2xl border border-outline-variant/20 p-12 shadow-lg shadow-primary/5">
                        <div className="text-center">
                            <div className="space-y-6 mb-8">
                                {[
                                    { label: 'Uploading file',         done: uiState === UI_STATES.PROCESSING || uploadProgress >= 90 },
                                    { label: 'Validating upload',       done: uiState === UI_STATES.PROCESSING },
                                    { label: progressCopy || 'Processing resume...', done: false },
                                    { label: 'Finalizing',              done: false },
                                ].map((step, idx) => (
                                    <div key={idx} className="flex items-center gap-3">
                                        {step.done ? (
                                            <div className="w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center flex-shrink-0">
                                                <span className="text-white text-xs font-bold">✓</span>
                                            </div>
                                        ) : (
                                            <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin flex-shrink-0"></div>
                                        )}
                                        <p className={`text-sm font-medium ${step.done ? 'text-on-surface-variant' : 'text-on-surface'}`}>
                                            {step.label}
                                        </p>
                                    </div>
                                ))}
                            </div>
                            <div className="w-full bg-surface-container-highest rounded-full h-2 overflow-hidden">
                                <div
                                    className="bg-gradient-to-r from-primary to-secondary h-full rounded-full transition-all duration-500"
                                    style={{ width: `${uiState === UI_STATES.PROCESSING ? 90 : uploadProgress}%` }}
                                ></div>
                            </div>
                            <p className="mt-4 text-on-surface-variant text-sm">{progressCopy || 'Processing your resume...'}</p>
                            {jobId != null && (
                                <p className="mt-2 text-on-surface-variant text-xs opacity-60">
                                    Job #{jobId} — keep this tab open while we work.
                                </p>
                            )}
                        </div>
                    </div>
                )}

                {uiState === UI_STATES.COMPLETED && (
                    <div className="bg-surface-container rounded-2xl border border-outline-variant/20 p-12 shadow-lg shadow-primary/5">
                        <div className="text-center">
                            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-emerald-500/20 mb-6 animate-bounce">
                                <span className="text-4xl">✅</span>
                            </div>
                            <h2 className="text-2xl font-headline font-bold text-on-surface mb-2">
                                Resume Processing Complete
                            </h2>
                            <p className="text-on-surface-variant text-base mb-8">
                                Your personalized interview is ready to begin.
                            </p>
                            <div className="inline-flex items-center gap-2 bg-emerald-500/10 px-4 py-2 rounded-full mb-8 border border-emerald-500/20">
                                <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                                <span className="text-sm font-medium text-emerald-400">Ready to proceed</span>
                            </div>
                            {detectedRole && (
                                <div className="mt-4 bg-blue-50 rounded-xl p-4 border border-blue-100 flex items-center gap-3 mb-8 text-left">
                                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4 a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002 -2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <p className="text-sm font-medium text-blue-900">Role Detected: {detectedRole}</p>
                                        <p className="text-xs text-blue-600 mt-0.5">Questions tailored for {detectedRole} interviews</p>
                                    </div>
                                </div>
                            )}
                            <button
                                onClick={handleStartInterview}
                                disabled={!poolId}
                                className="w-full hero-gradient text-on-primary-container font-semibold py-4 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-base shadow-lg shadow-primary/20 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Start Interview
                                <span>→</span>
                            </button>
                            <p className="mt-6 text-on-surface-variant text-xs">
                                You have 48 hours to complete the interview
                            </p>
                        </div>
                    </div>
                )}

                {uiState === UI_STATES.FAILED && (
                    <div className="bg-surface-container rounded-2xl border border-red-500/40 p-12 shadow-lg shadow-red-500/5">
                        <div className="text-center">
                            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-red-500/20 mb-6">
                                <span className="text-4xl">⚠️</span>
                            </div>
                            <h2 className="text-2xl font-headline font-bold text-on-surface mb-2">
                                Resume Could Not Be Processed
                            </h2>
                            <p className="text-on-surface-variant text-base mb-8">
                                {fatalErrorMsg || 'Please try uploading a different file.'}
                            </p>
                            <div className="inline-flex items-center gap-2 bg-red-500/10 px-4 py-2 rounded-full mb-8 border border-red-500/20">
                                <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                                <span className="text-sm font-medium text-red-400">Processing failed — please retry</span>
                            </div>
                            <button
                                onClick={handleRetry}
                                className="w-full hero-gradient text-on-primary-container font-semibold py-4 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-base shadow-lg shadow-primary/20 active:scale-95"
                            >
                                Try Again
                                <span>↻</span>
                            </button>
                            <p className="mt-6 text-on-surface-variant text-xs">
                                Your previous upload was discarded and you can submit a fresh resume.
                            </p>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
