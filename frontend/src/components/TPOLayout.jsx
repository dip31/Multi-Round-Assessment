import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
import {
    Home, Target, Users, AlertCircle, Menu, X, Gauge,
} from 'lucide-react';

const TPOLayoutContext = createContext(null);

export function TPOMenuButton({ className = '' }) {
    const ctx = useContext(TPOLayoutContext);
    const btnRef = useRef(null);

    useEffect(() => {
        if (!ctx?.registerMenuBtn || !btnRef.current) return undefined;
        return ctx.registerMenuBtn(btnRef.current);
    }, [ctx]);

    if (!ctx) return null;
    return (
        <button
            ref={btnRef}
            onClick={() => ctx.openSidebar()}
            className={`md:hidden block px-3 py-2 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 text-xs font-semibold shadow-sm transition-all ${className}`}
            aria-label="Open navigation menu"
            aria-expanded={ctx.sidebarOpen}
            aria-controls="tpo-sidebar-drawer"
        >
            <Menu size={18} className="mr-1" />
            Menu
        </button>
    );
}

export default function TPOLayout({ children }) {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const drawerCloseRef = useRef(null);
    const menuBtnElsRef = useRef(new Set());

    const navigate = useNavigate();
    const location = useLocation();
    const onHome = location.pathname === '/tpo/dashboard';
    const onDrives = location.pathname === '/tpo/mock-drives';
    const onStudents = location.pathname === '/tpo/students';
    const onReadiness = location.pathname === '/tpo/readiness';
    const onAnalytics = location.pathname === '/tpo/analytics';
    const onProfile = location.pathname === '/profile';

    const navItems = [
        { href: '/tpo/dashboard', label: 'Dashboard', icon: Home, active: onHome },
        { href: '/tpo/mock-drives', label: 'Drives', icon: Target, active: onDrives },
        { href: '/tpo/students', label: 'Candidates', icon: Users, active: onStudents },
        { href: '/tpo/readiness', label: 'Readiness', icon: Gauge, active: onReadiness },
        { href: '/tpo/analytics', label: 'Analytics', icon: AlertCircle, active: onAnalytics },
        { href: '/profile', label: 'TPO Profile', icon: Target, active: onProfile },
    ];

    const registerMenuBtn = useCallback((el) => {
        if (!el) return undefined;
        menuBtnElsRef.current.add(el);
        return () => menuBtnElsRef.current.delete(el);
    }, []);

    const closeSidebar = useCallback(() => {
        setSidebarOpen(false);
        const first = menuBtnElsRef.current.values().next().value;
        if (first) first.focus();
    }, []);

    useEffect(() => {
        if (!sidebarOpen) return undefined;
        const onKeyDown = (e) => {
            if (e.key === 'Escape') closeSidebar();
        };
        window.addEventListener('keydown', onKeyDown);
        if (drawerCloseRef.current) drawerCloseRef.current.focus();
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [sidebarOpen, closeSidebar]);

    const ctx = {
        sidebarOpen,
        openSidebar: () => setSidebarOpen(true),
        closeSidebar,
        registerMenuBtn,
    };

    return (
        <TPOLayoutContext.Provider value={ctx}>
            <div className="min-h-screen bg-slate-50 glass-wash text-slate-900 font-['Inter'] antialiased">
                <Navbar position="sticky" onLogout={() => navigate('/login')} />

                {/* Desktop sidebar - hover-expandable rail (collapsed w-20, expands to w-64 on hover/focus) */}
                <aside
                    id="tpo-sidebar"
                    aria-label="TPO navigation"
                    className="group/sidebar hidden md:flex fixed left-0 top-[69px] bottom-0 w-20 hover:w-64 focus-within:w-64 flex-col z-40 overflow-hidden border-r border-slate-200 sidebar-glass transition-[width] duration-300 ease-in-out"
                >
                    <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-200 shrink-0">
                        <div className="w-8 h-8 shrink-0 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md">
                            AI
                        </div>
                        <span className="text-lg font-bold tracking-tight text-slate-900 whitespace-nowrap opacity-0 group-hover/sidebar:opacity-100 group-focus-within/sidebar:opacity-100 transition-opacity duration-300">
                            AIPlacement
                        </span>
                    </div>
                    <nav className="flex-1 px-3 py-4 overflow-y-auto overflow-x-hidden" aria-label="Primary">
                        <ul className="space-y-1">
                            {navItems.map((item) => (
                                <li key={item.href}>
                                    <a
                                        href={item.href}
                                        aria-current={item.active ? 'page' : undefined}
                                        className={`group/item flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white ${
                                            item.active
                                                ? 'bg-sky-100 text-sky-700'
                                                : 'text-slate-600 hover:bg-sky-100 hover:text-sky-700'
                                        }`}
                                    >
                                        <item.icon
                                            size={18}
                                            className={`shrink-0 ${item.active ? 'text-sky-600' : 'text-slate-400 group-hover/item:text-sky-600'}`}
                                        />
                                        <span className="opacity-0 group-hover/sidebar:opacity-100 group-focus-within/sidebar:opacity-100 transition-opacity duration-300">
                                            {item.label}
                                        </span>
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </nav>
                </aside>

                {/* Mobile sidebar drawer */}
                <div
                    className={`md:hidden fixed inset-0 z-[60] ${sidebarOpen ? '' : 'pointer-events-none'}`}
                    aria-hidden={!sidebarOpen || undefined}
                >
                    <div
                        onClick={closeSidebar}
                        aria-hidden="true"
                        className={`absolute inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity duration-300 ${
                            sidebarOpen ? 'opacity-100' : 'opacity-0'
                        }`}
                    />
                    <div
                        id="tpo-sidebar-drawer"
                        role="dialog"
                        aria-modal={sidebarOpen ? 'true' : undefined}
                        aria-label="TPO navigation menu"
                        className={`absolute inset-y-0 left-0 w-72 max-w-[85vw] sidebar-glass border-r border-slate-200 flex flex-col transition-transform duration-300 ${
                            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
                        }`}
                    >
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 shrink-0">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 shrink-0 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md">
                                    AI
                                </div>
                                <span className="text-lg font-bold tracking-tight text-slate-900">AIPlacement</span>
                            </div>
                            <button
                                ref={drawerCloseRef}
                                onClick={closeSidebar}
                                aria-label="Close navigation menu"
                                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                            >
                                <X size={18} />
                            </button>
                        </div>
                        <nav className="flex-1 px-3 py-4 overflow-y-auto" aria-label="Primary mobile">
                            <ul className="space-y-1">
                                {navItems.map((item) => (
                                    <li key={item.href}>
                                        <a
                                            href={item.href}
                                            onClick={closeSidebar}
                                            aria-current={item.active ? 'page' : undefined}
                                            className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                                                item.active
                                                    ? 'bg-sky-100 text-sky-700'
                                                    : 'text-slate-600 hover:bg-sky-50 hover:text-sky-700'
                                            }`}
                                        >
                                            <item.icon size={18} className={item.active ? 'text-sky-600' : 'text-slate-400'} />
                                            {item.label}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </nav>
                    </div>
                </div>

                {/* Main content */}
                <div className="md:pl-64">{children}</div>
            </div>
        </TPOLayoutContext.Provider>
    );
}
