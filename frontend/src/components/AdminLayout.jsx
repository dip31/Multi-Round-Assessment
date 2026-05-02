import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function AdminLayout({ children }) {
    const { logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/admin/login');
    };

    const navItems = [
        { to: '/admin/dashboard', label: 'Analytics Overview', icon: '📊' },
        { to: '/admin/analytics', label: 'Candidate Reports', icon: '👥' },
        { to: '/admin/review', label: 'Question Review', icon: '📋' },
        { to: '/admin/proctoring', label: 'Proctoring Monitor', icon: '🔍' },
    ];

    return (
        <div className="flex bg-slate-50 min-h-screen">
            {/* Sidebar */}
            <div className="w-56 bg-slate-900 h-screen fixed flex flex-col z-50">
                <div className="p-6 flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-md">
                        <div className="w-4 h-4 bg-white rounded-sm"></div>
                    </div>
                    <span className="text-white font-bold tracking-wide">Admin Portal</span>
                </div>

                <nav className="flex-1 px-4 space-y-1 mt-4">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-4 py-2.5 rounded-xl transition-colors text-sm font-medium ${
                                    isActive
                                        ? 'bg-slate-700 text-white'
                                        : 'text-slate-400 hover:text-white hover:bg-slate-800'
                                }`
                            }
                        >
                            <span className="text-lg">{item.icon}</span>
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                <div className="p-4 border-t border-slate-800 mt-auto flex flex-col gap-3">
                    <div className="flex items-center justify-between px-2">
                        <span className="text-slate-400 text-xs font-semibold">Pending Approvals</span>
                        <span className="bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full font-bold">12</span>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="w-full text-left px-4 py-2 text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
                    >
                        ← Sign out
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div className="ml-56 flex-1 flex flex-col h-screen overflow-y-auto">
                <main className="flex-1 p-8">
                    {children}
                </main>
            </div>
        </div>
    );
}
