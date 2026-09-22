import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import StudentLayout from '../components/StudentLayout';
import Navbar from '../components/Navbar';

import { getProfile } from '../services/profileService';
import { getResumes, getResumeFileUrl, viewResumeFile } from '../services/resumeService';
import { getSessionStatus, startSession, startFreshSession } from '../services/sessionService';
import { getAnalytics } from '../services/reportService';
import api from '../services/api';
import PortfolioView from '../components/portfolio/PortfolioView';

export default function Dashboard() {
    const navigate = useNavigate();

    // Data state
    const [profileData, setProfileData] = useState(null);
    const [resumes, setResumes] = useState([]);
    const [sessionData, setSessionData] = useState(null);
    const [analytics, setAnalytics] = useState(null);

    // UI state
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [toast, setToast] = useState(null);
    const [startingRound, setStartingRound] = useState(null);
    const [showFreshModal, setShowFreshModal] = useState(false);
    const [freshLoading, setFreshLoading] = useState(false);

    // Load all real data in parallel
    const loadDashboardData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const [profRes, resumesRes, sessionRes, analyticsRes] = await Promise.allSettled([
                getProfile(),
                getResumes(),
                getSessionStatus(),
                getAnalytics(),
            ]);

            // Handle Profile
            if (profRes.status === 'fulfilled') {
                setProfileData(profRes.value);
            } else {
                console.warn('Profile fetch warning:', profRes.reason);
            }

            // Handle Resumes
            if (resumesRes.status === 'fulfilled') {
                setResumes(Array.isArray(resumesRes.value) ? resumesRes.value : []);
            } else {
                setResumes([]);
            }

            // Handle Session
            if (sessionRes.status === 'fulfilled') {
                setSessionData(sessionRes.value);
            } else {
                setSessionData(null);
            }

            // Handle Analytics
            if (analyticsRes.status === 'fulfilled') {
                setAnalytics(analyticsRes.value);
            } else {
                setAnalytics(null);
            }
        } catch (err) {
            console.error('Failed to load dashboard data:', err);
            setError('Unable to load dashboard data from the server. Please check your connection and try again.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadDashboardData();
    }, [loadDashboardData]);

    // Student identity extraction
    const user = profileData || {};
    const studentProfile = user.student_profile || {};
    const displayName = studentProfile.full_name || user.name || user.email?.split('@')[0] || 'Candidate';
    const rollNumber = studentProfile.roll_number || 'Not Set';
    const department = studentProfile.department || 'General Engineering';
    const graduationYear = studentProfile.graduation_year || 2026;
    const targetRole = studentProfile.target_role || 'Software Developer';
    const institution = studentProfile.institution || 'EDI5 Engineering Campus';
    const cgpa = studentProfile.cgpa !== undefined && studentProfile.cgpa !== null ? Number(studentProfile.cgpa) : 0.0;
    const backlogs = studentProfile.backlogs_count !== undefined && studentProfile.backlogs_count !== null ? Number(studentProfile.backlogs_count) : 0;
    const eligibility = studentProfile.placement_eligibility || null;

    // Greeting by time of day
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    // Parse rounds state from real session
    const rounds = Array.isArray(sessionData?.rounds) ? sessionData.rounds : [];
    const getRoundData = (type) => {
        return rounds.find((r) => r.round_type === type) || null;
    };

    const aptRound = getRoundData('aptitude');
    const codRound = getRoundData('coding');
    const intRound = getRoundData('interview');

    // Use ONLY the current session's round status for card state.
    // analyticsCompletedRounds spans all historical sessions and incorrectly
    // marks a round as "completed" when the current session has it active.
    const analyticsCompletedRounds = Array.isArray(analytics?.completed_rounds) ? analytics.completed_rounds : [];

    const isAptitudeCompleted = aptRound?.status === 'completed';
    const isCodingCompleted = codRound?.status === 'completed';
    const isInterviewCompleted = intRound?.status === 'completed';

    // For progress KPIs (dashboard metrics), include historical data so the
    // overall score / percentile / rounds-done count remains meaningful.
    const completedRoundsCount = [isAptitudeCompleted, isCodingCompleted, isInterviewCompleted].filter(Boolean).length;
    const progressPercent = Math.round((completedRoundsCount / 3) * 100);

    // Real analytics values
    const overallScore = analytics?.overall_score !== undefined ? analytics.overall_score : (sessionData?.total_score ? Math.round(sessionData.total_score * 100) : 0);
    const accuracyRate = analytics?.accuracy !== undefined ? analytics.accuracy : 0;
    const percentile = analytics?.percentile !== undefined && analytics?.percentile !== null ? analytics.percentile : null;

    // Extracted / Verified Skills
    const profileSkills = Array.isArray(studentProfile.skills) ? studentProfile.skills : [];
    const resumeSkills = Array.from(new Set(resumes.flatMap((r) => r.parsed_skills || [])));
    const allSkills = Array.from(new Set([...profileSkills, ...resumeSkills]));

    const [selectedTechSubject, setSelectedTechSubject] = useState('all');

    // Round action handlers
    const handleStartPractice = async (practiceType, subject = null) => {
        setStartingRound(practiceType);
        try {
            const config = { practice_type: practiceType, subject: subject };
            localStorage.setItem('edi5_practice_config', JSON.stringify(config));

            // Always use startFreshSession for practice starts.
            // - If there is no active session: creates one with a fresh aptitude round.
            // - If there IS an active session: completes it first, then creates a new one.
            // This avoids stale React state causing the wrong branch to execute.
            // startFreshSession is defined in session_router as POST /session/fresh.
            await startFreshSession();

            navigate('/aptitude', { state: { practice_config: config } });
        } catch (err) {
            setToast({ type: 'error', message: err.response?.data?.detail || 'Failed to initialize practice round' });
        } finally {
            setStartingRound(null);
        }
    };

    const handleStartAptitude = () => handleStartPractice('mcq');

    const handleStartCoding = async () => {
        setStartingRound('coding');
        try {
            await api.post('/coding/start');
            setToast({ type: 'success', message: 'Coding challenge loaded' });
            setTimeout(() => navigate('/coding'), 200);
        } catch (err) {
            setToast({ type: 'error', message: err.response?.data?.detail || 'Unable to start coding round right now' });
        } finally {
            setStartingRound(null);
        }
    };

    const handleStartInterview = (interviewType = 'technical') => {
        navigate('/resume-upload', { state: { interview_type: interviewType } });
    };

    const handleStartFreshCycle = async () => {
        setFreshLoading(true);
        try {
            await startFreshSession();
            setShowFreshModal(false);
            setToast({ type: 'success', message: 'Fresh assessment cycle initialized successfully' });
            await loadDashboardData();
        } catch (err) {
            setToast({ type: 'error', message: err.response?.data?.detail || 'Failed to start fresh cycle' });
        } finally {
            setFreshLoading(false);
        }
    };

    // Helper for round card status badge
    const renderRoundBadge = (isCompleted, roundObj) => {
        if (isCompleted) {
            return (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                    Completed
                </span>
            );
        }
        if (roundObj?.status === 'active') {
            return (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 animate-pulse">
                    <span className="w-1.5 h-1.5 rounded-full bg-sky-500"></span>
                    In Progress
                </span>
            );
        }
        return (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                Ready to Start
            </span>
        );
    };

    if (loading) {
        return <PageSkeleton variant="light" cardCount={4} />;
    }

    if (error) {
        return (
            <div className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased">
                <Navbar position="sticky" />
                <main className="max-w-4xl mx-auto px-6 py-16 text-center">
                    <div className="bg-white border border-rose-200 rounded-3xl p-10 shadow-sm max-w-lg mx-auto">
                        <div className="w-16 h-16 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center mx-auto mb-4 text-2xl">
                            ⚠️
                        </div>
                        <h2 className="text-2xl font-black text-slate-900 mb-2">Dashboard Connection Error</h2>
                        <p className="text-sm text-slate-600 mb-6">{error}</p>
                        <button
                            onClick={loadDashboardData}
                            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl text-sm transition-all shadow-sm active:scale-95"
                        >
                            Retry Connection
                        </button>
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased selection:bg-indigo-100">
            <Navbar
                position="sticky"
                rightContent={
                    <button
                        onClick={() => navigate('/profile')}
                        className="flex items-center gap-2.5 hover:opacity-85 transition-opacity px-2 py-1 rounded-xl"
                        title="View Profile"
                    >
                        <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white font-bold text-sm shadow-sm">
                            {displayName.charAt(0).toUpperCase()}
                        </div>
                        <span className="hidden md:inline text-xs font-semibold text-slate-700">{displayName}</span>
                    </button>
                }
            />

            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-6 py-8">
                {/* ── 1. Student Identity & Authoritative Eligibility Header ── */}
                <div className="bg-white border border-slate-200/90 rounded-3xl p-6 md:p-8 mb-8 shadow-sm">
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                        {/* Candidate Identity */}
                        <div className="flex items-start gap-4 md:gap-5">
                            <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-gradient-to-tr from-indigo-600 via-indigo-700 to-violet-600 flex items-center justify-center text-white font-black text-2xl md:text-3xl shadow-md flex-shrink-0">
                                {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div className="flex flex-wrap items-center gap-2 mb-1">
                                    <h1 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight">
                                        {getGreeting()}, <span className="text-indigo-600">{displayName}</span>
                                    </h1>
                                </div>
                                <p className="text-xs md:text-sm text-slate-500 font-medium mb-3">
                                    {institution}
                                </p>

                                {/* Student Meta Pills */}
                                <div className="flex flex-wrap items-center gap-2 text-xs">
                                    <span className="px-3 py-1 rounded-lg bg-slate-100 font-semibold text-slate-700 border border-slate-200/80">
                                        Roll: {rollNumber}
                                    </span>
                                    <span className="px-3 py-1 rounded-lg bg-indigo-50 font-semibold text-indigo-700 border border-indigo-200/80">
                                        {department}
                                    </span>
                                    <span className="px-3 py-1 rounded-lg bg-slate-100 font-semibold text-slate-700 border border-slate-200/80">
                                        Class of {graduationYear}
                                    </span>
                                    <span className="px-3 py-1 rounded-lg bg-violet-50 font-semibold text-violet-700 border border-violet-200/80">
                                        Target: {targetRole}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Authoritative Placement Drive Eligibility */}
                        <div className="flex flex-col sm:flex-row lg:flex-col items-start lg:items-end justify-between gap-3 border-t lg:border-t-0 pt-4 lg:pt-0 border-slate-100">
                            <div className="text-left lg:text-right">
                                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 block mb-1.5">
                                    Placement Drive Eligibility
                                </span>
                                {eligibility ? (
                                    <div className="flex flex-col lg:items-end gap-1">
                                        <span
                                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border shadow-xs ${
                                                eligibility.badge_variant === 'emerald'
                                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                    : eligibility.badge_variant === 'sky'
                                                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                                                    : eligibility.badge_variant === 'amber'
                                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                                    : 'bg-slate-100 text-slate-700 border-slate-200'
                                            }`}
                                        >
                                            <span
                                                className={`w-2 h-2 rounded-full ${
                                                    eligibility.badge_variant === 'emerald'
                                                        ? 'bg-emerald-500'
                                                        : eligibility.badge_variant === 'sky'
                                                        ? 'bg-sky-500'
                                                        : eligibility.badge_variant === 'amber'
                                                        ? 'bg-amber-500'
                                                        : 'bg-slate-400'
                                                }`}
                                            ></span>
                                            {eligibility.label}
                                        </span>
                                        <p className="text-[11px] text-slate-600 font-medium max-w-xs mt-0.5">
                                            CGPA: <strong className="text-slate-900">{cgpa.toFixed(2)}</strong> • Backlogs: <strong className="text-slate-900">{backlogs}</strong>
                                        </p>
                                    </div>
                                ) : (
                                    <div className="text-xs font-medium text-slate-600">
                                        CGPA: {cgpa.toFixed(2)} • {backlogs} Backlog(s)
                                    </div>
                                )}
                            </div>

                            <button
                                onClick={() => navigate('/profile')}
                                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100/70 border border-indigo-200/80 rounded-xl transition-all"
                            >
                                <span>✏️</span> Edit Profile & CV
                            </button>
                        </div>
                    </div>
                </div>

                {/* ── 2. Executive KPI Strip (Real Data) ── */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    {/* KPI 1: Overall Readiness Score */}
                    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Overall Readiness</span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                                📊
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-indigo-600">{overallScore}%</span>
                            <span className="text-xs text-slate-600 font-medium">Placement Score</span>
                        </div>
                        <div className="w-full h-1.5 bg-slate-100 rounded-full mt-3 overflow-hidden">
                            <div
                                className="h-full bg-indigo-600 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(100, Math.max(0, overallScore))}%` }}
                            ></div>
                        </div>
                    </div>



                    {/* KPI 3: Percentile Rank */}
                    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Cohort Percentile</span>
                            <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center font-bold text-sm">
                                🏆
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            {percentile !== null ? (
                                <>
                                    <span className="text-3xl font-black text-violet-600">{percentile}th</span>
                                    <span className="text-xs text-slate-600 font-medium">Percentile</span>
                                </>
                            ) : (
                                <>
                                    <span className="text-xl font-bold text-slate-700">Not available</span>
                                </>
                            )}
                        </div>
                        <p className="text-[11px] text-slate-600 mt-2 font-medium truncate">
                            {percentile !== null ? `Top ${100 - percentile}% of active candidates` : 'Complete rounds to join cohort ranking'}
                        </p>
                    </div>

                    {/* KPI 4: Active CVs & Skills */}
                    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Portfolio Assets</span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">
                                📁
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-slate-900">{resumes.length}</span>
                            <span className="text-xs text-slate-600 font-medium">Active CV{resumes.length !== 1 ? 's' : ''}</span>
                        </div>
                        <p className="text-[11px] text-slate-600 mt-2 font-medium truncate">
                            {allSkills.length} Verified & Extracted Skills
                        </p>
                    </div>
                </div>

                {/* ── 3. Practice Rounds ── */}
                <div className="mb-8">
                            {/* Practice Rounds Header */}
                            <div>
                                <h2 className="text-xl font-black text-slate-900 tracking-tight">Practice Assessment Rounds</h2>
                                <p className="text-xs text-slate-500 font-medium">
                                    Targeted institutional placement evaluation modes backed by AI adaptivity and multi-modal proctoring
                                </p>
                            </div>

                            {/* 4 Practice Cards Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Card 1: MCQ Round */}
                                <div className="bg-white border border-slate-200 hover:border-indigo-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                    <div>
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                                                </svg>
                                            </div>
                                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                                Aptitude Prep
                                            </span>
                                        </div>

                                        <h3 className="text-lg font-bold text-slate-900 mb-1">MCQ Round</h3>
                                        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                            Practice quantitative, logical, verbal and reasoning-based questions.
                                        </p>

                                        <div className="space-y-2 mb-6">
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">📊</span> Quantitative & Logical Reasoning
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">📖</span> Verbal Ability & Comprehension
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">📈</span> Data Interpretation Graphs & Tables
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        <button
                                            onClick={() => handleStartPractice('mcq')}
                                            disabled={startingRound === 'mcq'}
                                            className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {startingRound === 'mcq' ? 'Starting...' : 'Start MCQ Round →'}
                                        </button>
                                    </div>
                                </div>

                                {/* Card 2: Technical Round (with subject selector) */}
                                <div className="bg-white border border-slate-200 hover:border-blue-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                    <div>
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                                </svg>
                                            </div>
                                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                                Core CS Fundamentals
                                            </span>
                                        </div>

                                        <h3 className="text-lg font-bold text-slate-900 mb-1">Technical Round</h3>
                                        <p className="text-xs text-slate-500 mb-3 leading-relaxed">
                                            Test your Computer Science fundamentals across OS, CN, OOPS, DBMS and Data Structures.
                                        </p>

                                        {/* Subject Selector Buttons */}
                                        <div className="mb-4">
                                            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">
                                                Select Subject Focus:
                                            </label>
                                            <div className="flex flex-wrap gap-1.5">
                                                {[
                                                    { id: 'all', label: 'All Technical' },
                                                    { id: 'os', label: 'OS' },
                                                    { id: 'cn', label: 'CN' },
                                                    { id: 'oops', label: 'OOPS' },
                                                    { id: 'dbms', label: 'DBMS' },
                                                    { id: 'dsa', label: 'DSA' },
                                                ].map((subj) => {
                                                    const isSelected = selectedTechSubject === subj.id;
                                                    return (
                                                        <button
                                                            key={subj.id}
                                                            type="button"
                                                            onClick={() => setSelectedTechSubject(subj.id)}
                                                            className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                                                                isSelected
                                                                    ? 'bg-blue-600 text-white shadow-xs'
                                                                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 border border-slate-200'
                                                            }`}
                                                        >
                                                            {subj.label}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>

                                        <div className="space-y-1 mb-6 text-[11px] text-slate-500">
                                            <span>Active Subject: <strong className="text-slate-800 uppercase">{selectedTechSubject === 'all' ? 'All Technical (OS, CN, OOPS, DBMS, DSA)' : selectedTechSubject}</strong></span>
                                        </div>
                                    </div>

                                    <div>
                                        <button
                                            onClick={() => handleStartPractice('technical', selectedTechSubject)}
                                            disabled={startingRound === 'technical'}
                                            className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {startingRound === 'technical' ? 'Starting...' : `Start Technical Round (${selectedTechSubject === 'all' ? 'All' : selectedTechSubject.toUpperCase()}) →`}
                                        </button>
                                    </div>
                                </div>

                                {/* Card 3: Combined Round */}
                                <div className="bg-white border border-slate-200 hover:border-purple-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                    <div>
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
                                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                                                </svg>
                                            </div>
                                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                                                50% Apti + 50% Tech
                                            </span>
                                        </div>

                                        <h3 className="text-lg font-bold text-slate-900 mb-1">Combined Round</h3>
                                        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                            Practice a balanced combination of aptitude and technical questions.
                                        </p>

                                        <div className="space-y-2 mb-6">
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">⚖️</span> 50% Quantitative & Logical Aptitude
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">💻</span> 50% Core Computer Science Questions
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">🎯</span> Institutional placement paper simulation
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        <button
                                            onClick={() => handleStartPractice('combined')}
                                            disabled={startingRound === 'combined'}
                                            className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {startingRound === 'combined' ? 'Starting...' : 'Start Combined Round →'}
                                        </button>
                                    </div>
                                </div>

                                {/* Card 4: Algorithmic Coding Challenge (intact) */}
                                <div className={`bg-white border rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between ${
                                    isCodingCompleted ? 'border-emerald-200' : 'border-slate-200 hover:border-emerald-300'
                                }`}>
                                    <div>
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
                                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                </svg>
                                            </div>
                                            {renderRoundBadge(isCodingCompleted, codRound)}
                                        </div>

                                        <h3 className="text-lg font-bold text-slate-900 mb-1">Algorithmic Coding Challenge</h3>
                                        <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                            Write and execute code in Python, C++, Java, or JS evaluated by Judge0.
                                        </p>

                                        {isCodingCompleted && (
                                            <div className="mb-4 p-3 rounded-xl bg-emerald-50/70 border border-emerald-100">
                                                <div className="flex items-center justify-between text-xs">
                                                    <span className="font-semibold text-emerald-800">Completed Score:</span>
                                                    <span className="font-black text-emerald-700 text-sm">
                                                        {codRound?.score ? `${Math.round(codRound.score * 100)}%` : 'Completed'}
                                                    </span>
                                                </div>
                                            </div>
                                        )}

                                        <div className="space-y-2 mb-6">
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">⚡</span> Real-time Judge0 compiler
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">🧪</span> Visible & hidden test cases
                                            </div>
                                            <div className="flex items-center gap-2 text-xs text-slate-600 font-medium">
                                                <span className="text-slate-400">🔤</span> Python, C++, Java, JavaScript
                                            </div>
                                        </div>
                                    </div>

                                    <div>
                                        {isCodingCompleted ? (
                                            <div className="flex flex-col gap-2">
                                                <button
                                                    onClick={() => navigate('/coding/result')}
                                                    className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 transition-all text-center"
                                                >
                                                    Review Submissions →
                                                </button>
                                                <button
                                                    onClick={() => handleStartPractice('mcq')}
                                                    disabled={startingRound === 'mcq'}
                                                    className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50"
                                                >
                                                    {startingRound === 'mcq' ? 'Starting...' : 'New Practice Attempt →'}
                                                </button>
                                            </div>
                                        ) : codRound?.status === 'active' ? (
                                            <button
                                                onClick={() => navigate('/coding')}
                                                className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all shadow-sm active:scale-95"
                                            >
                                                Resume Coding Round →
                                            </button>
                                        ) : (
                                            <button
                                                onClick={handleStartCoding}
                                                disabled={startingRound === 'coding'}
                                                className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50"
                                            >
                                                {startingRound === 'coding' ? 'Starting...' : 'Start Coding Challenge →'}
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Section: Interview Mode Simulation (Technical, HR, Communication) */}
                            <div className="pt-4 border-t border-slate-200">
                                <div className="flex items-center justify-between mb-4">
                                    <div>
                                        <h3 className="text-xl font-black text-slate-900 tracking-tight">AI Interview Simulation Modes</h3>
                                        <p className="text-xs text-slate-500 font-medium">
                                            Conversational voice interviews tailored to your selected profile resume
                                        </p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                                    {/* Interview 1: Technical Interview */}
                                    <div className="bg-white border border-slate-200 hover:border-indigo-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                                    </svg>
                                                </div>
                                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                                                    Tech Focus
                                                </span>
                                            </div>
                                            <h4 className="font-bold text-slate-900 text-sm mb-1">Technical Interview</h4>
                                            <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                                Evaluates CS fundamentals, technical projects, and resume-based technical competencies.
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleStartInterview('technical')}
                                            className="w-full py-2 px-3 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-all shadow-sm active:scale-95 text-center"
                                        >
                                            Select CV & Start Technical →
                                        </button>
                                    </div>

                                    {/* Interview 2: HR Interview */}
                                    <div className="bg-white border border-slate-200 hover:border-rose-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
                                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                                    </svg>
                                                </div>
                                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
                                                    Behavioral Focus
                                                </span>
                                            </div>
                                            <h4 className="font-bold text-slate-900 text-sm mb-1">HR Interview</h4>
                                            <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                                Evaluates behavioral traits, leadership, adaptability, teamwork, and situational judgment.
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleStartInterview('hr')}
                                            className="w-full py-2 px-3 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white transition-all shadow-sm active:scale-95 text-center"
                                        >
                                            Select CV & Start HR →
                                        </button>
                                    </div>

                                    {/* Interview 3: Communication Interview */}
                                    <div className="bg-white border border-slate-200 hover:border-amber-300 rounded-2xl p-6 shadow-sm transition-all flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
                                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                                    </svg>
                                                </div>
                                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                                                    Articulation Focus
                                                </span>
                                            </div>
                                            <h4 className="font-bold text-slate-900 text-sm mb-1">Communication Interview</h4>
                                            <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                                                Evaluates professional communication, articulation, explaining technical concepts simply, and clarity.
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleStartInterview('communication')}
                                            className="w-full py-2 px-3 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white transition-all shadow-sm active:scale-95 text-center"
                                        >
                                            Select CV & Start Communication →
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                {/* ── 3B. Mock Drive Simulation ── */}
                <div className="mb-8">
                        <div className="space-y-6">
                            <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm">
                                <div className="mb-6">
                                    <h2 className="text-xl font-black text-slate-900 tracking-tight">Recruitment Drive Simulation</h2>
                                    <p className="text-xs text-slate-500 font-medium">
                                        Company-specific mock hiring drives calibrated against real eligibility cutoffs and recruitment patterns
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                    {/* Drive 1: Tier-1 Tech Product Drive */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                                                    Tier-1 Product Tech
                                                </span>
                                                <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                                                    🚀
                                                </span>
                                            </div>
                                            <h3 className="text-lg font-bold text-slate-900 mb-1">Software Development Engineer</h3>
                                            <p className="text-xs text-slate-500 mb-4">
                                                Simulating top product company recruitment cycles: DS & Algo, system design, and behavioral fit.
                                            </p>

                                            {/* Criteria vs Student Reality */}
                                            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-6 text-xs">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Required CGPA:</span>
                                                    <span className="font-bold text-slate-800">≥ 7.00 (Yours: {cgpa.toFixed(2)})</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Backlogs allowed:</span>
                                                    <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                                                </div>
                                                <div className="flex justify-between items-center pt-2 border-t border-slate-200">
                                                    <span className="font-semibold text-slate-700">Status:</span>
                                                    {cgpa >= 7.0 && backlogs === 0 ? (
                                                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                                                            Eligible ✓
                                                        </span>
                                                    ) : (
                                                        <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
                                                            Criteria Pending
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => navigate('/instructions')}
                                            disabled={!(cgpa >= 7.0 && backlogs === 0)}
                                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                                cgpa >= 7.0 && backlogs === 0
                                                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm active:scale-95'
                                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                                            }`}
                                        >
                                            {cgpa >= 7.0 && backlogs === 0 ? 'Enter Mock Drive Simulation →' : 'Criteria Not Met'}
                                        </button>
                                    </div>

                                    {/* Drive 2: Global IT & Consulting */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                                                    Global IT Services
                                                </span>
                                                <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">
                                                    🌐
                                                </span>
                                            </div>
                                            <h3 className="text-lg font-bold text-slate-900 mb-1">Associate Software Engineer</h3>
                                            <p className="text-xs text-slate-500 mb-4">
                                                Institutional campus drive pattern: Aptitude speed test, core CS concepts, and client-facing communication.
                                            </p>

                                            {/* Criteria vs Student Reality */}
                                            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-6 text-xs">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Required CGPA:</span>
                                                    <span className="font-bold text-slate-800">≥ 6.00 (Yours: {cgpa.toFixed(2)})</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Backlogs allowed:</span>
                                                    <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                                                </div>
                                                <div className="flex justify-between items-center pt-2 border-t border-slate-200">
                                                    <span className="font-semibold text-slate-700">Status:</span>
                                                    {cgpa >= 6.0 && backlogs === 0 ? (
                                                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                                                            Eligible ✓
                                                        </span>
                                                    ) : (
                                                        <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
                                                            Criteria Pending
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => navigate('/instructions')}
                                            disabled={!(cgpa >= 6.0 && backlogs === 0)}
                                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                                cgpa >= 6.0 && backlogs === 0
                                                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm active:scale-95'
                                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                                            }`}
                                        >
                                            {cgpa >= 6.0 && backlogs === 0 ? 'Enter Mock Drive Simulation →' : 'Criteria Not Met'}
                                        </button>
                                    </div>

                                    {/* Drive 3: FinTech & Quant Analysis */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-xs flex flex-col justify-between">
                                        <div>
                                            <div className="flex items-center justify-between mb-3">
                                                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                                                    FinTech & Quant
                                                </span>
                                                <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">
                                                    📈
                                                </span>
                                            </div>
                                            <h3 className="text-lg font-bold text-slate-900 mb-1">Quantitative Systems Analyst</h3>
                                            <p className="text-xs text-slate-500 mb-4">
                                                Advanced probability modeling, high-performance algorithms, and scenario analysis under strict timelines.
                                            </p>

                                            {/* Criteria vs Student Reality */}
                                            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-6 text-xs">
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Required CGPA:</span>
                                                    <span className="font-bold text-slate-800">≥ 7.50 (Yours: {cgpa.toFixed(2)})</span>
                                                </div>
                                                <div className="flex justify-between items-center">
                                                    <span className="text-slate-600">Backlogs allowed:</span>
                                                    <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                                                </div>
                                                <div className="flex justify-between items-center pt-2 border-t border-slate-200">
                                                    <span className="font-semibold text-slate-700">Status:</span>
                                                    {cgpa >= 7.5 && backlogs === 0 ? (
                                                        <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                                                            Eligible ✓
                                                        </span>
                                                    ) : (
                                                        <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded-md border border-rose-200">
                                                            Criteria Pending
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        <button
                                            onClick={() => navigate('/instructions')}
                                            disabled={!(cgpa >= 7.5 && backlogs === 0)}
                                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                                cgpa >= 7.5 && backlogs === 0
                                                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm active:scale-95'
                                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                                            }`}
                                        >
                                            {cgpa >= 7.5 && backlogs === 0 ? 'Enter Mock Drive Simulation →' : 'Criteria Not Met'}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                </div>

                {/* ── 4. Technical Subject & Competency Breakdown (Real Backend Data) ── */}
                <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm mb-8">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-black text-slate-900 tracking-tight">Technical Subject & Competency Breakdown</h2>
                            <p className="text-xs text-slate-500 font-medium">
                                Real accuracy metrics recorded across Computer Science topics (OS, CN, OOPS, DBMS, DSA) and Aptitude
                            </p>
                        </div>
                        {analytics?.skill_breakdown && analytics.skill_breakdown.length > 0 && (
                            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-xl">
                                {analytics.skill_breakdown.length} Tracked Topic{analytics.skill_breakdown.length !== 1 ? 's' : ''}
                            </span>
                        )}
                    </div>

                    {analytics?.skill_breakdown && analytics.skill_breakdown.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {analytics.skill_breakdown.map((item, idx) => {
                                const scoreVal = Math.round(item.score || 0);
                                const isHigh = scoreVal >= 70;
                                const isMid = scoreVal >= 50;
                                return (
                                    <div key={idx} className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-slate-300 transition-all">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs font-bold text-slate-900 truncate max-w-[180px]">{item.name}</h4>
                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                                                isHigh
                                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                    : isMid
                                                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                                                    : 'bg-amber-50 text-amber-700 border-amber-200'
                                            }`}>
                                                {isHigh ? 'Proficient' : isMid ? 'Developing' : 'Needs Practice'}
                                            </span>
                                        </div>
                                        <div className="flex items-baseline gap-2 mb-2">
                                            <span className="text-2xl font-black text-slate-900">{scoreVal}%</span>
                                            <span className="text-[11px] text-slate-500">Accuracy</span>
                                        </div>
                                        <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all duration-500 ${
                                                    isHigh ? 'bg-emerald-500' : isMid ? 'bg-sky-500' : 'bg-amber-500'
                                                }`}
                                                style={{ width: `${Math.min(100, Math.max(0, scoreVal))}%` }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="text-center py-10 px-4 rounded-2xl bg-slate-50 border border-dashed border-slate-200">
                            <span className="text-3xl block mb-2">📊</span>
                            <p className="text-xs font-semibold text-slate-700 mb-1">No practice attempts recorded yet.</p>
                            <p className="text-[11px] text-slate-500 mb-4 max-w-md mx-auto">
                                Start an MCQ or Technical practice round above to view your breakdown across OS, CN, OOPS, DBMS, DSA, and Aptitude.
                            </p>
                            <button
                                onClick={() => handleStartPractice('technical', 'all')}
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm active:scale-95"
                            >
                                Start Technical Practice Round →
                            </button>
                        </div>
                    )}
                </div>

                {/* ── 5. Real Session History Table (Distinguishing all 7 Round Types) ── */}
                <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm mb-8">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <h2 className="text-xl font-black text-slate-900 tracking-tight">Assessment Session History</h2>
                            <p className="text-xs text-slate-500 font-medium">
                                Chronological record of completed rounds across MCQ, Technical, Combined, Coding, and Interview modes
                            </p>
                        </div>
                        <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1 rounded-xl">
                            {analytics?.session_history?.length || 0} Recorded Attempt{analytics?.session_history?.length !== 1 ? 's' : ''}
                        </span>
                    </div>

                    {analytics?.session_history && analytics.session_history.length > 0 ? (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-xs border-collapse">
                                <thead>
                                    <tr className="border-b border-slate-200 text-slate-600 uppercase tracking-wider font-bold">
                                        <th className="pb-3 pl-2">Attempt ID</th>
                                        <th className="pb-3">Round Type</th>
                                        <th className="pb-3">Date Completed</th>
                                        <th className="pb-3">Duration</th>
                                        <th className="pb-3 text-right pr-2">Score</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {analytics.session_history.map((record, index) => {
                                        const typeLower = (record.type || '').toLowerCase();
                                        return (
                                            <tr key={index} className="hover:bg-slate-50/80 transition-colors">
                                                <td className="py-3.5 pl-2 font-mono font-bold text-slate-700">
                                                    {record.id || `ATT-${index + 1}`}
                                                </td>
                                                <td className="py-3.5">
                                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md font-semibold text-xs ${
                                                        typeLower.includes('coding')
                                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                            : typeLower.includes('technical interview')
                                                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                                            : typeLower.includes('hr interview')
                                                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                                            : typeLower.includes('communication interview')
                                                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                                            : typeLower.includes('technical round')
                                                            ? 'bg-sky-50 text-sky-700 border border-sky-200'
                                                            : typeLower.includes('combined')
                                                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                                            : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                                    }`}>
                                                        {record.type || 'Assessment'}
                                                    </span>
                                                </td>
                                                <td className="py-3.5 text-slate-600 font-medium">{record.date || 'Recent'}</td>
                                                <td className="py-3.5 text-slate-600 font-medium">{record.duration || 'N/A'}</td>
                                                <td className="py-3.5 text-right pr-2 font-bold text-slate-900">
                                                    <span className={`px-2.5 py-1 rounded-lg ${
                                                        Number(record.score) >= 70
                                                            ? 'bg-emerald-50 text-emerald-700'
                                                            : Number(record.score) >= 40
                                                            ? 'bg-sky-50 text-sky-700'
                                                            : 'bg-slate-100 text-slate-700'
                                                    }`}>
                                                        {record.score}%
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="text-center py-10 px-4 rounded-2xl bg-slate-50 border border-dashed border-slate-200">
                            <span className="text-3xl block mb-2">📋</span>
                            <p className="text-xs font-semibold text-slate-700 mb-1">No assessment sessions recorded yet.</p>
                            <p className="text-[11px] text-slate-500 mb-4 max-w-md mx-auto">
                                Complete your first MCQ, Technical, Combined, Coding, or Mock Interview round to start tracking your performance history.
                            </p>
                            <button
                                onClick={() => handleStartPractice('mcq')}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm active:scale-95"
                            >
                                Start First Practice Round
                            </button>
                        </div>
                    )}
                </div>

                {/* ── 5. Metric-Driven Optimization Insights ── */}
                {analytics?.optimization_areas && analytics.optimization_areas.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 md:p-8 shadow-sm mb-8">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-sm font-bold">
                                💡
                            </span>
                            <div>
                                <h2 className="text-lg font-black text-slate-900">Performance Optimization Recommendations</h2>
                                <p className="text-xs text-slate-500 font-medium">
                                    Transparent rule-based recommendations derived from your accuracy rates and pacing
                                </p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {analytics.optimization_areas.map((opt, index) => (
                                <div
                                    key={index}
                                    className={`p-4 rounded-2xl border ${
                                        opt.severity === 'warning'
                                            ? 'bg-amber-50/50 border-amber-200/80 text-amber-900'
                                            : 'bg-indigo-50/40 border-indigo-200/80 text-indigo-950'
                                    }`}
                                >
                                    <h4 className="text-xs font-bold mb-1 flex items-center gap-1.5">
                                        <span>{opt.severity === 'warning' ? '⚡' : '📌'}</span>
                                        {opt.title}
                                    </h4>
                                    <p className="text-xs text-slate-600 leading-relaxed">{opt.description}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </main>

            {/* Fresh Assessment Cycle Modal */}
            {showFreshModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
                    <div className="bg-white rounded-3xl p-6 md:p-8 max-w-md w-full shadow-2xl border border-slate-200">
                        <div className="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-2xl mb-4">
                            🔄
                        </div>
                        <h3 className="text-xl font-black text-slate-900 mb-2">Start Fresh Assessment Cycle?</h3>
                        <p className="text-xs text-slate-600 leading-relaxed mb-6">
                            This will archive your currently active session and initialize a brand-new assessment cycle.
                            All your past round attempts and scores will be safely preserved in your session history.
                        </p>
                        <div className="flex items-center justify-end gap-3">
                            <button
                                onClick={() => setShowFreshModal(false)}
                                disabled={freshLoading}
                                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-900 rounded-xl transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleStartFreshCycle}
                                disabled={freshLoading}
                                className="px-5 py-2 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-sm transition-all active:scale-95 disabled:opacity-50"
                            >
                                {freshLoading ? 'Initializing...' : 'Confirm & Start Fresh'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
