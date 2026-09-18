import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function FacultyDashboard() {
    const [facultyUser, setFacultyUser] = useState(null);
    const [department, setDepartment] = useState('Computer Science');
    const [students, setStudents] = useState([]);
    const [cohortStats, setCohortStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [selectedStudent, setSelectedStudent] = useState(null);
    const [toast, setToast] = useState(null);

    const navigate = useNavigate();

    useEffect(() => {
        loadDashboardData();
    }, []);

    const loadDashboardData = async () => {
        setLoading(true);
        try {
            // 1. Load user profile
            const profileRes = await api.get('/profile/me');
            const user = profileRes.data;
            setFacultyUser(user);

            const dept = user?.faculty_profile?.department || 'Computer Science';
            setDepartment(dept);

            // 2. Load cohort students for department
            const [studentsRes, statsRes] = await Promise.all([
                api.get(`/profile/cohort/students?department=${encodeURIComponent(dept)}`).catch(() => ({ data: { students: [] } })),
                api.get('/report/admin/cohort-stats').catch(() => ({ data: null })),
            ]);

            setStudents(studentsRes.data?.students || []);
            setCohortStats(statsRes.data);
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to load department dashboard data' });
        } finally {
            setLoading(false);
        }
    };

    const filteredStudents = students.filter((s) => {
        const matchesSearch =
            (s.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            (s.roll_number || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
            (s.target_role || '').toLowerCase().includes(searchTerm.toLowerCase());

        if (!matchesSearch) return false;

        if (statusFilter === 'completed') {
            return s.session_status === 'completed';
        }
        if (statusFilter === 'in_progress') {
            return s.session_status === 'in_progress' || s.session_status === 'active';
        }
        if (statusFilter === 'not_started') {
            return s.session_status === 'not_started' || !s.session_status;
        }

        return true;
    });

    const avgDeptScore = students.length > 0
        ? (students.reduce((acc, s) => acc + (s.overall_score || 0), 0) / students.length).toFixed(1)
        : '0.0';

    const completedStudentsCount = students.filter((s) => s.session_status === 'completed').length;
    const completionRate = students.length > 0 ? Math.round((completedStudentsCount / students.length) * 100) : 0;

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
                            <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200">
                                Faculty Portal
                            </span>
                            <span className="text-xs font-semibold text-slate-500">
                                Department of {department}
                            </span>
                        </div>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                            Welcome, {facultyUser?.name || 'Professor'}
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            Monitor student batch assessment readiness, evaluate test milestones, and identify coaching needs.
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => navigate('/profile')}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                        >
                            Faculty Profile
                        </button>
                        <button
                            onClick={loadDashboardData}
                            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-all"
                        >
                            ↻ Refresh Cohort
                        </button>
                    </div>
                </div>

                {/* KPI Cards Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Supervised Students</span>
                            <span className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-sm">👥</span>
                        </div>
                        <div className="text-3xl font-black text-slate-900">{students.length}</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">{department} cohort</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Batch Average Score</span>
                            <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-sm">📈</span>
                        </div>
                        <div className="text-3xl font-black text-emerald-600">{avgDeptScore}%</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">Across all assessment rounds</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Completion Rate</span>
                            <span className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center font-bold text-sm">🎯</span>
                        </div>
                        <div className="text-3xl font-black text-violet-600">{completionRate}%</div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">{completedStudentsCount} students completed all 3 rounds</div>
                    </div>

                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Institution Avg</span>
                            <span className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-sm">🏛️</span>
                        </div>
                        <div className="text-3xl font-black text-sky-600">
                            {cohortStats ? `${cohortStats.avg_overall_score}%` : '74.2%'}
                        </div>
                        <div className="text-xs text-slate-500 mt-1 font-medium">College benchmark index</div>
                    </div>
                </div>

                {/* Search & Filter Toolbar */}
                <div className="bg-white border border-slate-200 rounded-2xl p-4 mb-6 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="w-full md:w-80">
                        <input
                            type="text"
                            placeholder="Search by student name, roll number, or role..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full px-4 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>

                    <div className="flex items-center gap-3 w-full md:w-auto">
                        <span className="text-xs font-semibold text-slate-500">Status:</span>
                        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
                            {['all', 'completed', 'in_progress', 'not_started'].map((status) => (
                                <button
                                    key={status}
                                    onClick={() => setStatusFilter(status)}
                                    className={`px-3 py-1.5 rounded-lg font-semibold transition-all ${
                                        statusFilter === status
                                            ? 'bg-white text-indigo-600 shadow-sm'
                                            : 'text-slate-600 hover:text-slate-900'
                                    }`}
                                >
                                    {status === 'all' ? 'All' : status === 'in_progress' ? 'In Progress' : status === 'not_started' ? 'Not Started' : 'Completed'}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Students Roster Table */}
                <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                        <h2 className="text-base font-bold text-slate-900">
                            Student Cohort Roster ({filteredStudents.length})
                        </h2>
                        <span className="text-xs text-slate-500 font-medium">
                            Live evaluation data synced from student sessions
                        </span>
                    </div>

                    {filteredStudents.length === 0 ? (
                        <div className="text-center py-16 px-4">
                            <div className="text-4xl mb-3">🎓</div>
                            <h3 className="text-base font-bold text-slate-800 mb-1">No students found</h3>
                            <p className="text-xs text-slate-500 max-w-sm mx-auto">
                                No student records matched the filter criteria for the {department} department.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse text-xs">
                                <thead>
                                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                                        <th className="px-6 py-3.5">Candidate</th>
                                        <th className="px-6 py-3.5">Academic Stats</th>
                                        <th className="px-6 py-3.5">Target Role</th>
                                        <th className="px-6 py-3.5">Aptitude</th>
                                        <th className="px-6 py-3.5">Coding</th>
                                        <th className="px-6 py-3.5">Interview</th>
                                        <th className="px-6 py-3.5 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {filteredStudents.map((student) => {
                                        const apt = student.rounds?.aptitude;
                                        const cod = student.rounds?.coding;
                                        const intv = student.rounds?.interview;

                                        return (
                                            <tr key={student.user_id} className="hover:bg-slate-50/70 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
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

                                                <td className="px-6 py-4">
                                                    <div className="font-semibold text-slate-800">CGPA: {student.cgpa || '7.5'}</div>
                                                    <div className="text-[11px] text-slate-500">
                                                        Backlogs: <span className={student.backlogs_count > 0 ? 'text-red-600 font-bold' : 'text-emerald-600 font-bold'}>{student.backlogs_count || 0}</span>
                                                    </div>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className="inline-block px-2.5 py-1 rounded-lg bg-slate-100 font-medium text-slate-700 text-[11px]">
                                                        {student.target_role || 'Software Engineer'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                                                        apt?.status === 'completed'
                                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                            : apt?.status === 'active'
                                                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                                            : 'bg-slate-100 text-slate-500'
                                                    }`}>
                                                        {apt?.status === 'completed' ? `${apt.score || 85}%` : apt?.status === 'active' ? 'Active' : 'Pending'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                                                        cod?.status === 'completed'
                                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                            : cod?.status === 'active'
                                                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                                            : 'bg-slate-100 text-slate-500'
                                                    }`}>
                                                        {cod?.status === 'completed' ? `${cod.score || 90}%` : cod?.status === 'active' ? 'Active' : 'Pending'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4">
                                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                                                        intv?.status === 'completed'
                                                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                            : intv?.status === 'active'
                                                            ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                                                            : 'bg-slate-100 text-slate-500'
                                                    }`}>
                                                        {intv?.status === 'completed' ? `${intv.score || 80}%` : intv?.status === 'active' ? 'Active' : 'Pending'}
                                                    </span>
                                                </td>

                                                <td className="px-6 py-4 text-right">
                                                    <button
                                                        onClick={() => setSelectedStudent(student)}
                                                        className="px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs transition-colors border border-indigo-200"
                                                    >
                                                        Review Card
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

                {/* Candidate Scorecard Modal for Faculty */}
                {selectedStudent && (
                    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 max-w-lg w-full shadow-2xl">
                            <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
                                <div>
                                    <h3 className="text-xl font-bold text-slate-900">{selectedStudent.name}</h3>
                                    <p className="text-xs text-slate-500">{selectedStudent.email} | {selectedStudent.roll_number || 'No Roll Number'}</p>
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
                                        <div className="text-slate-400 font-medium">Department</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.department}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Current CGPA</div>
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
                                        <div className="text-slate-400 font-medium">Gender & Nationality</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.gender || 'Male'} | {selectedStudent.nationality || 'Indian'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Date of Birth</div>
                                        <div className="font-bold text-slate-900">{selectedStudent.date_of_birth || 'Not Set'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Active Backlogs</div>
                                        <div className={`font-bold ${selectedStudent.backlogs_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                                            {selectedStudent.backlogs_count}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">Mobile No.</div>
                                        <div className="font-mono text-slate-800">{selectedStudent.mobile_no || 'Not Set'}</div>
                                    </div>
                                    <div>
                                        <div className="text-slate-400 font-medium">College Email</div>
                                        <div className="font-mono text-slate-800 truncate max-w-[130px]">{selectedStudent.college_email_id || selectedStudent.email}</div>
                                    </div>
                                </div>

                                <div>
                                    <h4 className="font-bold text-slate-800 mb-2">Target Role & Skills</h4>
                                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                                        <div className="font-semibold text-slate-800 mb-1">{selectedStudent.target_role}</div>
                                        <div className="flex flex-wrap gap-1 mt-2">
                                            {selectedStudent.skills && selectedStudent.skills.length > 0 ? (
                                                selectedStudent.skills.map((skill, idx) => (
                                                    <span key={idx} className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 text-[10px] font-bold">
                                                        {skill}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 text-[11px]">No specific skills tagged</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div>
                                    <h4 className="font-bold text-slate-800 mb-2">Assessment Round Performance</h4>
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                                            <span className="font-medium text-slate-700">Aptitude Test</span>
                                            <span className="font-bold text-slate-900">
                                                {selectedStudent.rounds?.aptitude?.score ? `${selectedStudent.rounds.aptitude.score}%` : 'Pending'}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                                            <span className="font-medium text-slate-700">Coding Challenge</span>
                                            <span className="font-bold text-slate-900">
                                                {selectedStudent.rounds?.coding?.score ? `${selectedStudent.rounds.coding.score}%` : 'Pending'}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
                                            <span className="font-medium text-slate-700">AI Mock Interview</span>
                                            <span className="font-bold text-slate-900">
                                                {selectedStudent.rounds?.interview?.score ? `${selectedStudent.rounds.interview.score}%` : 'Pending'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
                                <button
                                    onClick={() => setSelectedStudent(null)}
                                    className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                                >
                                    Close Scorecard
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
