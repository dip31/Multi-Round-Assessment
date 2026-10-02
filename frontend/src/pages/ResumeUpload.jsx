import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { startInterview, getInterviewers, getInterviewVoiceModes, synthesizeSpeech } from '../services/interviewService';
import api from '../services/api';
import { Toast } from '../components/Toast';

const STATES = {
    IDLE: 'idle',
    UPLOADING: 'uploading',
    WAITING_APPROVAL: 'waiting_approval',
    APPROVED: 'approved',
};

export default function ResumeUpload() {
    const navigate = useNavigate();
    const location = useLocation();
    const initialInterviewType = location.state?.interview_type || 'technical';
    const [selectedInterviewType, setSelectedInterviewType] = useState(initialInterviewType);

    const [state, setState] = useState(STATES.IDLE);
    const [profileResumes, setProfileResumes] = useState([]);
    const [selectedResumeId, setSelectedResumeId] = useState(null);
    const [showUploadNew, setShowUploadNew] = useState(false);

    // New resume upload states
    const [newCvName, setNewCvName] = useState('');
    const [newCvType, setNewCvType] = useState('Software Developer');
    const [selectedFile, setSelectedFile] = useState(null);

    const [poolId, setPoolId] = useState(null);
    const [interviewId, setInterviewId] = useState(null);
    const [toast, setToast] = useState(null);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [detectedRole, setDetectedRole] = useState(null);

    // Interviewer selection state
    const [interviewers, setInterviewers] = useState([]);
    const [selectedInterviewerId, setSelectedInterviewerId] = useState(null);
    const [loadingInterviewers, setLoadingInterviewers] = useState(false);
    const [previewingVoice, setPreviewingVoice] = useState(null);
    const [voiceModes, setVoiceModes] = useState(null);
    const [voiceModesError, setVoiceModesError] = useState(false);
    const [selectedVoiceMode, setSelectedVoiceMode] = useState('retell_hosted');

    const intervalIdRef = useRef(null);
    const fileInputRef = useRef(null);

    useEffect(() => {
        fetchProfileResumes();
        return () => {
            if (intervalIdRef.current) {
                clearInterval(intervalIdRef.current);
            }
        };
    }, []);

    // Fetch interviewers on mount
    useEffect(() => {
        const fetchInterviewersList = async () => {
            setLoadingInterviewers(true);
            try {
                const data = await getInterviewers();
                setInterviewers(data.interviewers || []);
                // Set default interviewer if none selected
                if (data.default_interviewer_id && !selectedInterviewerId) {
                    setSelectedInterviewerId(data.default_interviewer_id);
                }
            } catch (err) {
                console.error('Failed to load interviewers:', err);
            } finally {
                setLoadingInterviewers(false);
            }
        };
        fetchInterviewersList();
    }, [selectedInterviewerId]);

    useEffect(() => {
        getInterviewVoiceModes()
            .then((modes) => {
                setVoiceModes(modes);
                if (modes.retell_hosted?.available) {
                    setSelectedVoiceMode('retell_hosted');
                } else if (modes.edi5_core?.available) {
                    setSelectedVoiceMode('edi5_core');
                }
            })
            .catch((error) => {
                console.error('Failed to load interview voice modes:', error);
                setVoiceModesError(true);
            });
    }, []);

    // Voice preview function
    const previewVoice = async (interviewer) => {
        if (previewingVoice === interviewer.id) return;
        setPreviewingVoice(interviewer.id);
        try {
            const previewText = interviewer.greeting || `Hello, I'm ${interviewer.name}.`;
            const audioBytes = await synthesizeSpeech(previewText);
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const audioBuffer = await audioContext.decodeAudioData(audioBytes);
            const source = audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContext.destination);
            source.start(0);
            source.onended = () => {
                setPreviewingVoice(null);
            };
        } catch (err) {
            console.warn('Voice preview failed:', err);
            setPreviewingVoice(null);
        }
    };

    const fetchProfileResumes = async () => {
        try {
            const res = await api.get('/profile/resumes');
            const list = res.data || [];
            setProfileResumes(list);
            if (list.length > 0) {
                setSelectedResumeId(list[0].id);
            } else {
                setShowUploadNew(true);
            }
        } catch (err) {
            console.error('Failed to load profile resumes:', err);
            setShowUploadNew(true);
        }
    };

    const handleFileSelect = (e) => {
        const file = e.target.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            if (!newCvName) {
                setNewCvName(file.name.replace(/\.pdf$/i, ''));
            }
        } else {
            setToast({
                type: 'error',
                message: 'Please select a valid PDF file',
            });
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const file = e.dataTransfer.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            if (!newCvName) {
                setNewCvName(file.name.replace(/\.pdf$/i, ''));
            }
        } else {
            setToast({
                type: 'error',
                message: 'Please select a valid PDF file',
            });
        }
    };

    const handleProceedWithSelectedResume = async () => {
        if (!selectedResumeId) {
            setToast({
                type: 'error',
                message: 'Please select a resume from your profile to proceed',
            });
            return;
        }

        // If interviewer not selected yet, just show the interviewer selection step
        if (!selectedInterviewerId) {
            return;
        }

        setState(STATES.UPLOADING);
        setUploadProgress(20);

        try {
            setUploadProgress(50);
            const res = await api.post(`/interview/resume/use-profile-resume/${selectedResumeId}?interview_type=${selectedInterviewType}`);
            setPoolId(res.data.pool_id);
            setDetectedRole(res.data.detected_role || null);
            setUploadProgress(100);

            setTimeout(() => {
                setState(STATES.WAITING_APPROVAL);
                pollForApproval(res.data.pool_id);
            }, 1200);
        } catch (error) {
            console.error('Failed to use profile resume:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to generate questions from selected resume',
            });
            setState(STATES.IDLE);
            setUploadProgress(0);
        }
    };

    const handleUploadNewAndProceed = async () => {
        if (!selectedFile) {
            setToast({
                type: 'error',
                message: 'Please select a PDF file first',
            });
            return;
        }

        // If interviewer not selected yet, just show the interviewer selection step
        if (!selectedInterviewerId) {
            return;
        }

        setState(STATES.UPLOADING);
        setUploadProgress(20);

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('cv_name', newCvName.trim() || 'My Resume');
            formData.append('cv_type', newCvType);

            setUploadProgress(40);
            const profileUploadRes = await api.post('/profile/resumes', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const newResume = profileUploadRes.data;
            setProfileResumes((prev) => [newResume, ...prev]);
            setSelectedResumeId(newResume.id);

            setUploadProgress(70);
            const res = await api.post(`/interview/resume/use-profile-resume/${newResume.id}?interview_type=${selectedInterviewType}`);
            setPoolId(res.data.pool_id);
            setDetectedRole(res.data.detected_role || newCvType);
            setUploadProgress(100);

            setTimeout(() => {
                setState(STATES.WAITING_APPROVAL);
                pollForApproval(res.data.pool_id);
            }, 1200);
        } catch (error) {
            console.error('Failed to upload and use resume:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to upload and process resume',
            });
            setState(STATES.IDLE);
            setUploadProgress(0);
        }
    };

    const pollForApproval = (pId) => {
        intervalIdRef.current = setInterval(async () => {
            try {
                const response = await fetch(`/api/v1/interview/pool/${pId}`, {
                    headers: {
                        Authorization: `Bearer ${localStorage.getItem('access_token')}`,
                    },
                });

                if (!response.ok) {
                    throw new Error('Failed to fetch pool status');
                }

                const pool = await response.json();
                if (pool.admin_approved) {
                    clearInterval(intervalIdRef.current);
                    setState(STATES.APPROVED);
                    await startInterviewSession(pId);
                }
            } catch (error) {
                console.error('Polling failed:', error);
            }
        }, 2000);

        setTimeout(() => {
            if (intervalIdRef.current) {
                clearInterval(intervalIdRef.current);
                setState(STATES.APPROVED);
                startInterviewSession(pId);
            }
        }, 4000);
    };

    const startInterviewSession = async (pId) => {
        try {
            const res = await startInterview(pId, selectedInterviewerId, selectedVoiceMode);
            if (res && res.interview_id) {
                setInterviewId(res.interview_id);
                localStorage.setItem('interview_id', res.interview_id);

                // Store Retell connection info if using Retell voice provider
                if (res.voice_provider === 'retell' && res.retell_call_id) {
                    localStorage.setItem('retell_call_id', res.retell_call_id);
                    localStorage.setItem('retell_access_token', res.retell_access_token);
                    localStorage.setItem('retell_ice_servers', JSON.stringify(res.retell_ice_servers || []));
                    localStorage.setItem('voice_provider', 'retell');
                    localStorage.setItem('interview_voice_mode', res.voice_mode || selectedVoiceMode);
                } else {
                    localStorage.setItem('voice_provider', 'legacy');
                    localStorage.removeItem('interview_voice_mode');
                }
            } else {
                setToast({
                    type: 'error',
                    message: 'Failed to initialize interview session ID',
                });
            }
        } catch (error) {
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to start interview',
            });
        }
    };

    const handleStartInterview = () => {
        const storedInterviewId = localStorage.getItem('interview_id');
        const voiceProvider = localStorage.getItem('voice_provider') || 'legacy';
        if (interviewId || storedInterviewId) {
            if (voiceProvider === 'retell') {
                navigate('/interview/retell');
            } else {
                navigate('/interview');
            }
        } else {
            setToast({
                type: 'error',
                message: 'Interview ID not ready yet. Please wait a moment.',
            });
        }
    };

    const steps = [
        { label: 'Choose Resume', completed: [STATES.UPLOADING, STATES.WAITING_APPROVAL, STATES.APPROVED].includes(state) },
        { label: 'AI Question Generation', completed: [STATES.WAITING_APPROVAL, STATES.APPROVED].includes(state) },
        { label: 'Select Interviewer', completed: state === STATES.APPROVED },
        { label: 'Session Ready', completed: state === STATES.APPROVED },
        { label: 'AI Mock Interview', completed: false },
    ];

    const typeColors = {
        'Software Developer': 'bg-blue-50 text-blue-700 border-blue-200',
        'Data Science': 'bg-purple-50 text-purple-700 border-purple-200',
        'Software Testing / QA': 'bg-amber-50 text-amber-700 border-amber-200',
        'Core Industry': 'bg-emerald-50 text-emerald-700 border-emerald-200',
        'Marketing': 'bg-rose-50 text-rose-700 border-rose-200',
        'Others': 'bg-slate-100 text-slate-700 border-slate-200',
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter'] antialiased">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="mx-auto max-w-3xl px-6 py-12 pt-20">
                {/* Back Link */}
                <div className="mb-8">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="text-slate-500 hover:text-slate-900 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                        <span>←</span> Back to Dashboard
                    </button>
                </div>

                {/* Header */}
                <div className="mb-10">
                    <div className="inline-block text-[11px] font-bold uppercase tracking-widest text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-200 mb-3">
                        Round 3 — AI Technical & Behavioral Interview
                    </div>
                    <h1 className="text-3xl font-black tracking-tight text-slate-900 mb-2">
                        Select Resume for Interview
                    </h1>
                    <p className="text-slate-500 text-sm">
                        Choose which resume from your profile you want to be interviewed for, or upload a new one.
                    </p>
                </div>

                {/* Progress Stepper */}
                <div className="mb-10 bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                    <div className="flex items-center justify-between">
                        {steps.map((step, idx) => (
                            <div key={idx} className="flex flex-col items-center flex-1 relative">
                                <div
                                    className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 font-bold text-xs transition-all ${
                                        step.completed
                                            ? 'bg-emerald-600 text-white shadow-sm shadow-emerald-600/30'
                                            : idx === 0 && state !== STATES.IDLE
                                            ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                                            : 'bg-slate-100 text-slate-500 border border-slate-200'
                                    }`}
                                >
                                    {step.completed ? '✓' : idx + 1}
                                </div>
                                <p
                                    className={`text-[11px] font-semibold text-center ${
                                        step.completed ? 'text-emerald-700' : 'text-slate-600'
                                    }`}
                                >
                                    {step.label}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Main Content Area */}
                {state === STATES.IDLE && (
                    <div className="space-y-6">
                        {/* Step 1: Interview Type Selection */}
                        <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm">
                            <div className="mb-4">
                                <div className="flex items-center gap-2">
                                    <span className="w-6 h-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">1</span>
                                    <h3 className="text-base font-bold text-slate-900">Select Interview Type</h3>
                                </div>
                                <p className="text-xs text-slate-500 mt-1 ml-8">
                                    Choose the specific interview assessment format tailored to your target focus area:
                                </p>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                                {/* Technical Interview */}
                                <div
                                    onClick={() => setSelectedInterviewType('technical')}
                                    className={`p-5 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                                        selectedInterviewType === 'technical'
                                            ? 'border-indigo-600 bg-indigo-50/50 shadow-sm ring-2 ring-indigo-500/20'
                                            : 'border-slate-200 hover:border-slate-300 bg-white'
                                    }`}
                                >
                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100">
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                                </svg>
                                            </div>
                                            <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                                selectedInterviewType === 'technical' ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                                            }`}>
                                                {selectedInterviewType === 'technical' && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                                            </span>
                                        </div>
                                        <h4 className="font-bold text-slate-900 text-sm mb-1">Technical Interview</h4>
                                        <p className="text-[11px] text-slate-500 leading-relaxed">
                                            Evaluates CS fundamentals, technical projects, and resume-based technical competencies.
                                        </p>
                                    </div>
                                    <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] font-semibold text-indigo-700">
                                        CS Concepts • Code • Projects
                                    </div>
                                </div>

                                {/* HR Interview */}
                                <div
                                    onClick={() => setSelectedInterviewType('hr')}
                                    className={`p-5 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                                        selectedInterviewType === 'hr'
                                            ? 'border-indigo-600 bg-indigo-50/50 shadow-sm ring-2 ring-indigo-500/20'
                                            : 'border-slate-200 hover:border-slate-300 bg-white'
                                    }`}
                                >
                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-100">
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                                </svg>
                                            </div>
                                            <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                                selectedInterviewType === 'hr' ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                                            }`}>
                                                {selectedInterviewType === 'hr' && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                                            </span>
                                        </div>
                                        <h4 className="font-bold text-slate-900 text-sm mb-1">HR Interview</h4>
                                        <p className="text-[11px] text-slate-500 leading-relaxed">
                                            Evaluates behavioral traits, leadership, adaptability, teamwork, and situational judgment.
                                        </p>
                                    </div>
                                    <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] font-semibold text-rose-700">
                                        STAR Method • Culture • Behavior
                                    </div>
                                </div>

                                {/* Communication Interview */}
                                <div
                                    onClick={() => setSelectedInterviewType('communication')}
                                    className={`p-5 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between ${
                                        selectedInterviewType === 'communication'
                                            ? 'border-indigo-600 bg-indigo-50/50 shadow-sm ring-2 ring-indigo-500/20'
                                            : 'border-slate-200 hover:border-slate-300 bg-white'
                                    }`}
                                >
                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-100">
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                                </svg>
                                            </div>
                                            <span className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                                                selectedInterviewType === 'communication' ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                                            }`}>
                                                {selectedInterviewType === 'communication' && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                                            </span>
                                        </div>
                                        <h4 className="font-bold text-slate-900 text-sm mb-1">Communication Interview</h4>
                                        <p className="text-[11px] text-slate-500 leading-relaxed">
                                            Evaluates professional communication, articulation, explaining technical concepts simply, and clarity.
                                        </p>
                                    </div>
                                    <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] font-semibold text-amber-700">
                                        Articulation • Clarity • Structure
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Step 2: Profile Resumes Selection */}
                        {profileResumes.length > 0 && !showUploadNew && (
                            <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
                                <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="w-6 h-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">2</span>
                                            <h3 className="text-base font-bold text-slate-900">
                                                Select Saved Resume ({profileResumes.length})
                                            </h3>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1 ml-8">
                                            Select the resume you would like the AI interviewer to assess:
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setShowUploadNew(true)}
                                        className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                                    >
                                        + Upload New CV
                                    </button>
                                </div>

                                <div className="space-y-3">
                                    {profileResumes.map((res) => {
                                        const isSelected = selectedResumeId === res.id;
                                        const badgeClass = typeColors[res.cv_type] || typeColors['Others'];
                                        const formattedDate = res.uploaded_at
                                            ? new Date(res.uploaded_at).toLocaleDateString(undefined, {
                                                  year: 'numeric',
                                                  month: 'short',
                                                  day: 'numeric',
                                              })
                                            : 'Recent';
                                        const formattedSize = res.file_size
                                            ? `${Math.round(res.file_size / 1024)} KB`
                                            : 'PDF';

                                        return (
                                            <div
                                                key={res.id}
                                                onClick={() => {
                                                    setSelectedResumeId(res.id);
                                                    setSelectedInterviewerId(null);
                                                }}
                                                className={`p-4 rounded-2xl border-2 transition-all cursor-pointer flex items-center justify-between gap-4 ${
                                                    isSelected
                                                        ? 'border-indigo-600 bg-indigo-50/40 shadow-sm'
                                                        : 'border-slate-200 hover:border-slate-300 bg-white'
                                                }`}
                                            >
                                                <div className="flex items-center gap-3.5 min-w-0">
                                                    <div
                                                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${
                                                            isSelected
                                                                ? 'border-indigo-600 bg-indigo-600 text-white'
                                                                : 'border-slate-300 bg-white'
                                                        }`}
                                                    >
                                                        {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
                                                    </div>
                                                    <div className="min-w-0">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <h4 className="font-bold text-slate-900 text-xs truncate">
                                                                {res.cv_name}
                                                            </h4>
                                                            <span
                                                                className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${badgeClass}`}
                                                            >
                                                                {res.cv_type}
                                                            </span>
                                                        </div>
                                                        <p className="text-[11px] text-slate-500 truncate mt-0.5">
                                                            {res.file_name} • {formattedSize} • Uploaded {formattedDate}
                                                        </p>
                                                    </div>
                                                </div>
                                                <div className="text-xs font-bold text-indigo-600 shrink-0">
                                                    {isSelected ? '✓ Selected' : 'Choose'}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                <div className="mt-8 pt-6 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                                    <button
                                        type="button"
                                        onClick={() => navigate('/profile')}
                                        className="text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors"
                                    >
                                        Manage all resumes in Profile →
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleProceedWithSelectedResume}
                                        disabled={!selectedResumeId}
                                        className="w-full sm:w-auto px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 uppercase tracking-wider"
                                    >
                                        {selectedInterviewerId ? 'Generate Questions & Continue →' : 'Select Interviewer →'}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Upload New Resume Box */}
                        {showUploadNew && (
                            <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
                                <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
                                    <div>
                                        <h3 className="text-base font-bold text-slate-900">Upload New Resume</h3>
                                        <p className="text-xs text-slate-500 mt-0.5">
                                            This resume will be saved to your profile and used for this interview session.
                                        </p>
                                    </div>
                                    {profileResumes.length > 0 && (
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setShowUploadNew(false);
                                                setSelectedInterviewerId(null);
                                            }}
                                            className="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                                        >
                                            ← Back to Saved Resumes
                                        </button>
                                    )}
                                </div>

                                <div className="space-y-4 text-xs mb-6">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">
                                                CV Name <span className="text-red-500">*</span>
                                            </label>
                                            <input
                                                type="text"
                                                value={newCvName}
                                                onChange={(e) => setNewCvName(e.target.value)}
                                                placeholder="e.g. Software Developer Resume"
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                            />
                                        </div>
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">
                                                CV Type <span className="text-red-500">*</span>
                                            </label>
                                            <select
                                                value={newCvType}
                                                onChange={(e) => setNewCvType(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                            >
                                                <option value="Software Developer">Software Developer</option>
                                                <option value="Data Science">Data Science</option>
                                                <option value="Software Testing / QA">Software Testing / QA</option>
                                                <option value="Core Industry">Core Industry</option>
                                                <option value="Marketing">Marketing</option>
                                                <option value="Others">Others</option>
                                            </select>
                                        </div>
                                    </div>

                                    <div
                                        onDragOver={(e) => e.preventDefault()}
                                        onDrop={handleDrop}
                                        className="border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-2xl p-8 text-center bg-slate-50/50 hover:bg-slate-50 transition-colors cursor-pointer"
                                        onClick={() => fileInputRef.current?.click()}
                                    >
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept=".pdf"
                                            onChange={handleFileSelect}
                                            className="hidden"
                                        />
                                        <div className="text-4xl mb-2">📄</div>
                                        <div className="font-bold text-slate-800 text-sm">
                                            {selectedFile ? selectedFile.name : 'Click to select or drag & drop resume'}
                                        </div>
                                        <div className="text-slate-400 text-xs mt-1">
                                            {selectedFile
                                                ? `${Math.round(selectedFile.size / 1024)} KB`
                                                : 'PDF document only, up to 10MB'}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                                    {profileResumes.length > 0 && (
                                        <button
                                            type="button"
                                            onClick={() => setShowUploadNew(false)}
                                            className="px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                                        >
                                            Cancel
                                        </button>
                                    )}
                                    <button
                                        type="button"
                                        onClick={handleUploadNewAndProceed}
                                        disabled={!selectedFile}
                                        className="px-8 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all uppercase tracking-wider"
                                    >
                                        {selectedInterviewerId ? 'Save & Continue →' : 'Select Interviewer →'}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Step 3: Interviewer Selection (shown after resume is selected or file chosen for upload) */}
                        {((poolId || selectedResumeId || (showUploadNew && selectedFile)) && state === STATES.IDLE) && (
                            <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm animate-in fade-in duration-300">
                                <div className="mb-6">
                                    <div className="flex items-center gap-2">
                                        <span className="w-6 h-6 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">3</span>
                                        <h3 className="text-base font-bold text-slate-900">Select Your Interviewer</h3>
                                    </div>
                                    <p className="text-xs text-slate-500 mt-1 ml-8">
                                        Choose who will conduct your interview. This changes the voice, tone, and style — not the questions or scoring.
                                    </p>
                                </div>

                                {loadingInterviewers ? (
                                    <div className="flex justify-center py-8">
                                        <div className="w-8 h-8 border-4 border-slate-200 border-t-indigo-500 rounded-full animate-spin"></div>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                        {interviewers.map((interviewer) => {
                                            const isSelected = selectedInterviewerId === interviewer.id;
                                            const isDefault = interviewer.is_default;
                                            return (
                                                <div
                                                    key={interviewer.id}
                                                    role="button"
                                                    tabIndex={0}
                                                    onClick={() => setSelectedInterviewerId(interviewer.id)}
                                                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedInterviewerId(interviewer.id); } }}
                                                    className={`relative p-4 rounded-2xl border-2 transition-all flex flex-col items-center text-center gap-3 cursor-pointer ${
                                                        isSelected
                                                            ? 'border-indigo-600 bg-indigo-50/40 shadow-sm ring-2 ring-indigo-500/20'
                                                            : 'border-slate-200 hover:border-slate-300 bg-white'
                                                    } ${previewingVoice !== null && previewingVoice !== interviewer.id ? 'opacity-50 pointer-events-none' : ''}`}
                                                >
                                                    {/* Selected indicator */}
                                                    {isSelected && (
                                                        <div className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-indigo-600 text-white text-xs font-bold flex items-center justify-center">
                                                            ✓
                                                        </div>
                                                    )}

                                                    {/* Default badge */}
                                                    {isDefault && (
                                                        <span className="absolute -top-2 left-1/2 -translate-x-1/2 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                            Default
                                                        </span>
                                                    )}

                                                    {/* Avatar */}
                                                    <div className={`w-16 h-16 rounded-2xl flex items-center justify-center text-white font-bold text-xl shrink-0 ${
                                                        interviewer.accent === 'indigo' ? 'bg-indigo-500' :
                                                        interviewer.accent === 'violet' ? 'bg-violet-500' :
                                                        interviewer.accent === 'slate' ? 'bg-slate-500' :
                                                        interviewer.accent === 'emerald' ? 'bg-emerald-500' :
                                                        'bg-indigo-500'
                                                    }`}>
                                                        {interviewer.avatar_initials}
                                                    </div>

                                                    {/* Name & Title */}
                                                    <div>
                                                        <h4 className="font-bold text-slate-900 text-sm">{interviewer.name}</h4>
                                                        <p className="text-[11px] text-slate-500">{interviewer.title}</p>
                                                    </div>

                                                    {/* Tagline */}
                                                    <p className="text-[11px] text-slate-600 leading-relaxed">{interviewer.tagline}</p>

                                                    {/* Voice Preview Button */}
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            previewVoice(interviewer);
                                                        }}
                                                        disabled={previewingVoice === interviewer.id}
                                                        className={`mt-auto w-full px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all flex items-center justify-center gap-1.5 ${
                                                            previewingVoice === interviewer.id
                                                                ? 'bg-slate-100 text-slate-500 cursor-wait'
                                                                : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                                                        }`}
                                                    >
                                                        <span className={`w-3 h-3 rounded-full animate-pulse ${previewingVoice === interviewer.id ? 'bg-indigo-500' : 'bg-slate-300'}`}></span>
                                                        {previewingVoice === interviewer.id ? 'Playing...' : 'Preview Voice'}
                                                    </button>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}

                                <div className="mt-8 rounded-2xl border border-slate-200 p-5">
                                    <h4 className="font-bold text-slate-900 text-sm">Choose interview intelligence</h4>
                                    <p className="mt-1 text-xs text-slate-500">
                                        Retell-hosted mode is simpler to connect. EDI5 Core mode uses adaptive EDI5 questions and scoring.
                                    </p>
                                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                                        {[
                                            {
                                                id: 'retell_hosted',
                                                title: 'Retell-hosted LLM',
                                                description: 'Retell runs the conversation. Your report includes its transcript and analysis, without EDI5 per-answer scores.',
                                            },
                                            {
                                                id: 'edi5_core',
                                                title: 'EDI5 Core',
                                                description: 'EDI5 chooses questions, follow-ups, and scores answers. Requires a public Retell WebSocket endpoint.',
                                            },
                                        ].map((mode) => {
                                            const available = Boolean(voiceModes?.[mode.id]?.available);
                                            const reason = voiceModes?.[mode.id]?.reason;
                                            return (
                                                <button
                                                    key={mode.id}
                                                    type="button"
                                                    disabled={!available || state !== STATES.IDLE}
                                                    onClick={() => setSelectedVoiceMode(mode.id)}
                                                    className={`rounded-xl border-2 p-4 text-left transition-colors ${
                                                        selectedVoiceMode === mode.id
                                                            ? 'border-indigo-600 bg-indigo-50'
                                                            : 'border-slate-200 bg-white'
                                                    } disabled:cursor-not-allowed disabled:opacity-50`}
                                                >
                                                    <span className="flex items-center justify-between gap-3">
                                                        <span className="font-bold text-sm text-slate-900">{mode.title}</span>
                                                        <span className={`h-4 w-4 rounded-full border-2 ${
                                                            selectedVoiceMode === mode.id ? 'border-indigo-600 bg-indigo-600' : 'border-slate-300'
                                                        }`} />
                                                    </span>
                                                    <span className="mt-2 block text-xs text-slate-600">{mode.description}</span>
                                                    {!available && (
                                                        <span className="mt-2 block text-[11px] font-medium text-amber-700">
                                                            {voiceModesError ? 'Could not check backend mode availability.' : reason || (voiceModes ? 'Not configured on the backend.' : 'Checking backend configuration...')}
                                                        </span>
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>
                                    {!voiceModes?.retell_hosted?.available && !voiceModes?.edi5_core?.available && voiceModes && (
                                        <p className="mt-3 text-xs text-red-600">
                                            Neither Retell mode is currently configured. Ask an administrator to configure Retell credentials before starting.
                                        </p>
                                    )}
                                </div>

                                <div className="mt-8 pt-6 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                                    <button
                                        type="button"
                                        onClick={handleProceedWithSelectedResume}
                                        disabled={(!selectedResumeId && !selectedFile) || !voiceModes?.[selectedVoiceMode]?.available}
                                        className="w-full sm:w-auto px-8 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 uppercase tracking-wider"
                                    >
                                        {selectedResumeId ? 'Generate Questions & Continue →' : 'Upload & Continue →'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* State: Processing & Generating */}
                {state === STATES.UPLOADING && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-10 shadow-sm text-center">
                        <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-6 text-2xl animate-pulse">
                            🤖
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">
                            Analyzing Resume & Generating Questions
                        </h3>
                        <p className="text-slate-500 text-xs max-w-md mx-auto mb-8">
                            Our AI is analyzing your technical competencies, project highlights, and role alignment to prepare tailored interview prompts.
                        </p>

                        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden max-w-md mx-auto">
                            <div
                                className="bg-gradient-to-r from-indigo-600 to-sky-500 h-full rounded-full transition-all duration-500"
                                style={{ width: `${uploadProgress}%` }}
                            />
                        </div>
                        <p className="mt-3 text-xs font-semibold text-slate-400">{uploadProgress}% complete</p>
                    </div>
                )}

                {/* State: Waiting Approval / Ready */}
                {state === STATES.WAITING_APPROVAL && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-10 shadow-sm text-center">
                        <div className="w-16 h-16 rounded-2xl bg-sky-50 text-sky-600 flex items-center justify-center mx-auto mb-4 text-2xl animate-spin">
                            ⚡
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Finalizing Interview Environment</h3>
                        {detectedRole && (
                            <div className="inline-block text-xs font-bold px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 mb-4">
                                Role Track: {detectedRole}
                            </div>
                        )}
                        <p className="text-slate-500 text-xs max-w-sm mx-auto">
                            Allocating AI interview room and audio streams...
                        </p>
                    </div>
                )}

                {/* State: Approved & Ready */}
                {state === STATES.APPROVED && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-10 shadow-sm text-center">
                        <div className="w-16 h-16 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-4 text-3xl animate-bounce">
                            ✅
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Interview Room Ready!</h3>
                        <p className="text-slate-500 text-xs max-w-md mx-auto mb-6">
                            Your personalized question pool is loaded based on your selected CV. Click below to enter the live interview environment.
                        </p>

                        <button
                            type="button"
                            onClick={handleStartInterview}
                            className="px-10 py-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm shadow-md shadow-emerald-600/30 transition-all uppercase tracking-wider inline-flex items-center gap-2"
                        >
                            Enter Interview Room →
                        </button>
                    </div>
                )}
            </main>
        </div>
    );
}
