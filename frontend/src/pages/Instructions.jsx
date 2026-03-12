import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useSession } from '../hooks/useSession';
import { useState } from 'react';

export default function Instructions() {
    const navigate = useNavigate();
    const { startSession } = useSession();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleStartAssessment = async () => {
        setLoading(true);
        setError('');
        try {
            await startSession();
            navigate('/aptitude');
        } catch (err) {
            if (err.response?.status === 409) {
                // If they have an active session, just let them back in
                navigate('/aptitude');
            } else {
                setError('Failed to initialize the assessment. Please check your connection and try again.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex h-screen flex-col bg-[var(--color-bg-primary)]">
            <Navbar />
            
            <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col justify-center px-4 py-8 sm:px-6 lg:px-8">
                <div className="overflow-hidden rounded-2xl border border-[var(--color-border)] bg-white shadow-xl shadow-black/5">
                    
                    {/* Header */}
                    <div className="border-b border-[var(--color-border)] bg-[var(--color-bg-surface)] px-8 py-6">
                        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-text-primary)] font-display">
                            Assessment Instructions
                        </h1>
                        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                            Please read all instructions carefully before beginning the technical aptitude round.
                        </p>
                    </div>

                    {/* Content */}
                    <div className="px-8 py-8">
                        <div className="space-y-8">
                            
                            {/* Section 1: format */}
                            <section>
                                <h2 className="mb-4 flex items-center text-lg font-semibold text-[var(--color-text-primary)]">
                                    <span className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
                                        ⏱️
                                    </span>
                                    Test Format
                                </h2>
                                <ul className="ml-11 list-outside list-disc space-y-2 text-sm text-[var(--color-text-secondary)] marker:text-[var(--color-border)]">
                                    <li>The assessment consists of exactly <strong>10 algorithmic and logical reasoning questions</strong>.</li>
                                    <li>The total accumulated time limit for the entire section is <strong>30 minutes</strong>.</li>
                                    <li>There is NO negative marking for incorrect answers. Attempt all questions.</li>
                                </ul>
                            </section>

                            {/* Section 2: Adaptive Engine */}
                            <section>
                                <h2 className="mb-4 flex items-center text-lg font-semibold text-[var(--color-text-primary)]">
                                    <span className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)]">
                                        🧠
                                    </span>
                                    Adaptive AI Engine
                                </h2>
                                <ul className="ml-11 list-outside list-disc space-y-2 text-sm text-[var(--color-text-secondary)] marker:text-[var(--color-border)]">
                                    <li>This test is powered by a Reinforcement Learning engine.</li>
                                    <li>Your subsequent question difficulty will algorithmically adjust based on your current accuracy and speed streaks.</li>
                                    <li><strong>Sequential Lock:</strong> You cannot skip a question and return to it later. Once an answer is submitted, the AI generates the next state and you cannot go backward.</li>
                                </ul>
                            </section>

                            {/* Section 3: Proctoring Rules */}
                            <section>
                                <h2 className="mb-4 flex items-center text-lg font-semibold text-[var(--color-text-primary)]">
                                    <span className="mr-3 flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-danger)]/10 text-[var(--color-danger)]">
                                        🛡️
                                    </span>
                                    Proctoring Environment
                                </h2>
                                <div className="ml-11 rounded-lg border border-[var(--color-danger)]/20 bg-[var(--color-danger)]/5 p-4">
                                    <p className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">
                                        Strict anti-cheat protocols are active:
                                    </p>
                                    <ul className="list-inside list-disc space-y-2 text-sm text-[var(--color-text-secondary)] marker:text-[var(--color-danger)]/50">
                                        <li>You must grant <strong>Camera permissions</strong> to begin the exam.</li>
                                        <li>The platform will enforce a <strong>Full-Screen lock</strong>. Escaping full-screen is a recorded violation.</li>
                                        <li><strong>Tab-switching is monitored</strong>. Leaving the test window will immediately flag your attempt.</li>
                                        <li>Refreshing the page will result in a hard penalty flag.</li>
                                    </ul>
                                </div>
                            </section>

                        </div>

                        {/* Error state */}
                        {error && (
                            <div className="mt-8 rounded-lg border border-[var(--color-danger)]/20 bg-[var(--color-danger)]/10 p-4 text-sm text-[var(--color-danger)]">
                                {error}
                            </div>
                        )}

                        {/* Action Builder */}
                        <div className="mt-10 border-t border-[var(--color-border)] pt-8 flex items-center justify-between">
                            <button
                                onClick={() => navigate('/dashboard')}
                                className="rounded-lg px-6 py-2.5 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-elevated)]"
                            >
                                ← Back to Dashboard
                            </button>
                            
                            <button
                                onClick={handleStartAssessment}
                                disabled={loading}
                                className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-accent)] px-8 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[var(--color-accent)]/90 disabled:opacity-50"
                            >
                                {loading ? (
                                    <>
                                        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Initializing Engine...
                                    </>
                                ) : (
                                    <>
                                        I Understand, Begin Assessment
                                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                        </svg>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
