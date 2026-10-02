import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { retellClient } from '../services/interviewService';
import { getInterviewStatus, saveRetellTranscript } from '../services/interviewService';
import AdvancedProctoringMonitor from '../components/AdvancedProctoringMonitor';
import ProctoringVideoDisplay from '../components/ProctoringVideoDisplay';
import useAdvancedProctoring from '../hooks/useAdvancedProctoring';
import { Toast } from '../components/Toast';
import api from '../services/api';

// AI Speaking Animation Component
const AISpeakingIndicator = ({ isSpeaking, className = "" }) => (
    <div className={`flex items-center gap-3 ${className}`}>
        <div className="relative flex items-center justify-center">
            {/* Pulsing rings */}
            {isSpeaking && (
                <>
                    <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-purple-400/60 animate-ping opacity-75" />
                    <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-blue-400/40 animate-ping opacity-50" style={{ animationDelay: '300ms' }} />
                    <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-purple-300/30 animate-ping opacity-25" style={{ animationDelay: '600ms' }} />
                </>
            )}
            {/* Central AI icon */}
            <div className={`relative w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-300 ${
                isSpeaking 
                    ? 'bg-gradient-to-br from-purple-600 to-blue-600 shadow-[0_0_30px_rgba(147,51,234,0.6)] animate-pulse' 
                    : 'bg-slate-800 border border-slate-700'
            }`}>
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {isSpeaking ? (
                        // Sound waves when speaking
                        <>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12l4-4 4 4M15 12l4-4 4 4" />
                        </>
                    ) : (
                        // Brain/chip icon when idle
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    )}
                </svg>
            </div>
        </div>
        <div className="flex flex-col">
            <span className={`text-xs font-medium ${isSpeaking ? 'text-purple-400' : 'text-slate-500'}`}>
                {isSpeaking ? 'AI Interviewer Speaking' : 'AI Interviewer Ready'}
            </span>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                {isSpeaking ? 'Listening to your response...' : 'Waiting for your answer'}
            </span>
        </div>
    </div>
);

const STATES = {
    LOADING: 'loading',
    CONNECTING: 'connecting',
    READY: 'ready',
    LISTENING: 'listening',
    PROCESSING: 'processing',
    COMPLETE: 'complete',
    ERROR: 'error',
};

export default function RetellInterviewRoom() {
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
    const [liveTip, setLiveTip] = useState('');
    const [liveTranscript, setLiveTranscript] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('connecting');
    const [isAISpeaking, setIsAISpeaking] = useState(false);
    
    const navigate = useNavigate();
    
    // Get interview ID from localStorage (stable refs - these don't change)
    const interviewId = localStorage.getItem('interview_id');
    const voiceMode = localStorage.getItem('interview_voice_mode') || 'edi5_core';
    const retellCallId = localStorage.getItem('retell_call_id');
    const retellAccessToken = localStorage.getItem('retell_access_token');
    // Parse ice servers once and store in a ref to avoid new array on every render
    const retellIceServersRef = useRef(
        JSON.parse(localStorage.getItem('retell_ice_servers') || '[]')
    );
    const retellIceServers = retellIceServersRef.current;
    const [proctoringSessionId, setProctoringSessionId] = useState(null);
    
    const proctoring = useAdvancedProctoring(proctoringSessionId, null);
    
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const startTimeRef = useRef(null);
    const timerIntervalRef = useRef(null);
    const tipPollingRef = useRef(null);
    const isInitializedRef = useRef(false);
    const liveTranscriptRef = useRef([]);

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
        } else if (!retellCallId || !retellAccessToken) {
            console.error('Retell connection info not found');
            setToast({
                type: 'error',
                message: 'Retell connection info missing. Please start interview again.',
            });
            setTimeout(() => {
                navigate('/dashboard');
            }, 3000);
        } else {
            console.log('Interview ID found:', interviewId);
            console.log('Retell Call ID:', retellCallId);
        }
    }, [interviewId, retellCallId, retellAccessToken, navigate]);

    useEffect(() => {
        if (!interviewId) return;
        getInterviewStatus(interviewId)
            .then((data) => setProctoringSessionId(data.session_id))
            .catch((error) => console.error('Failed to resolve assessment session:', error));
    }, [interviewId]);

    // Initialize Retell Web Call
    const initializeRetell = useCallback(async () => {
        if (isInitializedRef.current) return;
        isInitializedRef.current = true;
        
        setRoomState(STATES.CONNECTING);
        setConnectionStatus('connecting');
        
        console.log('Retell init - callId:', retellCallId);
        console.log('Retell init - accessToken:', retellAccessToken ? retellAccessToken.substring(0, 20) + '...' : 'MISSING');
        console.log('Retell init - iceServers:', retellIceServers);
        
        try {
            // Initialize Retell client
            await retellClient.initialize(retellCallId, retellAccessToken, retellIceServers);
            
            // Set up callbacks
            retellClient.onTranscript((transcriptData) => {
                liveTranscriptRef.current = transcriptData;
                setLiveTranscript(transcriptData);
                
                // Detect AI speaking state - check if latest message is from agent
                if (transcriptData.length > 0) {
                    const latestMessage = transcriptData[transcriptData.length - 1];
                    setIsAISpeaking(latestMessage.role === 'agent');
                    
                    const latestUser = [...transcriptData].reverse().find(u => u.role === 'user');
                    if (latestUser) {
                        setTranscript(latestUser.content);
                    }
                    if (voiceMode === 'edi5_core') {
                        const latestAgent = [...transcriptData].reverse().find(u => u.role === 'agent');
                        if (latestAgent) setCurrentQuestion(latestAgent.content);
                    }
                }
            });
            
            retellClient.onCallEnded(() => {
                console.log('Retell call ended');
                setRoomState(STATES.COMPLETE);
                handleInterviewComplete();
            });
            
            retellClient.onError((error) => {
                console.error('Retell error:', error);
                setToast({
                    type: 'error',
                    message: 'Connection error. Please try again.',
                });
                setRoomState(STATES.ERROR);
            });
            
            // Start the call (connects WebSocket, WebRTC, starts audio)
            await retellClient.startCall();
            setIsRecording(true);
            setRoomState(STATES.READY);
            setConnectionStatus('connected');
            
        } catch (error) {
            console.error('Failed to initialize Retell:', error);
            setToast({
                type: 'error',
                message: 'Failed to connect to Retell. Please retry or contact support; this interview will not switch providers automatically.',
            });
            setRoomState(STATES.ERROR);
        }
    }, [retellCallId, retellAccessToken, retellIceServers, voiceMode]);

    const fetchFirstQuestion = async () => {
        if (!interviewId) return;
        
        try {
            const res = await getNextQuestion(interviewId);
            setCurrentQuestion(res.question);
            setTurnNumber(res.turn_number);
            setDifficulty(res.difficulty);
            setPhase(res.phase);
            setTranscript('');
            setQuestionScore(null);
        } catch (error) {
            console.error('Failed to fetch first question:', error);
            setToast({
                type: 'error',
                message: 'Failed to load first question',
            });
        }
    };

    const fetchNextQuestion = async () => {
        if (!interviewId) return;
        
        try {
            const res = await getNextQuestion(interviewId);
            setCurrentQuestion(res.question);
            setTurnNumber(res.turn_number);
            setDifficulty(res.difficulty);
            setPhase(res.phase);
            setTranscript('');
            setQuestionScore(null);
        } catch (error) {
            console.error('Failed to fetch next question:', error);
        }
    };

    // Handle interview completion
    const handleInterviewComplete = async () => {
        proctoring.stopMonitoring?.();
        try {
            const transcript = liveTranscriptRef.current
                .map((utterance) => `${utterance.role === 'user' ? 'Candidate' : 'Interviewer'}: ${utterance.content}`)
                .join('\n');
            if (transcript) {
                await saveRetellTranscript(interviewId, transcript);
            }
            await api.post(`/interview/session/${interviewId}/complete`);
        } catch (error) {
            console.error('Failed to persist Retell interview data:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to save the interview transcript or completion status.',
            });
        }
        setRoomState(STATES.COMPLETE);
    };

    const handleViewReport = () => {
        navigate(`/interview/report/${interviewId}`);
    };

    const handleSubmitInterview = async () => {
        const confirmed = window.confirm(
            `Are you sure you want to submit the interview early?\n\n` +
            `Progress: ${turnNumber} out of ${totalTurns} questions answered\n\n` +
            `This action cannot be undone.`
        );
        
        if (!confirmed) return;
        
        try {
            // End Retell call
            await retellClient.endCall();
            const transcript = liveTranscriptRef.current
                .map((utterance) => `${utterance.role === 'user' ? 'Candidate' : 'Interviewer'}: ${utterance.content}`)
                .join('\n');
            if (transcript) {
                await saveRetellTranscript(interviewId, transcript);
            }
            
            // Stop proctoring
            proctoring.stopMonitoring?.();
            
            // Call complete endpoint
            const response = await api.post(`/interview/session/${interviewId}/complete`);
            console.log('Interview completed:', response.data);
            
            navigate(`/interview/report/${interviewId}`);
        } catch (error) {
            console.error('Failed to submit interview:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to submit interview',
            });
        }
    };

    // Timer for recording display
    useEffect(() => {
        if (!isRecording) {
            if (timerIntervalRef.current) {
                clearInterval(timerIntervalRef.current);
                timerIntervalRef.current = null;
            }
            return;
        }
        
        setRecordingSeconds(0);
        timerIntervalRef.current = setInterval(() => {
            setRecordingSeconds((s) => s + 1);
        }, 1000);
        
        return () => {
            if (timerIntervalRef.current) {
                clearInterval(timerIntervalRef.current);
                timerIntervalRef.current = null;
            }
        };
    }, [isRecording]);

    // Initialize on mount — run exactly once
    useEffect(() => {
        if (interviewId && retellCallId && retellAccessToken) {
            initializeRetell();
        }
        
        return () => {
            clearInterval(timerIntervalRef.current);
            clearInterval(tipPollingRef.current);
            retellClient.endCall().catch(() => {});
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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
                {/* Logo & Connection Status */}
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-sm">AI</span>
                    </div>
                    <span className="font-semibold text-sm">Interview</span>
                    {/* Connection Status Indicator */}
                    <div className="flex items-center gap-1.5">
                        <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' : connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'}`}></div>
                        <span className="text-xs text-slate-400 capitalize">{connectionStatus}</span>
                    </div>
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

                {/* Phase Badge & Timer & Submit */}
                <div className="flex items-center gap-4">
                    {/* Submit Interview Button */}
                    <button
                        onClick={handleSubmitInterview}
                        disabled={roomState === STATES.COMPLETE || roomState === STATES.LOADING || roomState === STATES.CONNECTING}
                        className="flex-shrink-0 px-4 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs font-semibold rounded-full transition-colors"
                    >
                        Finish Round
                    </button>
                    
                    {/* Phase Badge */}
                    <div className={`px-4 py-1.5 rounded-full text-xs font-semibold text-white ${getPhaseColor(phase)}`}>
                        {phase?.toUpperCase() || 'INTERVIEW'}
                    </div>

                    {/* Timer */}
                    <div className="text-sm font-mono text-slate-400">
                        {Math.floor(recordingSeconds / 60)}:{String(recordingSeconds % 60).padStart(2, '0')}
                    </div>
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

                        {/* Head Stability */}
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

                        {/* Face Detected */}
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
                        
                        {roomState === STATES.CONNECTING && (
                            <div className="flex flex-col items-center justify-center h-full">
                                <div className="w-12 h-12 border-4 border-slate-700 border-t-yellow-500 rounded-full animate-spin mb-4"></div>
                                <p className="text-slate-400 text-center">Connecting to voice service...</p>
                            </div>
                        )}
                        
                        {(roomState === STATES.READY || roomState === STATES.LISTENING || roomState === STATES.PROCESSING) && (
                            <>
                                {/* AI Speaking Indicator */}
                                <AISpeakingIndicator 
                                    isSpeaking={isAISpeaking} 
                                    className="mb-4 p-4 bg-slate-800/50 rounded-xl border border-slate-700"
                                />
                                
                                {voiceMode === 'edi5_core' ? (
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
                                        <p className="text-2xl font-semibold leading-relaxed text-slate-100 mb-8">{currentQuestion}</p>
                                    </>
                                ) : (
                                    // retell_hosted mode - show current question from transcript
                                    <>
                                        <div className="flex items-center gap-3 mb-4 pb-4 border-b border-slate-800">
                                            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Question {turnNumber || 1}</span>
                                            <span className="px-2 py-1 rounded-full text-xs font-medium text-white bg-purple-600 bg-opacity-20">
                                                Retell Hosted
                                            </span>
                                        </div>
                                        <div className="mb-6 rounded-xl border border-slate-700 bg-slate-800/50 p-4 text-sm text-slate-300">
                                            Retell is conducting this interview. Your live conversation transcript appears below.
                                        </div>
                                        {/* Show current question from transcript if available */}
                                        {(liveTranscript.length > 0) && (
                                            <>
                                                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Current Question</p>
                                                <p className="text-lg font-medium leading-relaxed text-slate-100 mb-6">
                                                    {(() => {
                                                        const agentMsgs = liveTranscript.filter(u => u.role === 'agent');
                                                        return agentMsgs.length > 0 ? agentMsgs[agentMsgs.length - 1].content : 'Listening...';
                                                    })()}
                                                </p>
                                            </>
                                        )}
                                    </>
                                )}
                                
                                {/* Live Transcript Display - Enhanced with better formatting */}
                                {liveTranscript.length > 0 && (
                                    <div className="mb-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700">
                                        <div className="flex items-center justify-between mb-3">
                                            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Live Conversation</p>
                                            <span className="text-[10px] text-slate-400 bg-slate-700 px-2 py-0.5 rounded">
                                                {liveTranscript.length} messages
                                            </span>
                                        </div>
                                        <div className="space-y-2 max-h-60 overflow-y-auto">
                                            {liveTranscript.map((utt, idx) => {
                                                const isUser = utt.role === 'user';
                                                const isFinal = utt.is_final !== false;
                                                return (
                                                    <div 
                                                        key={`${utt.utterance_id || idx}-${utt.role}`}
                                                        className={`flex gap-3 animate-slide-in ${!isFinal ? 'opacity-70' : ''}`}
                                                    >
                                                        {/* Speaker Avatar */}
                                                        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                                                            isUser 
                                                                ? 'bg-blue-600/20 border border-blue-500/30' 
                                                                : 'bg-purple-600/20 border border-purple-500/30'
                                                        }`}>
                                                            {isUser ? (
                                                                <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                                </svg>
                                                            ) : (
                                                                <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 002 2v10a2 2 0 002 2z" />
                                                                </svg>
                                                            )}
                                                        </div>
                                                        
                                                        {/* Message Content */}
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-baseline gap-2 mb-1">
                                                                <span className={`text-xs font-semibold ${isUser ? 'text-blue-300' : 'text-purple-300'}`}>
                                                                    {isUser ? 'You' : 'Interviewer'}
                                                                </span>
                                                                <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                                                                    {utt.message_type || (isUser ? 'ANSWER' : 'QUESTION')}
                                                                </span>
                                                                {!isFinal && (
                                                                    <span className="text-[10px] text-amber-400 animate-pulse flex items-center gap-1">
                                                                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                                                                        Transcribing...
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <p className={`text-sm leading-relaxed ${isUser ? 'text-blue-200' : 'text-purple-200'} break-words`}>
                                                                {utt.content}
                                                            </p>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}
                                
                                {transcript && roomState !== STATES.READY && (
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
                        
                        {roomState === STATES.ERROR && (
                            <div className="flex flex-col items-center justify-center h-full text-center">
                                <div className="w-20 h-20 rounded-full bg-red-500 bg-opacity-20 flex items-center justify-center mb-6">
                                    <span className="text-4xl">⚠️</span>
                                </div>
                                <h2 className="text-3xl font-bold text-red-400 mb-3">Connection Error</h2>
                                <p className="text-slate-400 text-base max-w-sm mb-6">
                                    Lost connection to voice service. Your progress has been saved.
                                </p>
                                <button
                                    onClick={() => navigate('/dashboard')}
                                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-colors"
                                >
                                    Return to Dashboard
                                </button>
                            </div>
                        )}
                    </div>
                    
                    {/* Control Panel */}
                    <div className="bg-slate-900 rounded-2xl border border-slate-800 p-8">
                        {roomState === STATES.LOADING && (
                            <div className="text-center">
                                <div className="w-12 h-12 border-4 border-slate-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
                                <p className="text-slate-400">Initializing...</p>
                            </div>
                        )}
                        
                        {roomState === STATES.CONNECTING && (
                            <div className="text-center">
                                <div className="w-12 h-12 border-4 border-slate-700 border-t-yellow-500 rounded-full animate-spin mx-auto mb-4"></div>
                                <p className="text-slate-400">Connecting to voice service...</p>
                            </div>
                        )}
                        
                        {roomState === STATES.READY && (
                            <div className="text-center">
                                <p className="text-slate-400 text-base mb-6">Connected. Ready to answer.</p>
                                <div className="flex items-center justify-center gap-3 mb-6">
                                    <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                                    <span className="font-semibold text-green-400">Live</span>
                                </div>
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
                        
                        {roomState === STATES.ERROR && (
                            <div className="text-center">
                                <button
                                    onClick={initializeRetell}
                                    className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-bold py-4 rounded-xl transition-all duration-150 text-base flex items-center justify-center gap-2"
                                >
                                    <span>🔄</span>
                                    Retry Connection
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