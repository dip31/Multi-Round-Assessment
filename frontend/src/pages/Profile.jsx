import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import { viewResumeFile } from '../services/resumeService';

export default function Profile() {
    const [profileData, setProfileData] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState(null);

    // Form states for Student Profile
    const [fullName, setFullName] = useState('');
    const [department, setDepartment] = useState('Computer Science');
    const [cgpa, setCgpa] = useState('7.50');
    const [graduationYear, setGraduationYear] = useState('2026');
    const [backlogsCount, setBacklogsCount] = useState('0');
    const [institution, setInstitution] = useState('Engineering College');
    const [targetRole, setTargetRole] = useState('Software Development Engineer');
    const [skillsText, setSkillsText] = useState('');
    const [rollNumber, setRollNumber] = useState('');
    const [mobileNo, setMobileNo] = useState('');
    const [collegeEmailId, setCollegeEmailId] = useState('');
    const [gender, setGender] = useState('Male');
    const [dateOfBirth, setDateOfBirth] = useState('');
    const [nationality, setNationality] = useState('Indian');
    const [tenthMarks, setTenthMarks] = useState('');
    const [twelfthMarks, setTwelfthMarks] = useState('');
    const [bio, setBio] = useState('');

    // Form states for Faculty / TPO
    const [designation, setDesignation] = useState('');
    const [employeeId, setEmployeeId] = useState('');
    const [phoneNumber, setPhoneNumber] = useState('');

    // Resume/CV Management states
    const [resumes, setResumes] = useState([]);
    const [isResumeModalOpen, setIsResumeModalOpen] = useState(false);
    const [uploadingResume, setUploadingResume] = useState(false);
    const [cvName, setCvName] = useState('');
    const [cvType, setCvType] = useState('Software Developer');
    const [cvFile, setCvFile] = useState(null);
    const [deletingResumeId, setDeletingResumeId] = useState(null);

    const navigate = useNavigate();

    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = async () => {
        setLoading(true);
        try {
            const [profRes, sessionRes] = await Promise.all([
                api.get('/profile/me'),
                api.get('/session/status').catch(() => ({ data: null })),
            ]);

            const user = profRes.data;
            setProfileData(user);
            setStats(sessionRes.data);

            if (user.resumes) {
                setResumes(user.resumes);
            } else if (user.role === 'student') {
                api.get('/profile/resumes').then((r) => setResumes(r.data || [])).catch(() => {});
            }

            if (user.role === 'student' && user.student_profile) {
                const sp = user.student_profile;
                setFullName(sp.full_name || user.name || '');
                setDepartment(sp.department || 'Computer Science');
                setCgpa(String(sp.cgpa || '7.50'));
                setGraduationYear(String(sp.graduation_year || '2026'));
                setBacklogsCount(String(sp.backlogs_count || '0'));
                setInstitution(sp.institution || 'Engineering College');
                setTargetRole(sp.target_role || 'Software Development Engineer');
                setSkillsText(Array.isArray(sp.skills) ? sp.skills.join(', ') : '');
                setRollNumber(sp.roll_number || '');
                setMobileNo(sp.mobile_no || sp.phone_number || '');
                setCollegeEmailId(sp.college_email_id || '');
                setGender(sp.gender || 'Male');
                setDateOfBirth(sp.date_of_birth || '');
                setNationality(sp.nationality || 'Indian');
                setTenthMarks(sp.tenth_marks != null ? String(sp.tenth_marks) : '');
                setTwelfthMarks(sp.twelfth_marks != null ? String(sp.twelfth_marks) : '');
                setBio(sp.bio || '');
            } else if (user.role === 'faculty' && user.faculty_profile) {
                const fp = user.faculty_profile;
                setDepartment(fp.department || 'Computer Science');
                setDesignation(fp.designation || 'Assistant Professor');
                setInstitution(fp.institution || 'Engineering College');
                setEmployeeId(fp.employee_id || '');
                setBio(fp.bio || '');
            } else if (user.role === 'tpo' && user.tpo_profile) {
                const tp = user.tpo_profile;
                setInstitution(tp.institution || 'Engineering College');
                setDesignation(tp.designation || 'Training & Placement Officer');
                setPhoneNumber(tp.contact_phone || '');
                setBio(tp.bio || '');
            }
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to load profile details' });
        } finally {
            setLoading(false);
        }
    };

    const handleSaveStudent = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const skillsArray = skillsText
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);

            const payload = {
                full_name: fullName,
                department,
                cgpa: parseFloat(cgpa) || 7.5,
                graduation_year: parseInt(graduationYear, 10) || 2026,
                backlogs_count: parseInt(backlogsCount, 10) || 0,
                institution,
                target_role: targetRole,
                skills: skillsArray,
                roll_number: rollNumber,
                mobile_no: mobileNo,
                phone_number: mobileNo,
                college_email_id: collegeEmailId,
                gender,
                date_of_birth: dateOfBirth,
                nationality,
                tenth_marks: tenthMarks !== '' ? parseFloat(tenthMarks) : null,
                twelfth_marks: twelfthMarks !== '' ? parseFloat(twelfthMarks) : null,
                bio,
            };

            await api.put('/profile/student/me', payload);

            if (fullName) {
                const stored = localStorage.getItem('user');
                if (stored) {
                    try {
                        const parsed = JSON.parse(stored);
                        parsed.name = fullName;
                        localStorage.setItem('user', JSON.stringify(parsed));
                        localStorage.setItem('user_name', fullName);
                    } catch (err) {}
                }
            }

            setProfileData((prev) => ({
                ...prev,
                name: fullName || prev?.name,
                student_profile: {
                    ...prev?.student_profile,
                    ...payload,
                },
            }));

            setToast({ type: 'success', message: 'Student profile updated successfully!' });
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to update student profile.' });
        } finally {
            setSaving(false);
        }
    };

    const handleSaveFaculty = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.put('/profile/faculty/me', {
                department,
                designation,
                institution,
                employee_id: employeeId,
                bio,
            });
            setToast({ type: 'success', message: 'Faculty profile updated successfully!' });
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to update faculty profile.' });
        } finally {
            setSaving(false);
        }
    };

    const handleSaveTPO = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.put('/profile/tpo/me', {
                institution,
                designation,
                contact_phone: phoneNumber,
                bio,
            });
            setToast({ type: 'success', message: 'TPO profile updated successfully!' });
        } catch (err) {
            setToast({ type: 'error', message: 'Failed to update TPO profile.' });
        } finally {
            setSaving(false);
        }
    };

    const handleOpenResumeModal = () => {
        setCvName('');
        setCvType('Software Developer');
        setCvFile(null);
        setIsResumeModalOpen(true);
    };

    const handleUploadResume = async (e) => {
        e.preventDefault();
        if (!cvName.trim()) {
            setToast({ type: 'error', message: 'Please enter a CV Name' });
            return;
        }
        if (!cvFile) {
            setToast({ type: 'error', message: 'Please select a CV file' });
            return;
        }
        if (!cvFile.name.toLowerCase().endsWith('.pdf')) {
            setToast({ type: 'error', message: 'Only PDF format is supported' });
            return;
        }
        setUploadingResume(true);
        try {
            const formData = new FormData();
            formData.append('file', cvFile);
            formData.append('cv_name', cvName.trim());
            formData.append('cv_type', cvType);

            const res = await api.post('/profile/resumes', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setResumes((prev) => [res.data, ...prev]);
            setIsResumeModalOpen(false);
            setCvFile(null);
            setCvName('');
            setToast({ type: 'success', message: 'CV uploaded successfully!' });
        } catch (err) {
            setToast({
                type: 'error',
                message: err.response?.data?.detail || 'Failed to upload CV',
            });
        } finally {
            setUploadingResume(false);
        }
    };

    const handleDeleteResume = async (resumeId) => {
        if (!window.confirm('Are you sure you want to delete this resume?')) return;
        setDeletingResumeId(resumeId);
        try {
            await api.delete(`/profile/resumes/${resumeId}`);
            setResumes((prev) => prev.filter((r) => r.id !== resumeId));
            setToast({ type: 'success', message: 'Resume deleted successfully!' });
        } catch (err) {
            setToast({
                type: 'error',
                message: err.response?.data?.detail || 'Failed to delete resume',
            });
        } finally {
            setDeletingResumeId(null);
        }
    };

    if (loading) {
        return <PageSkeleton variant="light" cardCount={3} />;
    }

    const user = profileData;
    const role = user?.role || 'student';

    return (
        <div className="bg-slate-50 text-slate-900 font-['Inter'] antialiased min-h-screen">
            <Navbar position="sticky" onLogout={() => navigate('/login')} />
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-5xl mx-auto px-6 py-10">
                {/* Profile Identity Card */}
                <div className="bg-white border border-slate-200 rounded-3xl p-8 mb-8 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
                    <div className="flex items-center gap-5">
                        <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white font-extrabold text-3xl shadow-md">
                            {user?.name?.charAt(0).toUpperCase() || 'U'}
                        </div>
                        <div>
                            <div className="flex items-center gap-2.5 mb-1">
                                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{user?.name}</h1>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-indigo-50 text-indigo-700 border border-indigo-200">
                                    {role}
                                </span>
                            </div>
                            <p className="text-sm text-slate-500 font-medium">{user?.email}</p>
                            <p className="text-xs text-slate-400 mt-1">
                                Member since: {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Active Member'}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => {
                                const target = role === 'faculty' ? '/faculty/dashboard' : role === 'tpo' ? '/tpo/dashboard' : role === 'admin' ? '/admin/dashboard' : '/dashboard';
                                navigate(target);
                            }}
                            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all border border-slate-300"
                        >
                            ← Back to {role === 'faculty' ? 'Faculty Portal' : role === 'tpo' ? 'TPO Portal' : 'Dashboard'}
                        </button>
                    </div>
                </div>

                {/* Role Specific Profile Editor */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Left Form: Academic / Role Details (2 cols) */}
                    <div className="lg:col-span-2">
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm">
                            <div className="border-b border-slate-100 pb-4 mb-6">
                                <h2 className="text-lg font-bold text-slate-900">
                                    {role === 'student' ? 'Academic & Placement Profile' : role === 'faculty' ? 'Faculty Details' : 'TPO Placement Cell Profile'}
                                </h2>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    {role === 'student'
                                        ? 'Keep your academic metrics up-to-date for eligibility evaluation in Mock Drives.'
                                        : 'Institutional and departmental information.'}
                                </p>
                            </div>

                            {role === 'student' && (
                                <form onSubmit={handleSaveStudent} className="space-y-6 text-xs">
                                    {/* 1. Personal Information */}
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2 pb-1.5 border-b border-slate-100">
                                            <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px]">1</span>
                                            Personal Information
                                        </h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Full Name
                                                </label>
                                                <input
                                                    type="text"
                                                    value={fullName}
                                                    onChange={(e) => setFullName(e.target.value)}
                                                    placeholder="Candidate's Full Name"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Gender
                                                </label>
                                                <select
                                                    value={gender}
                                                    onChange={(e) => setGender(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                >
                                                    <option value="Male">Male</option>
                                                    <option value="Female">Female</option>
                                                    <option value="Other">Other</option>
                                                    <option value="Prefer not to say">Prefer not to say</option>
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Date of Birth
                                                </label>
                                                <input
                                                    type="date"
                                                    value={dateOfBirth}
                                                    onChange={(e) => setDateOfBirth(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Nationality
                                                </label>
                                                <input
                                                    type="text"
                                                    value={nationality}
                                                    onChange={(e) => setNationality(e.target.value)}
                                                    placeholder="e.g. Indian"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* 2. Contact & Identity */}
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2 pb-1.5 border-b border-slate-100">
                                            <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px]">2</span>
                                            Contact & Institutional Identity
                                        </h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Roll Number / Student ID
                                                </label>
                                                <input
                                                    type="text"
                                                    value={rollNumber}
                                                    onChange={(e) => setRollNumber(e.target.value)}
                                                    placeholder="e.g. 21CS042"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Mobile Number
                                                </label>
                                                <input
                                                    type="tel"
                                                    value={mobileNo}
                                                    onChange={(e) => setMobileNo(e.target.value)}
                                                    placeholder="e.g. +91 9876543210"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    College Email ID
                                                </label>
                                                <input
                                                    type="email"
                                                    value={collegeEmailId}
                                                    onChange={(e) => setCollegeEmailId(e.target.value)}
                                                    placeholder="e.g. student@college.edu"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Institution / College
                                                </label>
                                                <input
                                                    type="text"
                                                    value={institution}
                                                    onChange={(e) => setInstitution(e.target.value)}
                                                    placeholder="e.g. National Institute of Technology"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* 3. Academic Records & Eligibility */}
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2 pb-1.5 border-b border-slate-100">
                                            <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px]">3</span>
                                            Academic Qualifications & Scores
                                        </h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    10th Standard Marks (%)
                                                </label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    max="100"
                                                    value={tenthMarks}
                                                    onChange={(e) => setTenthMarks(e.target.value)}
                                                    placeholder="e.g. 88.50"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    12th Standard Marks (%)
                                                </label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    max="100"
                                                    value={twelfthMarks}
                                                    onChange={(e) => setTwelfthMarks(e.target.value)}
                                                    placeholder="e.g. 91.20"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Department / Branch
                                                </label>
                                                <select
                                                    value={department}
                                                    onChange={(e) => setDepartment(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                >
                                                    <option value="Computer Science">Computer Science</option>
                                                    <option value="Information Technology">Information Technology</option>
                                                    <option value="Electronics & Communication">Electronics & Communication</option>
                                                    <option value="Mechanical Engineering">Mechanical Engineering</option>
                                                    <option value="Civil Engineering">Civil Engineering</option>
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Current CGPA (out of 10)
                                                </label>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    max="10"
                                                    value={cgpa}
                                                    onChange={(e) => setCgpa(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Graduation Year
                                                </label>
                                                <select
                                                    value={graduationYear}
                                                    onChange={(e) => setGraduationYear(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                >
                                                    <option value="2024">2024</option>
                                                    <option value="2025">2025</option>
                                                    <option value="2026">2026</option>
                                                    <option value="2027">2027</option>
                                                    <option value="2028">2028</option>
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Active Backlogs
                                                </label>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    value={backlogsCount}
                                                    onChange={(e) => setBacklogsCount(e.target.value)}
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {/* 4. Career Aspirations & Skills */}
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-3 flex items-center gap-2 pb-1.5 border-b border-slate-100">
                                            <span className="w-5 h-5 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-[10px]">4</span>
                                            Career Aspirations & Technical Skills
                                        </h3>
                                        <div className="space-y-4">
                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Target Job Role
                                                </label>
                                                <input
                                                    type="text"
                                                    value={targetRole}
                                                    onChange={(e) => setTargetRole(e.target.value)}
                                                    placeholder="e.g. Full Stack Engineer, SDE-1"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Core Skills (comma-separated)
                                                </label>
                                                <input
                                                    type="text"
                                                    value={skillsText}
                                                    onChange={(e) => setSkillsText(e.target.value)}
                                                    placeholder="Python, Data Structures, React, PostgreSQL"
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>

                                            <div>
                                                <label className="block font-semibold text-slate-700 mb-1.5 uppercase tracking-wider">
                                                    Bio / Summary
                                                </label>
                                                <textarea
                                                    rows={3}
                                                    value={bio}
                                                    onChange={(e) => setBio(e.target.value)}
                                                    placeholder="Brief background and career interests..."
                                                    className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    <div className="pt-3 flex justify-end">
                                        <button
                                            type="submit"
                                            disabled={saving}
                                            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold text-xs shadow-md shadow-indigo-600/30 transition-all uppercase tracking-wider"
                                        >
                                            {saving ? 'Saving...' : 'Save Student Profile'}
                                        </button>
                                    </div>

                                    {/* Section 5: My Resumes / CVs (Multiple Uploads) */}
                                    <div className="mt-8 pt-8 border-t border-slate-200">
                                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                                            <div>
                                                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                                    <span className="text-lg">📄</span> My Resumes / CVs
                                                    <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
                                                        {resumes.length} {resumes.length === 1 ? 'CV' : 'CVs'}
                                                    </span>
                                                </h3>
                                                <p className="text-[11px] text-slate-500 mt-0.5">
                                                    Upload multiple CVs tailored for specific roles. You can pick any resume when taking AI interviews.
                                                </p>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={handleOpenResumeModal}
                                                className="self-start sm:self-auto px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-sm hover:shadow-md transition-all flex items-center gap-1.5"
                                            >
                                                <span>+</span> Add CV
                                            </button>
                                        </div>

                                        {resumes.length === 0 ? (
                                            <div className="p-6 rounded-2xl bg-slate-50 border-2 border-dashed border-slate-200 text-center">
                                                <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-2 text-xl font-bold">
                                                    📄
                                                </div>
                                                <p className="text-xs font-semibold text-slate-700">No Resumes Uploaded Yet</p>
                                                <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
                                                    Click "+ Add CV" to upload resumes for different roles (e.g. Software Developer, Data Science, QA).
                                                </p>
                                                <button
                                                    type="button"
                                                    onClick={handleOpenResumeModal}
                                                    className="mt-3 px-4 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold shadow-xs"
                                                >
                                                    Upload Your First CV
                                                </button>
                                            </div>
                                        ) : (
                                            <div className="space-y-3">
                                                {resumes.map((res) => {
                                                    const typeColors = {
                                                        'Software Developer': 'bg-blue-50 text-blue-700 border-blue-200',
                                                        'Data Science': 'bg-purple-50 text-purple-700 border-purple-200',
                                                        'Software Testing / QA': 'bg-amber-50 text-amber-700 border-amber-200',
                                                        'Core Industry': 'bg-emerald-50 text-emerald-700 border-emerald-200',
                                                        'Marketing': 'bg-rose-50 text-rose-700 border-rose-200',
                                                        'Others': 'bg-slate-100 text-slate-700 border-slate-200',
                                                    };
                                                    const badgeClass = typeColors[res.cv_type] || typeColors['Others'];
                                                    const formattedDate = res.uploaded_at
                                                        ? new Date(res.uploaded_at).toLocaleDateString(undefined, {
                                                              year: 'numeric',
                                                              month: 'short',
                                                              day: 'numeric',
                                                          })
                                                        : 'Recent';
                                                    const formattedSize = res.file_size
                                                        ? `${Math.round(res.file_size / 1024)} KB`
                                                        : 'PDF';

                                                    return (
                                                        <div
                                                            key={res.id}
                                                            className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs hover:border-indigo-200 hover:shadow-sm transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
                                                        >
                                                            <div className="flex items-start gap-3 min-w-0">
                                                                <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold shrink-0 text-lg">
                                                                    📄
                                                                </div>
                                                                <div className="min-w-0">
                                                                    <div className="flex items-center gap-2 flex-wrap">
                                                                        <h4 className="font-bold text-slate-900 text-xs truncate">
                                                                            {res.cv_name}
                                                                        </h4>
                                                                        <span
                                                                            className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${badgeClass}`}
                                                                        >
                                                                            {res.cv_type}
                                                                        </span>
                                                                    </div>
                                                                    <p className="text-[11px] text-slate-500 truncate mt-0.5">
                                                                        {res.file_name} • {formattedSize} • Uploaded {formattedDate}
                                                                    </p>
                                                                </div>
                                                            </div>

                                                            <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                                                                <button
                                                                    type="button"
                                                                    onClick={() => viewResumeFile(res.id)}
                                                                    className="px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold text-[11px] border border-slate-200 transition-colors cursor-pointer"
                                                                >
                                                                    View
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleDeleteResume(res.id)}
                                                                    disabled={deletingResumeId === res.id}
                                                                    className="px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 font-semibold text-[11px] border border-red-200 transition-colors"
                                                                >
                                                                    {deletingResumeId === res.id ? 'Deleting...' : 'Delete'}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </form>
                            )}

                            {role === 'faculty' && (
                                <form onSubmit={handleSaveFaculty} className="space-y-4 text-xs">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Department</label>
                                            <input
                                                type="text"
                                                value={department}
                                                onChange={(e) => setDepartment(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Designation</label>
                                            <input
                                                type="text"
                                                value={designation}
                                                onChange={(e) => setDesignation(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Employee ID</label>
                                            <input
                                                type="text"
                                                value={employeeId}
                                                onChange={(e) => setEmployeeId(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Institution</label>
                                            <input
                                                type="text"
                                                value={institution}
                                                onChange={(e) => setInstitution(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                    </div>
                                    <div className="pt-2 flex justify-end">
                                        <button
                                            type="submit"
                                            disabled={saving}
                                            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs"
                                        >
                                            {saving ? 'Saving...' : 'Save Faculty Profile'}
                                        </button>
                                    </div>
                                </form>
                            )}

                            {role === 'tpo' && (
                                <form onSubmit={handleSaveTPO} className="space-y-4 text-xs">
                                    <div>
                                        <label className="block font-semibold text-slate-700 mb-1.5">Institution</label>
                                        <input
                                            type="text"
                                            value={institution}
                                            onChange={(e) => setInstitution(e.target.value)}
                                            className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Designation</label>
                                            <input
                                                type="text"
                                                value={designation}
                                                onChange={(e) => setDesignation(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                        <div>
                                            <label className="block font-semibold text-slate-700 mb-1.5">Contact Phone</label>
                                            <input
                                                type="text"
                                                value={phoneNumber}
                                                onChange={(e) => setPhoneNumber(e.target.value)}
                                                className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900"
                                            />
                                        </div>
                                    </div>
                                    <div className="pt-2 flex justify-end">
                                        <button
                                            type="submit"
                                            disabled={saving}
                                            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs"
                                        >
                                            {saving ? 'Saving...' : 'Save TPO Profile'}
                                        </button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>

                    {/* Right Panel: Role-Specific Summary */}
                    <div className="space-y-6">
                        {role === 'student' && (
                            <>
                                <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1">Placement Eligibility Card</h3>
                                    <p className="text-xs text-slate-500 mb-4">Values verified during corporate mock drive checks</p>

                                    <div className="space-y-3 text-xs">
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">CGPA</span>
                                            <span className="font-bold text-indigo-600">{cgpa} / 10.0</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">10th Standard</span>
                                            <span className="font-bold text-slate-900">{tenthMarks ? `${tenthMarks}%` : 'Not Set'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">12th Standard</span>
                                            <span className="font-bold text-slate-900">{twelfthMarks ? `${twelfthMarks}%` : 'Not Set'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Department</span>
                                            <span className="font-semibold text-slate-800">{department}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Graduation Year</span>
                                            <span className="font-semibold text-slate-800">{graduationYear}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Active Backlogs</span>
                                            <span className={`font-bold ${parseInt(backlogsCount, 10) === 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                                {backlogsCount}
                                            </span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Gender & Nationality</span>
                                            <span className="font-semibold text-slate-700">{gender || 'Male'} | {nationality || 'Indian'}</span>
                                        </div>
                                        {collegeEmailId && (
                                            <div className="flex justify-between py-2 border-b border-slate-100">
                                                <span className="text-slate-500">College Email</span>
                                                <span className="font-mono text-slate-700 text-[11px] truncate max-w-[140px]">{collegeEmailId}</span>
                                            </div>
                                        )}
                                        {mobileNo && (
                                            <div className="flex justify-between py-2 border-b border-slate-100">
                                                <span className="text-slate-500">Mobile</span>
                                                <span className="font-mono text-slate-700 text-[11px]">{mobileNo}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Assessment Rounds Status Card */}
                                <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1">Assessment Practice Progress</h3>
                                    <p className="text-xs text-slate-500 mb-4">Multi-round readiness status</p>

                                    <div className="space-y-2.5 text-xs">
                                        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                                            <span className="font-medium text-slate-700">Aptitude Round</span>
                                            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                                                Ready
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                                            <span className="font-medium text-slate-700">Coding Challenge</span>
                                            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                                                Ready
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200">
                                            <span className="font-medium text-slate-700">AI Mock Interview</span>
                                            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700">
                                                Ready
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </>
                        )}

                        {role === 'faculty' && (
                            <>
                                <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-lg">
                                            🎓
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-bold text-slate-900">Faculty Credentials</h3>
                                            <p className="text-[11px] text-slate-500">Academic department record</p>
                                        </div>
                                    </div>

                                    <div className="space-y-3 text-xs mt-4">
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Department</span>
                                            <span className="font-bold text-indigo-600">{department || 'Computer Science'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Designation</span>
                                            <span className="font-semibold text-slate-800">{designation || 'Faculty Member'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Employee ID</span>
                                            <span className="font-mono text-slate-700 font-semibold">{employeeId || 'FAC-2026'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Institution</span>
                                            <span className="font-semibold text-slate-800">{institution || 'Engineering College'}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-gradient-to-br from-indigo-50/70 to-slate-50 border border-indigo-100 rounded-3xl p-6 shadow-sm">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1">Supervised Student Cohort</h3>
                                    <p className="text-xs text-slate-500 mb-4">Departmental assessment monitoring</p>

                                    <div className="space-y-3 text-xs">
                                        <div className="p-3 bg-white border border-indigo-100 rounded-xl">
                                            <div className="text-[11px] text-slate-500 font-medium">Department Focus</div>
                                            <div className="text-sm font-bold text-slate-900">{department}</div>
                                        </div>
                                        <button
                                            onClick={() => navigate('/faculty/dashboard')}
                                            className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl transition-all shadow-sm"
                                        >
                                            Open Faculty Dashboard →
                                        </button>
                                    </div>
                                </div>
                            </>
                        )}

                        {role === 'tpo' && (
                            <>
                                <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm">
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className="w-9 h-9 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center font-bold text-lg">
                                            🏢
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-bold text-slate-900">Placement Cell Desk</h3>
                                            <p className="text-[11px] text-slate-500">Institutional placement office</p>
                                        </div>
                                    </div>

                                    <div className="space-y-3 text-xs mt-4">
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Designation</span>
                                            <span className="font-bold text-sky-600">{designation || 'Placement Officer'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Contact Phone</span>
                                            <span className="font-semibold text-slate-800">{phoneNumber || '+91-9876543210'}</span>
                                        </div>
                                        <div className="flex justify-between py-2 border-b border-slate-100">
                                            <span className="text-slate-500">Institution</span>
                                            <span className="font-semibold text-slate-800">{institution || 'Engineering College'}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-gradient-to-br from-sky-50/70 to-slate-50 border border-sky-100 rounded-3xl p-6 shadow-sm">
                                    <h3 className="text-sm font-bold text-slate-900 mb-1">Corporate Placement Drives</h3>
                                    <p className="text-xs text-slate-500 mb-4">Eligibility rules & drive pipeline</p>

                                    <div className="space-y-3 text-xs">
                                        <div className="p-3 bg-white border border-sky-100 rounded-xl">
                                            <div className="text-[11px] text-slate-500 font-medium">Recruitment Status</div>
                                            <div className="text-sm font-bold text-emerald-600">Active Recruitment Drives</div>
                                        </div>
                                        <button
                                            onClick={() => navigate('/tpo/dashboard')}
                                            className="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs rounded-xl transition-all shadow-sm"
                                        >
                                            Open TPO Portal →
                                        </button>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Add CV Modal matching reference */}
                {isResumeModalOpen && (
                    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
                        <div className="bg-white rounded-2xl overflow-hidden shadow-2xl max-w-lg w-full border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
                            {/* Modal Header Banner */}
                            <div className="bg-gradient-to-r from-[#123962] to-[#1e4e7e] px-6 py-4 flex items-center justify-between text-white">
                                <h3 className="text-lg font-bold tracking-tight">Add CV</h3>
                                <button
                                    type="button"
                                    onClick={() => setIsResumeModalOpen(false)}
                                    className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center text-sm font-bold transition-colors"
                                >
                                    ✕
                                </button>
                            </div>

                            {/* Modal Form */}
                            <form onSubmit={handleUploadResume} className="p-6 space-y-5">
                                {/* CV Name */}
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                                        CV Name <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        value={cvName}
                                        onChange={(e) => setCvName(e.target.value)}
                                        placeholder="e.g. Software Developer"
                                        className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 font-medium"
                                    />
                                </div>

                                {/* CV Type Dropdown */}
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                                        CV Type <span className="text-red-500">*</span>
                                    </label>
                                    <select
                                        value={cvType}
                                        onChange={(e) => setCvType(e.target.value)}
                                        className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-slate-900 text-xs focus:outline-none focus:ring-2 focus:ring-sky-500 font-medium"
                                    >
                                        <option value="Software Developer">Software Developer</option>
                                        <option value="Data Science">Data Science</option>
                                        <option value="Software Testing / QA">Software Testing / QA</option>
                                        <option value="Core Industry">Core Industry</option>
                                        <option value="Marketing">Marketing</option>
                                        <option value="Others">Others</option>
                                    </select>
                                </div>

                                {/* CV File Upload */}
                                <div>
                                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                                        CV File <span className="text-red-500">*</span>
                                    </label>
                                    <label className="border-2 border-dashed border-slate-300 hover:border-sky-500 rounded-xl p-5 flex items-center justify-center gap-3 bg-slate-50/70 hover:bg-slate-50 cursor-pointer transition-colors">
                                        <span className="text-3xl">📄</span>
                                        <div className="text-left">
                                            <div className="text-xs font-bold text-slate-800">
                                                {cvFile ? cvFile.name : 'Select CV file'}
                                            </div>
                                            <div className="text-[10px] text-slate-400">
                                                {cvFile ? `${Math.round(cvFile.size / 1024)} KB` : 'Click to browse file'}
                                            </div>
                                        </div>
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            className="hidden"
                                            onChange={(e) => setCvFile(e.target.files?.[0] || null)}
                                        />
                                    </label>
                                    <p className="text-[11px] text-slate-500 mt-1.5">
                                        File Size Should be less than 250 kb, JPEG, JPG & PDF
                                    </p>
                                </div>

                                {/* Modal Actions */}
                                <div className="pt-2 flex justify-end gap-3 border-t border-slate-100">
                                    <button
                                        type="button"
                                        onClick={() => setIsResumeModalOpen(false)}
                                        className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={uploadingResume}
                                        className="px-6 py-2 rounded-xl bg-gradient-to-r from-[#123962] to-[#1e4e7e] hover:opacity-95 text-white text-xs font-bold shadow-sm transition-all flex items-center gap-2"
                                    >
                                        {uploadingResume ? 'Uploading...' : 'Save CV'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
