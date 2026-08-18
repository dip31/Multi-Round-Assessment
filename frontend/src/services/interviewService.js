import api from './api';

/**
 * Upload a resume PDF and generate personalized question pool (synchronous).
 *
 * LEGACY sync endpoint — DEPRECATED on the frontend after Stage 6B but
 * PRESERVED on the backend for backward compatibility. Do NOT delete.
 */
export const uploadResume = async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(
        `/interview/resume/upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
};

/**
 * Upload a resume PDF for ASYNCHRONOUS processing (Stage 6B).
 *
 * Backend flow: HTTP → MinIO → resume_processing_jobs(row, PENDING) → Celery task.
 * Returns immediately with { job_id, status: "PENDING" }. Poll the status of the
 * returned job_id with pollResumeProcessing() or getResumeProcessingStatus().
 *
 * The Celery worker carries ONLY { job_id, storage_key } — never raw bytes.
 */
export const uploadResumeAsync = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(
        `/interview/resume/upload-async`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
};

/**
 * GET one-shot status snapshot for an async resume processing job.
 * Backend enforces ownership: a candidate querying another candidate's
 * job_id receives 404 (not 403, to prevent enumeration).
 */
export const getResumeProcessingStatus = async (jobId) => {
    const response = await api.get(`/interview/resume/processing/${jobId}`);
    return response.data;
};

/**
 * Poll the resume-processing status endpoint until a terminal state
 * (COMPLETED | FAILED) is reached or a timeout/max-attempts bound fires.
 *
 * Behavior:
 *   - Polls every `intervalMs` (default 1500ms).
 *   - Rejects with {reason: 'timeout'} after `timeoutMs` (default 5 min).
 *   - Rejects with {reason: 'failed', status, error_message} if FAILED.
 *   - Rejects with {reason: 'network', error} on a network/HTTP error
 *     so the caller can decide to retry the poll vs abandon. After
 *     `maxConsecutiveErrors` consecutive network failures (default 5)
 *     the poll rejects with {reason: 'network', consecutiveErrors}.
 *   - Resolves with the COMPLETED status payload (includes pool_id,
 *     detected_role, question_count) so callers can immediately call
 *     startInterview() without an extra round trip.
 */
export const pollResumeProcessing = async (
    jobId,
    {
        intervalMs = 1500,
        timeoutMs = 5 * 60 * 1000,
        maxConsecutiveErrors = 5,
        signal,
    } = {}
) => {
    if (!jobId) throw new Error('jobId is required');

    const start = Date.now();
    let consecutiveErrors = 0;

    // Local helper so we can re-use the loop logic across poll cycles.
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const isCancelled = () => (signal && signal.aborted);

    while (true) {
        if (isCancelled()) {
            throw { reason: 'cancelled' };
        }
        if (Date.now() - start > timeoutMs) {
            throw { reason: 'timeout', elapsedMs: Date.now() - start };
        }

        let status;
        try {
            status = await getResumeProcessingStatus(jobId);
            consecutiveErrors = 0;
        } catch (err) {
            consecutiveErrors += 1;
            const status_code = err?.response?.status;
            // 404 — job not found (invalid/expired/deleted). Don't retry; surface.
            if (status_code === 404) {
                throw { reason: 'not_found', error: err };
            }
            // 403 — should not happen given server returns 404 deliberately,
            // but treat as auth-related and fatal.
            if (status_code === 403) {
                throw { reason: 'forbidden', error: err };
            }
            // Network error / 5xx — retry up to maxConsecutiveErrors.
            if (consecutiveErrors >= maxConsecutiveErrors) {
                throw {
                    reason: 'network',
                    consecutiveErrors,
                    error: err,
                    lastStatus: status_code,
                };
            }
            await sleep(intervalMs);
            continue;
        }

        if (status.status === 'COMPLETED') {
            return status;
        }
        if (status.status === 'FAILED') {
            throw {
                reason: 'failed',
                status: status.status,
                error_message: status.error_message,
                progress_step: status.progress_step,
            };
        }
        // PENDING or PROCESSING — keep polling.
        await sleep(intervalMs);
    }
};

/**
 * Get the approved question pool by pool ID
 */
export const getPool = async (poolId) => {
    const response = await api.get(`/interview/pool/${poolId}`);
    return response.data;
};

/**
 * Approve or reject a question pool
 */
export const approvePool = async (poolId, approved) => {
    const response = await api.put(`/interview/pool/${poolId}/approve`, {
        approved,
    });
    return response.data;
};

/**
 * Start an interview session with an approved pool
 */
export const startInterview = async (poolId) => {
    const response = await api.post(`/interview/session/start?pool_id=${poolId}`);
    return response.data;
};

/**
 * Get the next interview question
 */
export const getNextQuestion = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/next`);
    return response.data;
};

/**
 * Submit a response to an interview question
 */
export const submitResponse = async (interviewId, transcript, responseTimeSec, behavioralSnapshot) => {
    const response = await api.post(`/interview/session/${interviewId}/respond`, {
        transcript,
        response_time_sec: responseTimeSec,
        behavioral_snapshot: behavioralSnapshot,
    });
    return response.data;
};

/**
 * Transcribe audio to text using Whisper
 */
export const transcribeAudio = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'audio.webm');
    
    const response = await api.post('/interview/stt', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

/**
 * Synthesize speech from text using Sarvam Bulbul v3 API
 * 
 * Returns WAV audio bytes (ArrayBuffer). Must use responseType: 'arraybuffer'
 * to get binary data instead of coercing to string.
 * 
 * @param {string} text - Interview question or statement text
 * @returns {Promise<ArrayBuffer>} Raw WAV audio bytes
 * @throws Error if TTS service fails (non-blocking to interview flow)
 */
export const synthesizeSpeech = async (text) => {
    let response;
    try {
        response = await api.post(
            `/interview/tts?text=${encodeURIComponent(text)}`,
            null,
            { 
                responseType: 'arraybuffer',  // Critical: fetch as binary, not string
                timeout: 30000,               // 30s timeout for TTS
            }
        );
    } catch (err) {
        // HTTP 4xx/5xx — decode the ArrayBuffer error body for diagnostics
        const status = err.response?.status;
        let detail = `HTTP ${status}`;
        try {
            const decoded = new TextDecoder().decode(err.response?.data);
            const parsed = JSON.parse(decoded);
            detail = parsed.detail || detail;
        } catch (_) {}
        throw new Error(`TTS failed: ${detail}`);
    }

    // Validate successful response
    const contentType = response.headers?.['content-type'] || '';
    const byteLen = response.data?.byteLength ?? 0;
    if (!contentType.includes('audio') || byteLen < 1000) {
        throw new Error(`TTS response invalid: content-type=${contentType}, bytes=${byteLen}`);
    }

    return response.data; // Raw ArrayBuffer of WAV bytes
};

/**
 * Get interview final report
 */
export const getReport = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/report`);
    return response.data;
};

/**
 * Analyze a frame for proctoring (phone detection)
 */
export const analyzeFrame = async (sessionId, frameBlob) => {
    const formData = new FormData();
    formData.append('frame', frameBlob, 'frame.jpg');
    const response = await api.post(`/interview/advanced-proctoring/analyze-frame?session_id=${sessionId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
};

export const logProctoringEvent = async (sessionId, eventType, options = {}) => {
    const body = {
        session_id: sessionId,
        event_type: eventType,
        confidence_score: options.confidence_score,
        face_count: options.face_count,
        metadata: options.metadata || {},
    };
    const response = await api.post(`/interview/advanced-proctoring/log-event`, body);
    return response.data;
};
