import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function Dashboard() {
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState('');
    const navigate = useNavigate();

    const handleStart = async () => {
        setLoading(true);
        setMessage('');
        try {
            // We just navigate to instructions, we don't start the session here yet
            navigate('/instructions');
        } catch (err) {
            setMessage('Failed to proceed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[var(--color-bg-primary)]">
            <Navbar />

            <main className="mx-auto max-w-3xl px-6 py-16">
                {/* Hero */}
                <div className="mb-12 text-center">
                    <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text-primary)] font-display">
                        Adaptive Assessment
                    </h1>
                    <p className="mx-auto mt-4 max-w-lg text-lg text-[var(--color-text-secondary)]">
                        Questions adapt to your skill level in real time using reinforcement learning.
                        The system adjusts difficulty based on your accuracy and speed.
                    </p>
                </div>

                {/* Cards */}
                <div className="grid gap-4 sm:grid-cols-3">
                    {[
                        { icon: '🧠', title: 'Adaptive', desc: 'Difficulty adjusts per answer' },
                        { icon: '⏱️', title: 'Timed', desc: 'Each question has a time limit' },
                        { icon: '📊', title: 'Analytics', desc: 'Detailed performance report' },
                    ].map((item) => (
                        <div
                            key={item.title}
                            className="rounded-[12px] border border-[var(--color-border)] bg-white p-6 text-center shadow-sm"
                        >
                            <div className="mb-3 text-2xl">{item.icon}</div>
                            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</h3>
                            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{item.desc}</p>
                        </div>
                    ))}
                </div>

                {/* Start button */}
                <div className="mt-12 text-center">
                    {message && (
                        <div className="mx-auto mb-4 max-w-sm rounded-lg border border-[#EAB308]/20 bg-[#EAB308]/10 px-4 py-3 text-sm text-[#EAB308]">
                            {message}
                        </div>
                    )}
                    <button
                        onClick={handleStart}
                        disabled={loading}
                        className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-accent)] px-8 py-3.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50 shadow-sm"
                    >
                        {loading ? (
                            <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        ) : (
                            <>
                                <span>Start Assessment</span>
                                <span>→</span>
                            </>
                        )}
                    </button>
                </div>
            </main>
        </div>
    );
}
