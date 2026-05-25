import { useNavigate } from 'react-router-dom';

export default function Navbar({ onLogout, rightContent, position = 'fixed' }) {
    const navigate = useNavigate();

    const navPositionClass = position === 'sticky' ? 'sticky' : position === 'relative' ? 'relative' : 'fixed';

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

    return (
        <nav className={`${navPositionClass} top-0 w-full z-50 bg-zinc-950/60 backdrop-blur-xl border-b border-zinc-800/20 shadow-2xl shadow-violet-900/10 font-['Inter'] antialiased tracking-tight`}>
            <div className="flex justify-between items-center px-6 py-4 max-w-7xl mx-auto w-full">
                <div className="text-2xl font-black tracking-tighter text-zinc-100">AIPlacement</div>
                <div className="flex items-center gap-8">
                    {rightContent}
                    {onLogout && (
                        <button
                            onClick={handleLogout}
                            className="bg-primary text-on-primary-container px-6 py-2 rounded-full font-semibold hover:bg-primary-container active:scale-95 transition-all duration-200"
                        >
                            Logout
                        </button>
                    )}
                </div>
            </div>
        </nav>
    );
}
