import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../services/api';

export default function Analytics() {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [analytics, setAnalytics] = useState(null);
    const [userName, setUserName] = useState('');

    useEffect(() => {
        const fetchAnalytics = async () => {
            try {
                const response = await api.get('/report/analytics');
                setAnalytics(response.data);
                
                // Try to get user name from localStorage
                const storedName = localStorage.getItem('user_name') || localStorage.getItem('full_name');
                setUserName(storedName || 'Candidate');
            } catch (err) {
                console.error('Failed to fetch analytics:', err);
                if (err.response?.status === 401) {
                    navigate('/login');
                    return;
                }
                setError(err.response?.data?.detail || 'Failed to load analytics');
            } finally {
                setLoading(false);
            }
        };

        fetchAnalytics();
    }, [navigate]);

    // Loading state
    if (loading) {
        return (
            <div className="bg-[#0e0e10] text-[#f9f5f8] min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-on-surface-variant">Loading your analytics...</p>
                </div>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="bg-[#0e0e10] text-[#f9f5f8] min-h-screen flex items-center justify-center">
                <div className="text-center max-w-md mx-auto p-8">
                    <div className="w-16 h-16 bg-error-container/20 rounded-full flex items-center justify-center mx-auto mb-4">
                        <span className="material-symbols-outlined text-error-dim text-2xl">error</span>
                    </div>
                    <h2 className="text-xl font-bold text-on-surface mb-2">Unable to Load Analytics</h2>
                    <p className="text-on-surface-variant mb-6">{error}</p>
                    <button 
                        onClick={() => window.location.reload()} 
                        className="bg-primary text-on-primary px-6 py-3 rounded-full font-semibold"
                    >
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    // No data state
    if (!analytics || analytics.completed_rounds.length === 0) {
        return (
            <div className="bg-[#0e0e10] text-[#f9f5f8] min-h-screen">
                <nav className="fixed top-0 w-full z-50 bg-[#0e0e10]/60 backdrop-blur-xl border-b border-[#48474a]/20 flex justify-between items-center px-8 h-16">
                    <div className="text-xl font-bold tracking-tighter text-[#f9f5f8] flex items-center gap-2">
                        <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>analytics</span>
                        AIPlacement
                    </div>
                    <Link to="/dashboard" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">← Back to Dashboard</Link>
                </nav>
                
                <main className="pt-28 pb-20 px-8 max-w-3xl mx-auto text-center">
                    <div className="glass-panel p-12 rounded-3xl">
                        <div className="w-20 h-20 bg-surface-container rounded-full flex items-center justify-center mx-auto mb-6">
                            <span className="material-symbols-outlined text-on-surface-variant text-4xl">query_stats</span>
                        </div>
                        <h1 className="text-2xl font-bold text-on-surface mb-4">No Analytics Available Yet</h1>
                        <p className="text-on-surface-variant mb-8 max-w-md mx-auto">
                            Complete at least one assessment round to see your performance analytics and insights.
                        </p>
                        <Link 
                            to="/dashboard" 
                            className="inline-flex items-center gap-2 bg-primary text-on-primary px-8 py-3 rounded-full font-bold"
                        >
                            Start an Assessment
                            <span className="material-symbols-outlined text-sm">arrow_forward</span>
                        </Link>
                    </div>
                </main>
            </div>
        );
    }

    // Calculate derived values
    const responseTimeDiff = analytics.benchmark_response_time > 0 
        ? Math.round(((analytics.benchmark_response_time - analytics.avg_response_time) / analytics.benchmark_response_time) * 100)
        : 0;
    const isFasterThanBenchmark = responseTimeDiff > 0;

    return (
        <div className="bg-[#0e0e10] text-[#f9f5f8] font-body selection:bg-primary/30 min-h-screen relative z-0 overflow-x-hidden">
            {/* Background Glows */}
            <div className="fixed w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(186,158,255,0.08)_0%,rgba(14,14,16,0)_70%)] -z-10 blur-[80px] top-[-10%] right-[-10%]"></div>
            <div className="fixed w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(186,158,255,0.08)_0%,rgba(14,14,16,0)_70%)] -z-10 blur-[80px] bottom-[-10%] left-[-10%] opacity-50"></div>

            {/* TopNavBar */}
            <nav className="fixed top-0 w-full z-50 bg-[#0e0e10]/60 backdrop-blur-xl border-b border-[#48474a]/20 flex justify-between items-center px-8 h-16 shadow-2xl shadow-black/50">
                <div className="text-xl font-bold tracking-tighter text-[#f9f5f8] flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>analytics</span>
                    AIPlacement
                </div>
                <div className="hidden md:flex gap-8 items-center font-['Inter'] tracking-tight">
                    <Link to="/dashboard" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">Dashboard</Link>
                    <Link to="/analytics" className="text-[#ba9eff] border-b-2 border-[#ba9eff] pb-1">Analytics</Link>
                </div>
                <div className="flex items-center gap-4">
                    <button className="p-2 text-[#adaaad] hover:bg-[#262528]/50 rounded-lg transition-all active:scale-95 duration-200">
                        <span className="material-symbols-outlined">notifications</span>
                    </button>
                    <div className="h-8 w-8 rounded-full overflow-hidden border border-outline-variant/30 bg-primary/20 flex items-center justify-center">
                        <span className="text-primary font-bold text-sm">{userName.charAt(0).toUpperCase()}</span>
                    </div>
                </div>
            </nav>

            <main className="pt-28 pb-20 px-8 max-w-7xl mx-auto">
                {/* Header Section */}
                <header className="mb-12 flex flex-col md:flex-row justify-between items-end gap-6">
                    <div>
                        <span className="text-primary text-sm font-medium tracking-[0.2em] uppercase mb-2 block">Performance Analytics</span>
                        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-on-surface">Your Progress</h1>
                        <p className="text-on-surface-variant mt-4 max-w-lg leading-relaxed">
                            Detailed analysis of your assessment performance. AI-driven metrics highlight your strengths and identify areas for improvement.
                        </p>
                    </div>
                    <div className="flex gap-3">
                        <Link 
                            to="/dashboard"
                            className="bg-surface-container-high text-on-surface px-6 py-3 rounded-full border border-outline-variant/20 hover:bg-surface-bright transition-all flex items-center gap-2 text-sm font-semibold"
                        >
                            <span className="material-symbols-outlined text-sm">arrow_back</span> Dashboard
                        </Link>
                    </div>
                </header>

                {/* Summary Metrics */}
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                    <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between group">
                        <span className="text-on-surface-variant text-sm font-medium">Overall Score</span>
                        <div className="mt-4 flex items-baseline gap-2">
                            <span className="text-4xl font-bold text-primary tracking-tighter">{analytics.overall_score}%</span>
                        </div>
                        <div className="w-full bg-surface-container-lowest h-1.5 rounded-full mt-6 overflow-hidden">
                            <div 
                                className="bg-primary h-full rounded-full shadow-[0_0_10px_rgba(186,158,255,0.5)]"
                                style={{ width: `${Math.min(analytics.overall_score, 100)}%` }}
                            ></div>
                        </div>
                    </div>
                    
                    <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
                        <span className="text-on-surface-variant text-sm font-medium">Accuracy</span>
                        <div className="mt-4 flex items-baseline gap-2">
                            <span className="text-4xl font-bold text-on-surface tracking-tighter">{analytics.accuracy}%</span>
                            {analytics.accuracy >= 80 && (
                                <span className="material-symbols-outlined text-secondary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>verified</span>
                            )}
                        </div>
                        <p className="text-xs text-on-surface-variant mt-6">
                            {analytics.accuracy >= 90 ? 'Excellent consistency' : 
                             analytics.accuracy >= 70 ? 'Good accuracy' : 
                             'Room for improvement'}
                        </p>
                    </div>

                    <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
                        <span className="text-on-surface-variant text-sm font-medium">Percentile Rank</span>
                        <div className="mt-4">
                            <span className="text-4xl font-bold text-tertiary tracking-tighter">
                                {analytics.percentile}<span className="text-lg">th</span>
                            </span>
                        </div>
                        <p className="text-xs text-on-surface-variant mt-6">
                            {analytics.percentile >= 90 ? 'Top performer!' : 
                             analytics.percentile >= 75 ? 'Above average' : 
                             analytics.percentile >= 50 ? 'Average performance' :
                             'Keep improving'}
                        </p>
                    </div>

                    <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between">
                        <span className="text-on-surface-variant text-sm font-medium">Total Questions</span>
                        <div className="mt-4">
                            <span className="text-4xl font-bold text-on-surface tracking-tighter">{analytics.total_questions}</span>
                        </div>
                        <p className="text-xs text-on-surface-variant mt-6">
                            {analytics.completed_rounds.length} round{analytics.completed_rounds.length !== 1 ? 's' : ''} completed
                        </p>
                    </div>
                </section>

                {/* Main Analytics Grid */}
                <div className="grid grid-cols-12 gap-6 mb-12">
                    {/* Completed Rounds Progress */}
                    <div className="col-span-12 lg:col-span-8 glass-panel p-8 rounded-3xl">
                        <div className="flex justify-between items-start mb-10">
                            <div>
                                <h3 className="text-xl font-bold text-on-surface tracking-tight">Round Completion</h3>
                                <p className="text-sm text-on-surface-variant">Your assessment journey progress</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-3 gap-4">
                            {['aptitude', 'coding', 'interview'].map((roundType) => {
                                const isCompleted = analytics.completed_rounds.includes(roundType);
                                const roundNames = {
                                    aptitude: 'Aptitude',
                                    coding: 'Coding',
                                    interview: 'Interview'
                                };
                                return (
                                    <div 
                                        key={roundType}
                                        className={`p-6 rounded-2xl border ${
                                            isCompleted 
                                                ? 'bg-primary/10 border-primary/30' 
                                                : 'bg-surface-container border-outline-variant/20'
                                        }`}
                                    >
                                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                                            isCompleted ? 'bg-primary' : 'bg-surface-container-high'
                                        }`}>
                                            {isCompleted ? (
                                                <span className="material-symbols-outlined text-on-primary">check</span>
                                            ) : (
                                                <span className="material-symbols-outlined text-on-surface-variant">hourglass_empty</span>
                                            )}
                                        </div>
                                        <h4 className="font-bold text-on-surface">{roundNames[roundType]}</h4>
                                        <p className={`text-xs mt-1 ${isCompleted ? 'text-primary' : 'text-on-surface-variant'}`}>
                                            {isCompleted ? 'Completed' : 'Pending'}
                                        </p>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Skill Breakdown */}
                    <div className="col-span-12 lg:col-span-4 glass-panel p-8 rounded-3xl">
                        <h3 className="text-xl font-bold text-on-surface tracking-tight mb-8">Skill Breakdown</h3>
                        {analytics.skill_breakdown.length > 0 ? (
                            <div className="space-y-6">
                                {analytics.skill_breakdown.map((skill, idx) => (
                                    <div key={idx} className="space-y-2">
                                        <div className="flex justify-between text-xs font-medium uppercase tracking-wider text-on-surface-variant">
                                            <span>{skill.name}</span>
                                            <span className="text-on-surface">{skill.score}%</span>
                                        </div>
                                        <div className="h-2 w-full bg-surface-container rounded-full overflow-hidden">
                                            <div 
                                                className="h-full bg-primary transition-all duration-500"
                                                style={{ width: `${Math.min(skill.score, 100)}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-on-surface-variant text-sm">Complete assessments to see skill breakdown</p>
                        )}

                        {analytics.skill_breakdown.length > 0 && (
                            <div className="mt-10 p-4 rounded-xl bg-primary/5 border border-primary/10">
                                <p className="text-xs text-primary leading-relaxed">
                                    <span className="font-bold">Pro Tip:</span> Focus on your lowest scoring areas to maximize improvement.
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
                    {/* Response Time Analysis */}
                    <div className="glass-panel p-8 rounded-3xl">
                        <h3 className="text-xl font-bold text-on-surface tracking-tight mb-2">Response Time Analysis</h3>
                        <p className="text-sm text-on-surface-variant mb-8">Average seconds per answer</p>
                        
                        <div className="flex items-end gap-12 h-40 pb-4 border-b border-outline-variant/10">
                            <div className="flex flex-col items-center gap-4 flex-1">
                                <div className="w-full bg-surface-container rounded-t-xl h-[90%] relative group">
                                    <div 
                                        className="absolute bottom-0 w-full bg-secondary rounded-t-xl shadow-[0_0_20px_rgba(45,183,242,0.3)]"
                                        style={{ height: `${Math.min((analytics.avg_response_time / 120) * 100, 100)}%` }}
                                    ></div>
                                    <span className="absolute -top-8 text-xs font-bold text-on-surface">{Math.round(analytics.avg_response_time)}s</span>
                                </div>
                                <span className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest text-center">Your Avg</span>
                            </div>
                            <div className="flex flex-col items-center gap-4 flex-1">
                                <div className="w-full bg-surface-container rounded-t-xl h-[90%] relative group">
                                    <div 
                                        className="absolute bottom-0 w-full bg-outline-variant/50 rounded-t-xl"
                                        style={{ height: `${Math.min((analytics.benchmark_response_time / 120) * 100, 100)}%` }}
                                    ></div>
                                    <span className="absolute -top-8 text-xs font-bold text-on-surface-variant">{Math.round(analytics.benchmark_response_time)}s</span>
                                </div>
                                <span className="text-[10px] uppercase font-bold text-on-surface-variant tracking-widest text-center">Benchmark</span>
                            </div>
                        </div>

                        <p className="mt-6 text-sm text-on-surface-variant">
                            {isFasterThanBenchmark ? (
                                <>You are answering <span className="text-secondary font-bold">{Math.abs(responseTimeDiff)}% faster</span> than the benchmark.</>
                            ) : responseTimeDiff < 0 ? (
                                <>You are <span className="text-tertiary font-bold">{Math.abs(responseTimeDiff)}% slower</span> than the benchmark. Practice for speed!</>
                            ) : (
                                <>You are performing at the <span className="text-on-surface font-bold">benchmark level</span>.</>
                            )}
                        </p>
                    </div>

                    {/* Optimization Areas */}
                    <div className="glass-panel p-8 rounded-3xl">
                        <h3 className="text-xl font-bold text-on-surface tracking-tight mb-6">Optimization Areas</h3>
                        {analytics.optimization_areas.length > 0 ? (
                            <div className="space-y-4">
                                {analytics.optimization_areas.map((area, idx) => (
                                    <div 
                                        key={idx}
                                        className={`flex items-start gap-4 p-4 rounded-2xl ${
                                            area.severity === 'warning' 
                                                ? 'bg-error-container/10 border border-error-container/20'
                                                : 'bg-tertiary-container/10 border border-tertiary-container/20'
                                        }`}
                                    >
                                        <div className={`p-2 rounded-lg ${
                                            area.severity === 'warning'
                                                ? 'bg-error-container/20 text-error-dim'
                                                : 'bg-tertiary-container/20 text-tertiary-dim'
                                        }`}>
                                            <span className="material-symbols-outlined text-sm">
                                                {area.severity === 'warning' ? 'warning' : 'psychology'}
                                            </span>
                                        </div>
                                        <div>
                                            <h4 className="text-sm font-bold text-on-surface">{area.title}</h4>
                                            <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                                                {area.description}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-32 text-on-surface-variant">
                                <div className="text-center">
                                    <span className="material-symbols-outlined text-4xl text-secondary mb-2">celebration</span>
                                    <p className="text-sm">Great job! No major areas need attention.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Sessions Table */}
                {analytics.session_history.length > 0 && (
                    <div className="glass-panel rounded-3xl overflow-hidden mb-12 border border-outline-variant/20">
                        <div className="p-8 border-b border-outline-variant/10 flex justify-between items-center">
                            <h3 className="text-xl font-bold text-on-surface tracking-tight">Recent Sessions</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="bg-surface-container-low border-b border-outline-variant/10">
                                        <th className="px-8 py-4 text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">Session ID</th>
                                        <th className="px-8 py-4 text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">Type</th>
                                        <th className="px-8 py-4 text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">Date</th>
                                        <th className="px-8 py-4 text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">Score</th>
                                        <th className="px-8 py-4 text-[10px] uppercase tracking-[0.2em] font-bold text-on-surface-variant">Duration</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/5 bg-surface-container-lowest/30">
                                    {analytics.session_history.map((session, idx) => (
                                        <tr key={idx} className="hover:bg-surface-container-high/50 transition-colors">
                                            <td className="px-8 py-6">
                                                <span className="text-sm font-bold text-on-surface">{session.id}</span>
                                            </td>
                                            <td className="px-8 py-6">
                                                <span className="text-sm text-on-surface-variant">{session.type}</span>
                                            </td>
                                            <td className="px-8 py-6 text-sm text-on-surface-variant">{session.date}</td>
                                            <td className="px-8 py-6">
                                                <span className={`text-sm font-bold ${session.score >= 70 ? 'text-primary' : 'text-on-surface'}`}>
                                                    {session.score}%
                                                </span>
                                            </td>
                                            <td className="px-8 py-6 text-sm text-on-surface-variant">{session.duration}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </main>

            {/* Footer */}
            <footer className="bg-[#0e0e10] border-t border-[#48474a]/10 w-full py-12 relative z-10">
                <div className="flex flex-col md:flex-row justify-between items-center px-8 max-w-7xl mx-auto">
                    <div className="flex flex-col items-center md:items-start gap-4">
                        <div className="text-[#f9f5f8] font-bold flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>bolt</span>
                            AIPlacement
                        </div>
                        <p className="font-['Inter'] text-sm text-[#adaaad]">© 2024 AIPlacement. All rights reserved.</p>
                    </div>
                    <div className="flex gap-8 mt-8 md:mt-0 font-['Inter'] text-sm">
                        <Link to="#" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">Privacy Policy</Link>
                        <Link to="#" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">Terms of Service</Link>
                        <Link to="#" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">Documentation</Link>
                        <Link to="#" className="text-[#adaaad] hover:text-[#f9f5f8] transition-colors">Support</Link>
                    </div>
                </div>
            </footer>
        </div>
    );
}
