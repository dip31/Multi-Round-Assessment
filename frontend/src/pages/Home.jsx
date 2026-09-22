import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { getProfile } from '../services/profileService';
import { getResumes } from '../services/resumeService';
import { getAnalytics } from '../services/reportService';

export default function Home() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [profileData, setProfileData] = useState(null);
    const [analytics, setAnalytics] = useState(null);
    const [resumes, setResumes] = useState([]);

    useEffect(() => {
        const loadData = async () => {
            try {
                const [profRes, analyticsRes, resumesRes] = await Promise.allSettled([
                    getProfile(),
                    getAnalytics(),
                    getResumes(),
                ]);

                if (profRes.status === 'fulfilled') setProfileData(profRes.value);
                if (analyticsRes.status === 'fulfilled') setAnalytics(analyticsRes.value);
                if (resumesRes.status === 'fulfilled') setResumes(Array.isArray(resumesRes.value) ? resumesRes.value : []);
            } catch (err) {
                console.error('Failed to load home data:', err);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, []);

    const studentProfile = profileData?.student_profile || {};
    const displayName = studentProfile.full_name || profileData?.name || 'Student';
    const cgpa = studentProfile.cgpa ?? 0.0;
    const backlogs = studentProfile.backlogs_count ?? 0;
    const overallScore = analytics?.overall_score ?? 0;
    const percentile = analytics?.percentile;

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    if (loading) {
        return (
            <StudentModeLayout>
                <div className="flex items-center justify-center min-h-screen">
                    <div className="text-center">
                        <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-sm text-slate-600">Loading...</p>
                    </div>
                </div>
            </StudentModeLayout>
        );
    }

    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-6 py-8">
                {/* Welcome Header */}
                <div className="bg-white border border-slate-200 rounded-3xl p-8 mb-8 shadow-sm">
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">
                        {getGreeting()}, <span className="text-indigo-600">{displayName}</span>
                    </h1>
                    <p className="text-slate-600 text-sm">
                        Welcome to AIPlacement — your comprehensive placement preparation platform
                    </p>
                </div>

                {/* Quick Stats */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Overall Score</span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                                📊
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-indigo-600">{overallScore}%</span>
                        </div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Percentile</span>
                            <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center font-bold text-sm">
                                🏆
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            {percentile !== null && percentile !== undefined ? (
                                <span className="text-3xl font-black text-violet-600">{percentile}th</span>
                            ) : (
                                <span className="text-xl font-bold text-slate-700">N/A</span>
                            )}
                        </div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">CGPA</span>
                            <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">
                                📚
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-slate-900">{cgpa.toFixed(2)}</span>
                        </div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">Portfolio</span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">
                                📁
                            </span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="text-3xl font-black text-slate-900">{resumes.length}</span>
                            <span className="text-xs text-slate-600 font-medium">CV{resumes.length !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                </div>

                {/* Mode Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Practice Card */}
                    <div 
                        onClick={() => navigate('/practice')}
                        className="bg-white border-2 border-indigo-200 hover:border-indigo-400 rounded-2xl p-6 shadow-sm transition-all cursor-pointer group"
                    >
                        <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-4 group-hover:scale-110 transition-transform">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Practice</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Practice MCQ, technical questions, coding, and interviews independently
                        </p>
                        <button className="w-full py-2 px-4 rounded-xl text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-all">
                            Start Practicing →
                        </button>
                    </div>

                    {/* Portfolio Card */}
                    <div 
                        onClick={() => navigate('/portfolio')}
                        className="bg-white border-2 border-emerald-200 hover:border-emerald-400 rounded-2xl p-6 shadow-sm transition-all cursor-pointer group"
                    >
                        <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 mb-4 group-hover:scale-110 transition-transform">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Portfolio</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Build and verify your profile, resume, projects, and skills
                        </p>
                        <button className="w-full py-2 px-4 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all">
                            Manage Portfolio →
                        </button>
                    </div>

                    {/* Mock Drive Card */}
                    <div 
                        onClick={() => navigate('/mock-drive')}
                        className="bg-white border-2 border-violet-200 hover:border-violet-400 rounded-2xl p-6 shadow-sm transition-all cursor-pointer group"
                    >
                        <div className="w-12 h-12 rounded-xl bg-violet-50 border border-violet-100 flex items-center justify-center text-violet-600 mb-4 group-hover:scale-110 transition-transform">
                            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                        </div>
                        <h3 className="text-xl font-bold text-slate-900 mb-2">Mock Drive</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Simulate real recruitment drives with structured assessments
                        </p>
                        <button className="w-full py-2 px-4 rounded-xl text-sm font-bold bg-violet-600 hover:bg-violet-700 text-white transition-all">
                            Explore Drives →
                        </button>
                    </div>
                </div>
            </div>
        </StudentModeLayout>
    );
}
