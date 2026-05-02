import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../components/AdminLayout';
import api from '../services/api';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function AdminCandidateReports() {
    const [candidates, setCandidates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        const fetchCandidates = async () => {
            try {
                const res = await api.get('/report/admin/all-candidates');
                setCandidates(res.data.candidates || []);
            } catch (err) {
                console.error("Failed to fetch candidate list", err);
            } finally {
                setLoading(false);
            }
        };
        fetchCandidates();
    }, []);

    const filteredCandidates = candidates.filter(c => 
        (c.name || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
        (c.email || '').toLowerCase().includes(searchTerm.toLowerCase())
    );

    const getStatusStyles = (status) => {
        switch(status) {
            case 'completed': return 'bg-green-100 text-green-700';
            case 'in_progress': return 'bg-blue-100 text-blue-700';
            case 'terminated': return 'bg-red-100 text-red-700';
            default: return 'bg-slate-100 text-slate-700';
        }
    };

    const getPercentileBadge = (percentile) => {
        if (percentile >= 90) {
            return { text: 'Top 10%', styles: 'bg-green-100 text-green-700' };
        } else if (percentile >= 75) {
            return { text: 'Top 25%', styles: 'bg-blue-100 text-blue-700' };
        } else if (percentile >= 50) {
            return { text: 'Top 50%', styles: 'bg-slate-100 text-slate-600' };
        } else {
            return { text: 'Below Avg', styles: 'bg-amber-100 text-amber-700' };
        }
    };

    if (loading) {
        return (
            <AdminLayout>
                <PageSkeleton variant="light" embedded showTable cardCount={3} />
            </AdminLayout>
        );
    }

    return (
        <AdminLayout>
            <div className="max-w-6xl mx-auto space-y-6">
                <div className="flex justify-between items-end">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Candidate Reports</h1>
                        <p className="text-slate-500 text-sm">Detailed performance overview of all students</p>
                    </div>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">🔍</span>
                        <input 
                            type="text" 
                            placeholder="Search by name or email..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-10 pr-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm w-64 shadow-sm"
                        />
                    </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Rank</th>
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Candidate</th>
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Overall Score</th>
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Percentile</th>
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                                <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filteredCandidates.length > 0 ? (
                                filteredCandidates.map((c) => {
                                    const badge = getPercentileBadge(c.percentile);
                                    return (
                                        <tr key={c.user_id} className="hover:bg-slate-50/50 transition-colors">
                                            <td className="px-6 py-4">
                                                <span className={`text-sm font-bold ${c.rank <= 3 ? 'text-blue-600' : 'text-slate-500'}`}>
                                                    {c.rank <= 3 ? ['🥇', '🥈', '🥉'][c.rank - 1] : `#${c.rank}`}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-bold text-slate-900">{c.name || 'Unknown'}</span>
                                                    <span className="text-xs text-slate-500">{c.email}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                        <div 
                                                            className="h-full bg-blue-500 rounded-full" 
                                                            style={{ width: `${c.overall_score * 100}%` }}
                                                        ></div>
                                                    </div>
                                                    <span className="text-sm font-bold text-slate-700">
                                                        {(c.overall_score * 100).toFixed(1)}%
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${badge.styles}`}>
                                                    {badge.text}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${getStatusStyles(c.status)}`}>
                                                    {(c.status || 'not_started').replace('_', ' ')}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <button 
                                                    onClick={() => navigate(`/report/combined/${c.user_id}`)}
                                                    className="text-blue-600 hover:text-blue-700 font-semibold text-sm transition-colors"
                                                >
                                                    View Report →
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })
                            ) : (
                                <tr>
                                    <td colSpan="6" className="px-6 py-10 text-center text-slate-400">
                                        {searchTerm ? 'No candidates match your search' : 'No candidates found'}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </AdminLayout>
    );
}
