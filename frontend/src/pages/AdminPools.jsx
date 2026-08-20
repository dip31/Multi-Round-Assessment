import React, { useEffect, useState } from 'react';
import AdminLayout from '../components/AdminLayout';
import api from '../services/api';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function AdminPools() {
    const [pools, setPools] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPools = async () => {
            try {
                const res = await api.get('/interview/admin/pools');
                setPools(res.data || []);
            } catch (err) {
                console.error('Failed to fetch pools', err);
            } finally {
                setLoading(false);
            }
        };
        fetchPools();
    }, []);

    if (loading) {
        return (
            <AdminLayout>
                <PageSkeleton variant="light" embedded cardCount={4} />
            </AdminLayout>
        );
    }

    return (
        <AdminLayout>
            <div className="max-w-6xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold">Pending Question Pools</h1>
                        <p className="text-sm text-slate-500">Review generated pools and their detected roles</p>
                    </div>
                </div>

                <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                    {pools.length === 0 && (
                        <div className="col-span-full text-center py-12 text-slate-400">No pools found</div>
                    )}

                    {pools.map((p) => (
                        <div key={p.pool_id} className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm">
                            <div className="flex items-start justify-between">
                                <div>
                                    <h3 className="text-sm font-semibold text-slate-900">{p.candidate_name || 'Unknown'}</h3>
                                    <p className="text-xs text-slate-500">{p.candidate_email}</p>
                                    <p className="text-xs text-slate-400 mt-2">{new Date(p.created_at).toLocaleString()}</p>
                                </div>

                                <div className="text-right">
                                    <span className="text-xs px-2 py-1 rounded-full bg-emerald-50 text-emerald-700">{p.question_count} questions</span>
                                    {p.detected_role && (
                                        <div className="mt-2">
                                            <span className="text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-700">{p.detected_role}</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-4 flex items-center justify-between">
                                <button
                                    onClick={() => window.location.href = `/admin/review?pool=${p.pool_id}`}
                                    className="text-sm font-semibold text-blue-600 hover:text-blue-700"
                                >
                                    Review Pool →
                                </button>
                                <div className="text-xs text-slate-500">Approved: {p.approved ? 'Yes' : 'No'}</div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </AdminLayout>
    );
}
