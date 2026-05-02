import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import { useSession } from '../hooks/useSession';
import { useState, useEffect } from 'react';

export default function Instructions() {
    const navigate = useNavigate();
    const { startSession } = useSession();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [userName, setUserName] = useState('User');

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            try {
                const user = JSON.parse(storedUser);
                setUserName(user.full_name || user.name || 'User');
            } catch (e) {
                setUserName('User');
            }
        }
    }, []);

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
        <div className="min-h-screen bg-background text-on-surface font-body selection:bg-primary/30 antialiased">
            <Navbar 
                rightContent={
                    <button onClick={() => navigate('/profile')} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-r from-primary to-secondary flex items-center justify-center text-white font-bold text-sm">
                            {userName?.charAt(0) || 'U'}
                        </div>
                    </button>
                }
            />
            
            <main className="mx-auto max-w-4xl px-6 py-12 mt-12">
                <div className="bg-surface-container border border-outline-variant/20 rounded-2xl overflow-hidden shadow-lg shadow-primary/5">
                    
                    {/* Header */}
                    <div className="border-b border-outline-variant/20 bg-surface-container-high px-8 py-8">
                        <h1 className="text-3xl font-headline font-bold tracking-tight text-on-surface mb-2">
                            Assessment Instructions
                        </h1>
                        <p className="text-base text-on-surface-variant">
                            Please read all instructions carefully before beginning the technical aptitude round.
                        </p>
                    </div>

                    {/* Content */}
                    <div className="px-8 py-8">
                        <div className="space-y-10"
>
                            
                            {/* Section 1: format */}
                            <section>
                                <h2 className="mb-4 flex items-center text-xl font-headline font-bold text-on-surface">
                                    <span className="mr-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20 text-primary">
                                        ⏱️
                                    </span>
                                    Test Format
                                </h2>
                                <ul className="ml-14 list-outside list-disc space-y-3 text-sm text-on-surface-variant marker:text-outline-variant/50">
                                    <li>The assessment consists of exactly <strong>10 algorithmic and logical reasoning questions</strong>.</li>
                                    <li>The total accumulated time limit for the entire section is <strong>30 minutes</strong>.</li>
                                    <li>There is NO negative marking for incorrect answers. Attempt all questions.</li>
                                </ul>
                            </section>

                            {/* Section 2: Adaptive Engine */}
                            <section>
                                <h2 className="mb-4 flex items-center text-xl font-headline font-bold text-on-surface">
                                    <span className="mr-4 flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/20 text-secondary">
                                        🧠
                                    </span>
                                    Adaptive AI Engine
                                </h2>
                                <ul className="ml-14 list-outside list-disc space-y-3 text-sm text-on-surface-variant marker:text-outline-variant/50">
                                    <li>This test is powered by a Reinforcement Learning engine.</li>
                                    <li>Your subsequent question difficulty will algorithmically adjust based on your current accuracy and speed streaks.</li>
                                    <li><strong>Sequential Lock:</strong> You cannot skip a question and return to it later. Once an answer is submitted, the AI generates the next state and you cannot go backward.</li>
                                </ul>
                            </section>

                            {/* Section 3: Proctoring Rules */}
                            <section>
                                <h2 className="mb-4 flex items-center text-xl font-headline font-bold text-on-surface">
                                    <span className="mr-4 flex h-10 w-10 items-center justify-center rounded-lg bg-error/20 text-error">
                                        🛡️
                                    </span>
                                    Proctoring Environment
                                </h2>
                                <div className="ml-14 rounded-lg border border-error/30 bg-error/10 p-5">
                                    <p className="mb-4 text-base font-semibold text-on-surface">
                                        Strict anti-cheat protocols are active:
                                    </p>
                                    <ul className="list-inside list-disc space-y-2 text-sm text-on-surface-variant marker:text-error/50">
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
                            <div className="mt-8 rounded-lg border border-error/30 bg-error/10 p-4 text-sm text-error">
                                {error}
                            </div>
                        )}

                        {/* Action Builder */}
                        <div className="mt-12 border-t border-outline-variant/20 pt-8 flex items-center justify-between">
                            <button
                                onClick={() => navigate('/dashboard')}
                                className="rounded-lg px-6 py-3 text-sm font-semibold text-on-surface-variant transition hover:text-on-surface hover:bg-surface-container-high"
                            >
                                ← Back to Dashboard
                            </button>
                            
                            <button
                                onClick={handleStartAssessment}
                                disabled={loading}
                                className="inline-flex items-center gap-2 hero-gradient text-on-primary-container px-8 py-3 text-sm font-semibold shadow-lg shadow-primary/20 transition active:scale-95 disabled:opacity-50 rounded-lg"
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
