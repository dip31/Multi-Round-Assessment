import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { getProfile } from '../services/profileService';
import api from '../services/api';
import { Toast } from '../components/Toast';

const ROUND_LABELS = {
    aptitude: 'Aptitude',
    coding: 'Coding',
    technical_interview: 'Tech Interview',
    hr_interview: 'HR Interview',
};

export default function MockDriveOverview() {
    const navigate = useNavigate();
    const [profileData, setProfileData] = useState(null);
    const [availableDrives, setAvailableDrives] = useState([]);
    const [activeDriveStatus, setActiveDriveStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [startingDriveId, setStartingDriveId] = useState(null);
    const [advancingDriveId, setAdvancingDriveId] = useState(null);
    const [toast, setToast] = useState(null);

    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            const [profile, drivesRes] = await Promise.all([
                getProfile().catch(() => null),
                api.get('/mock-drives/available').catch(() => ({ data: [] })),
            ]);
            setProfileData(profile);
            const drives = drivesRes.data || [];
            setAvailableDrives(drives);

            // Check if any drive has an active session in progress
            if (drives.length > 0) {
                for (const drive of drives) {
                    try {
                        const statusRes = await api.get(`/mock-drives/${drive.id}/status`);
                        if (statusRes.data.status === 'in_progress') {
                            setActiveDriveStatus(statusRes.data);
                            break;
                        }
                    } catch { /* ignore */ }
                }
            }
        } catch {
            setToast({ type: 'error', message: 'Failed to load mock drives.' });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const studentProfile = profileData?.student_profile || {};
    const cgpa = studentProfile.cgpa ?? 0.0;
    const backlogs = studentProfile.backlogs_count ?? 0;

    const handleStartDrive = async (driveId) => {
        setStartingDriveId(driveId);
        try {
            const res = await api.post(`/mock-drives/${driveId}/start`);
            const data = res.data;
            if (data.status === 'completed') {
                setToast({ type: 'info', message: 'This mock drive is already completed.' });
                setActiveDriveStatus(data);
            } else {
                setToast({ type: 'success', message: `Mock drive started! ${data.company_name} — ${data.target_role}` });
                if (data.redirect_url) {
                    setTimeout(() => navigate(data.redirect_url), 800);
                }
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            setToast({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to start mock drive.',
            });
        } finally {
            setStartingDriveId(null);
        }
    };

    const handleContinueDrive = async () => {
        if (!activeDriveStatus) return;
        if (activeDriveStatus.redirect_url) {
            navigate(activeDriveStatus.redirect_url);
        }
    };

    const handleAdvanceRound = async (driveId) => {
        setAdvancingDriveId(driveId);
        try {
            const res = await api.post(`/mock-drives/${driveId}/advance`);
            const data = res.data;
            if (data.status === 'completed') {
                setToast({ type: 'success', message: 'Mock Drive completed! 🎉' });
                setActiveDriveStatus(null);
                loadData();
            } else if (data.redirect_url) {
                setToast({ type: 'info', message: `Next round: ${ROUND_LABELS[data.current_round] || data.current_round}` });
                setTimeout(() => navigate(data.redirect_url), 800);
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            setToast({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to advance to next round.',
            });
        } finally {
            setAdvancingDriveId(null);
        }
    };

    return (
        <StudentModeLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="mb-8 flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Mock Drive</h1>
                        <p className="text-slate-600 text-sm">
                            Company-specific mock hiring drives calibrated against real eligibility criteria and recruitment patterns
                        </p>
                    </div>
                    <button
                        onClick={loadData}
                        className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                    >
                        ↻ Refresh
                    </button>
                </div>

                {/* Active drive progress banner */}
                {activeDriveStatus && activeDriveStatus.status === 'in_progress' && (
                    <div className="mb-6 bg-violet-50 border border-violet-200 rounded-2xl p-5 shadow-sm">
                        <div className="flex items-center justify-between flex-wrap gap-3">
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-sm font-bold text-violet-800">{activeDriveStatus.company_name}</span>
                                    <span className="text-xs text-violet-500">— {activeDriveStatus.target_role}</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    {activeDriveStatus.enabled_rounds.map((r, i) => {
                                        const isDone = activeDriveStatus.completed_rounds.includes(r);
                                        const isCurrent = r === activeDriveStatus.current_round;
                                        return (
                                            <span key={r} className={`px-2 py-0.5 rounded-md border text-[10px] font-semibold ${
                                                isDone ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                                                : isCurrent ? 'bg-violet-600 text-white border-violet-600'
                                                : 'bg-white text-slate-500 border-slate-200'
                                            }`}>
                                                {isDone ? '✓ ' : ''}{ROUND_LABELS[r] || r}
                                            </span>
                                        );
                                    })}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleContinueDrive}
                                    className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold shadow-sm transition-all"
                                >
                                    Continue →
                                </button>
                                <button
                                    onClick={() => handleAdvanceRound(activeDriveStatus.mock_drive_id)}
                                    disabled={advancingDriveId === activeDriveStatus.mock_drive_id}
                                    className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold border border-slate-300 transition-all disabled:opacity-50"
                                >
                                    {advancingDriveId === activeDriveStatus.mock_drive_id ? 'Advancing…' : 'Complete Round'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Completed drive banner */}
                {activeDriveStatus && activeDriveStatus.status === 'completed' && (
                    <div className="mb-6 bg-emerald-50 border border-emerald-200 rounded-2xl p-5 shadow-sm text-center">
                        <div className="text-2xl mb-1">🎉</div>
                        <h3 className="text-sm font-bold text-emerald-800">Mock Drive Completed!</h3>
                        <p className="text-xs text-emerald-600 mt-0.5">
                            {activeDriveStatus.company_name} — {activeDriveStatus.target_role}
                        </p>
                    </div>
                )}

                {loading ? (
                    <div className="text-center py-16 text-sm text-slate-400">Loading available drives…</div>
                ) : availableDrives.length === 0 ? (
                    <div className="bg-white border border-slate-200 rounded-3xl p-10 shadow-sm text-center">
                        <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4 text-2xl">🎯</div>
                        <h3 className="text-base font-bold text-slate-800 mb-1">No mock drives available right now</h3>
                        <p className="text-xs text-slate-500 max-w-sm mx-auto">
                            New drives will appear here when your TPO publishes them and you meet the eligibility criteria.
                        </p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {availableDrives.map(drive => {
                            const enabledRounds = Object.entries(drive.selected_rounds || {})
                                .filter(([, v]) => v)
                                .map(([k]) => ROUND_LABELS[k] || k);

                            return (
                                <div key={drive.id} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <span className="text-xs font-bold uppercase tracking-wider text-violet-600 bg-violet-50 px-2 py-0.5 rounded border border-violet-200">
                                                Mock Drive
                                            </span>
                                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                Published
                                            </span>
                                        </div>
                                        <h3 className="text-lg font-bold text-slate-900 mb-1">{drive.company_name}</h3>
                                        <p className="text-xs text-slate-500 mb-4">{drive.target_role}</p>

                                        {drive.description && (
                                            <p className="text-xs text-slate-400 mb-4">{drive.description}</p>
                                        )}

                                        {/* Eligibility info */}
                                        <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-4 text-xs">
                                            <div className="flex justify-between">
                                                <span className="text-slate-600">Min CGPA:</span>
                                                <span className="font-bold text-slate-800">
                                                    ≥ {drive.minimum_cgpa} (Yours: {cgpa.toFixed(2)})
                                                </span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-slate-600">Max Backlogs:</span>
                                                <span className="font-bold text-slate-800">
                                                    ≤ {drive.maximum_backlogs} (Yours: {backlogs})
                                                </span>
                                            </div>
                                            {drive.eligible_branches?.length > 0 && (
                                                <div className="flex justify-between">
                                                    <span className="text-slate-600">Branches:</span>
                                                    <span className="font-semibold text-slate-700 text-right max-w-[150px] truncate">
                                                        {drive.eligible_branches.join(', ')}
                                                    </span>
                                                </div>
                                            )}
                                            <div className="flex justify-between pt-2 border-t border-slate-200">
                                                <span className="font-semibold text-slate-700">Status:</span>
                                                <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                                    Eligible ✓
                                                </span>
                                            </div>
                                        </div>

                                        {/* Configured rounds */}
                                        {enabledRounds.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5 mb-4">
                                                {enabledRounds.map(r => (
                                                    <span key={r} className="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded border border-slate-200">
                                                        {r}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    <button
                                        onClick={() => handleStartDrive(drive.id)}
                                        disabled={startingDriveId === drive.id || (activeDriveStatus?.mock_drive_id === drive.id && activeDriveStatus?.status === 'in_progress')}
                                        className="w-full py-2.5 px-4 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white shadow-sm transition-all active:scale-95"
                                    >
                                        {startingDriveId === drive.id ? 'Starting…' : 'Start Mock Drive →'}
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </StudentModeLayout>
    );
}
