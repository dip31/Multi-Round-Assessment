import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function TPODashboard() {
    const [tpoUser, setTpoUser] = useState(null);
    const [students, setStudents] = useState([]);
    const [cohortStats, setCohortStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [deptFilter, setDeptFilter] = useState('all');
    const [eligibilityFilter, setEligibilityFilter] = useState('all');
    const [selectedStudent, setSelectedStudent] = useState(null);
    const [toast, setToast] = useState(null);

    const navigate = useNavigate();

    useEffect(() => {
        loadTPOData();
    }, []);

    const loadTPOData = async () => {
        setLoading(true);
        try {
            const [profRes, studentsRes, statsRes] = await Promise.all([
                api.get('/profile/me'),
                api.get('/profile/cohort/students').catch(() => ({ data: { students: [] } })),
                api.get('/report/admin/cohort-stats').catch(() => ({ data: null })),
            ]);

            setTpoUser(profRes.data);
            setStudents(studentsRes.data?.students || []);
            setCohortStats(statsRes.data);
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to load TPO dashboard data' });
        } finally {
            setLoading(false);
        }
    };

    // Placement eligibility calculation: CGPA >= 7.0 and 0 backlogs
    const eligiblePool = students.filter((s) => (s.cgpa || 0) >= 7.0 && (s.backlogs_count || 0) === 0);

    const filteredStudents = students.filter((s) => {
        const matchesSearch =
            (s.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            (s.roll_number || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            (s.department || '').toLowerCase().includes(searchTerm.toLowerCase());

        if (!matchesSearch) return false;

        if (deptFilter !== 'all') {
            if ((s.department || '').toLowerCase() !== deptFilter.toLowerCase()) return false;
        }

        if (eligibilityFilter === 'eligible') {
            return (s.cgpa || 0) >= 7.0 && (s.backlogs_count || 0) === 0;
        }
        if (eligibilityFilter === 'with_backlogs') {
            return (s.backlogs_count || 0) > 0;
        }

        return true;
    });

    if (loading) {
        return <PageSkeleton variant="light" cardCount={4} />;
    }

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-['Inter'] antialiased">
            <Navbar position="sticky" onLogout={() => navigate('/login')} />
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-6 py-10">
                {/* Header Banner */}
                <div className="bg-white border border-slate-200 rounded-3xl p-8 mb-8 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-sky-50 text-sky-700 border border-sky-200">
                                Training & Placement Office
                            </span>
                            <span className="text-xs font-semibold text-slate-500">
                                {tpoUser?.tpo_profile?.institution || 'Engineering College'}
                            </span>
                        </div>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                            Corporate Recruitment & Placement Portal
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            Drive placement simulations, verify student eligibility criteria, and track multi-round hiring qualifications.
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/profile')}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                        >
                            TPO Profile
                        </button>
                        <button
                            onClick={loadTPOData}
                            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all"
                        >
                            ↻ Refresh Roster
                        </button>
                    </div>
                </div>

                {/* KPI Overview */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Eligible Candidate Pool</span>
                            <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">✓</span>
                        </div>
                        <div className="text-3xl font-black text-emerald-600">{eligiblePool.length}</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">CGPA ≥ 7.0 & 0 backlogs</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Registered Pool</span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">🎓</span>
                        </div>
                        <div className="text-3xl font-black text-slate-900">{students.length}</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">Candidates across all branches</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Hiring Partners Active</span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">🏢</span>
                        </div>
                        <div className="text-3xl font-black text-sky-600">4</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">Tier-1 & Core corporate drives</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Cohort Benchmark</span>
                            <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center font-bold text-sm">📊</span>
                        </div>
                        <div className="text-3xl font-black text-violet-600">
                            {cohortStats?.avg_overall_score ? `${cohortStats.avg_overall_score}%` : '78.5%'}
                        </div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">Average assessment readiness</div>
                    </div>
                </div>

                {/* Recruitment Drives Pipeline */}
                <div className="mb-8">
                    <h2 className="text-lg font-bold text-slate-900 mb-4">Active Placement Drives Pipeline</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-base font-bold text-slate-900">Google SDE Recruitment</div>
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Active Simulation
                                </span>
                            </div>
                            <div className="space-y-2 text-xs text-slate-600 mb-4">
                                <div className="flex justify-between">
                                    <span>Eligibility:</span>
                                    <span className="font-semibold text-slate-900">CGPA ≥ 8.0, 0 Backlogs</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Eligible Candidates:</span>
                                    <span className="font-bold text-indigo-600">
                                        {students.filter((s) => (s.cgpa || 0) >= 8.0 && (s.backlogs_count || 0) === 0).length}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Stages:</span>
                                    <span className="font-medium text-slate-700">Aptitude → Coding → Tech Interview</span>
                                </div>
                            </div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-base font-bold text-slate-900">Amazon Software Engineer</div>
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Active Simulation
                                </span>
                            </div>
                            <div className="space-y-2 text-xs text-slate-600 mb-4">
                                <div className="flex justify-between">
                                    <span>Eligibility:</span>
                                    <span className="font-semibold text-slate-900">CGPA ≥ 7.5, 0 Backlogs</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Eligible Candidates:</span>
                                    <span className="font-bold text-indigo-600">
                                        {students.filter((s) => (s.cgpa || 0) >= 7.5 && (s.backlogs_count || 0) === 0).length}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Stages:</span>
                                    <span className="font-medium text-slate-700">Coding (LeetCode Med) → System Design</span>
                                </div>
                            </div>
                        </div>

                        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="text-base font-bold text-slate-900">TCS Digital / Prime</div>
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-50 text-sky-700 border border-sky-200">
                                    Open Pool
                                </span>
                            </div>
                            <div className="space-y-2 text-xs text-slate-600 mb-4">
                                <div className="flex justify-between">
                                    <span>Eligibility:</span>
                                    <span className="font-semibold text-slate-900">CGPA ≥ 6.5, Max 1 Backlog</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Eligible Candidates:</span>
                                    <span className="font-bold text-indigo-600">
                                        {students.filter((s) => (s.cgpa || 0) >= 6.5 && (s.backlogs_count || 0) <= 1).length}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Stages:</span>
                                    <span className="font-medium text-slate-700">National Qualifier → HR Round</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Filter Toolbar */}
                <div className="bg-white border border-slate-200 rounded-2xl p-4 mb-6 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="w-full md:w-72">
                        <input
                            type="text"
                            placeholder="Search candidate or roll number..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full px-4 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        />
                    </div>

                    <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
                        <select
                            value={deptFilter}
                            onChange={(e) => setDeptFilter(e.target.value)}
                            className="px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                        >
                            <option value="all">All Departments</option>
                            <option value="Computer Science">Computer Science</option>
                            <option value="Information Technology">Information Technology</option>
                            <option value="Electronics & Communication">Electronics</option>
                            <option value="Mechanical Engineering">Mechanical</option>
                        </select>

                        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
                            <button
                                onClick={() => setEligibilityFilter('all')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                    eligibilityFilter === 'all' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600'
                                }`}
                            >
                                All Pool
                            </button>
                            <button
                                onClick={() => setEligibilityFilter('eligible')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                    eligibilityFilter === 'eligible' ? 'bg-white text-emerald-700 shadow-sm' : 'text-slate-600'
                                }`}
                            >
                                Placement Eligible
                            </button>
                            <button
                                onClick={() => setEligibilityFilter('with_backlogs')}
                                className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                    eligibilityFilter === 'with_backlogs' ? 'bg-white text-red-700 shadow-sm' : 'text-slate-600'
                                }`}
                            >
                                Has Backlogs
                            </button>
                        </div>
                    </div>
                </div>

                {/* Candidate Placement Roster Table */}
                <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                        <h2 className="text-base font-bold text-slate-900">
                            Placement Verification Roster ({filteredStudents.length})
                        </h2>
                        <span className="text-xs text-slate-500 font-medium">
                            Eligibility automatically mapped against corporate criteria
                        </span>
                    </div>

                    {filteredStudents.length === 0 ? (
                        <div className="text-center py-16 px-4">
                            <div className="text-4xl mb-3">📋</div>
                            <h3 className="text-base font-bold text-slate-800 mb-1">No candidate records match</h3>
                            <p className="text-xs text-slate-500 max-w-sm mx-auto">
                                Adjust your department or eligibility filters to inspect other student cohorts.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                                        <th className="px-6 py-3.5">Student</th>
                                        <th className="px-6 py-3.5">Department</th>
                                        <th className="px-6 py-3.5">CGPA</th>
                                        <th className="px-6 py-3.5">Backlogs</th>
                                        <th className="px-6 py-3.5">Target Role</th>
                                        <th className="px-6 py-3.5">Eligibility Status</th>
                                        <th className="px-6 py-3.5 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {filteredStudents.map((student) => {
                                        const isEligible = (student.cgpa || 0) >= 7.0 && (student.backlogs_count || 0) === 0;

                                        return (
                                            <tr key={student.user_id} className="hover:bg-slate-50/70 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-full bg-sky-100 text-sky-700 flex items-center justify-center font-bold text-xs">
                                                            {student.name?.charAt(0).toUpperCase() || 'S'}
                                                        </div>
                                                        <div>
                                                            <div className="font-bold text-slate-900">{student.name}</div>
                                                            <div className="text-[11px] text-slate-400 font-mono">
                                                                {student.roll_number || student.email}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </td>

                                                <td className="px-6 py-4 font-medium text-slate-700">
                                                    {student.department}
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`font-bold ${student.cgpa >= 7.5 ? 'text-indigo-600' : 'text-slate-800'}`}>
                                                        {student.cgpa || '7.50'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`font-bold ${student.backlogs_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                                                        {student.backlogs_count || 0}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className="px-2 py-1 rounded bg-slate-100 font-medium text-slate-700 text-[11px]">
                                                        {student.target_role || 'Software Engineer'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                                                        isEligible
                                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                                                    }`}>
                                                        {isEligible ? '✓ Eligible Tier-1' : '⚠️ Conditional'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4 text-right">
                                                    <button
                                                        onClick={() => setSelectedStudent(student)}
                                                        className="px-3 py-1.5 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold text-xs transition-colors border border-sky-200"
                                                    >
                                                        Review Student
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Candidate Review Modal */}
                {selectedStudent && (
                    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 max-w-lg w-full shadow-2xl">
                            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
                                <div>
                                    <h3 className="text-xl font-bold text-slate-900">{selectedStudent.name}</h3>
                                    <p className="text-xs text-slate-500">{selectedStudent.email} | {selectedStudent.department}</p>
                                </div>
                                <button
                                    onClick={() => setSelectedStudent(null)}
                                    className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="space-y-4 text-xs">
                                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-slate-50 rounded-2xl border border-slate-200">
                                    <div>
                                        <div className="text-slate-400 font-medium">CGPA</div>
                                        <div className="font-bold text-indigo-600">{selectedStudent.cgpa} / 10.0</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">10th Marks</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.tenth_marks ? `${selectedStudent.tenth_marks}%` : 'Not Set'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">12th Marks</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.twelfth_marks ? `${selectedStudent.twelfth_marks}%` : 'Not Set'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Active Backlogs</div>
                                        <div className={`font-bold ${selectedStudent.backlogs_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                                            {selectedStudent.backlogs_count}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Gender & Nationality</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.gender || 'Male'} | {selectedStudent.nationality || 'Indian'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Date of Birth</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.date_of_birth || 'Not Set'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Graduation Year</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.graduation_year}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Mobile No.</div>
                                        <div className="font-mono text-slate-800">{selectedStudent.mobile_no || 'Not Set'}</div>
                                    </div>
                                    <div className="sm:col-span-3">
                                        <div className="text-slate-400 font-medium">College Email ID</div>
                                        <div className="font-mono text-slate-800">{selectedStudent.college_email_id || selectedStudent.email}</div>
                                    </div>
                                </div>

                                <div className="p-4 bg-sky-50/60 rounded-2xl border border-sky-100">
                                    <h4 className="font-bold text-slate-800 mb-2">Drive Eligibility Check</h4>
                                    <div className="space-y-1.5 text-slate-700">
                                        <div className="flex items-center justify-between">
                                            <span>Google SDE (CGPA ≥ 8.0, 0 Backlogs):</span>
                                            <span className="font-bold">{selectedStudent.cgpa >= 8.0 && selectedStudent.backlogs_count === 0 ? '✓ Yes' : '✕ No'}</span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span>Amazon SDE (CGPA ≥ 7.5, 0 Backlogs):</span>
                                            <span className="font-bold">{selectedStudent.cgpa >= 7.5 && selectedStudent.backlogs_count === 0 ? '✓ Yes' : '✕ No'}</span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span>TCS Prime (CGPA ≥ 6.5, ≤1 Backlog):</span>
                                            <span className="font-bold">{selectedStudent.cgpa >= 6.5 && selectedStudent.backlogs_count <= 1 ? '✓ Yes' : '✕ No'}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
                                <button
                                    onClick={() => setSelectedStudent(null)}
                                    className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                                >
                                    Done
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
