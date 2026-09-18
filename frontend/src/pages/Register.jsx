import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import api from '../services/api';

export default function Register() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('student');

    // Student specific fields
    const [department, setDepartment] = useState('Computer Science');
    const [graduationYear, setGraduationYear] = useState('2026');
    const [targetRole, setTargetRole] = useState('Software Development Engineer');

    // Faculty specific fields
    const [facultyDesignation, setFacultyDesignation] = useState('Assistant Professor');

    // TPO specific fields
    const [institution, setInstitution] = useState('Engineering College');

    const [errors, setErrors] = useState({});
    const [apiError, setApiError] = useState('');
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const navigate = useNavigate();

    const validate = () => {
        const e = {};
        if (!name || name.trim().length < 2) e.name = 'Name must be at least 2 characters';
        if (!email || !/\S+@\S+\.\S+/.test(email)) e.email = 'Valid email address is required';
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
            await register(name.trim(), email.trim().toLowerCase(), password, role);

            // Log in right away or redirect to login
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
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter'] antialiased flex flex-col">
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
                        to="/login"
                        className="bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 px-5 py-1.5 rounded-full text-xs font-semibold active:scale-95 transition-all"
                    >
                        Sign In
                    </Link>
                </div>
            </nav>

            {/* Main Content */}
            <main className="flex-1 flex items-center justify-center px-6 py-20 pt-28">
                <div className="w-full max-w-lg">
                    {/* Heading */}
                    <div className="mb-8 text-center">
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200 mb-3">
                            EDI5 Identity & Registration
                        </span>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-2">Create Your Account</h1>
                        <p className="text-sm text-slate-500">Join the placement readiness and competency platform</p>
                    </div>

                    {/* Card */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-xl shadow-slate-200/50">
                        {apiError && (
                            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-5 text-red-700 text-xs font-medium">
                                {apiError}
                            </div>
                        )}

                        {/* Role Selector Tabs */}
                        <div className="mb-6">
                            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
                                I am registering as a:
                            </label>
                            <div className="grid grid-cols-3 gap-2 p-1 bg-slate-100 rounded-xl border border-slate-200">
                                {[
                                    { key: 'student', label: 'Student', icon: '🎓' },
                                    { key: 'faculty', label: 'Faculty', icon: '👨‍🏫' },
                                    { key: 'tpo', label: 'TPO Officer', icon: '🏢' },
                                ].map((r) => (
                                    <button
                                        key={r.key}
                                        type="button"
                                        onClick={() => setRole(r.key)}
                                        className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                                            role === r.key
                                                ? 'bg-white text-indigo-700 shadow-sm border border-slate-200'
                                                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                                        }`}
                                    >
                                        <span>{r.icon}</span>
                                        <span>{r.label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Full Name */}
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                    Full Name
                                </label>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="Jane Doe"
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-xs transition-all"
                                    disabled={loading}
                                />
                                {errors.name && <p className="mt-1 text-xs text-red-600 font-medium">{errors.name}</p>}
                            </div>

                            {/* Email */}
                            <div>
                                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                    Email Address
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="jane@college.edu"
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-xs transition-all"
                                    disabled={loading}
                                />
                                {errors.email && <p className="mt-1 text-xs text-red-600 font-medium">{errors.email}</p>}
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
                                    placeholder="At least 8 characters"
                                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white text-xs transition-all"
                                    disabled={loading}
                                />
                                {errors.password && <p className="mt-1 text-xs text-red-600 font-medium">{errors.password}</p>}
                            </div>

                            {/* Role Specific Fields */}
                            {role === 'student' && (
                                <div className="grid grid-cols-2 gap-3 pt-1">
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                            Department
                                        </label>
                                        <select
                                            value={department}
                                            onChange={(e) => setDepartment(e.target.value)}
                                            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        >
                                            <option value="Computer Science">Computer Science</option>
                                            <option value="Information Technology">Information Technology</option>
                                            <option value="Electronics & Communication">Electronics & Comm</option>
                                            <option value="Mechanical Engineering">Mechanical</option>
                                            <option value="Civil Engineering">Civil</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                            Graduation Year
                                        </label>
                                        <select
                                            value={graduationYear}
                                            onChange={(e) => setGraduationYear(e.target.value)}
                                            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        >
                                            <option value="2025">2025</option>
                                            <option value="2026">2026</option>
                                            <option value="2027">2027</option>
                                            <option value="2028">2028</option>
                                        </select>
                                    </div>
                                </div>
                            )}

                            {role === 'faculty' && (
                                <div className="grid grid-cols-2 gap-3 pt-1">
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                            Department
                                        </label>
                                        <input
                                            type="text"
                                            value={department}
                                            onChange={(e) => setDepartment(e.target.value)}
                                            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                            Designation
                                        </label>
                                        <input
                                            type="text"
                                            value={facultyDesignation}
                                            onChange={(e) => setFacultyDesignation(e.target.value)}
                                            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        />
                                    </div>
                                </div>
                            )}

                            {role === 'tpo' && (
                                <div className="pt-1">
                                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                                        Institution Name
                                    </label>
                                    <input
                                        type="text"
                                        value={institution}
                                        onChange={(e) => setInstitution(e.target.value)}
                                        className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    />
                                </div>
                            )}

                            {/* Submit Button */}
                            <div className="pt-3">
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold rounded-xl transition-all shadow-md shadow-indigo-600/30 text-xs uppercase tracking-wider flex items-center justify-center gap-2"
                                >
                                    {loading ? 'Creating Account...' : `Register as ${role.toUpperCase()}`}
                                </button>
                            </div>
                        </form>

                        {/* Sign In Link */}
                        <div className="mt-6 text-center text-xs text-slate-500 border-t border-slate-100 pt-4">
                            Already have an account?{' '}
                            <Link to="/login" className="text-indigo-600 font-bold hover:underline">
                                Sign In
                            </Link>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
