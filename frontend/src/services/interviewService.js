import { RetellWebClient } from 'retell-client-js-sdk';
import api from './api';

/**
 * Retell Web Call Client using official Retell Web SDK (legacy RetellWebClient)
 * Handles real-time voice communication via Retell's Web Call SDK
 */
class RetellWebCallClient {
    constructor() {
        this.client = null;
        this.onTranscriptCallback = null;
        this.onCallEndedCallback = null;
        this.onErrorCallback = null;
    }

    /**
     * Initialize a new Web Call with Retell
     */
    async initialize(callId, accessToken, iceServers) {
        // Create Retell Web Client (legacy, but works with access token)
        this.client = new RetellWebClient();

        // Set up event listeners on the client
        this.client.on('callReady', (analyzer) => {
            console.log('Retell call ready, analyzer:', !!analyzer);
        });

        // Legacy RetellWebClient emits 'transcript' events directly
        this.client.on('transcript', (transcript) => {
            console.log('Retell SDK transcript event:', transcript);
            if (this.onTranscriptCallback) {
                this.onTranscriptCallback(transcript);
            }
        });

        this.client.on('data', (event) => {
            console.log('Retell SDK data event:', JSON.stringify(event).substring(0, 500));
            // Handle transcript updates - multiple possible event types
            if ((event.type === 'transcript' || event.type === 'update' || event.type === 'transcript_update') && event.transcript) {
                if (this.onTranscriptCallback) {
                    this.onTranscriptCallback(event.transcript);
                }
            }
        });

        this.client.on('disconnected', () => {
            console.log('Retell SDK disconnected');
            if (this.onCallEndedCallback) this.onCallEndedCallback({});
        });

        this.client.on('error', (error) => {
            console.error('Retell SDK error:', error);
            if (this.onErrorCallback) this.onErrorCallback(error);
        });

        // Also listen for other possible events
        this.client.on('agent_start_talking', () => console.log('Agent started talking'));
        this.client.on('agent_stop_talking', () => console.log('Agent stopped talking'));
        this.client.on('metadata', (meta) => console.log('Metadata:', meta));
        this.client.on('call_ended', (data) => console.log('Call ended event:', JSON.stringify(data)));
        this.client.on('end', (data) => console.log('End event:', JSON.stringify(data)));

        // Store connection config for startCall
        // Backend returns transport: "gateway" - must specify explicitly
        this._callConfig = {
            accessToken,
            callId,
            transport: 'gateway',
            iceServers: iceServers || [{ urls: 'stun:stun.l.google.com:19302' }],
        };

        console.log('Retell SDK initialized for call:', callId);
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
            console.log('Retell call started');
        } catch (error) {
            console.error('Failed to start Retell call:', error);
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
                console.log('Retell call ended');
            } catch (error) {
                console.error('Error ending call:', error);
            }
        }
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

    // Event callbacks
    onTranscript(callback) { this.onTranscriptCallback = callback; }
    onCallEnded(callback) { this.onCallEndedCallback = callback; }
    onError(callback) { this.onErrorCallback = callback; }
}

// Export singleton instance
export const retellClient = new RetellWebCallClient();


/**
 * Upload a resume PDF and generate personalized question pool
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