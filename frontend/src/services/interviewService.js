import { RetellWebClient } from 'retell-client-js-sdk';
import api from './api';

/**
 * Retell Web Call Client using official Retell Web SDK (legacy RetellWebClient)
 * Handles real-time voice communication via Retell's Web Call SDK
 *
 * SDK v3 legacy RetellWebClient events (verified from source):
 *   - 'update'              → { event_type: "update", transcript: Utterance[], turntaking?: "agent_turn" | "user_turn" }
 *   - 'agent_start_talking'  → no payload
 *   - 'agent_stop_talking'   → no payload
 *   - 'metadata'             → { event_type: "metadata", metadata: ... }
 *   - 'call_started'         → no payload
 *   - 'call_ended'           → no payload
 *   - 'call_ready'           → analyser component or undefined
 *   - 'error'                → error message string
 *   - 'node_transition'      → node transition event
 *   - 'audio'                → Float32Array (only with emitRawAudioSamples)
 *
 * NOTE: There is NO 'transcript', 'transcript_update', 'data', or
 * 'disconnected' event on the legacy client. Transcript data arrives
 * ONLY through the 'update' event.
 *
 * The 'update' event delivers a FULL cumulative transcript snapshot on every
 * partial STT result. We deduplicate by tracking the last seen transcript
 * fingerprint (length + last utterance content hash).
 */
class RetellWebCallClient {
    constructor() {
        this.client = null;
        this._transcriptListeners = new Set();
        this._agentStartListeners = new Set();
        this._agentStopListeners = new Set();
        this._callEndedListeners = new Set();
        this._errorListeners = new Set();
        
        // Deduplication state for cumulative snapshots
        this._lastTranscriptFingerprint = null;
    }

    /**
     * Normalize the transcript array from a Retell 'update' event.
     *
     * The SDK sends Utterance[] with shape (verified from SDK types):
     *   { role: 'agent'|'user'|'transfer_target', content: string, metadata?: { is_backchannel?, response_id?, interrupt_id? } }
     *
     * IMPORTANT: The base Utterance type has NO 'is_final', NO 'id', NO 'utterance_id'.
     * The SDK sends a FULL cumulative snapshot on every partial STT result.
     *
     * We normalize to a consistent shape for the UI:
     *   { role: 'agent'|'user', content: string, is_final: boolean, utterance_id: string }
     *   
     * Since SDK provides no 'is_final' or stable IDs, we:
     * - Deduplicate by comparing transcript fingerprint (length + last content)
     * - Infer interim/final from turntaking: user_turn = candidate speaking = likely interim
     * - Generate deterministic utterance_id from content hash + index
     */
    /**
     * Normalize the transcript array from a Retell 'update' event.
     *
     * The SDK sends Utterance[] with shape (verified from SDK types):
     *   { role: 'agent'|'user'|'transfer_target', content: string, metadata?: { is_backchannel?, response_id?, interrupt_id? } }
     *
     * We normalize to a consistent shape for the UI:
     *   { role: 'agent'|'user', content: string, is_final: boolean, utterance_id: string }
     *
     * Utterance normalization rules:
     * - Tolerates bare array or { utterances: [...] } wrapper
     * - Case-insensitive role mapping (agent/assistant/bot -> agent, user/candidate -> user)
     * - Extracts content from u.content, u.text, or words array fallback
     * - Filters out empty utterances
     * - Computes is_final: previous turns are always final; last turn is final if speaker no longer has turn
     * - Generates deterministic utterance_id from content hash + index
     */
    static _normalizeTranscript(transcript, turntaking) {
        let rawList = transcript;
        if (!Array.isArray(rawList)) {
            if (rawList && rawList.utterances && Array.isArray(rawList.utterances)) {
                rawList = rawList.utterances;
            } else {
                return [];
            }
        }

        // Filter and map to basic role + content first
        const relevant = [];
        for (const u of rawList) {
            if (!u) continue;
            const rawRole = String(u.role || '').toLowerCase().trim();
            const role = (rawRole === 'agent' || rawRole === 'assistant' || rawRole === 'bot')
                ? 'agent'
                : (rawRole === 'user' || rawRole === 'candidate')
                    ? 'user'
                    : null;
            if (!role) continue;

            let content = '';
            if (typeof u.content === 'string') {
                content = u.content;
            } else if (typeof u.text === 'string') {
                content = u.text;
            } else if (Array.isArray(u.words)) {
                content = u.words
                    .map(w => (typeof w === 'string' ? w : w?.word || w?.content || ''))
                    .filter(Boolean)
                    .join(' ');
            }
            content = content.trim();
            if (!content) continue;

            relevant.push({
                role,
                content,
                metadata: u.metadata || {},
            });
        }

        return relevant.map((u, idx) => {
            // Generate deterministic ID from content hash + index for stability across snapshots
            const contentHash = u.content.split('').reduce((h, c) => Math.imul(31, h) + c.charCodeAt(0) | 0, 0) >>> 0;
            const utteranceId = `utt-${contentHash}-${idx}`;

            // Determine finality:
            // 1. All turns before the last one are completed (final)
            // 2. For the last turn, it is final if the turntaking indicates the speaker is done
            const isLast = (idx === relevant.length - 1);
            let isFinal = true;
            if (isLast) {
                if (u.role === 'user' && turntaking === 'user_turn') {
                    isFinal = false; // candidate actively speaking
                } else if (u.role === 'agent' && turntaking === 'agent_turn') {
                    isFinal = false; // interviewer actively speaking
                }
            }

            return {
                role: u.role,
                content: u.content,
                is_final: isFinal,
                utterance_id: utteranceId,
                metadata: u.metadata,
            };
        });
    }

    /**
     * Compute a fingerprint for deduplicating cumulative transcript snapshots.
     * Uses count + hash of all relevant utterance contents + turntaking to catch in-place STT updates
     * and turn transitions without missing updates.
     */
    static _computeFingerprint(transcript, turntaking) {
        let rawList = transcript;
        if (!Array.isArray(rawList)) {
            if (rawList && rawList.utterances && Array.isArray(rawList.utterances)) {
                rawList = rawList.utterances;
            } else {
                return 'empty';
            }
        }
        if (rawList.length === 0) {
            return 'empty';
        }

        let hash = 0;
        let count = 0;
        for (const u of rawList) {
            if (!u) continue;
            const rawRole = String(u.role || '').toLowerCase().trim();
            if (rawRole !== 'agent' && rawRole !== 'user' && rawRole !== 'assistant' && rawRole !== 'candidate' && rawRole !== 'bot') {
                continue;
            }
            let content = '';
            if (typeof u.content === 'string') content = u.content;
            else if (typeof u.text === 'string') content = u.text;
            else if (Array.isArray(u.words)) {
                content = u.words.map(w => (typeof w === 'string' ? w : w?.word || w?.content || '')).filter(Boolean).join(' ');
            }
            content = content.trim();
            if (!content) continue;

            count++;
            for (let i = 0; i < content.length; i++) {
                hash = Math.imul(31, hash) + content.charCodeAt(i) | 0;
            }
        }
        if (count === 0) {
            return 'empty';
        }
        return `${count}:${hash >>> 0}:${turntaking || ''}`;
    }

    /**
     * Initialize a new Web Call with Retell
     */
    async initialize(callId, accessToken, iceServers) {
        // Create Retell Web Client (legacy, but works with access token)
        this.client = new RetellWebClient();

        // ── 'update' is the ONLY event that carries transcript data ────────
        // Payload: { event_type: "update", transcript: Utterance[], turntaking?: "agent_turn" | "user_turn" }
        this.client.on('update', (update) => {
            const rawTranscript = update?.transcript;
            const utterancesArray = Array.isArray(rawTranscript)
                ? rawTranscript
                : (rawTranscript?.utterances && Array.isArray(rawTranscript.utterances) ? rawTranscript.utterances : []);

            console.log('[RetellDiag] SDK update event fired:', {
                eventType: update?.event_type,
                payloadKeys: update ? Object.keys(update) : [],
                hasTranscriptArray: Array.isArray(rawTranscript),
                utterancesReceived: utterancesArray.length,
                turntaking: update?.turntaking,
                listenersCount: this._transcriptListeners.size,
            });

            // Accept both direct transcript array or wrapper object with 'utterances'
            const transcriptArray = update?.transcript || (update?.utterances && Array.isArray(update.utterances) ? update.utterances : []);
            if (!transcriptArray || transcriptArray.length === 0) {
                console.log('[RetellDiag] No transcript in payload, skipping');
                return;
            }

            // Deduplicate cumulative snapshots using fingerprint
            const fingerprint = RetellWebCallClient._computeFingerprint(transcriptArray, update.turntaking);
            if (fingerprint === this._lastTranscriptFingerprint && fingerprint !== 'empty') {
                console.debug('[RetellDiag] Duplicate transcript fingerprint, skipping:', fingerprint);
                return;
            }
            this._lastTranscriptFingerprint = fingerprint;
            const normalized = RetellWebCallClient._normalizeTranscript(transcriptArray, update.turntaking);

            console.log('[RetellDiag] Normalized transcript:', {
                normalizedCount: normalized.length,
                fingerprint,
                listenersCount: this._transcriptListeners.size,
            });

            if (this._transcriptListeners.size === 0) {
                console.warn('[RetellDiag] Transcript present but NO listeners registered — dropping update');
                return;
            }

            if (normalized.length > 0) {
                for (const listener of this._transcriptListeners) {
                    try {
                        listener(normalized, update.turntaking);
                    } catch (err) {
                        console.error('[RetellDiag] Error in transcript listener:', err);
                    }
                }
            }
        });

        // ── Agent speaking state ───────────────────────────────────────────
        this.client.on('agent_start_talking', () => {
            console.log('[RetellDiag] agent_start_talking event fired');
            for (const listener of this._agentStartListeners) {
                try {
                    listener();
                } catch (err) {
                    console.error('[RetellDiag] Error in agentStart listener:', err);
                }
            }
        });

        this.client.on('agent_stop_talking', () => {
            console.log('[RetellDiag] agent_stop_talking event fired');
            for (const listener of this._agentStopListeners) {
                try {
                    listener();
                } catch (err) {
                    console.error('[RetellDiag] Error in agentStop listener:', err);
                }
            }
        });

        // ── Call lifecycle ─────────────────────────────────────────────────
        this.client.on('call_started', () => {
            console.log('[RetellDiag] call_started');
        });

        this.client.on('call_ready', (analyzer) => {
            console.log('[RetellDiag] call_ready, analyzer:', !!analyzer);
        });

        this.client.on('call_ended', () => {
            console.log('[RetellDiag] call_ended');
            for (const listener of this._callEndedListeners) {
                try {
                    listener({});
                } catch (err) {
                    console.error('[RetellDiag] Error in callEnded listener:', err);
                }
            }
        });

        this.client.on('error', (error) => {
            console.error('[RetellDiag] error:', error);
            for (const listener of this._errorListeners) {
                try {
                    listener(error);
                } catch (err) {
                    console.error('[RetellDiag] Error in error listener:', err);
                }
            }
        });

        this.client.on('metadata', (meta) => {
            console.debug('[RetellDiag] metadata event received');
        });

        // Reset fingerprint state on fresh init
        this._lastTranscriptFingerprint = null;

        // Store connection config for startCall
        this._callConfig = {
            accessToken,
            callId,
            transport: 'gateway',
            call_details: true,
            iceServers: iceServers || [{ urls: 'stun:stun.l.google.com:19302' }],
        };

        console.log('[RetellDiag] Initialized for call:', callId);
        return this;
    }

    /**
     * Start the call (connects WebSocket, WebRTC, starts audio)
     */
    async startCall() {
        if (!this.client || !this._callConfig) {
            throw new Error('Client not initialized. Call initialize() first.');
        }

        try {
            await this.client.startCall(this._callConfig);
            console.log('[Retell] call started');
        } catch (error) {
            console.error('[Retell] failed to start call:', error);
            throw error;
        }
    }

    /**
     * Stop and end the call
     */
    async endCall() {
        if (this.client) {
            try {
                this.client.stopCall();
                console.log('[Retell] call ended');
            } catch (error) {
                console.error('[Retell] error ending call:', error);
            }
        }
        this._lastTranscriptFingerprint = null;
    }

    /**
     * Mute/unmute microphone
     */
    setMuted(muted) {
        if (this.client) {
            if (muted) {
                this.client.mute();
            } else {
                this.client.unmute();
            }
        }
    }

    // Event callbacks with Set management and unsubscribe functions
    onTranscript(callback) {
        if (typeof callback !== 'function') return () => {};
        this._transcriptListeners.add(callback);
        console.log('[Retell] transcript listener registered, total listeners:', this._transcriptListeners.size);
        return () => {
            this._transcriptListeners.delete(callback);
            console.log('[Retell] transcript listener removed, total listeners:', this._transcriptListeners.size);
        };
    }

    onAgentStartTalking(callback) {
        if (typeof callback !== 'function') return () => {};
        this._agentStartListeners.add(callback);
        return () => {
            this._agentStartListeners.delete(callback);
        };
    }

    onAgentStopTalking(callback) {
        if (typeof callback !== 'function') return () => {};
        this._agentStopListeners.add(callback);
        return () => {
            this._agentStopListeners.delete(callback);
        };
    }

    onCallEnded(callback) {
        if (typeof callback !== 'function') return () => {};
        this._callEndedListeners.add(callback);
        return () => {
            this._callEndedListeners.delete(callback);
        };
    }

    onError(callback) {
        if (typeof callback !== 'function') return () => {};
        this._errorListeners.add(callback);
        return () => {
            this._errorListeners.delete(callback);
        };
    }

    clearListeners() {
        this._transcriptListeners.clear();
        this._agentStartListeners.clear();
        this._agentStopListeners.clear();
        this._callEndedListeners.clear();
        this._errorListeners.clear();
    }
}

export const retellClient = new RetellWebCallClient();

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
 * Get list of available interviewers
 */
export const getInterviewers = async () => {
    const response = await api.get('/interview/interviewers');
    return response.data;
};

/**
 * Start an interview session with an approved pool
 */
export const startInterview = async (poolId, interviewerId = null, voiceMode = null) => {
    const params = new URLSearchParams({ pool_id: String(poolId) });
    if (interviewerId) params.set('interviewer_id', interviewerId);
    if (voiceMode) params.set('voice_mode', voiceMode);
    const url = `/interview/session/start?${params.toString()}`;
    const response = await api.post(url);
    return response.data;
};

export const getInterviewVoiceModes = async () => {
    const response = await api.get('/interview/voice-modes');
    return response.data;
};

/**
 * Get the next interview question
 */
export const getNextQuestion = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/next`);
    return response.data;
};

export const getInterviewStatus = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/status`);
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
 */
export const synthesizeSpeech = async (text) => {
    let response;
    try {
        response = await api.post(
            `/interview/tts?text=${encodeURIComponent(text)}`,
            null,
            { 
                responseType: 'arraybuffer',
                timeout: 30000,
            }
        );
    } catch (err) {
        const status = err.response?.status;
        let detail = `HTTP ${status}`;
        try {
            const decoded = new TextDecoder().decode(err.response?.data);
            const parsed = JSON.parse(decoded);
            detail = parsed.detail || detail;
        } catch (_) {}
        throw new Error(`TTS failed: ${detail}`);
    }

    const contentType = response.headers?.['content-type'] || '';
    const byteLen = response.data?.byteLength ?? 0;
    if (!contentType.includes('audio') || byteLen < 1000) {
        throw new Error(`TTS response invalid: content-type=${contentType}, bytes=${byteLen}`);
    }

    return response.data;
};

/**
 * Get interview final report
 */
export const getReport = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/report`);
    return response.data;
};

export const saveRetellTranscript = async (interviewId, transcript) => {
    const response = await api.post(
        `/interview/session/${interviewId}/retell-transcript`,
        { transcript }
    );
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

/**
 * Get list of interviewers for admin management (includes inactive)
 */
export const getInterviewersForManagement = async (activeOnly = false, limit = 50, offset = 0) => {
    const params = new URLSearchParams({
        active_only: activeOnly.toString(),
        limit: limit.toString(),
        offset: offset.toString(),
    });
    const response = await api.get(`/interview/interviewers/manage?${params}`);
    return response.data;
};

/**
 * Get a specific dynamic interviewer by ID
 */
export const getInterviewerById = async (interviewerId) => {
    const response = await api.get(`/interview/interviewers/manage/${interviewerId}`);
    return response.data;
};

/**
 * Create a new dynamic interviewer with Retell integration
 */
export const createInterviewer = async (interviewerData) => {
    const response = await api.post('/interview/interviewers', interviewerData);
    return response.data;
};

/**
 * Update an existing dynamic interviewer
 */
export const updateInterviewer = async (interviewerId, interviewerData) => {
    const response = await api.patch(`/interview/interviewers/manage/${interviewerId}`, interviewerData);
    return response.data;
};

/**
 * Deactivate (soft delete) a dynamic interviewer
 */
export const deactivateInterviewer = async (interviewerId) => {
    const response = await api.delete(`/interview/interviewers/manage/${interviewerId}`);
    return response.data;
};

/**
 * Preview a voice using the TTS service
 */
export const previewVoice = async (voiceId, text = "Hello, this is a preview of my voice.") => {
    const response = await api.post(`/interview/interviewers/preview-voice?voice_id=${encodeURIComponent(voiceId)}&text=${encodeURIComponent(text)}`);
    return response.data;
};

/**
 * Get available voices for interviewer creation
 */
export const getAvailableVoices = async () => {
    const response = await api.get('/interview/interviewers/voices');
    return response.data;
};