import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { getProfile } from '../services/profileService';

export default function MockDriveOverview() {
    const navigate = useNavigate();
    const [profileData, setProfileData] = useState(null);

    useEffect(() => {
        const loadProfile = async () => {
            try {
                const data = await getProfile();
                setProfileData(data);
            } catch (err) {
                console.error('Failed to load profile:', err);
            }
        };
        loadProfile();
    }, []);

    const studentProfile = profileData?.student_profile || {};
    const cgpa = studentProfile.cgpa ?? 0.0;
    const backlogs = studentProfile.backlogs_count ?? 0;

    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Mock Drive</h1>
                    <p className="text-slate-600 text-sm">
                        Company-specific mock hiring drives calibrated against real eligibility criteria and recruitment patterns
                    </p>
                </div>

                {/* Mock Drives Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Drive 1: Tier-1 Tech */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                                Tier-1 Product Tech
                            </span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">
                                🚀
                            </span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Software Development Engineer</h3>
                        <p className="text-xs text-slate-500 mb-4">
                            DS & Algo, system design, and behavioral fit
                        </p>

                        {/* Eligibility */}
                        <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-4 text-xs">
                            <div className="flex justify-between">
                                <span className="text-slate-600">Required CGPA:</span>
                                <span className="font-bold text-slate-800">≥ 7.00 (Yours: {cgpa.toFixed(2)})</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-600">Backlogs:</span>
                                <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                            </div>
                            <div className="flex justify-between pt-2 border-t border-slate-200">
                                <span className="font-semibold text-slate-700">Status:</span>
                                {cgpa >= 7.0 && backlogs === 0 ? (
                                    <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                        Eligible ✓
                                    </span>
                                ) : (
                                    <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                                        Not Eligible
                                    </span>
                                )}
                            </div>
                        </div>

                        <button
                            onClick={() => navigate('/instructions')}
                            disabled={!(cgpa >= 7.0 && backlogs === 0)}
                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                cgpa >= 7.0 && backlogs === 0
                                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white'
                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                            }`}
                        >
                            {cgpa >= 7.0 && backlogs === 0 ? 'Apply Now →' : 'Not Eligible'}
                        </button>
                    </div>

                    {/* Drive 2: Global IT Services */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                                Global IT Services
                            </span>
                            <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">
                                🌐
                            </span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Associate Software Engineer</h3>
                        <p className="text-xs text-slate-500 mb-4">
                            Aptitude, core CS, and communication skills
                        </p>

                        {/* Eligibility */}
                        <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-4 text-xs">
                            <div className="flex justify-between">
                                <span className="text-slate-600">Required CGPA:</span>
                                <span className="font-bold text-slate-800">≥ 6.00 (Yours: {cgpa.toFixed(2)})</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-600">Backlogs:</span>
                                <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                            </div>
                            <div className="flex justify-between pt-2 border-t border-slate-200">
                                <span className="font-semibold text-slate-700">Status:</span>
                                {cgpa >= 6.0 && backlogs === 0 ? (
                                    <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                        Eligible ✓
                                    </span>
                                ) : (
                                    <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                                        Not Eligible
                                    </span>
                                )}
                            </div>
                        </div>

                        <button
                            onClick={() => navigate('/instructions')}
                            disabled={!(cgpa >= 6.0 && backlogs === 0)}
                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                cgpa >= 6.0 && backlogs === 0
                                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                            }`}
                        >
                            {cgpa >= 6.0 && backlogs === 0 ? 'Apply Now →' : 'Not Eligible'}
                        </button>
                    </div>

                    {/* Drive 3: FinTech & Quant */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
                                FinTech & Quant
                            </span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">
                                📈
                            </span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Quantitative Analyst</h3>
                        <p className="text-xs text-slate-500 mb-4">
                            Probability, algorithms, and scenario analysis
                        </p>

                        {/* Eligibility */}
                        <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2 mb-4 text-xs">
                            <div className="flex justify-between">
                                <span className="text-slate-600">Required CGPA:</span>
                                <span className="font-bold text-slate-800">≥ 7.50 (Yours: {cgpa.toFixed(2)})</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-600">Backlogs:</span>
                                <span className="font-bold text-slate-800">0 (Yours: {backlogs})</span>
                            </div>
                            <div className="flex justify-between pt-2 border-t border-slate-200">
                                <span className="font-semibold text-slate-700">Status:</span>
                                {cgpa >= 7.5 && backlogs === 0 ? (
                                    <span className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                        Eligible ✓
                                    </span>
                                ) : (
                                    <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                                        Not Eligible
                                    </span>
                                )}
                            </div>
                        </div>

                        <button
                            onClick={() => navigate('/instructions')}
                            disabled={!(cgpa >= 7.5 && backlogs === 0)}
                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold transition-all ${
                                cgpa >= 7.5 && backlogs === 0
                                    ? 'bg-sky-600 hover:bg-sky-700 text-white'
                                    : 'bg-slate-100 text-slate-600 border border-slate-200 cursor-not-allowed'
                            }`}
                        >
                            {cgpa >= 7.5 && backlogs === 0 ? 'Apply Now →' : 'Not Eligible'}
                        </button>
                    </div>
                </div>
            </div>
        </StudentModeLayout>
    );
}
