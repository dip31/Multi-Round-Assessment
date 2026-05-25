import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../services/api';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function Profile() {
    const [user, setUser] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    const resolveDisplayName = () => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            try {
                const parsed = JSON.parse(storedUser);
                return parsed.full_name || parsed.name || parsed.username || 'Candidate';
            } catch (e) {
                // ignore malformed localStorage JSON
            }
        }

        const namedKeys = ['user_name', 'full_name', 'candidate_name', 'profile_name'];
        for (const key of namedKeys) {
            const value = localStorage.getItem(key);
            if (value && value.trim()) return value.trim();
        }

        const email = localStorage.getItem('user_email') || localStorage.getItem('email');
        if (email && email.includes('@')) return email.split('@')[0];
        return 'Candidate';
    };

    const resolveEmail = () => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            try {
                const parsed = JSON.parse(storedUser);
                if (parsed.email) return parsed.email;
            } catch (e) {
                // ignore malformed localStorage JSON
            }
        }
        return localStorage.getItem('user_email') || localStorage.getItem('email') || '';
    };

    const isRoundCompleted = (roundType) => {
        const rounds = Array.isArray(stats?.rounds) ? stats.rounds : [];
        const round = rounds.find((r) => r.round_type === roundType);
        return round?.status === 'completed';
    };

    const profileMenu = (
        <button
            onClick={() => navigate('/profile')}
            className="flex items-center gap-2"
        >
            <div className="w-10 h-10 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center text-white font-bold text-sm">
                {user?.name?.charAt(0) || 'U'}
            </div>
        </button>
    );

    useEffect(() => {
        fetchProfileData();
    }, []);

    const fetchProfileData = async () => {
        try {
            const sessionResponse = await api.get('/session/status');
            setUser({
                name: resolveDisplayName(),
                email: resolveEmail(),
            });
            setStats(sessionResponse.data);
        } catch (error) {
            setUser({
                name: resolveDisplayName(),
                email: resolveEmail(),
            });
            setStats(null);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <PageSkeleton variant="dark" cardCount={4} />;
    }

    return (
        <div className="bg-background text-on-surface font-body selection:bg-primary/30 antialiased min-h-screen">
            <Navbar position="sticky" rightContent={profileMenu} onLogout={() => navigate('/login')} />

            <main className="pt-8 pb-12">
                <div className="max-w-4xl mx-auto px-6">
                    {/* Profile Header Card */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-12 mb-8 shadow-lg shadow-primary/5">
                        <div className="flex flex-col md:flex-row items-start md:items-center gap-8">
                            {/* Avatar */}
                            <div className="w-32 h-32 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white flex-shrink-0">
                                <span className="text-6xl font-black">{user?.name?.charAt(0) || 'U'}</span>
                            </div>

                            {/* User Info */}
                            <div className="flex-grow">
                                <h1 className="text-4xl font-headline font-black text-on-surface mb-2">{user?.name || 'Loading...'}</h1>
                                <p className="text-on-surface-variant text-lg mb-4">{user?.email || ''}</p>
                                <div className="flex gap-4">
                                    <button
                                        onClick={() => navigate('/dashboard')}
                                        className="hero-gradient text-on-primary-container px-6 py-2 rounded-full font-semibold transition-all duration-200 shadow-lg shadow-primary/20 hover:shadow-[0_0_20px_rgba(186,158,255,0.4)] active:scale-95"
                                    >
                                        Continue Assessment
                                    </button>
                                    <button
                                        onClick={() => navigate('/analytics')}
                                        className="bg-surface-container-high border border-outline-variant/30 text-on-surface px-6 py-2 rounded-full font-semibold transition-all hover:border-primary/50"
                                    >
                                        View Analytics
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                        <div className="bg-surface-container border border-outline-variant/20 rounded-xl p-6 text-center shadow-lg shadow-primary/5 hover:shadow-primary/10 transition-all hover:-translate-y-1">
                            <div className="text-on-surface-variant text-sm font-label uppercase tracking-widest mb-2">Assessment Status</div>
                            <div className="text-4xl font-black bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                                {isRoundCompleted('aptitude') ? '✓' : '○'}
                            </div>
                            <div className="text-xs text-on-surface-variant mt-2">Aptitude Test</div>
                        </div>

                        <div className="bg-surface-container border border-outline-variant/20 rounded-xl p-6 text-center shadow-lg shadow-primary/5 hover:shadow-primary/10 transition-all hover:-translate-y-1">
                            <div className="text-on-surface-variant text-sm font-label uppercase tracking-widest mb-2">Coding Round</div>
                            <div className="text-4xl font-black bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                                {isRoundCompleted('coding') ? '✓' : '○'}
                            </div>
                            <div className="text-xs text-on-surface-variant mt-2">In Progress</div>
                        </div>

                        <div className="bg-surface-container border border-outline-variant/20 rounded-xl p-6 text-center shadow-lg shadow-primary/5 hover:shadow-primary/10 transition-all hover:-translate-y-1">
                            <div className="text-on-surface-variant text-sm font-label uppercase tracking-widest mb-2">Interview</div>
                            <div className="text-4xl font-black bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
                                {isRoundCompleted('interview') ? '✓' : '○'}
                            </div>
                            <div className="text-xs text-on-surface-variant mt-2">Ready</div>
                        </div>

                        <div className="bg-surface-container border border-outline-variant/20 rounded-xl p-6 text-center shadow-lg shadow-primary/5 hover:shadow-primary/10 transition-all hover:-translate-y-1">
                            <div className="text-on-surface-variant text-sm font-label uppercase tracking-widest mb-2">Overall</div>
                            <div className="text-4xl font-black text-secondary">
                                {stats ? Math.round(((isRoundCompleted('aptitude') ? 1 : 0) + (isRoundCompleted('coding') ? 1 : 0) + (isRoundCompleted('interview') ? 1 : 0)) / 3 * 100) : 0}%
                            </div>
                            <div className="text-xs text-on-surface-variant mt-2">Complete</div>
                        </div>
                    </div>

                    {/* Activity Timeline */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5 mb-8">
                        <h2 className="text-2xl font-headline font-bold text-on-surface mb-6">Assessment Progress</h2>
                        <div className="space-y-6">
                            {/* Aptitude */}
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-white font-bold flex-shrink-0 mt-1">
                                    📊
                                </div>
                                <div className="flex-grow">
                                    <h3 className="text-lg font-bold text-on-surface mb-1">Aptitude Assessment</h3>
                                    <p className="text-on-surface-variant text-sm mb-2">
                                        {isRoundCompleted('aptitude') 
                                            ? 'Completed - You demonstrated strong problem-solving skills' 
                                            : 'Ready to start - Answer 20 questions with adaptive difficulty'}
                                    </p>
                                    <div className="w-full h-2 bg-surface-container-highest rounded-full overflow-hidden">
                                        <div 
                                            className="h-full bg-gradient-to-r from-primary to-secondary transition-all duration-500"
                                            style={{ width: isRoundCompleted('aptitude') ? '100%' : '0%' }}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Coding Round */}
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-secondary to-cyan-600 flex items-center justify-center text-white font-bold flex-shrink-0 mt-1">
                                    💻
                                </div>
                                <div className="flex-grow">
                                    <h3 className="text-lg font-bold text-on-surface mb-1">Coding Interview</h3>
                                    <p className="text-on-surface-variant text-sm mb-2">
                                        {isRoundCompleted('coding') 
                                            ? 'Completed - Impressive coding solutions' 
                                            : 'Pending - Write and optimize code solutions'}
                                    </p>
                                    <div className="w-full h-2 bg-surface-container-highest rounded-full overflow-hidden">
                                        <div 
                                            className="h-full bg-gradient-to-r from-secondary to-cyan-500 transition-all duration-500"
                                            style={{ width: isRoundCompleted('coding') ? '100%' : '0%' }}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* HR Interview */}
                            <div className="flex items-start gap-4">
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center text-white font-bold flex-shrink-0 mt-1">
                                    🎤
                                </div>
                                <div className="flex-grow">
                                    <h3 className="text-lg font-bold text-on-surface mb-1">AI Mock Interview</h3>
                                    <p className="text-on-surface-variant text-sm mb-2">
                                        {isRoundCompleted('interview') 
                                            ? 'Completed - Strong verbal communication' 
                                            : 'Ready to start - Voice-based 1-on-1 simulation'}
                                    </p>
                                    <div className="w-full h-2 bg-surface-container-highest rounded-full overflow-hidden">
                                        <div 
                                            className="h-full bg-gradient-to-r from-purple-600 to-pink-500 transition-all duration-500"
                                            style={{ width: isRoundCompleted('interview') ? '100%' : '0%' }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Skills Section */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5 mb-8">
                        <h2 className="text-2xl font-headline font-bold text-on-surface mb-6">Technical Strengths</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {['Problem Solving', 'Time Management', 'Coding', 'Communication', 'Adaptability', 'Logic', 'Algorithms', 'System Design'].map((skill, idx) => (
                                <div key={idx} className="bg-surface-container-high px-4 py-3 rounded-lg text-center hover:bg-surface-variant transition-colors border border-outline-variant/20 hover:border-primary/30">
                                    <span className="text-sm font-semibold text-on-surface">{skill}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Achievements Section */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                        <h2 className="text-2xl font-headline font-bold text-on-surface mb-6">Achievements</h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-surface-container-high rounded-xl p-6 text-center hover:scale-105 transition-transform duration-300">
                                <div className="text-4xl mb-2">🚀</div>
                                <p className="text-xs text-on-surface-variant font-label uppercase tracking-tighter">Quick Learner</p>
                            </div>
                            <div className="bg-surface-container-high rounded-xl p-6 text-center hover:scale-105 transition-transform duration-300">
                                <div className="text-4xl mb-2">⚡</div>
                                <p className="text-xs text-on-surface-variant font-label uppercase tracking-tighter">Fast Solver</p>
                            </div>
                            <div className="bg-surface-container-high rounded-xl p-6 text-center hover:scale-105 transition-transform duration-300">
                                <div className="text-4xl mb-2">🎯</div>
                                <p className="text-xs text-on-surface-variant font-label uppercase tracking-tighter">High Accuracy</p>
                            </div>
                            <div className="bg-surface-container-high rounded-xl p-6 text-center hover:scale-105 transition-transform duration-300 opacity-50">
                                <div className="text-4xl mb-2">🏆</div>
                                <p className="text-xs text-on-surface-variant font-label uppercase tracking-tighter">Perfect Score</p>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
