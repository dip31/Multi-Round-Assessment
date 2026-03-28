import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function Dashboard() {
    const [userName, setUserName] = useState('Candidate');
    const [currentTime, setCurrentTime] = useState(new Date());
    const [comingSoonModal, setComingSoonModal] = useState(null);
    const [progress, setProgress] = useState(0);
    const navigate = useNavigate();

    useEffect(() => {
        // Get user info from auth context or localStorage
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            try {
                const user = JSON.parse(storedUser);
                setUserName(user.full_name || 'Candidate');
            } catch (e) {
                setUserName('Candidate');
            }
        }

        // Update time every minute
        const interval = setInterval(() => setCurrentTime(new Date()), 60000);
        return () => clearInterval(interval);
    }, []);

    const getGreeting = () => {
        const hour = currentTime.getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 18) return 'Good afternoon';
        return 'Good evening';
    };

    useEffect(() => {
        // Calculate progress: 0% on start, 33% per completed round
        // For now, show 0% (user just started, no rounds completed yet)
        setProgress(0);
    }, []);

    const handleStartAptitude = async () => {
        try {
            // Start or get existing session (idempotent)
            const response = await fetch('/api/v1/session/start', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            if (response.ok) {
                navigate('/aptitude');
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('Failed to start aptitude:', response.status, errorData);
                setComingSoonModal('Error starting aptitude test');
            }
        } catch (error) {
            console.error('Failed to start aptitude:', error);
            setComingSoonModal('Error starting aptitude test');
        }
    };

    const handleStartCoding = () => {
        setComingSoonModal('Coding Challenge');
    };

    const handleResumeUpload = async () => {
        try {
            // Start or get existing session (idempotent)
            const response = await fetch('/api/v1/session/start', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            if (response.ok) {
                navigate('/resume-upload');
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('Failed to get or create session:', response.status, errorData);
            }
        } catch (error) {
            console.error('Failed to start interview:', error);
        }
    };

    const roundFeatures = [
        { label: 'Adaptive' },
        { label: 'Real-time' },
        { label: 'Proctored' }
    ];

    const activities = [
        { id: 1, text: 'Started Aptitude Test', time: '2 hours ago' },
        { id: 2, text: 'Completed Coding Round', time: 'Yesterday' },
        { id: 3, text: 'Assessment started', time: '2 days ago' }
    ];

    return (
        <div className="min-h-screen bg-slate-50">
            <Navbar />

            <main className="mx-auto max-w-6xl px-6 py-12">
                {/* Greeting Section */}
                <div className="mb-12">
                    <h1 className="text-4xl font-bold text-slate-900 mb-2">
                        {getGreeting()}, <span className="text-blue-600">{userName}</span>
                    </h1>
                    <p className="text-slate-600 text-base">Continue with your assessment rounds. You're {Math.round(progress)}% complete.</p>
                </div>

                {/* Progress Card */}
                <div className="mb-12 bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                        <div>
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Overall Progress</p>
                            <p className="text-4xl font-bold text-slate-900">{Math.round(progress)}%</p>
                        </div>
                        <div className="text-right">
                            <p className="text-sm text-slate-600 mb-1">1 of 3 rounds complete</p>
                        </div>
                    </div>

                    {/* Progress Stepper */}
                    <div className="flex items-center gap-4">
                        {/* Step 1: Aptitude */}
                        <div className="flex flex-col items-center gap-2 flex-1">
                            <div className="w-10 h-10 bg-green-100 border border-green-300 rounded-full flex items-center justify-center">
                                <span className="text-green-600 text-lg">✓</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 text-center">Aptitude</p>
                        </div>

                        {/* Connection */}
                        <div className="flex-1 h-1 bg-green-300 rounded-full"></div>

                        {/* Step 2: Coding */}
                        <div className="flex flex-col items-center gap-2 flex-1">
                            <div className="w-10 h-10 bg-green-100 border border-green-300 rounded-full flex items-center justify-center">
                                <span className="text-green-600 text-lg">✓</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 text-center">Coding</p>
                        </div>

                        {/* Connection */}
                        <div className="flex-1 h-1 bg-slate-300 rounded-full"></div>

                        {/* Step 3: Interview */}
                        <div className="flex flex-col items-center gap-2 flex-1">
                            <div className="w-10 h-10 bg-slate-200 border border-slate-300 rounded-full flex items-center justify-center">
                                <span className="text-slate-600 font-bold text-sm">3</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 text-center">Interview</p>
                        </div>
                    </div>
                </div>

                {/* Assessment Rounds Grid */}
                <div className="mb-12">
                    <h2 className="text-xl font-bold text-slate-900 mb-6">Assessment Rounds</h2>
                    <div className="grid grid-cols-3 gap-6">
                        {/* Round 1: Aptitude - Ready */}
                        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between mb-4">
                                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <span className="text-blue-600 text-xl font-bold">T</span>
                                </div>
                                <span className="inline-flex items-center gap-1.5 bg-green-100 text-green-700 text-xs font-semibold px-3 py-1 rounded-full">
                                    Ready to Start
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-1">Aptitude Test</h3>
                            <p className="text-slate-600 text-sm mb-6">Verbal, logical, and quantitative reasoning</p>
                            <div className="flex flex-col gap-2 mb-6">
                                <div className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-full">
                                    <span>•</span>
                                    <span>Adaptive</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-full">
                                    <span>•</span>
                                    <span>RL-Driven</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-full">
                                    <span>•</span>
                                    <span>Timed</span>
                                </div>
                            </div>
                            <button
                                onClick={handleStartAptitude}
                                className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold py-3 px-4 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-sm"
                            >
                                Start Test
                                <span>→</span>
                            </button>
                        </div>

                        {/* Round 2: Coding - Coming Soon */}
                        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm opacity-60 cursor-not-allowed">
                            <div className="flex items-start justify-between mb-4">
                                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                                    <span className="text-slate-400 text-xl font-bold">C</span>
                                </div>
                                <span className="inline-flex items-center gap-1.5 bg-slate-100 text-slate-600 text-xs font-semibold px-3 py-1 rounded-full">
                                    Coming Soon
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-1">Coding Challenge</h3>
                            <p className="text-slate-600 text-sm mb-6">Write working code to solve problems</p>
                            <div className="bg-slate-50 rounded-xl p-4">
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Status</p>
                                <p className="text-sm font-medium text-slate-600">Not available yet</p>
                            </div>
                        </div>

                        {/* Round 3: Interview - Ready */}
                        <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between mb-4">
                                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <span className="text-blue-600 text-xl font-bold">I</span>
                                </div>
                                <span className="inline-flex items-center gap-1.5 bg-blue-100 text-blue-700 text-xs font-semibold px-3 py-1 rounded-full">
                                    Ready to Start
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-1">AI Mock Interview</h3>
                            <p className="text-slate-600 text-sm mb-6">Voice-based interview with personalized questions</p>

                            {/* Feature Pills */}
                            <div className="flex flex-col gap-2 mb-6">
                                {roundFeatures.map((feature, idx) => (
                                    <div
                                        key={idx}
                                        className="flex items-center gap-2 text-xs font-medium text-slate-700 bg-slate-50 px-3 py-2 rounded-full"
                                    >
                                        <span>{feature.icon}</span>
                                        <span>{feature.label}</span>
                                    </div>
                                ))}
                            </div>

                            {/* CTA Button */}
                            <button
                                onClick={handleResumeUpload}
                                className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-semibold py-3 px-4 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-sm"
                            >
                                Start Interview
                                <span>→</span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Recent Activity */}
                <div className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm">
                    <h2 className="text-lg font-bold text-slate-900 mb-6">Recent Activity</h2>
                    <div className="space-y-4">
                        {activities.map((activity) => (
                            <div key={activity.id} className="flex items-start gap-4">
                                <div className="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center flex-shrink-0">
                                    <span className="text-slate-400 text-xs font-bold">•</span>
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-slate-900">{activity.text}</p>
                                    <p className="text-xs text-slate-500 mt-1">{activity.time}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Coming Soon Modal */}
                {comingSoonModal && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-2xl p-8 max-w-sm shadow-2xl">
                            <h2 className="text-2xl font-bold text-slate-900 mb-2">{comingSoonModal}</h2>
                            <p className="text-slate-600 mb-6">This round is coming soon. Currently, only the AI Mock Interview is available.</p>
                            <button
                                onClick={() => setComingSoonModal(null)}
                                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-all"
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
