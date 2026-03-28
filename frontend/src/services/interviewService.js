import api from './api';

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
    const response = await api.post(
        `/interview/tts?text=${encodeURIComponent(text)}`,
        null,
        { 
            responseType: 'arraybuffer',  // Critical: fetch as binary, not string
            timeout: 30000,               // 30s timeout for TTS
        }
    );
    return response.data; // Raw ArrayBuffer of WAV bytes
};

/**
 * Get interview final report
 */
export const getReport = async (interviewId) => {
    const response = await api.get(`/interview/session/${interviewId}/report`);
    return response.data;
};
