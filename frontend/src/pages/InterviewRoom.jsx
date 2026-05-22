import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getNextQuestion,
    submitResponse,
    transcribeAudio,
    synthesizeSpeech,
} from '../services/interviewService';
import AdvancedProctoringMonitor from '../components/AdvancedProctoringMonitor';
import ProctoringVideoDisplay from '../components/ProctoringVideoDisplay';
import useAdvancedProctoring from '../hooks/useAdvancedProctoring';
import { Toast } from '../components/Toast';
import api from '../services/api';

const STATES = {
    LOADING: 'loading',
    READY: 'ready',
    LISTENING: 'listening',
    PROCESSING: 'processing',
    COMPLETE: 'complete',
};

export default function InterviewRoom() {
    const [roomState, setRoomState] = useState(STATES.LOADING);
    const [currentQuestion, setCurrentQuestion] = useState(null);
    const [turnNumber, setTurnNumber] = useState(0);
    const [totalTurns] = useState(10);
    const [difficulty, setDifficulty] = useState(null);
    const [phase, setPhase] = useState('HR');
    const [transcript, setTranscript] = useState('');
    const [recordingSeconds, setRecordingSeconds] = useState(0);
    const [toast, setToast] = useState(null);
    const [questionScore, setQuestionScore] = useState(null);
    const [isRecording, setIsRecording] = useState(false);
    const [liveTip, setLiveTip] = useState(''); // Real-time feedback tip
    
    const navigate = useNavigate();
    const proctoring = useAdvancedProctoring({
        idleThreshold: 30,
        roundType: 'INTERVIEW',
    });
    
    const interviewId = localStorage.getItem('interview_id');
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const startTimeRef = useRef(null);
    const timerIntervalRef = useRef(null);
    const audioContextRef = useRef(null);
    const audioSourceRef = useRef(null);
    const tipPollingRef = useRef(null); // Real-time feedback polling

    // Check if interview_id exists
    useEffect(() => {
        if (!interviewId) {
            console.error('No interview_id found in localStorage');
            setToast({
                type: 'error',
                message: 'Interview session not found. Redirecting to dashboard...',
            });
            setTimeout(() => {
                navigate('/dashboard');
            }, 3000);
        } else {
            console.log('Interview ID found:', interviewId);
        }
    }, [interviewId, navigate]);

    // Initialize Web Audio API context
    const getAudioContext = () => {
        if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        return audioContextRef.current;
    };

    /**
     * Play audio from ArrayBuffer with Web Audio API
     * Returns promise that resolves when playback finishes
     */
    const playAudio = async (arrayBuffer) => {
        try {
            const audioContext = getAudioContext();
            
            // Decode audio data
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
            
            // Create source and connect to destination
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            
            // Store reference for cleanup
            audioSourceRef.current = source;
            
            // Play and return promise that resolves on end
            source.start(0);
            
            return new Promise((resolve) => {
                source.onended = () => {
                    audioSourceRef.current = null;
                    resolve();
                };
            });
        } catch (error) {
            console.warn('Audio playback failed:', error);
            // Non-blocking error — interview continues
            throw error;
        }
    };

    
    /**
     * TTS with retry logic (retry once, then fallback to text)
     * Demo-safe: won't crash on TTS failures
     */
    const playTTSWithRetry = useCallback(async (text) => {
        try {
            const audioBytes = await synthesizeSpeech(text);
            await playAudio(audioBytes);
        } catch (firstError) {
            console.warn('TTS failed, retrying once...', firstError);
            try {
                // Wait a moment before retry
                await new Promise(r => setTimeout(r, 500));
                const audioBytes = await synthesizeSpeech(text);
                await playAudio(audioBytes);
            } catch (secondError) {
                console.error('TTS failed twice → fallback to text display', secondError);
                // Fallback: just show toast, question is visible on screen
                setToast({
                    type: 'info',
                    message: 'Audio unavailable. Please read the question on screen.',
                });
            }
        }
    }, []);
    
    // Fetch next question (MOVED UP - declared before use in startup)
    const fetchNextQuestion = useCallback(async () => {
        if (!interviewId) {
            console.error('Cannot fetch question: No interview ID');
            setToast({
                type: 'error',
                message: 'Interview session not found',
            });
            return;
        }
        
        try {
            console.log('Fetching next question for interview:', interviewId);
            const res = await getNextQuestion(interviewId);
            console.log('Question received:', res);
            
            setCurrentQuestion(res.question);
            setTurnNumber(res.turn_number);
            setDifficulty(res.difficulty);
            setPhase(res.phase);
            setTranscript('');
            setQuestionScore(null);
            setRoomState(STATES.READY);
            
            // Play question via TTS
            try {
                const audioBytes = await synthesizeSpeech(res.question);
                try {
                    await playAudio(audioBytes);
                } catch (audioError) {
                    // TTS failed but interview continues
                    console.warn('Audio playback failed, showing text instead');
                }
            } catch (ttsError) {
                console.warn('TTS failed:', ttsError);
                // Interview continues, question visible on screen
            }
        } catch (error) {
            console.error('Failed to fetch next question:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to load next question',
            });
            setRoomState(STATES.READY);
        }
    }, [interviewId]);
    
    // Startup: play intro, then fetch first question
    useEffect(() => {
        if (!interviewId) {
            console.log('Skipping startup: No interview ID');
            return;
        }
        
        const startup = async () => {
            try {
                console.log('Starting interview room...');
                const startupText =
                    'Welcome. I am your AI interviewer. Please introduce yourself and tell me about your background.';
                // Use retry-enabled TTS
                await playTTSWithRetry(startupText);
                fetchNextQuestion();
            } catch (error) {
                console.error('Startup error:', error);
                fetchNextQuestion();
            }
        };
        
        startup();
        
        return () => {
            if (timerIntervalRef.current) {
                clearInterval(timerIntervalRef.current);
            }
            // Stop any playing audio on unmount
            if (audioSourceRef.current) {
                try {
                    audioSourceRef.current.stop();
                } catch (e) {
                    // Ignore - source may already be stopped
                }
            }
        };
    }, [interviewId, playTTSWithRetry, fetchNextQuestion]);
    
    // ═══════════════════════════════════════════════════════════════════════
    // REAL-TIME FEEDBACK POLLING (every 3 seconds during recording)
    // Uses behaviorSnapshotRef to avoid stale closure issues
    // ═══════════════════════════════════════════════════════════════════════
    useEffect(() => {
        // Only poll when recording
        if (!isRecording || !interviewId) {
            if (tipPollingRef.current) {
                clearInterval(tipPollingRef.current);
                tipPollingRef.current = null;
            }
            return;
        }
        
        // Start polling for real-time feedback
        tipPollingRef.current = setInterval(async () => {
            try {
                // Get current snapshot from ref (avoids stale closure)
                const snapshot = proctoring.getBehaviorSnapshot 
                    ? proctoring.getBehaviorSnapshot()
                    : {
                        face_detected: proctoring.metrics?.faceDetected ?? true,
                        eye_contact_pct: proctoring.metrics?.eyeContactPercent ?? 0.5,
                        head_stability: proctoring.metrics?.headStability ?? 0.5,
                        looking_away_count: proctoring.metrics?.lookingAwayCount ?? 0,
                        response_time_sec: recordingSeconds,
                    };
                
                const res = await api.post('/interview/realtime-feedback', {
                    session_id: parseInt(interviewId, 10),
                    ...snapshot,
                });
                
                if (res.data?.tip) {
                    setLiveTip(res.data.tip);
                }
            } catch (error) {
                // Silent fail - feedback is non-critical
                console.debug('Realtime feedback poll failed:', error);
            }
        }, 3000);
        
        return () => {
            if (tipPollingRef.current) {
                clearInterval(tipPollingRef.current);
                tipPollingRef.current = null;
            }
        };
    }, [isRecording, interviewId, proctoring, recordingSeconds]);
    
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false,
            });
            
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];
            
            mediaRecorder.ondataavailable = (e) => {
                audioChunksRef.current.push(e.data);
            };
            
            mediaRecorder.start();
            startTimeRef.current = Date.now();
            setIsRecording(true);
            setRoomState(STATES.LISTENING);
            
            setRecordingSeconds(0);
            timerIntervalRef.current = setInterval(() => {
                setRecordingSeconds((s) => s + 1);
            }, 1000);
        } catch (error) {
            setToast({
                type: 'error',
                message: 'Failed to access microphone',
            });
        }
    };
    
    const stopAndSubmit = async () => {
        try {
            mediaRecorderRef.current.stop();
            clearInterval(timerIntervalRef.current);
            setIsRecording(false);
            setLiveTip(''); // Clear live tip
            setRoomState(STATES.PROCESSING);
            
            await new Promise((resolve) => {
                mediaRecorderRef.current.onstop = resolve;
            });
            
            const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            const responseTimeSec = (Date.now() - startTimeRef.current) / 1000;
            
            let recognizedTranscript = '';
            try {
                const sttRes = await transcribeAudio(audioBlob);
                recognizedTranscript = sttRes.transcript || '';
            } catch (error) {
                console.error('STT failed:', error);
            }
            
            setTranscript(recognizedTranscript);
            
            // ═══════════════════════════════════════════════════════════════
            // BEHAVIORAL SNAPSHOT - Use proctoring.metrics (reactive state)
            // Falls back to defaults if metrics unavailable
            // ═══════════════════════════════════════════════════════════════
            const behavioralSnapshot = {
                eye_contact_pct: proctoring.metrics?.eyeContactPercent ?? 0.5,
                head_stability: proctoring.metrics?.headStability ?? 0.5,
                face_detected: proctoring.metrics?.faceDetected ?? true,
                looking_away_count: proctoring.metrics?.lookingAwayCount ?? 0,
                response_time_sec: responseTimeSec,
                dominant_emotion: proctoring.metrics?.dominantEmotion ?? 'neutral',
            };
            
            const submitRes = await submitResponse(
                interviewId,
                recognizedTranscript,
                responseTimeSec,
                behavioralSnapshot
            );
            
            // Reset metrics for next recording
            if (proctoring.resetMetrics) {
                proctoring.resetMetrics();
            }
            
            if (submitRes.is_complete) {
                setQuestionScore(submitRes.score);
                setRoomState(STATES.COMPLETE);
            } else {
                setTranscript('');
                setTimeout(fetchNextQuestion, 2000);
            }
        } catch (error) {
            setToast({
                type: 'error',
                message: 'Failed to submit response',
            });
            setRoomState(STATES.READY);
        }
    };
    
    const handleViewReport = () => {
        navigate(`/interview/report/${interviewId}`);
    };

    // Get phase color
    const getPhaseColor = (p) => {
        switch (p?.toUpperCase()) {
            case 'HR':
                return 'bg-purple-600';
            case 'TECHNICAL':
                return 'bg-blue-600';
            default:
                return 'bg-slate-600';
        }
    };

    // Get score color
    const getScoreColor = (score) => {
        if (!score) return 'text-slate-400';
        if (score >= 0.7) return 'text-green-400';
        if (score >= 0.4) return 'text-amber-400';
        return 'text-red-400';
    };
    
    return (
        <div className="h-screen bg-slate-950 text-white flex flex-col overflow-hidden">
            {/* Top Bar */}
            <div className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-8">
                {/* Logo */}
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-sm">AI</span>
                    </div>
                    <span className="font-semibold text-sm">Interview</span>
                </div>

                {/* Turn Indicator - 10 dots */}
                <div className="flex items-center gap-2">
                    {Array.from({ length: 10 }).map((_, idx) => (
                        <div
                            key={idx}
                            className={`w-2 h-2 rounded-full transition-all ${
                                idx < turnNumber ? 'bg-green-500' : 'bg-slate-700'
                            }`}
                        ></div>
                    ))}
                </div>

                {/* Phase Badge & Timer & REC */}
                <div className="flex items-center gap-4">
                    {/* Phase Badge */}
                    <div className={`px-4 py-1.5 rounded-full text-xs font-semibold text-white ${getPhaseColor(phase)}`}>
                        {phase?.toUpperCase() || 'INTERVIEW'}
                    </div>

                    {/* Timer (show during recording) */}
                    {isRecording && (
                        <div className="text-sm font-mono text-slate-400">
                            {Math.floor(recordingSeconds / 60)}:{String(recordingSeconds % 60).padStart(2, '0')}
                        </div>
                    )}

                    {/* REC Indicator (show during recording) */}
                    {isRecording && (
                        <div className="flex items-center gap-1.5 bg-red-900 px-3 py-1.5 rounded-full">
                            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                            <span className="text-xs font-bold text-red-300">REC</span>
                        </div>
                    )}
                </div>
            </div>
            
            {/* Main Container */}
            <div className="flex-1 flex gap-6 p-6 overflow-hidden">
                {/* Left Sidebar - Proctoring (w-72) */}
                <div className="w-72 flex flex-col gap-4 overflow-y-auto">
                    {/* Webcam */}
                    <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-900">
                        <ProctoringVideoDisplay 
                            videoRef={proctoring.videoRef}
                            canvasRef={proctoring.canvasRef}
                            isMonitoring={proctoring.isMonitoring}
                            detectionResults={proctoring.detectionResults}
                        />
                    </div>

                    {/* Proctoring Monitor */}
                    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                        <AdvancedProctoringMonitor 
                            violations={proctoring.violations || []}
                            riskScore={proctoring.riskScore || 0}
                            detectionResults={proctoring.detectionResults}
                            isMonitoring={proctoring.isMonitoring}
                        />
                    </div>

                    {/* Behavioral Metrics */}
                    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4">Behavioral Metrics</h3>
                        
                        {/* Eye Contact */}
                        <div className="mb-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400">Eye Contact</span>
                                <span className={`text-xs font-bold ${
                                    (proctoring.metrics?.eyeContactPercent ?? 0.5) > 0.7 ? 'text-green-400' : 'text-amber-400'
                                }`}>
                                    {Math.round((proctoring.metrics?.eyeContactPercent ?? 0.5) * 100)}%
                                </span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${
                                        (proctoring.metrics?.eyeContactPercent ?? 0.5) > 0.7 ? 'bg-green-500' : 'bg-amber-500'
                                    }`}
                                    style={{ width: `${(proctoring.metrics?.eyeContactPercent ?? 0.5) * 100}%` }}
                                ></div>
                            </div>
                        </div>

                        {/* Head Stability (renamed from Engagement) */}
                        <div className="mb-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400">Head Stability</span>
                                <span className={`text-xs font-bold ${
                                    (proctoring.metrics?.headStability ?? 0.5) > 0.6 ? 'text-blue-400' : 'text-amber-400'
                                }`}>
                                    {Math.round((proctoring.metrics?.headStability ?? 0.5) * 100)}%
                                </span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${
                                        (proctoring.metrics?.headStability ?? 0.5) > 0.6 ? 'bg-blue-500' : 'bg-amber-500'
                                    }`}
                                    style={{ width: `${(proctoring.metrics?.headStability ?? 0.5) * 100}%` }}
                                ></div>
                            </div>
                        </div>

                        {/* Face Detected Indicator */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs text-slate-400">Face Detection</span>
                                <span className={`text-xs font-bold ${
                                    proctoring.metrics?.faceDetected ? 'text-green-400' : 'text-red-400'
                                }`}>
                                    {proctoring.metrics?.faceDetected ? 'Detected' : 'Not Found'}
                                </span>
                            </div>
                            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${
                                        proctoring.metrics?.faceDetected ? 'bg-green-500' : 'bg-red-500'
                                    }`}
                                    style={{ width: proctoring.metrics?.faceDetected ? '100%' : '20%' }}
                                ></div>
                            </div>
                        </div>
                    </div>
                </div>
                
                {/* Main Panel - Question & Controls */}
                <div className="flex-1 flex flex-col justify-between overflow-hidden">
                    {/* Question Card */}
                    <div className="bg-slate-900 rounded-2xl border border-slate-800 p-8 overflow-auto flex-1 mb-6">
                        {roomState === STATES.LOADING && (
                            <div className="flex flex-col items-center justify-center h-full">
                                <div className="w-12 h-12 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mb-4"></div>
                                <p className="text-slate-400 text-center">Preparing your interview...</p>
                            </div>
                        )}
                        
                        {(roomState === STATES.READY || roomState === STATES.LISTENING || roomState === STATES.PROCESSING) && (
                            <>
                                <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-800">
                                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Question {turnNumber}</span>
                                    <div className="flex items-center gap-2">
                                        {difficulty && (
                                            <span className="px-2 py-1 bg-slate-800 rounded-full text-xs font-medium text-slate-400">
                                                {difficulty}
                                            </span>
                                        )}
                                        {phase && (
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium text-white ${getPhaseColor(phase)} bg-opacity-20`}>
                                                {phase}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                
                                <p className="text-2xl font-semibold leading-relaxed text-slate-100 mb-8">
                                    {currentQuestion}
                                </p>
                                
                                {transcript && (
                                    <div className="mt-8 pt-6 border-t border-slate-800">
                                        <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Your Response</p>
                                        <p className="text-base text-slate-300 leading-relaxed">{transcript}</p>
                                    </div>
                                )}
                            </>
                        )}
                        
                        {roomState === STATES.COMPLETE && (
                            <div className="flex flex-col items-center justify-center h-full text-center">
                                <div className="w-20 h-20 rounded-full bg-green-500 bg-opacity-20 flex items-center justify-center mb-6 animate-bounce">
                                    <span className="text-4xl">✅</span>
                                </div>
                                <h2 className="text-3xl font-bold text-slate-100 mb-3">Interview Complete!</h2>
                                <p className="text-slate-400 text-base max-w-sm">
                                    Thank you for completing all interview rounds. Your responses are being evaluated.
                                </p>
                            </div>
                        )}
                    </div>
                    
                    {/* Control Panel */}
                    <div className="bg-slate-900 rounded-2xl border border-slate-800 p-8">
                        {roomState === STATES.READY && (
                            <div className="text-center">
                                <p className="text-slate-400 text-base mb-6">Ready to answer?</p>
                                <button
                                    onClick={startRecording}
                                    className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-bold py-4 rounded-xl transition-all duration-150 text-lg flex items-center justify-center gap-2"
                                >
                                    <span>🎤</span>
                                    Start Speaking
                                </button>
                            </div>
                        )}
                        
                        {roomState === STATES.LISTENING && (
                            <div className="text-center">
                                <div className="flex items-center justify-center gap-3 mb-6">
                                    <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                                    <span className="font-semibold text-red-400">Recording your answer...</span>
                                </div>
                                <div className="text-4xl font-mono font-bold text-slate-300 mb-6">
                                    {Math.floor(recordingSeconds / 60)}:{String(recordingSeconds % 60).padStart(2, '0')}
                                </div>
                                
                                {/* Real-Time Feedback Tip */}
                                {liveTip && (
                                    <div className="mb-6 px-4 py-3 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                                        <p className="text-sm text-blue-300 flex items-center justify-center gap-2">
                                            <span>💡</span>
                                            {liveTip}
                                        </p>
                                    </div>
                                )}
                                
                                <button
                                    onClick={stopAndSubmit}
                                    className="w-full bg-slate-800 hover:bg-slate-700 active:scale-[0.98] text-white font-bold py-4 rounded-xl transition-all duration-150 text-base"
                                >
                                    Done Speaking
                                </button>
                            </div>
                        )}
                        
                        {roomState === STATES.PROCESSING && (
                            <div className="text-center">
                                <div className="w-12 h-12 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
                                <p className="text-slate-400">Analyzing your response...</p>
                            </div>
                        )}
                        
                        {roomState === STATES.COMPLETE && (
                            <div className="text-center">
                                {questionScore && (
                                    <div className="mb-6 flex items-center justify-center gap-2">
                                        <span className="text-sm text-slate-400">Overall Score:</span>
                                        <span className={`text-3xl font-bold ${getScoreColor(questionScore)}`}>
                                            {Math.round(questionScore * 100)}%
                                        </span>
                                    </div>
                                )}
                                <button
                                    onClick={handleViewReport}
                                    className="w-full bg-green-600 hover:bg-green-700 active:scale-[0.98] text-white font-bold py-4 rounded-xl transition-all duration-150 text-base flex items-center justify-center gap-2"
                                >
                                    <span>📊</span>
                                    View Full Report
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
            
            {/* Toast */}
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
        </div>
    );
}
