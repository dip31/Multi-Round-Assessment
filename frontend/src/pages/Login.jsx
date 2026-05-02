import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Toast } from '../components/Toast';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [apiError, setApiError] = useState('');
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState(null);
    const [dismissError, setDismissError] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const validateEmail = (e) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setApiError('');
        setDismissError(false);

        // Validation
        if (!email.trim()) {
            setApiError('Email is required');
            return;
        }
        if (!validateEmail(email)) {
            setApiError('Please enter a valid email address');
            return;
        }
        if (!password) {
            setApiError('Password is required');
            return;
        }

        setLoading(true);
        try {
            await login(email, password);
            setToast({ type: 'success', message: 'Login successful! Redirecting...' });
            setTimeout(() => navigate('/dashboard'), 500);
        } catch (err) {
            const detail = err.response?.data?.detail || 'Login failed. Please try again.';
            if (typeof detail === 'string') {
                setApiError(detail);
            } else if (Array.isArray(detail)) {
                setApiError(detail.map((d) => d.msg).join(', '));
            } else {
                setApiError('Login failed. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    };

    const features = [
        { icon: '⚡', label: 'AI-Powered' },
        { icon: '🎯', label: 'Adaptive' },
        { icon: '📊', label: 'Real-time Analytics' }
    ];

    return (
        <div className="min-h-screen bg-background text-on-surface font-body selection:bg-primary/30 antialiased flex flex-col">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            {/* Top Navigation */}
            <nav className="fixed top-0 w-full z-50 bg-zinc-950/60 backdrop-blur-xl border-b border-zinc-800/20 shadow-2xl shadow-violet-900/10">
                <div className="flex justify-between items-center px-6 py-4 max-w-7xl mx-auto w-full">
                    <div className="text-2xl font-black tracking-tighter text-zinc-100">AIPlacement</div>
                    <Link
                        to="/register"
                        className="bg-primary text-on-primary-container px-6 py-2 rounded-full font-semibold hover:bg-primary-container active:scale-95 transition-all duration-200"
                    >
                        Sign Up
                    </Link>
                </div>
            </nav>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center px-6 py-20 pt-24">
                <div className="w-full max-w-md">
                    {/* Logo */}
                    <div className="mb-8 flex justify-center">
                        <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center">
                            <span className="text-3xl">🚀</span>
                        </div>
                    </div>

                    {/* Heading */}
                    <div className="mb-8 text-center">
                        <h1 className="text-4xl font-headline font-black tracking-tighter text-on-surface mb-3">Welcome Back</h1>
                        <p className="text-base text-on-surface-variant">Sign in to continue your assessment journey</p>
                    </div>

                    {/* Card */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                        <form onSubmit={handleSubmit} className="space-y-5">
                            {/* Error Banner */}
                            {apiError && !dismissError && (
                                <div className="bg-error/10 border border-error/30 rounded-lg px-4 py-3 flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-3 flex-1">
                                        <span className="text-error text-lg leading-none mt-0.5">⚠️</span>
                                        <p className="text-error text-sm font-medium leading-snug">{apiError}</p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setDismissError(true)}
                                        className="text-error/60 hover:text-error transition-colors flex-shrink-0"
                                        aria-label="Dismiss error"
                                    >
                                        ✕
                                    </button>
                                </div>
                            )}

                            {/* Email Field */}
                            <div>
                                <label htmlFor="email" className="block text-xs font-label text-on-surface-variant uppercase tracking-widest mb-2">
                                    Email Address
                                </label>
                                <input
                                    id="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    className="w-full px-4 py-3 bg-surface-container-high border border-outline-variant/30 rounded-lg text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all text-sm"
                                    disabled={loading}
                                />
                            </div>

                            {/* Password Field */}
                            <div>
                                <label htmlFor="password" className="block text-xs font-label text-on-surface-variant uppercase tracking-widest mb-2">
                                    Password
                                </label>
                                <input
                                    id="password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full px-4 py-3 bg-surface-container-high border border-outline-variant/30 rounded-lg text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all text-sm"
                                    disabled={loading}
                                />
                            </div>

                            {/* Forgot Password Link */}
                            <div className="text-right">
                                <Link
                                    to="#"
                                    className="text-xs font-label text-primary hover:text-primary/80 transition-colors"
                                >
                                    Forgot password?
                                </Link>
                            </div>

                            {/* Submit Button */}
                            <button
                                type="submit"
                                disabled={loading}
                                className="w-full hero-gradient text-on-primary-container font-semibold py-3 rounded-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm shadow-lg shadow-primary/20"
                            >
                                {loading ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-on-primary-container border-t-transparent rounded-full animate-spin"></div>
                                        Signing In...
                                    </>
                                ) : (
                                    <>
                                        Sign In
                                        <span>→</span>
                                    </>
                                )}
                            </button>
                        </form>

                        {/* Divider */}
                        <div className="my-6 relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-outline-variant/20"></div>
                            </div>
                            <div className="relative flex justify-center text-xs">
                                <span className="px-2 bg-surface-container text-on-surface-variant">or</span>
                            </div>
                        </div>

                        {/* Register Link */}
                        <div className="text-center">
                            <p className="text-on-surface-variant text-sm">
                                New here?{' '}
                                <Link
                                    to="/register"
                                    className="font-semibold text-primary hover:text-primary/80 transition-colors"
                                >
                                    Create an account
                                </Link>
                            </p>
                        </div>
                    </div>

                    {/* Footer Info */}
                    <div className="mt-8 text-center">
                        <p className="text-xs text-on-surface-variant">
                            By continuing, you agree to our Terms of Service and Privacy Policy
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
