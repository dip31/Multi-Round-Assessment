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
            const res = await login(email, password);
            setToast({ type: 'success', message: 'Login successful! Redirecting...' });
            const userRole = res?.role || res?.user?.role || localStorage.getItem('role') || 'student';
            const targetRoute = userRole === 'faculty'
                ? '/faculty/dashboard'
                : userRole === 'tpo'
                ? '/tpo/dashboard'
                : userRole === 'admin'
                ? '/admin/dashboard'
                : '/dashboard';
            setTimeout(() => navigate(targetRoute), 350);
        } catch (err) {
            const detail = err.response?.data?.detail || 'Login failed. Please check your credentials.';
            if (typeof detail === 'string') {
                setApiError(detail);
            } else if (Array.isArray(detail)) {
                setApiError(detail.map((d) => d.msg).join(', '));
            } else {
                setApiError('Login failed. Please check your credentials.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter'] antialiased flex flex-col">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            {/* Top Navigation */}
            <nav className="fixed top-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm">
                <div className="flex justify-between items-center px-6 py-3.5 max-w-7xl mx-auto w-full">
                    <Link to="/" className="flex items-center gap-2 group">
                        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-sm group-hover:bg-indigo-700 transition-colors">
                            AI
                        </div>
                        <span className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                            AIPlacement
                        </span>
                    </Link>
                    <Link
                        to="/register"
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-1.5 rounded-full text-xs font-semibold active:scale-95 transition-all shadow-sm"
                    >
                        Sign Up
                    </Link>
                </div>
            </nav>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center px-6 py-20 pt-28">
                <div className="w-full max-w-md">
                    {/* Heading */}
                    <div className="mb-8 text-center">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200 mb-3">
                            EDI5 Competency Platform
                        </span>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-2">Welcome Back</h1>
                        <p className="text-sm text-slate-500">Sign in to continue your placement-readiness journey</p>
                    </div>

                    {/* Card */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-xl shadow-slate-200/50">
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Error Banner */}
                            {apiError && !dismissError && (
                                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-red-700 text-xs font-medium flex items-center justify-between">
                                    <span>{apiError}</span>
                                    <button type="button" onClick={() => setDismissError(true)} className="text-red-500 hover:text-red-700">✕</button>
                                </div>
                            )}

                            {/* Email */}
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="your.email@institution.edu"
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-xs transition-all"
                                    disabled={loading}
                                />
                            </div>

                            {/* Password */}
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                    Password
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="Enter your password"
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-xs transition-all"
                                    disabled={loading}
                                />
                            </div>

                            {/* Submit Button */}
                            <div className="pt-2">
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-600/30 text-xs uppercase tracking-wider flex items-center justify-center gap-2"
                                >
                                    {loading ? 'Signing In...' : 'Sign In'}
                                </button>
                            </div>
                        </form>

                        {/* Sign Up Link */}
                        <div className="mt-6 text-center text-xs text-slate-500 border-t border-slate-100 pt-4">
                            Don't have an account?{' '}
                            <Link to="/register" className="text-indigo-600 font-bold hover:underline">
                                Create Account
                            </Link>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
