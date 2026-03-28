import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadResume, startInterview } from '../services/interviewService';
import { Toast } from '../components/Toast';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

const STATES = {
    IDLE: 'idle',
    UPLOADING: 'uploading',
    WAITING_APPROVAL: 'waiting_approval',
    APPROVED: 'approved',
};

export default function ResumeUpload() {
    const [state, setState] = useState(STATES.IDLE);
    const [selectedFile, setSelectedFile] = useState(null);
    const [poolId, setPoolId] = useState(null);
    const [interviewId, setInterviewId] = useState(null);
    const [toast, setToast] = useState(null);
    const [uploadProgress, setUploadProgress] = useState(0);
    
    const navigate = useNavigate();
    const intervalIdRef = useRef(null);
    const fileInputRef = useRef(null);
    
    useEffect(() => {
        return () => {
            if (intervalIdRef.current) {
                clearInterval(intervalIdRef.current);
            }
        };
    }, []);
    
    const handleFileSelect = (e) => {
        const file = e.target.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
        } else {
            setToast({
                type: 'error',
                message: 'Please select a valid PDF file',
            });
        }
    };
    
    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
    };
    
    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const file = e.dataTransfer.files?.[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
        } else {
            setToast({
                type: 'error',
                message: 'Please select a valid PDF file',
            });
        }
    };
    
    const handleUpload = async () => {
        if (!selectedFile) {
            setToast({
                type: 'error',
                message: 'Please select a file first',
            });
            return;
        }
        
        setState(STATES.UPLOADING);
        setUploadProgress(0);
        
        try {
            const res = await uploadResume(selectedFile);
            setPoolId(res.pool_id);
            setUploadProgress(100);
            
            // Simulate processing time before showing approval state
            setTimeout(() => {
                setState(STATES.WAITING_APPROVAL);
                pollForApproval(res.pool_id);
            }, 1500);
        } catch (error) {
            let errorMsg = 'Upload failed';
            
            if (error.response?.data?.detail) {
                if (typeof error.response.data.detail === 'string') {
                    errorMsg = error.response.data.detail;
                } else if (Array.isArray(error.response.data.detail)) {
                    errorMsg = error.response.data.detail[0]?.msg || 'Upload failed';
                }
            }
            
            setToast({
                type: 'error',
                message: errorMsg,
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
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    }
                });
                
                if (!response.ok) {
                    throw new Error('Failed to fetch pool status');
                }
                
                const pool = await response.json();
                // Check if pool is admin_approved (auto-approved by backend for dev)
                if (pool.admin_approved) {
                    clearInterval(intervalIdRef.current);
                    setState(STATES.APPROVED);
                    await startInterviewSession(pId);
                }
            } catch (error) {
                console.error('Polling failed:', error);
            }
        }, 2000); // Poll every 2 seconds instead of 3
        
        // Auto-approve after 5 seconds if still pending (fallback for instant approval)
        setTimeout(() => {
            if (intervalIdRef.current) {
                clearInterval(intervalIdRef.current);
                setState(STATES.APPROVED);
                startInterviewSession(pId);
            }
        }, 5000);
    };
    
    const startInterviewSession = async (pId) => {
        try {
            console.log('Starting interview session with pool_id:', pId);
            const res = await startInterview(pId);
            console.log('Interview session response:', res);
            
            if (res && res.interview_id) {
                setInterviewId(res.interview_id);
                localStorage.setItem('interview_id', res.interview_id);
                console.log('Interview ID saved:', res.interview_id);
            } else {
                console.error('No interview_id in response:', res);
                setToast({
                    type: 'error',
                    message: 'Failed to get interview ID',
                });
            }
        } catch (error) {
            console.error('Failed to start interview session:', error);
            setToast({
                type: 'error',
                message: error.response?.data?.detail || 'Failed to start interview',
            });
        }
    };
    
    const handleStartInterview = () => {
        console.log('handleStartInterview called');
        console.log('interviewId state:', interviewId);
        console.log('localStorage interview_id:', localStorage.getItem('interview_id'));
        
        const storedInterviewId = localStorage.getItem('interview_id');
        
        if (interviewId || storedInterviewId) {
            console.log('Navigating to /interview');
            navigate('/interview');
        } else {
            console.error('No interview ID found!');
            setToast({
                type: 'error',
                message: 'Interview ID not found. Please try uploading your resume again.',
            });
        }
    };

    const steps = [
        { label: 'Upload Resume', completed: [STATES.UPLOADING, STATES.WAITING_APPROVAL, STATES.APPROVED].includes(state) },
        { label: 'AI Processing', completed: [STATES.WAITING_APPROVAL, STATES.APPROVED].includes(state) },
        { label: 'Admin Review', completed: state === STATES.APPROVED },
        { label: 'Start Interview', completed: false }
    ];

    const whatHappensNext = [
        { num: 1, text: 'Our AI will analyze your resume and experience' },
        { num: 2, text: 'An admin will review the analysis for approval' },
        { num: 3, text: 'You\'ll proceed directly to the interview' }
    ];
    
    return (
        <div className="min-h-screen bg-slate-50">
            {/* Toast */}
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="mx-auto max-w-3xl px-6 py-12">
                {/* Back link */}
                <div className="mb-12">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="text-slate-600 hover:text-slate-900 text-sm font-medium flex items-center gap-1 transition-colors"
                    >
                        <span>←</span> Back to Dashboard
                    </button>
                </div>

                {/* Header */}
                <div className="mb-12">
                    <h1 className="text-4xl font-bold text-slate-900 mb-2">Resume Upload</h1>
                    <p className="text-slate-600">Upload your resume to begin the interview process</p>
                </div>

                {/* Progress Stepper */}
                <div className="mb-12 bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                    <div className="flex items-center justify-between">
                        {steps.map((step, idx) => (
                            <div key={idx} className="flex flex-col items-center flex-1">
                                {/* Step Circle */}
                                <div
                                    className={`w-12 h-12 rounded-full flex items-center justify-center mb-3 font-semibold text-sm transition-all ${
                                        step.completed
                                            ? 'bg-green-100 text-green-700 border-2 border-green-300'
                                            : idx === 0 && state !== STATES.IDLE
                                            ? 'bg-blue-100 text-blue-700 border-2 border-blue-300'
                                            : 'bg-slate-100 text-slate-600 border-2 border-slate-300'
                                    }`}
                                >
                                    {step.completed ? '✓' : idx + 1}
                                </div>
                                {/* Step Label */}
                                <p className={`text-xs font-medium text-center ${
                                    step.completed ? 'text-green-700' : 'text-slate-600'
                                }`}>
                                    {step.label}
                                </p>
                                {/* Connection Line */}
                                {idx < steps.length - 1 && (
                                    <div
                                        className={`absolute w-12 h-1 -ml-6 mt-6 ${
                                            steps[idx + 1].completed ? 'bg-green-300' : 'bg-slate-300'
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
                {state === STATES.IDLE && (
                    <div className="mb-12">
                        <div
                            onDragOver={handleDragOver}
                            onDrop={handleDrop}
                            className="bg-white rounded-2xl border-2 border-dashed border-slate-300 hover:border-blue-400 p-12 text-center transition-colors shadow-sm"
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf"
                                onChange={handleFileSelect}
                                className="hidden"
                                id="file-input"
                            />
                            
                            {/* Cloud Icon */}
                            <div className="text-5xl mb-4">☁️</div>
                            
                            {/* Upload Text */}
                            <h2 className="text-xl font-bold text-slate-900 mb-2">
                                {selectedFile ? 'File Selected' : 'Drag & drop your resume'}
                            </h2>
                            <p className="text-slate-600 text-sm mb-6">
                                {selectedFile 
                                    ? selectedFile.name 
                                    : 'or click below to browse. PDF format, max 10MB'
                                }
                            </p>
                            
                            {/* Upload Button */}
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className="inline-flex items-center justify-center bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold py-3 px-8 rounded-xl transition-all duration-150"
                            >
                                {selectedFile ? 'Change File' : 'Select Resume'}
                            </button>
                            
                            {/* Upload Action */}
                            {selectedFile && (
                                <div className="mt-6">
                                    <button
                                        onClick={handleUpload}
                                        className="w-full bg-slate-900 hover:bg-slate-800 active:scale-[0.98] text-white font-semibold py-3 rounded-xl transition-all duration-150"
                                    >
                                        Upload & Process
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* What Happens Next */}
                        <div className="mt-12 bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                            <h3 className="text-lg font-bold text-slate-900 mb-6">What happens next?</h3>
                            <div className="space-y-4">
                                {whatHappensNext.map((item) => (
                                    <div key={item.num} className="flex items-start gap-4">
                                        <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center font-bold text-sm">
                                            {item.num}
                                        </div>
                                        <p className="text-slate-700 text-sm font-medium pt-1">{item.text}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {state === STATES.UPLOADING && (
                    <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm">
                        <div className="text-center">
                            {/* Progress Steps During Upload */}
                            <div className="space-y-6 mb-8">
                                {[
                                    { label: 'Uploading file', progress: uploadProgress >= 25 },
                                    { label: 'Parsing resume', progress: uploadProgress >= 50 },
                                    { label: 'Extracting info', progress: uploadProgress >= 75 },
                                    { label: 'Finalizing', progress: uploadProgress === 100 }
                                ].map((step, idx) => (
                                    <div key={idx} className="flex items-center gap-3">
                                        {step.progress ? (
                                            <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center flex-shrink-0">
                                                <span className="text-white text-xs font-bold">✓</span>
                                            </div>
                                        ) : (
                                            <div className="w-5 h-5 border-2 border-blue-400 border-t-blue-400 border-r-transparent rounded-full animate-spin flex-shrink-0"></div>
                                        )}
                                        <p className={`text-sm font-medium ${step.progress ? 'text-slate-600' : 'text-slate-900'}`}>
                                            {step.label}
                                        </p>
                                    </div>
                                ))}
                            </div>
                            
                            {/* Overall Progress Bar */}
                            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                                <div
                                    className="bg-blue-600 h-full rounded-full transition-all duration-500"
                                    style={{ width: `${uploadProgress}%` }}
                                ></div>
                            </div>
                            <p className="mt-4 text-slate-600 text-sm">{uploadProgress}% complete</p>
                        </div>
                    </div>
                )}

                {state === STATES.WAITING_APPROVAL && (
                    <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm">
                        <div className="text-center">
                            {/* Animated Clock Icon */}
                            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 mb-6">
                                <div className="text-3xl animate-pulse">⏱️</div>
                            </div>
                            
                            <h2 className="text-2xl font-bold text-slate-900 mb-2">
                                Awaiting Admin Review
                            </h2>
                            <p className="text-slate-600 text-base mb-8">
                                Your resume is being reviewed by our admin team. This typically takes a few minutes.
                            </p>
                            
                            {/* Status Indicator */}
                            <div className="inline-flex items-center gap-2 bg-amber-50 px-4 py-2 rounded-full mb-8">
                                <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></div>
                                <span className="text-sm font-medium text-amber-700">Pending approval...</span>
                            </div>

                            {/* Preview Cards (Blurred) */}
                            <div className="mt-8 space-y-3 opacity-40 pointer-events-none">
                                <div className="bg-slate-100 h-20 rounded-xl"></div>
                                <div className="bg-slate-100 h-20 rounded-xl"></div>
                            </div>
                        </div>
                    </div>
                )}

                {state === STATES.APPROVED && (
                    <div className="bg-white rounded-2xl border border-slate-200 p-12 shadow-sm">
                        <div className="text-center">
                            {/* Checkmark with Bounce */}
                            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 mb-6 animate-bounce">
                                <span className="text-4xl">✅</span>
                            </div>
                            
                            <h2 className="text-2xl font-bold text-slate-900 mb-2">
                                Resume Approved!
                            </h2>
                            <p className="text-slate-600 text-base mb-8">
                                Your resume has been approved. You're ready to start the interview.
                            </p>
                            
                            {/* Status Badge */}
                            <div className="inline-flex items-center gap-2 bg-green-50 px-4 py-2 rounded-full mb-8">
                                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                <span className="text-sm font-medium text-green-700">Ready to proceed</span>
                            </div>

                            {/* CTA Button */}
                            <button
                                onClick={handleStartInterview}
                                className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold py-4 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-base"
                            >
                                Start Interview
                                <span>→</span>
                            </button>

                            {/* Footer Text */}
                            <p className="mt-6 text-slate-500 text-xs">
                                You have 48 hours to complete the interview
                            </p>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
