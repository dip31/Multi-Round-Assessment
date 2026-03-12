import { useNavigate } from 'react-router-dom';

export default function Navbar({ onLogout, rightContent }) {
    const navigate = useNavigate();

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        if (onLogout) onLogout();
        navigate('/login');
    };

    return (
        <nav className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-nav-bg)] shadow-sm">
            <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
                <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-accent)] shadow-sm">
                        <span className="text-sm font-bold text-white font-display">A</span>
                    </div>
                    <span className="text-xl font-bold tracking-tight text-white font-display">
                        Adaptive Assessment
                    </span>
                </div>

                <div className="flex items-center gap-4">
                    {rightContent}
                    {onLogout && (
                        <button
                            onClick={handleLogout}
                            className="rounded-lg border border-white/20 text-white px-4 py-2 text-sm transition-colors hover:border-[var(--color-danger)] hover:text-[var(--color-danger)] font-semibold"
                        >
                            Logout
                        </button>
                    )}
                </div>
            </div>
        </nav>
    );
}
