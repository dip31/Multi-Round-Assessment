import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { startPractice } from '../services/sessionService';

export default function PracticeOverview() {
    const navigate = useNavigate();
    const location = useLocation();
    const [starting, setStarting] = useState(null);

    // Detect which practice type is selected from URL
    const getSelectedPracticeType = () => {
        const path = location.pathname;
        if (path === '/practice/mcq') return 'mcq';
        if (path === '/practice/technical-mcq') return 'technical';
        if (path === '/practice/combined-mcq') return 'combined';
        if (path === '/practice/coding') return 'coding';
        if (path === '/practice/interview') return 'interview';
        return null; // Overview mode
    };

    const selectedType = getSelectedPracticeType();

    const handleStartPractice = async (practiceType, subject = null) => {
        setStarting(practiceType);
        try {
            const config = { practice_type: practiceType, subject: subject };
            localStorage.setItem('edi5_practice_config', JSON.stringify(config));

            let roundType = "aptitude";
            if (practiceType === 'coding') roundType = "coding";
            if (practiceType === 'interview') roundType = "interview";

            await startPractice(roundType, practiceType);

            // Navigate to appropriate assessment page
            if (practiceType === 'mcq' || practiceType === 'technical' || practiceType === 'combined') {
                navigate('/aptitude');
            } else if (practiceType === 'coding') {
                navigate('/coding');
            } else if (practiceType === 'interview') {
                navigate('/resume-upload');
            }
        } catch (error) {
            console.error('Failed to start practice:', error);
            if (error.response && error.response.status === 409) {
                alert(error.response.data.detail || 'An active practice session is already in progress. Please complete it before starting a new one.');
            } else {
                alert('Failed to start practice session. Please try again.');
            }
        } finally {
            setStarting(null);
        }
    };

    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Practice Mode</h1>
                    <p className="text-slate-600 text-sm">
                        {selectedType
                            ? `Practice ${
                                selectedType === 'mcq'
                                    ? 'MCQ'
                                    : selectedType === 'technical'
                                    ? 'Technical MCQ'
                                    : selectedType === 'combined'
                                    ? 'Combined MCQ'
                                    : selectedType === 'coding'
                                    ? 'Coding Challenges'
                                    : 'Interview'
                            } independently. Each practice session is separate and repeatable.`
                            : 'Practice independently across different assessment types. Each practice session is separate and repeatable.'}
                    </p>
                </div>

                {/* Show only selected practice type, or all if on overview */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* MCQ Card */}
                    {(!selectedType || selectedType === 'mcq') && (
                        <div className="bg-white border border-slate-200 hover:border-indigo-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                    Aptitude
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">MCQ Round</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Quantitative, logical, verbal, and reasoning-based questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('mcq')}
                                disabled={starting === 'mcq'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'mcq' ? 'Starting...' : 'Start MCQ Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Technical MCQ Card */}
                    {(!selectedType || selectedType === 'technical') && (
                        <div className="bg-white border border-slate-200 hover:border-blue-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                    Technical
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Technical MCQ</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                OS, CN, OOPS, DBMS, and Data Structures questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('technical', 'all')}
                                disabled={starting === 'technical'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'technical' ? 'Starting...' : 'Start Technical Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Combined MCQ Card */}
                    {(!selectedType || selectedType === 'combined') && (
                        <div className="bg-white border border-slate-200 hover:border-purple-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                                    Combined
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Combined MCQ</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                50% Aptitude + 50% Technical questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('combined')}
                                disabled={starting === 'combined'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-purple-600 hover:bg-purple-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'combined' ? 'Starting...' : 'Start Combined Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Coding Card */}
                    {(!selectedType || selectedType === 'coding') && (
                        <div className="bg-white border border-slate-200 hover:border-emerald-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Coding
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Coding Challenge</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Solve algorithmic problems with full proctoring
                            </p>
                            <button
                                onClick={() => handleStartPractice('coding')}
                                disabled={starting === 'coding'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'coding' ? 'Starting...' : 'Start Coding Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Interview Card */}
                    {(!selectedType || selectedType === 'interview') && (
                        <div className="bg-white border border-slate-200 hover:border-amber-300 rounded-2xl p-6 shadow-sm transition-all md:col-span-2">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                    Interview
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Interview Practice</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Practice technical, HR, or communication interviews with AI
                            </p>
                            <button
                                onClick={() => handleStartPractice('interview')}
                                disabled={starting === 'interview'}
                                className="w-full max-w-xs py-2.5 px-4 rounded-xl text-sm font-bold bg-amber-600 hover:bg-amber-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'interview' ? 'Starting...' : 'Start Interview Practice →'}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </StudentModeLayout>
    );
}
