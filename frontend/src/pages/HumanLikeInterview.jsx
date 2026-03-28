import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getNextQuestion,
    submitResponse,
    transcribeAudio,
    synthesizeSpeech,
} from '../services/interviewService';
import useBasicProctoring from '../hooks/useBasicProctoring';
import { Toast } from '../components/Toast';

const STATES = {
    LOADING: 'loading',
    LISTENING_TO_AI: 'listening_to_ai',
    WAITING_FOR_CANDIDATE: 'waiting_for_candidate',
    CANDIDATE_SPEAKING: 'candidate_speaking',
    PROCESSING_RESPONSE: 'processing_response',
    COMPLETE: 'complete',
};

export default function HumanLikeInterview() {
    const [interviewState, setInterviewState] = useState(STATES.LOADING);
    const [currentQuestion, setCurrentQuestion] = useState('');
    const [isFollowup, setIsFollowup] = useState(false);
    const [followupType, setFollowupType] = useState(null);
    const [turnNumber, setTurnNumber] = useState(0);
    const [totalTurns] = useState(10);
    const [phase, setPhase] = useState('HR');
    const [currentDifficulty, setCurrentDifficulty] = useState('MEDIUM');
    const [recordingSeconds, setRecordingSeconds] = useState(0);
    const [toast, setToast] = useState(null);
    const [summary, setSummary] = useState(null);

    const navigate = useNavigate();
    const proctoring = useBasicProctoring();

    const interviewId = localStorage.getItem('interview_id');
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const startTimeRef = useRef(null);
    const timerIntervalRef = useRef(null);
    const audioContextRef = useRef(null);
    const currentAudioRef = useRef(null);
    const isPlayingRef = useRef(false);

    // ── Audio control (useRef-based, overlap-safe) ─────────────────────
    const audioRequestIdRef = useRef(0);

    const getAudioContext = () => {
        if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        return audioContextRef.current;
    };

    const playAudio = async (text) => {
        // Stop any currently playing audio first
        if (currentAudioRef.current) {
            try {
                currentAudioRef.current.stop();
            } catch(e) {
                // Already stopped — safe to ignore
            }
            currentAudioRef.current = null;
        }

        // Claim this request with a unique ID
        // Any previous in-flight request becomes stale
        const requestId = ++audioRequestIdRef.current;

        try {
            // Network request — may take 600ms+
            const arrayBuffer = await synthesizeSpeech(text);

            // Check 1: after network await
            // If a newer playAudio call started while we waited,
            // our response is stale — discard silently
            if (requestId !== audioRequestIdRef.current) return;

            const audioContext = getAudioContext();

            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));

            // Check 2: after decode await
            // Check again in case another call started during decode
            if (requestId !== audioRequestIdRef.current) return;

            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            
            currentAudioRef.current = source;
            source.start(0);

            return new Promise((resolve) => {
                source.onended = () => {
                    currentAudioRef.current = null;
                    resolve();
                };
            });
        } catch (error) {
            currentAudioRef.current = null;
            // Non-blocking — interview continues without audio
            setToast({ type: 'error', message: "Audio unavailable. Read the question on screen." });
            console.warn('Audio unavailable:', error.message);
        }
    };

    // ── Cleanup on unmount ─────────────────────────────────────────────
    useEffect(() => {
        return () => {
            // Invalidate any in-flight audio requests on unmount
            audioRequestIdRef.current = Number.MAX_SAFE_INTEGER;
            
            if (currentAudioRef.current) {
                try { 
                    currentAudioRef.current.stop(); 
                } catch (e) { }
                currentAudioRef.current = null;
            }
            if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
            if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
                audioContextRef.current.close();
            }
            if (proctoring.stopCamera) proctoring.stopCamera();
        };
    }, []);

    // ── Initial load: fetch first question via GET /next ───────────────
    useEffect(() => {
        if (!interviewId) {
            setToast({ type: 'error', message: 'Interview session not found' });
            setTimeout(() => navigate('/dashboard'), 3000);
            return;
        }

        let isMounted = true;

        const startup = async () => {
            if (!isMounted) return;

            try {
                setInterviewState(STATES.LISTENING_TO_AI);

                // AI introduction
                const introText = "Hello! I'm your AI interviewer today. Let's have a natural conversation about your background and skills. Are you ready? Let's begin.";
                try {
                    await playAudio(introText);
                } catch (e) {
                    console.warn('Intro TTS unavailable');
                }

                // Fetch first question (ONLY call to /next)
                if (isMounted) {
                    const res = await getNextQuestion(interviewId);
                    setCurrentQuestion(res.question);
                    setTurnNumber(res.turn_number);
                    setPhase(res.phase);
                    setCurrentDifficulty(res.difficulty);
                    setIsFollowup(false);

                    // Speak the first question
                    const questionText = `Let's start with an easy one. ${res.question}`;
                    try {
                        await playAudio(questionText);
                    } catch (e) {
                        console.warn('Question TTS failed');
                    }

                    if (isMounted) setInterviewState(STATES.WAITING_FOR_CANDIDATE);
                }
            } catch (error) {
                console.error('Startup error:', error);
                if (isMounted) {
                    setToast({ type: 'error', message: 'Failed to load first question' });
                }
            }
        };

        startup();
        return () => { isMounted = false; };
    }, []);

    // ── Recording ──────────────────────────────────────────────────────
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
            setInterviewState(STATES.CANDIDATE_SPEAKING);

            setRecordingSeconds(0);
            timerIntervalRef.current = setInterval(() => {
                setRecordingSeconds((s) => s + 1);
            }, 1000);
        } catch (error) {
            setToast({ type: 'error', message: 'Failed to access microphone' });
        }
    };

    // ── Submit handler (single-response contract) ──────────────────────
    const stopAndSubmit = async () => {
        try {
            mediaRecorderRef.current.stop();
            clearInterval(timerIntervalRef.current);
            setInterviewState(STATES.PROCESSING_RESPONSE);

            await new Promise((resolve) => {
                mediaRecorderRef.current.onstop = resolve;
            });

            const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
            const responseTimeSec = (Date.now() - startTimeRef.current) / 1000;

            // STT
            let transcript = "";
            try {
                const sttRes = await transcribeAudio(audioBlob);
                // Depending on the axios setup, it may be sttRes.data.transcript or sttRes.transcript. 
                // Using the exact format requested by the user:
                transcript = sttRes.data ? sttRes.data.transcript : (sttRes.transcript || "");
            } catch (err) {
                if (err.response?.status === 429) {
                    // Groq rate limited — wait 2 seconds and retry once
                    await new Promise(res => setTimeout(res, 2000));
                    try {
                        const retryRes = await transcribeAudio(audioBlob);
                        transcript = retryRes.data ? retryRes.data.transcript : (retryRes.transcript || "");
                    } catch {
                        transcript = "";
                        setToast({ type: 'error', message: "Transcription unavailable. Submitting empty answer." });
                    }
                } else {
                    transcript = "";
                }
            }

            // Behavioral snapshot
            const behavioralSnapshot = {
                eye_contact_pct: 0.5,
                head_stability: 0.7,
            };

            // Submit to /respond — single response contains everything
            const data = await submitResponse(
                interviewId,
                transcript,
                responseTimeSec,
                behavioralSnapshot,
            );

            // ── Handle action ──────────────────────────────────────────

            if (data.action === 'RETRY') {
                // Silence retry — stay on same question
                setInterviewState(STATES.LISTENING_TO_AI);
                try { await playAudio(data.message); } catch (e) { }
                setInterviewState(STATES.WAITING_FOR_CANDIDATE);
            }

            else if (data.action === 'FOLLOWUP') {
                // Follow-up — stay on same turn number
                setInterviewState(STATES.LISTENING_TO_AI);
                setCurrentQuestion(data.message);
                setIsFollowup(true);
                setFollowupType(data.followup_type);
                try { await playAudio(data.message); } catch (e) { }
                setInterviewState(STATES.WAITING_FOR_CANDIDATE);
            }

            else if (data.action === 'NEXT') {
                // Next question — all data in this response
                setInterviewState(STATES.LISTENING_TO_AI);
                setIsFollowup(false);
                setFollowupType(null);

                if (data.next_question) {
                    setCurrentQuestion(data.next_question.text);
                    setCurrentDifficulty(data.next_question.difficulty);
                    setTurnNumber(data.next_question.turn_number);
                    setPhase(data.next_question.phase);
                }

                // Brain message includes transition + next question
                try { await playAudio(data.message); } catch (e) { }
                setInterviewState(STATES.WAITING_FOR_CANDIDATE);
            }

            else if (data.action === 'COMPLETE') {
                // Interview complete
                setInterviewState(STATES.LISTENING_TO_AI);
                setSummary(data.interview_summary);

                // Stop camera
                if (proctoring.stopCamera) proctoring.stopCamera();

                try { await playAudio(data.message); } catch (e) { }
                setInterviewState(STATES.COMPLETE);
            }

        } catch (error) {
            console.error('Submit error:', error);
            setToast({ type: 'error', message: 'Failed to submit response' });
            setInterviewState(STATES.WAITING_FOR_CANDIDATE);
        }
    };

    const handleViewReport = () => {
        navigate(`/interview/report/${interviewId}`);
    };

    return (
        <div className="h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white flex flex-col overflow-hidden">
            {/* Minimal Top Bar */}
            <div className="h-16 bg-black/30 backdrop-blur-sm border-b border-white/10 flex items-center justify-between px-8">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                        <span className="text-white font-bold">AI</span>
                    </div>
                    <div>
                        <div className="font-semibold">AI Interview</div>
                        <div className="text-xs text-slate-400">Question {turnNumber} of {totalTurns}</div>
                    </div>
                </div>

                {/* Progress Dots */}
                <div className="flex items-center gap-2">
                    {Array.from({ length: totalTurns }).map((_, idx) => (
                        <div
                            key={idx}
                            className={`w-2 h-2 rounded-full transition-all ${
                                idx < turnNumber ? 'bg-green-400 w-3' : 'bg-slate-700'
                            }`}
                        ></div>
                    ))}
                </div>

                {/* Phase Badge + Follow-up */}
                <div className="flex items-center gap-3">
                    {isFollowup && (
                        <div className="bg-amber-900/50 text-amber-300 border border-amber-700/50 px-3 py-1 rounded-full text-xs font-medium">
                            Follow-up {followupType ? `· ${followupType}` : ''}
                        </div>
                    )}
                    <div className={`px-4 py-2 rounded-full text-sm font-semibold ${
                        phase === 'HR' ? 'bg-purple-500/20 text-purple-300' : 'bg-blue-500/20 text-blue-300'
                    }`}>
                        {phase} Round
                    </div>
                    <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                        currentDifficulty === 'EASY' ? 'bg-green-500/20 text-green-300' :
                        currentDifficulty === 'HARD' ? 'bg-red-500/20 text-red-300' :
                        'bg-yellow-500/20 text-yellow-300'
                    }`}>
                        {currentDifficulty}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex gap-6 p-6 overflow-hidden">
                {/* Candidate Video - Large, Center */}
                <div className="flex-1 flex flex-col gap-4">
                    {/* Video Feed */}
                    <div className="flex-1 rounded-3xl overflow-hidden bg-black/50 backdrop-blur-sm border border-white/10 relative">
                        <video
                            ref={proctoring.videoRef}
                            autoPlay
                            playsInline
                            muted
                            className="w-full h-full object-cover"
                        />

                        {/* Recording Indicator */}
                        {interviewState === STATES.CANDIDATE_SPEAKING && (
                            <div className="absolute top-6 right-6 flex items-center gap-3 bg-red-500/90 backdrop-blur-sm px-4 py-2 rounded-full">
                                <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
                                <span className="font-bold text-white">RECORDING</span>
                                <span className="font-mono text-white">
                                    {Math.floor(recordingSeconds / 60)}:{String(recordingSeconds % 60).padStart(2, '0')}
                                </span>
                            </div>
                        )}

                        {/* AI Speaking Indicator */}
                        {interviewState === STATES.LISTENING_TO_AI && (
                            <div className="absolute top-6 left-6 flex items-center gap-3 bg-blue-500/90 backdrop-blur-sm px-4 py-2 rounded-full">
                                <div className="flex gap-1">
                                    <div className="w-1 h-4 bg-white rounded-full animate-pulse" style={{animationDelay: '0ms'}}></div>
                                    <div className="w-1 h-4 bg-white rounded-full animate-pulse" style={{animationDelay: '150ms'}}></div>
                                    <div className="w-1 h-4 bg-white rounded-full animate-pulse" style={{animationDelay: '300ms'}}></div>
                                </div>
                                <span className="font-semibold text-white">AI Speaking...</span>
                            </div>
                        )}
                    </div>

                    {/* Question Display */}
                    {currentQuestion && interviewState !== STATES.LOADING && interviewState !== STATES.COMPLETE && (
                        <div className={`rounded-2xl p-5 border ${
                            isFollowup
                                ? 'bg-amber-900/20 border-amber-700/50'
                                : 'bg-white/5 border-white/10'
                        }`}>
                            {isFollowup ? (
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="bg-amber-900/50 text-amber-300 border border-amber-700/50 px-3 py-1 rounded-full text-xs font-medium">
                                        Follow-up
                                    </span>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">
                                        Question {turnNumber} · {currentDifficulty}
                                    </span>
                                </div>
                            )}
                            <p className={`text-lg leading-relaxed ${isFollowup ? 'text-amber-100' : 'text-white'}`}>
                                {currentQuestion}
                            </p>
                        </div>
                    )}

                    {/* Control Button */}
                    <div className="h-24 flex items-center justify-center">
                        {interviewState === STATES.LOADING && (
                            <div className="text-center">
                                <div className="w-16 h-16 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-3"></div>
                                <p className="text-slate-400">Initializing interview...</p>
                            </div>
                        )}

                        {interviewState === STATES.LISTENING_TO_AI && (
                            <div className="text-center">
                                <div className="text-blue-400 text-lg font-medium mb-2">🎤 AI is speaking...</div>
                                <p className="text-slate-400 text-sm">Please listen carefully</p>
                            </div>
                        )}

                        {interviewState === STATES.WAITING_FOR_CANDIDATE && (
                            <button
                                onClick={startRecording}
                                className="group relative px-12 py-6 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-2xl font-bold text-xl transition-all duration-300 transform hover:scale-105 active:scale-95 shadow-2xl"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-3xl">🎤</span>
                                    <span>Start Speaking</span>
                                </div>
                                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl blur opacity-30 group-hover:opacity-50 transition-opacity"></div>
                            </button>
                        )}

                        {interviewState === STATES.CANDIDATE_SPEAKING && (
                            <button
                                onClick={stopAndSubmit}
                                className="px-12 py-6 bg-slate-700 hover:bg-slate-600 rounded-2xl font-bold text-xl transition-all duration-300 transform hover:scale-105 active:scale-95"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-3xl">⏹️</span>
                                    <span>Done Speaking</span>
                                </div>
                            </button>
                        )}

                        {interviewState === STATES.PROCESSING_RESPONSE && (
                            <div className="text-center">
                                <div className="w-16 h-16 border-4 border-slate-700 border-t-purple-500 rounded-full animate-spin mx-auto mb-3"></div>
                                <p className="text-slate-400">Analyzing your response...</p>
                            </div>
                        )}

                        {interviewState === STATES.COMPLETE && (
                            <div className="text-center">
                                <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mb-4 mx-auto">
                                    <span className="text-5xl">✅</span>
                                </div>
                                <h2 className="text-2xl font-bold mb-3">Interview Complete!</h2>
                                {summary && (
                                    <div className="mb-4 text-slate-400 text-sm">
                                        <span>{summary.total_turns} questions</span>
                                        <span className="mx-2">·</span>
                                        <span>Score: {(summary.avg_final_score * 100).toFixed(0)}%</span>
                                        <span className="mx-2">·</span>
                                        <span>Follow-up rate: {summary.followup_rate.toFixed(0)}%</span>
                                    </div>
                                )}
                                <button
                                    onClick={handleViewReport}
                                    className="px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 rounded-xl font-bold transition-all duration-300 transform hover:scale-105"
                                >
                                    View Your Report →
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Sidebar - Interview Progress */}
                <div className="w-80 flex flex-col gap-4">
                    {/* Interview Status */}
                    <div className="bg-black/30 backdrop-blur-sm rounded-2xl border border-white/10 p-6">
                        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4">Interview Status</h3>

                        {/* Progress */}
                        <div className="mb-5">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-400">Progress</span>
                                <span className="text-sm font-bold text-blue-400">
                                    {turnNumber}/{totalTurns}
                                </span>
                            </div>
                            <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-500"
                                    style={{ width: `${(turnNumber / totalTurns) * 100}%` }}
                                ></div>
                            </div>
                        </div>

                        {/* Phase */}
                        <div className="mb-5">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-400">Current Phase</span>
                                <span className="text-sm font-bold capitalize text-purple-400">
                                    {phase}
                                </span>
                            </div>
                        </div>

                        {/* State */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm text-slate-400">Status</span>
                                <span className="text-sm font-bold text-green-400">
                                    {interviewState === STATES.LISTENING_TO_AI && 'AI Speaking'}
                                    {interviewState === STATES.WAITING_FOR_CANDIDATE && 'Ready for Answer'}
                                    {interviewState === STATES.CANDIDATE_SPEAKING && 'Recording'}
                                    {interviewState === STATES.PROCESSING_RESPONSE && 'Processing'}
                                    {interviewState === STATES.COMPLETE && 'Complete'}
                                    {interviewState === STATES.LOADING && 'Loading'}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Tips */}
                    <div className="bg-black/30 backdrop-blur-sm rounded-2xl border border-white/10 p-6">
                        <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-3">Tips</h3>
                        <ul className="space-y-2 text-sm text-slate-400">
                            <li className="flex items-start gap-2">
                                <span className="text-green-400">✓</span>
                                <span>Maintain eye contact with camera</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-green-400">✓</span>
                                <span>Speak clearly and confidently</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-green-400">✓</span>
                                <span>Take your time to think</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-green-400">✓</span>
                                <span>Be natural and authentic</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Toast */}
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
        </div>
    );
}
