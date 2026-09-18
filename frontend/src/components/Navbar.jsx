import { useNavigate, Link } from 'react-router-dom';

export default function Navbar({ onLogout, rightContent, position = 'fixed' }) {
    const navigate = useNavigate();

    const navPositionClass = position === 'sticky' ? 'sticky' : position === 'relative' ? 'relative' : 'fixed';

    const getStoredUser = () => {
        try {
            const raw = localStorage.getItem('user');
            if (raw) return JSON.parse(raw);
        } catch (e) {
            // fallback
        }
        return null;
    };

    const user = getStoredUser();
    const displayName = user?.name || user?.full_name || localStorage.getItem('user_name') || 'User';
    const role = user?.role || 'student';

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        localStorage.removeItem('user_name');
        localStorage.removeItem('full_name');
        localStorage.removeItem('user_email');
        localStorage.removeItem('email');
        if (onLogout) onLogout();
        navigate('/login');
    };

    const dashboardLink = role === 'faculty'
        ? '/faculty/dashboard'
        : role === 'tpo'
        ? '/tpo/dashboard'
        : role === 'admin'
        ? '/admin/dashboard'
        : '/dashboard';

    return (
        <nav className={`${navPositionClass} top-0 w-full z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-sm font-['Inter'] antialiased`}>
            <div className="flex justify-between items-center px-6 py-3.5 max-w-7xl mx-auto w-full">
                <div className="flex items-center gap-6">
                    <Link to={dashboardLink} className="flex items-center gap-2 group">
                        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md group-hover:bg-indigo-700 transition-colors">
                            AI
                        </div>
                        <span className="text-xl font-bold tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                            AIPlacement
                        </span>
                    </Link>

                    {role && (
                        <span className="hidden sm:inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {role}
                        </span>
                    )}

                    {/* Role Navigation Items */}
                    <div className="hidden md:flex items-center gap-4 text-xs font-semibold text-slate-600">
                        <Link to={dashboardLink} className="hover:text-indigo-600 transition-colors">
                            {role === 'faculty' ? 'Faculty Portal' : role === 'tpo' ? 'TPO Portal' : role === 'admin' ? 'Admin Console' : 'Dashboard'}
                        </Link>
                        {role === 'student' && (
                            <>
                                <Link to="/portfolio" className="hover:text-indigo-600 transition-colors">
                                    Portfolio
                                </Link>
                                <Link to="/analytics" className="hover:text-indigo-600 transition-colors">
                                    Analytics
                                </Link>
                            </>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {rightContent}

                    <Link
                        to="/profile"
                        className="flex items-center gap-2.5 px-3 py-1.5 rounded-full hover:bg-slate-100 transition-colors border border-slate-200 text-xs font-semibold text-slate-700"
                        title="View Profile"
                    >
                        <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white font-bold text-xs">
                            {displayName.charAt(0).toUpperCase()}
                        </div>
                        <span className="hidden md:inline">{displayName}</span>
                    </Link>

                    {onLogout && (
                        <button
                            onClick={handleLogout}
                            className="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs px-4 py-2 rounded-full font-semibold active:scale-95 transition-all border border-slate-300"
                        >
                            Sign out
                        </button>
                    )}
                </div>
            </div>
        </nav>
    );
}
