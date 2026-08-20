import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Register() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errors, setErrors] = useState({});
    const [apiError, setApiError] = useState('');
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const navigate = useNavigate();

    const validate = () => {
        const e = {};
        if (!name || name.length < 2) e.name = 'Name must be at least 2 characters';
        if (!email || !/\S+@\S+\.\S+/.test(email)) e.email = 'Valid email is required';
        if (!password || password.length < 8) e.password = 'Password must be at least 8 characters';
        setErrors(e);
        return Object.keys(e).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setApiError('');
        if (!validate()) return;

        setLoading(true);
        try {
            await register(name, email, password);
            navigate('/login');
        } catch (err) {
            const detail = err.response?.data?.detail;
            if (typeof detail === 'string') {
                setApiError(detail);
            } else if (Array.isArray(detail)) {
                setApiError(detail.map((d) => d.msg).join(', '));
            } else {
                setApiError('Registration failed. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-background text-on-surface font-body selection:bg-primary/30 antialiased flex flex-col">
            {/* Top Navigation */}
            <nav className="fixed top-0 w-full z-50 bg-zinc-950/60 backdrop-blur-xl border-b border-zinc-800/20 shadow-2xl shadow-violet-900/10">
                <div className="flex justify-between items-center px-6 py-4 max-w-7xl mx-auto w-full">
                    <div className="text-2xl font-black tracking-tighter text-zinc-100">AIPlacement</div>
                    <Link
                        to="/login"
                        className="bg-primary text-on-primary-container px-6 py-2 rounded-full font-semibold hover:bg-primary-container active:scale-95 transition-all duration-200"
                    >
                        Sign In
                    </Link>
                </div>
            </nav>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center px-6 py-20 pt-24">
                <div className="w-full max-w-md">
                    {/* Logo */}
                    <div className="mb-8 flex justify-center">
                        <div className="w-16 h-16 rounded-2xl bg-primary/20 flex items-center justify-center">
                            <span className="text-3xl">✨</span>
                        </div>
                    </div>

                    {/* Heading */}
                    <div className="mb-8 text-center">
                        <h1 className="text-4xl font-headline font-black tracking-tighter text-on-surface mb-3">Create Your Account</h1>
                        <p className="text-base text-on-surface-variant">Get started with your adaptive assessment journey</p>
                    </div>

                    {/* Card */}
                    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-8 shadow-lg shadow-primary/5">
                        {apiError && (
                            <div className="bg-error/10 border border-error/30 rounded-lg px-4 py-3 mb-5 text-error text-sm">
                                {apiError}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-5">
                            {/* Name Field */}
                            <div>
                                <label className="block text-xs font-label text-on-surface-variant uppercase tracking-widest mb-2">Full Name</label>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="John Doe"
                                    className="w-full px-4 py-3 bg-surface-container-high border border-outline-variant/30 rounded-lg text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all text-sm"
                                    disabled={loading}
                                />
                                {errors.name && (
                                    <p className="mt-1 text-xs text-error">{errors.name}</p>
                                )}
                            </div>

                            {/* Email Field */}
                            <div>
                                <label className="block text-xs font-label text-on-surface-variant uppercase tracking-widest mb-2">Email Address</label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    className="w-full px-4 py-3 bg-surface-container-high border border-outline-variant/30 rounded-lg text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all text-sm"
                                    disabled={loading}
                                />
                                {errors.email && (
                                    <p className="mt-1 text-xs text-error">{errors.email}</p>
                                )}
                            </div>

                            {/* Password Field */}
                            <div>
                                <label className="block text-xs font-label text-on-surface-variant uppercase tracking-widest mb-2">Password</label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full px-4 py-3 bg-surface-container-high border border-outline-variant/30 rounded-lg text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 transition-all text-sm"
                                    disabled={loading}
                                />
                                {errors.password && (
                                    <p className="mt-1 text-xs text-error">{errors.password}</p>
                                )}
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
                                        Creating Account...
                                    </>
                                ) : (
                                    <>
                                        Create Account
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

                        {/* Login Link */}
                        <div className="text-center">
                            <p className="text-on-surface-variant text-sm">
                                Already have an account?{' '}
                                <Link
                                    to="/login"
                                    className="font-semibold text-primary hover:text-primary/80 transition-colors"
                                >
                                    Sign In
                                </Link>
                            </p>
                        </div>
                    </div>

                    {/* Footer Info */}
                    <div className="mt-8 text-center">
                        <p className="text-xs text-on-surface-variant">
                            By creating an account, you agree to our Terms of Service and Privacy Policy
                        </p>
                    </div>
                </div>
            </main>
        </div>
    );
}
