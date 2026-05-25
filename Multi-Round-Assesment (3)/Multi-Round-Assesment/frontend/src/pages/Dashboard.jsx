import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function Dashboard() {
    const [userName, setUserName] = useState('Candidate');
    const [currentTime, setCurrentTime] = useState(new Date());
    const [comingSoonModal, setComingSoonModal] = useState(null);
    const [progress, setProgress] = useState(0);
    const [completedRounds, setCompletedRounds] = useState(0);
    const [toast, setToast] = useState(null);
    const [loading, setLoading] = useState(true);
    const [roundStatus, setRoundStatus] = useState({
        aptitude: 'pending',
        coding: 'locked',
        interview: 'pending'
    });
    const navigate = useNavigate();

    const resolveDisplayName = () => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            try {
                const user = JSON.parse(storedUser);
                return user.full_name || user.name || user.username || 'Candidate';
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
        if (email && email.includes('@')) {
            const [prefix] = email.split('@');
            return prefix || 'Candidate';
        }

        return 'Candidate';
    };

    const getRoundCompletionMap = (sessionData) => {
        const roundMap = {
            aptitude: false,
            coding: false,
            interview: false,
        };

        const rounds = Array.isArray(sessionData?.rounds) ? sessionData.rounds : [];
        rounds.forEach((round) => {
            const roundType = round?.round_type;
            if (Object.prototype.hasOwnProperty.call(roundMap, roundType)) {
                roundMap[roundType] = round?.status === 'completed';
            }
        });

        return roundMap;
    };

    useEffect(() => {
        setUserName(resolveDisplayName());

        const interval = setInterval(() => setCurrentTime(new Date()), 60000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        const fetchProgress = async () => {
            setLoading(true);
            try {
                const res = await api.get('/session/status');
                const data = res.data;

                const completionMap = getRoundCompletionMap(data);
                const completed = Object.values(completionMap).filter(Boolean).length;
                const newStatus = {
                    aptitude: completionMap.aptitude ? 'completed' : 'pending',
                    coding: completionMap.coding ? 'completed' : 'pending',
                    interview: completionMap.interview ? 'completed' : 'pending',
                };
                
                setCompletedRounds(completed);
                setRoundStatus(newStatus);
                setProgress((completed / 3) * 100);
            } catch (err) {
                setCompletedRounds(0);
                setRoundStatus({
                    aptitude: 'pending',
                    coding: 'pending',
                    interview: 'pending',
                });
                setProgress(0);
            } finally {
                setLoading(false);
            }
        };
        
        fetchProgress();
    }, []);

    const handleStartAptitude = async () => {
        try {
            await api.post('/session/start');
            navigate('/aptitude');
        } catch (error) {
            setToast({ type: 'error', message: 'Failed to start aptitude test' });
        }
    };

    const handleStartCoding = () => {
        setComingSoonModal('Coding Challenge');
    };

    const handleResumeUpload = async () => {
        try {
            await api.post('/session/start');
            navigate('/resume-upload');
        } catch (error) {
            setToast({ type: 'error', message: 'Failed to start interview' });
        }
    };

    const getGreeting = () => {
        const hour = currentTime.getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'completed':
                return '✓';
            case 'pending':
                return '→';
            case 'locked':
                return '🔒';
            default:
                return '○';
        }
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'completed':
                return 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400';
            case 'pending':
                return 'bg-primary/20 border-primary/30 text-primary';
            case 'locked':
                return 'bg-gray-500/20 border-gray-500/30 text-gray-400';
            default:
                return 'bg-gray-500/20 border-gray-500/30 text-gray-400';
        }
    };

    if (loading) {
        return <PageSkeleton variant="dark" cardCount={3} />;
    }


    return (
        <div className="min-h-screen bg-background text-on-surface font-body selection:bg-primary/30 antialiased">
            <Navbar 
                position="sticky"
                rightContent={
                    <button onClick={() => navigate('/profile')} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center text-white font-bold text-sm">
                            {userName?.charAt(0) || 'U'}
                        </div>
                    </button>
                }
                onLogout={() => {}} 
            />
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-6 pt-10 pb-12">
                {/* Greeting Section */}
                <div className="mb-16">
                    <h1 className="text-5xl md:text-6xl font-headline font-black tracking-tighter text-on-surface mb-4">
                        {getGreeting()}, <span className="text-primary">{userName}</span>
                    </h1>
                    <p className="text-lg text-on-surface-variant max-w-2xl">
                        Continue with your assessment rounds. You're {Math.round(progress)}% complete.
                    </p>
                </div>

                {/* Progress Card */}
                <div className="mb-12 bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <p className="text-sm font-label text-on-surface-variant uppercase tracking-widest mb-2">Overall Progress</p>
                            <p className="text-5xl font-headline font-bold text-primary">{Math.round(progress)}%</p>
                        </div>
                        <div className="text-right">
                            <p className="text-sm text-on-surface-variant mb-2">{completedRounds} of 3 rounds complete</p>
                        </div>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-2 bg-surface-container-highest rounded-full overflow-hidden">
                        <div 
                            className="h-full bg-gradient-to-r from-primary to-secondary transition-all duration-500"
                            style={{ width: `${progress}%` }}
                        ></div>
                    </div>
                </div>

                {/* Assessment Rounds Grid */}
                <div className="mb-16">
                    <h2 className="text-2xl font-headline font-bold text-on-surface mb-8">Assessment Rounds</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Round 1: Aptitude */}
                        <div className={`bg-surface-container border border-outline-variant/20 rounded-xl p-8 backdrop-blur-sm transition-all ${roundStatus.aptitude === 'completed' ? 'border-primary/30' : 'hover:border-primary/50'}`}>
                            <div className="flex items-start gap-4 mb-6">
                                <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-xl">📊</span>
                                </div>
                                <span className={`text-xs font-label uppercase tracking-widest px-3 py-1 rounded-full border ${getStatusColor(roundStatus.aptitude)}`}>
                                    {roundStatus.aptitude === 'completed' ? 'Completed' : 'Ready'}
                                </span>
                            </div>
                            <h3 className="text-xl font-headline font-bold text-on-surface mb-2">Aptitude Test</h3>
                            <p className="text-sm text-on-surface-variant mb-6">Adaptive reasoning test powered by AI</p>
                            <div className="flex flex-col gap-3 mb-6">
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>⚙️</span>
                                    <span>Adaptive difficulty</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>🤖</span>
                                    <span>RL-Driven</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>⏱️</span>
                                    <span>30 minutes</span>
                                </div>
                            </div>
                            <button
                                onClick={handleStartAptitude}
                                disabled={roundStatus.aptitude === 'completed'}
                                className={`w-full py-3 px-4 rounded-lg font-semibold transition-all active:scale-95 ${
                                    roundStatus.aptitude === 'completed'
                                        ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                                        : 'hero-gradient text-on-primary-container shadow-lg shadow-primary/20 hover:shadow-lg hover:shadow-primary/30'
                                }`}
                            >
                                {roundStatus.aptitude === 'completed' ? 'Completed' : 'Start Test'} {getStatusIcon(roundStatus.aptitude)}
                            </button>
                        </div>

                        {/* Round 2: Coding */}
                        <div className={`bg-surface-container border border-outline-variant/20 rounded-xl p-8 backdrop-blur-sm transition-all ${roundStatus.coding === 'completed' ? 'border-primary/30' : 'hover:border-primary/50'}`}>
                            <div className="flex items-start gap-4 mb-6">
                                <div className="w-12 h-12 rounded-lg bg-gray-500/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-xl">💻</span>
                                </div>
                                <span className={`text-xs font-label uppercase tracking-widest px-3 py-1 rounded-full border ${getStatusColor(roundStatus.coding)}`}>
                                    {roundStatus.coding === 'completed' ? 'Completed' : 'Pending'}
                                </span>
                            </div>
                            <h3 className="text-xl font-headline font-bold text-on-surface mb-2">Coding Challenge</h3>
                            <p className="text-sm text-on-surface-variant mb-6">Write code to solve algorithmic problems</p>
                            <div className="flex flex-col gap-3 mb-6">
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>🎯</span>
                                    <span>Multiple languages</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>⚡</span>
                                    <span>Real-time evaluation</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>🏆</span>
                                    <span>Skill assessment</span>
                                </div>
                            </div>
                            <button
                                onClick={handleStartCoding}
                                disabled={roundStatus.coding === 'completed'}
                                className={`w-full py-3 px-4 rounded-lg font-semibold transition-all active:scale-95 ${
                                    roundStatus.coding === 'completed'
                                        ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                                        : 'bg-gray-500/20 text-gray-300 hover:bg-gray-500/30'
                                }`}
                            >
                                {roundStatus.coding === 'completed' ? 'Completed' : 'Coming Soon'} {getStatusIcon(roundStatus.coding)}
                            </button>
                        </div>

                        {/* Round 3: Interview */}
                        <div className={`bg-surface-container border border-outline-variant/20 rounded-xl p-8 backdrop-blur-sm transition-all ${roundStatus.interview === 'completed' ? 'border-secondary/30' : 'hover:border-secondary/50'}`}>
                            <div className="flex items-start gap-4 mb-6">
                                <div className="w-12 h-12 rounded-lg bg-secondary/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-xl">🎤</span>
                                </div>
                                <span className={`text-xs font-label uppercase tracking-widest px-3 py-1 rounded-full border ${getStatusColor(roundStatus.interview)}`}>
                                    {roundStatus.interview === 'completed' ? 'Completed' : 'Ready'}
                                </span>
                            </div>
                            <h3 className="text-xl font-headline font-bold text-on-surface mb-2">AI Mock Interview</h3>
                            <p className="text-sm text-on-surface-variant mb-6">Voice-based conversational interview</p>
                            <div className="flex flex-col gap-3 mb-6">
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>🎙️</span>
                                    <span>Voice interaction</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>🧠</span>
                                    <span>Personalized questions</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                                    <span>📹</span>
                                    <span>Proctored session</span>
                                </div>
                            </div>
                            <button
                                onClick={handleResumeUpload}
                                disabled={roundStatus.interview === 'completed'}
                                className={`w-full py-3 px-4 rounded-lg font-semibold transition-all active:scale-95 ${
                                    roundStatus.interview === 'completed'
                                        ? 'bg-emerald-500/20 text-emerald-400 cursor-default'
                                        : 'bg-secondary/20 text-secondary shadow-lg shadow-secondary/20 hover:shadow-lg hover:shadow-secondary/30'
                                }`}
                            >
                                {roundStatus.interview === 'completed' ? 'Completed' : 'Start Interview'} {getStatusIcon(roundStatus.interview)}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Analytics CTA */}
                {completedRounds >= 1 ? (
                    <div className="bg-gradient-to-r from-primary/20 to-secondary/20 border border-primary/30 rounded-xl p-8 flex items-center justify-between mb-16">
                        <div>
                            <p className="text-lg font-headline font-bold text-on-surface mb-2">View Your Performance Analysis</p>
                            <p className="text-sm text-on-surface-variant">
                                {completedRounds === 3 ? 'Complete analysis from all rounds' : `Based on ${completedRounds} completed round${completedRounds !== 1 ? 's' : ''}`}
                            </p>
                        </div>
                        <button
                            onClick={() => navigate('/analytics')}
                            className="flex-shrink-0 ml-6 hero-gradient text-on-primary-container font-semibold px-6 py-3 rounded-lg active:scale-95 transition-all shadow-lg shadow-primary/20"
                        >
                            View Analytics →
                        </button>
                    </div>
                ) : null}

                {/* Coming Soon Modal */}
                {comingSoonModal && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                        <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 max-w-sm shadow-2xl">
                            <h2 className="text-2xl font-headline font-bold text-on-surface mb-2">{comingSoonModal}</h2>
                            <p className="text-on-surface-variant mb-6 text-sm">This round is coming soon. Please check back later or contact support for updates.</p>
                            <button
                                onClick={() => setComingSoonModal(null)}
                                className="w-full hero-gradient text-on-primary-container font-semibold py-3 rounded-lg transition-all active:scale-95"
                            >
                                Got it
                            </button>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
