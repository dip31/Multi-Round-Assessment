import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

// Define navigation structure with modes and sub-items
const NAV_STRUCTURE = [
    {
        id: 'home',
        label: 'Home',
        href: '/home',
        icon: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
        ),
    },
    {
        id: 'practice',
        label: 'Practice',
        href: '/practice',
        icon: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
        ),
        subItems: [
            { label: 'Overview', href: '/practice' },
            { label: 'MCQ', href: '/practice/mcq' },
            { label: 'Technical MCQ', href: '/practice/technical-mcq' },
            { label: 'Combined MCQ', href: '/practice/combined-mcq' },
            { label: 'Coding', href: '/practice/coding' },
            { label: 'Interview', href: '/practice/interview' },
        ],
    },
    {
        id: 'portfolio',
        label: 'Portfolio',
        href: '/portfolio',
        icon: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
        ),
        subItems: [
            { label: 'Overview', href: '/portfolio' },
            { label: 'Profile', href: '/portfolio/profile' },
            { label: 'Resume/CV', href: '/portfolio/resume' },
            { label: 'Projects', href: '/portfolio/projects' },
            { label: 'Skills & Evidence', href: '/portfolio/skills' },
            { label: 'Verification', href: '/portfolio/verification' },
        ],
    },
    {
        id: 'mock-drive',
        label: 'Mock Drive',
        href: '/mock-drive',
        icon: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
        ),
        subItems: [
            { label: 'Overview', href: '/mock-drive' },
            { label: 'Available Drives', href: '/mock-drive/available' },
            { label: 'My Applications', href: '/mock-drive/applications' },
            { label: 'Assessments', href: '/mock-drive/assessments' },
            { label: 'Interviews', href: '/mock-drive/interviews' },
            { label: 'Results', href: '/mock-drive/results' },
        ],
    },
    {
        id: 'analytics',
        label: 'Analytics',
        href: '/analytics',
        icon: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
        ),
    },
];

export default function StudentModeSidebar() {
    const location = useLocation();
    const navigate = useNavigate();
    const [mobileOpen, setMobileOpen] = useState(false);

    const getStoredUser = () => {
        try {
            const raw = localStorage.getItem('user');
            if (raw) return JSON.parse(raw);
        } catch { }
        return null;
    };

    const user = getStoredUser();
    const displayName = user?.name || user?.full_name || 'Candidate';

    const handleLogout = () => {
        ['access_token', 'user', 'user_name', 'full_name', 'user_email', 'email'].forEach(
            (k) => localStorage.removeItem(k)
        );
        navigate('/login');
    };

    // Determine which mode is active based on current path
    const getActiveMode = () => {
        const path = location.pathname;
        if (path.startsWith('/practice')) return 'practice';
        if (path.startsWith('/portfolio')) return 'portfolio';
        if (path.startsWith('/mock-drive')) return 'mock-drive';
        if (path.startsWith('/analytics')) return 'analytics';
        if (path.startsWith('/home') || path === '/dashboard') return 'home';
        return null;
    };

    const activeMode = getActiveMode();

    const SidebarContent = () => (
        <div className="flex flex-col h-full">
            {/* Brand */}
            <div className="px-5 py-5 border-b border-slate-200">
                <Link to="/home" className="flex items-center gap-2.5 group">
                    <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md group-hover:bg-indigo-700 transition-colors shrink-0">
                        AI
                    </div>
                    <span className="text-base font-bold tracking-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                        AIPlacement
                    </span>
                </Link>
            </div>

            {/* Nav Items */}
            <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
                {NAV_STRUCTURE.map((item) => {
                    const isActive = activeMode === item.id;
                    const hasSubItems = item.subItems && item.subItems.length > 0;
                    const isExpanded = isActive && hasSubItems;

                    return (
                        <div key={item.id}>
                            <Link
                                to={item.href}
                                onClick={() => setMobileOpen(false)}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                                    isActive
                                        ? 'bg-indigo-600 text-white shadow-sm'
                                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                                }`}
                            >
                                {item.icon}
                                <span className="flex-1">{item.label}</span>
                                {hasSubItems && isActive && (
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                    </svg>
                                )}
                            </Link>

                            {/* Sub-items (only shown when mode is active) */}
                            {isExpanded && (
                                <div className="mt-1 ml-4 pl-4 border-l-2 border-indigo-200 space-y-1">
                                    {item.subItems.map((subItem) => {
                                        const isSubActive = location.pathname === subItem.href;
                                        return (
                                            <Link
                                                key={subItem.href}
                                                to={subItem.href}
                                                onClick={() => setMobileOpen(false)}
                                                className={`block px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                                                    isSubActive
                                                        ? 'bg-indigo-50 text-indigo-700 font-semibold'
                                                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                                                }`}
                                            >
                                                {subItem.label}
                                            </Link>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    );
                })}
            </nav>

            {/* Bottom section */}
            <div className="px-3 py-4 border-t border-slate-200 space-y-1">
                <Link
                    to="/profile"
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                        location.pathname === '/profile'
                            ? 'bg-slate-100 text-slate-900'
                            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`}
                >
                    <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center text-white font-bold text-xs shrink-0">
                        {displayName.charAt(0).toUpperCase()}
                    </div>
                    <span className="truncate">{displayName}</span>
                </Link>

                <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-all"
                >
                    <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Sign out
                </button>
            </div>
        </div>
    );

    return (
        <>
            {/* Desktop sidebar */}
            <aside className="hidden lg:flex flex-col w-64 shrink-0 bg-white border-r border-slate-200 h-screen sticky top-0">
                <SidebarContent />
            </aside>

            {/* Mobile hamburger button */}
            <button
                onClick={() => setMobileOpen(true)}
                className="lg:hidden fixed top-3 left-3 z-50 w-10 h-10 bg-white border border-slate-200 rounded-xl flex items-center justify-center shadow-sm text-slate-600 hover:bg-slate-50"
                aria-label="Open menu"
            >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
            </button>

            {/* Mobile drawer overlay */}
            {mobileOpen && (
                <div
                    className="lg:hidden fixed inset-0 z-40 bg-black/40"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* Mobile drawer */}
            <aside
                className={`lg:hidden fixed top-0 left-0 z-50 h-full w-72 bg-white border-r border-slate-200 shadow-xl transform transition-transform duration-200 ${
                    mobileOpen ? 'translate-x-0' : '-translate-x-full'
                }`}
            >
                <div className="flex justify-end p-3">
                    <button
                        onClick={() => setMobileOpen(false)}
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:bg-slate-100"
                        aria-label="Close menu"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
                <SidebarContent />
            </aside>
        </>
    );
}
