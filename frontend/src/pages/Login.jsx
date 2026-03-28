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
        <div className="min-h-screen flex bg-white">
            {/* Toast Notification */}
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            {/* Left Panel - Dark (45%) */}
            <div className="hidden lg:flex w-[45%] bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 flex-col items-center justify-center px-12 py-16">
                {/* Logo Mark */}
                <div className="mb-8">
                    <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center shadow-lg">
                        <div className="w-10 h-10 bg-blue-600 rounded-xl"></div>
                    </div>
                </div>

                {/* Tagline */}
                <div className="text-center mb-12">
                    <h1 className="text-3xl font-bold text-white mb-3">AssessmentAI</h1>
                    <p className="text-slate-300 text-base leading-relaxed max-w-xs">
                        Intelligent interview assessment platform powered by advanced AI and real-time proctoring
                    </p>
                </div>

                {/* Feature Pills */}
                <div className="flex flex-col gap-4 w-full">
                    {features.map((feature, idx) => (
                        <div
                            key={idx}
                            className="flex items-center gap-3 bg-slate-800 bg-opacity-50 px-4 py-3 rounded-full border border-slate-700 backdrop-blur-sm"
                        >
                            <span className="text-xl">{feature.icon}</span>
                            <span className="text-slate-200 text-sm font-medium">{feature.label}</span>
                        </div>
                    ))}
                </div>

                {/* Footer Text */}
                <div className="mt-auto text-center">
                    <p className="text-slate-400 text-xs">Secure • Fast • Fair</p>
                </div>
            </div>

            {/* Right Panel - Light (55% on desktop, 100% on mobile) */}
            <div className="w-full lg:w-[55%] flex items-center justify-center px-6 py-12 sm:px-8">
                <div className="w-full max-w-sm">
                    {/* Mobile Logo */}
                    <div className="lg:hidden mb-8 flex items-center justify-center">
                        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center shadow-md">
                            <div className="w-7 h-7 bg-white rounded-lg"></div>
                        </div>
                    </div>

                    {/* Heading */}
                    <div className="mb-8">
                        <h2 className="text-3xl font-bold text-slate-900 mb-2">Welcome Back</h2>
                        <p className="text-slate-600 text-sm">Sign in to access your assessment rounds</p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-6">
                        {/* Error Banner */}
                        {apiError && !dismissError && (
                            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start justify-between gap-3">
                                <div className="flex items-start gap-3 flex-1">
                                    <span className="text-red-600 text-lg leading-none mt-0.5">⚠️</span>
                                    <p className="text-red-800 text-sm font-medium leading-snug">{apiError}</p>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setDismissError(true)}
                                    className="text-red-400 hover:text-red-600 transition-colors flex-shrink-0"
                                    aria-label="Dismiss error"
                                >
                                    ✕
                                </button>
                            </div>
                        )}

                        {/* Email Field */}
                        <div>
                            <label htmlFor="email" className="block text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
                                Email Address
                            </label>
                            <input
                                id="email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@example.com"
                                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm font-normal"
                                disabled={loading}
                            />
                        </div>

                        {/* Password Field */}
                        <div>
                            <label htmlFor="password" className="block text-xs font-semibold text-slate-900 uppercase tracking-wider mb-2">
                                Password
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm font-normal"
                                disabled={loading}
                            />
                        </div>

                        {/* Forgot Password Link */}
                        <div className="text-right">
                            <Link
                                to="#"
                                className="text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors"
                            >
                                Forgot password?
                            </Link>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-blue-600 hover:bg-blue-700 active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-all duration-150 flex items-center justify-center gap-2 text-sm"
                        >
                            {loading ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
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

                    {/* Register Link */}
                    <div className="mt-6 text-center">
                        <p className="text-slate-600 text-sm">
                            New here?{' '}
                            <Link
                                to="/register"
                                className="font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                            >
                                Create an account
                            </Link>
                        </p>
                    </div>

                    {/* Footer Info */}
                    <div className="mt-8 pt-6 border-t border-slate-200 text-center">
                        <p className="text-xs text-slate-500">
                            By continuing, you agree to our Terms of Service and Privacy Policy
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
