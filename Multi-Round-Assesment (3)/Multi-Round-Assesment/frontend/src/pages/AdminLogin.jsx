import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Toast } from '../components/Toast';

const parseJwt = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
};

export default function AdminLogin() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [apiError, setApiError] = useState('');
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState(null);
    const { login, logout } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setApiError('');

        if (!email.trim() || !password) {
            setApiError('Email and password are required');
            return;
        }

        setLoading(true);
        try {
            const data = await login(email, password);
            const decoded = parseJwt(data.access_token);
            
            if (!decoded || !decoded.is_admin) {
                logout(); // remove the non-admin token
                setApiError('This account does not have admin access');
                setLoading(false);
                return;
            }

            setToast({ type: 'success', message: 'Admin login successful!' });
            setTimeout(() => navigate('/admin/dashboard'), 500);
        } catch (err) {
            setApiError(err.response?.data?.detail || 'Login failed. Please verify credentials.');
        } finally {
            if (!toast) setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
            
            <div className="w-full max-w-md bg-slate-800 p-8 rounded-2xl shadow-2xl border border-slate-700">
                <div className="flex flex-col items-center mb-8">
                    <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center mb-4">
                        <div className="w-6 h-6 bg-white rounded-md"></div>
                    </div>
                    <h2 className="text-2xl font-bold text-white">Admin Portal</h2>
                    <p className="text-slate-400 text-sm mt-1">Authorized personnel only</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    {apiError && (
                        <div className="bg-red-900/50 border border-red-500/50 rounded-lg p-3">
                            <p className="text-red-400 text-sm font-medium text-center">{apiError}</p>
                        </div>
                    )}

                    <div>
                        <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Email Address</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                            placeholder="admin@example.com"
                            disabled={loading}
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                            placeholder="••••••••"
                            disabled={loading}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-colors mt-4 text-sm flex justify-center items-center"
                    >
                        {loading ? 'Authenticating...' : 'Sign In Securely'}
                    </button>
                </form>
            </div>
        </div>
    );
}
