import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    getPortfolio,
    updatePortfolio,
    addProject,
    deleteProject,
    addCertification,
    deleteCertification,
    addExperience,
    deleteExperience,
    addAchievement,
    deleteAchievement,
    addResearch,
    deleteResearch,
} from '../../services/portfolioService';
import { viewResumeFile } from '../../services/resumeService';
import {
    EditProfileModal,
    AddProjectModal,
    AddCertificationModal,
    AddExperienceModal,
    AddAchievementModal,
    AddResearchModal,
} from './PortfolioModals';

export default function PortfolioView({ compact = false }) {
    const navigate = useNavigate();

    const [portfolio, setPortfolio] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'projects' | 'certifications' | 'experience' | 'research' | 'highlights' | 'journey'

    // Modal toggles
    const [showEditProfile, setShowEditProfile] = useState(false);
    const [showAddProject, setShowAddProject] = useState(false);
    const [showAddCert, setShowAddCert] = useState(false);
    const [showAddExp, setShowAddExp] = useState(false);
    const [showAddAch, setShowAddAch] = useState(false);
    const [showAddResearch, setShowAddResearch] = useState(false);

    // Filter for skills
    const [selectedSkillCategory, setSelectedSkillCategory] = useState('All');

    const fetchPortfolioData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getPortfolio();
            setPortfolio(data);
        } catch (err) {
            console.error('Failed to load portfolio:', err);
            setError(err.response?.data?.detail || 'Unable to load your portfolio from the server. Please try again.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPortfolioData();
    }, [fetchPortfolioData]);

    if (loading) {
        return (
            <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-xs animate-pulse space-y-6">
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-slate-200"></div>
                    <div className="space-y-2 flex-1">
                        <div className="h-5 bg-slate-200 rounded w-1/3"></div>
                        <div className="h-3 bg-slate-100 rounded w-1/4"></div>
                    </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-20 bg-slate-100 rounded-2xl"></div>
                    ))}
                </div>
                <div className="h-40 bg-slate-50 rounded-2xl"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-white border border-rose-200 rounded-3xl p-8 text-center shadow-xs">
                <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3 text-xl font-bold">
                    ⚠️
                </div>
                <h3 className="text-base font-bold text-slate-900 mb-1">Unable to Load Portfolio</h3>
                <p className="text-xs text-slate-500 mb-4 max-w-md mx-auto">{error}</p>
                <button
                    onClick={fetchPortfolioData}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all"
                >
                    Retry Loading
                </button>
            </div>
        );
    }

    const {
        profile = {},
        education = [],
        about = '',
        skills = [],
        projects = [],
        certifications = [],
        experience = [],
        achievements = [],
        research = [],
        patents = [],
        resumes = [],
        assessment_highlights = [],
        badges = [],
        learning_journey = [],
        external_profiles = {},
        completeness = { score: 0, completed_sections: [], missing_sections: [] },
        improvement_suggestions = [],
    } = portfolio || {};

    const initials = (profile.name || 'Student')
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();

    // Handlers
    const handleUpdateMetadata = async (payload) => {
        const updated = await updatePortfolio(payload);
        setPortfolio(updated);
    };

    const handleAddProject = async (payload) => {
        const updated = await addProject(payload);
        setPortfolio(updated);
    };

    const handleDeleteProject = async (id) => {
        if (window.confirm('Are you sure you want to remove this project?')) {
            const updated = await deleteProject(id);
            setPortfolio(updated);
        }
    };

    const handleAddCert = async (payload) => {
        const updated = await addCertification(payload);
        setPortfolio(updated);
    };

    const handleDeleteCert = async (id) => {
        if (window.confirm('Are you sure you want to remove this certification?')) {
            const updated = await deleteCertification(id);
            setPortfolio(updated);
        }
    };

    const handleAddExperience = async (payload) => {
        const updated = await addExperience(payload);
        setPortfolio(updated);
    };

    const handleDeleteExperience = async (id) => {
        if (window.confirm('Are you sure you want to remove this experience?')) {
            const updated = await deleteExperience(id);
            setPortfolio(updated);
        }
    };

    const handleAddAchievement = async (payload) => {
        const updated = await addAchievement(payload);
        setPortfolio(updated);
    };

    const handleDeleteAchievement = async (id) => {
        if (window.confirm('Are you sure you want to remove this achievement?')) {
            const updated = await deleteAchievement(id);
            setPortfolio(updated);
        }
    };

    const handleAddResearch = async (payload) => {
        const updated = await addResearch(payload);
        setPortfolio(updated);
    };

    const handleDeleteResearch = async (id) => {
        if (window.confirm('Are you sure you want to remove this publication?')) {
            const updated = await deleteResearch(id);
            setPortfolio(updated);
        }
    };

    // Filtered skills
    const skillCategories = ['All', 'Programming', 'Development', 'Core CS', 'AI/ML', 'Tools'];
    const filteredSkills =
        selectedSkillCategory === 'All'
            ? skills
            : skills.filter((s) => s.category?.toLowerCase() === selectedSkillCategory.toLowerCase());

    return (
        <div className="space-y-6 font-['Inter'] antialiased">
            {/* ── 1. PORTFOLIO HEADER CARD ── */}
            <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-xs relative overflow-hidden">
                <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-bl from-indigo-50/60 to-transparent rounded-bl-full pointer-events-none -z-0"></div>

                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div className="flex items-start gap-4 sm:gap-6">
                        <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center text-white font-black text-2xl sm:text-3xl shadow-md shrink-0">
                            {initials}
                        </div>
                        <div>
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                                <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                                    {profile.name}
                                </h1>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Placement Candidate
                                </span>
                            </div>
                            <p className="text-xs sm:text-sm font-semibold text-indigo-600 mb-1">
                                {profile.target_role || 'Software Engineer'} • {profile.department}
                            </p>
                            <p className="text-xs text-slate-500 font-medium">
                                Class of {profile.graduation_year || 2026} • {profile.institution}
                            </p>

                            {/* External Links Bar */}
                            <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
                                {external_profiles.github && (
                                    <a
                                        href={external_profiles.github}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors"
                                    >
                                        <span>💻</span> GitHub ↗
                                    </a>
                                )}
                                {external_profiles.linkedin && (
                                    <a
                                        href={external_profiles.linkedin}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 font-medium transition-colors border border-sky-100"
                                    >
                                        <span>🔗</span> LinkedIn ↗
                                    </a>
                                )}
                                {external_profiles.leetcode && (
                                    <a
                                        href={external_profiles.leetcode}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-700 font-medium transition-colors border border-amber-100"
                                    >
                                        <span>⚡</span> LeetCode ↗
                                    </a>
                                )}
                                {external_profiles.website && (
                                    <a
                                        href={external_profiles.website}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors"
                                    >
                                        <span>🌐</span> Portfolio ↗
                                    </a>
                                )}
                                <button
                                    onClick={() => setShowEditProfile(true)}
                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 text-indigo-600 font-semibold transition-colors"
                                >
                                    ✎ Edit Links & Summary
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Completeness Mini Badge & Quick Actions */}
                    <div className="flex flex-row md:flex-col items-end justify-between md:justify-center gap-3 pt-4 md:pt-0 border-t md:border-t-0 border-slate-100">
                        <div className="text-right">
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                                Portfolio Completeness
                            </span>
                            <div className="flex items-center justify-end gap-2 mt-0.5">
                                <span className="text-xl font-black text-slate-900">{completeness.score}%</span>
                                <div className="w-20 h-2 rounded-full bg-slate-100 overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-500 ${
                                            completeness.score >= 80
                                                ? 'bg-emerald-500'
                                                : completeness.score >= 50
                                                ? 'bg-indigo-600'
                                                : 'bg-amber-500'
                                        }`}
                                        style={{ width: `${completeness.score}%` }}
                                    ></div>
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => navigate('/analytics')}
                                className="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all"
                            >
                                View Analytics ↗
                            </button>
                            <button
                                onClick={() => navigate('/profile')}
                                className="px-3.5 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-xl border border-indigo-200 transition-all"
                            >
                                Academic Profile ↗
                            </button>
                        </div>
                    </div>
                </div>

                {/* Scorecard Metric Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 mt-6 pt-6 border-t border-slate-100">
                    <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                            College CGPA
                        </span>
                        <div className="flex items-baseline gap-1">
                            <span className="text-xl font-black text-slate-900">
                                {profile.cgpa !== undefined && profile.cgpa !== null
                                    ? Number(profile.cgpa).toFixed(2)
                                    : '0.00'}
                            </span>
                            <span className="text-[10px] text-slate-500">/ 10.0</span>
                        </div>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                            Active Backlogs
                        </span>
                        <div className="flex items-baseline gap-1">
                            <span
                                className={`text-xl font-black ${
                                    (profile.backlogs_count || 0) === 0 ? 'text-emerald-600' : 'text-amber-600'
                                }`}
                            >
                                {profile.backlogs_count || 0}
                            </span>
                            <span className="text-[10px] text-slate-500">
                                {(profile.backlogs_count || 0) === 0 ? 'Cleared' : 'Active'}
                            </span>
                        </div>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                            Secondary (10th)
                        </span>
                        <span className="text-xl font-black text-slate-900">
                            {profile.tenth_marks ? `${profile.tenth_marks}%` : '—'}
                        </span>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-slate-50/80 border border-slate-200/70">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">
                            Hr. Secondary (12th)
                        </span>
                        <span className="text-xl font-black text-slate-900">
                            {profile.twelfth_marks ? `${profile.twelfth_marks}%` : '—'}
                        </span>
                    </div>
                </div>
            </div>

            {/* ── 2. CORE EVIDENCE DISTINCTION EXPLAINER ── */}
            <div className="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 text-indigo-900 font-bold">
                    <span>🛡️</span>
                    <span>EDI5 Evidence-Aware Verification Architecture:</span>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-slate-600">
                    <span className="inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                        <strong className="text-slate-800">Student Claim:</strong> Self-declared information
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                        <strong className="text-slate-800">Assessment Evidence:</strong> Backed by completed tests
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                        <strong className="text-slate-800">Verified Evidence:</strong> Validated credentials
                    </span>
                </div>
            </div>

            {/* ── 3. IMPROVEMENT RECOMMENDATIONS STRIP (IF ANY) ── */}
            {improvement_suggestions.length > 0 && (
                <div className="p-4 rounded-2xl bg-amber-50/80 border border-amber-200/70 flex items-start gap-3 text-xs text-amber-900">
                    <span className="text-base mt-0.5">💡</span>
                    <div className="space-y-1 flex-1">
                        <span className="font-bold block">Actionable Portfolio Recommendations:</span>
                        <ul className="list-disc pl-4 space-y-0.5 text-amber-800 text-[11px]">
                            {improvement_suggestions.map((sug, i) => (
                                <li key={i}>{sug}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}

            {/* ── 4. TABS NAVIGATION ── */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-slate-200 scrollbar-none text-xs">
                {[
                    { id: 'overview', label: 'Overview & Skills' },
                    { id: 'projects', label: `Projects (${projects.length})` },
                    { id: 'certifications', label: `Certifications (${certifications.length})` },
                    { id: 'experience', label: `Experience (${experience.length})` },
                    { id: 'research', label: `Research & Awards (${research.length + achievements.length})` },
                    { id: 'highlights', label: 'Assessment Highlights' },
                    { id: 'journey', label: 'Learning Journey' },
                    { id: 'resumes', label: `Resumes (${resumes.length})` },
                ].map((t) => (
                    <button
                        key={t.id}
                        onClick={() => setActiveTab(t.id)}
                        className={`px-4 py-2.5 rounded-xl font-bold whitespace-nowrap transition-all cursor-pointer ${
                            activeTab === t.id
                                ? 'bg-indigo-600 text-white shadow-xs'
                                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                        }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* ── TAB 1: OVERVIEW & SKILLS ── */}
            {activeTab === 'overview' && (
                <div className="space-y-6">
                    {/* About Me Section */}
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Professional Summary / About Me
                            </h3>
                            <button
                                onClick={() => setShowEditProfile(true)}
                                className="text-xs text-indigo-600 font-semibold hover:underline"
                            >
                                ✎ Edit
                            </button>
                        </div>
                        <p className="text-xs sm:text-sm text-slate-700 leading-relaxed bg-slate-50/70 p-4 rounded-2xl border border-slate-200/60">
                            {about || 'No professional summary provided yet. Click edit to add your career focus.'}
                        </p>
                    </div>

                    {/* Education Card */}
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Education Background
                        </h3>
                        <div className="space-y-3">
                            {education.map((edu, idx) => (
                                <div
                                    key={idx}
                                    className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                                >
                                    <div>
                                        <h4 className="text-sm font-black text-slate-900">{edu.institution}</h4>
                                        <p className="text-xs text-indigo-600 font-semibold mt-0.5">
                                            {edu.degree} — {edu.department}
                                        </p>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            Graduation Year: {edu.graduation_year || 2026}
                                        </p>
                                    </div>
                                    <div className="text-right sm:border-l sm:border-slate-200 sm:pl-4">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                                            CGPA / Percentage
                                        </span>
                                        <span className="text-lg font-black text-slate-900">
                                            {edu.cgpa ? Number(edu.cgpa).toFixed(2) : '—'} / 10.0
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Categorized Skills with Evidence Status */}
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    Technical Competencies & Evidence ({skills.length})
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Distinguishing student claims from assessment evidence and validated credentials
                                </p>
                            </div>

                            {/* Category Filter Pills */}
                            <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none">
                                {skillCategories.map((cat) => (
                                    <button
                                        key={cat}
                                        onClick={() => setSelectedSkillCategory(cat)}
                                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                                            selectedSkillCategory === cat
                                                ? 'bg-slate-900 text-white'
                                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                        }`}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {filteredSkills.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                                {filteredSkills.map((sk, idx) => (
                                    <div
                                        key={idx}
                                        className="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-2xs hover:border-indigo-300 transition-all"
                                    >
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs font-bold text-slate-900">{sk.name}</h4>
                                            <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-md">
                                                {sk.category}
                                            </span>
                                        </div>

                                        {/* Evidence Checklist Grid */}
                                        <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-slate-100 text-[10px]">
                                            <div className="flex items-center gap-1.5">
                                                <span
                                                    className={
                                                        sk.practice_evidence ? 'text-emerald-600 font-bold' : 'text-slate-400'
                                                    }
                                                >
                                                    {sk.practice_evidence ? '✓' : '—'}
                                                </span>
                                                <span className="text-slate-600">Practice</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <span
                                                    className={
                                                        sk.project_evidence ? 'text-emerald-600 font-bold' : 'text-slate-400'
                                                    }
                                                >
                                                    {sk.project_evidence ? '✓' : '—'}
                                                </span>
                                                <span className="text-slate-600">Project</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <span
                                                    className={
                                                        sk.assessment_evidence
                                                            ? 'text-indigo-600 font-bold'
                                                            : 'text-slate-400'
                                                    }
                                                >
                                                    {sk.assessment_evidence ? '✓' : '—'}
                                                </span>
                                                <span className="text-slate-600">Assessment</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <span
                                                    className={
                                                        sk.verified ? 'text-emerald-600 font-bold' : 'text-slate-400'
                                                    }
                                                >
                                                    {sk.verified ? '✓' : 'Pending'}
                                                </span>
                                                <span className="text-slate-600">Verified</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-500 italic py-4">No skills found in this category.</p>
                        )}
                    </div>
                </div>
            )}

            {/* ── TAB 2: PROJECTS ── */}
            {activeTab === 'projects' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Technical Engineering Projects
                            </h3>
                            <p className="text-xs text-slate-500">Demonstrating architecture, implementation, and code repositories</p>
                        </div>
                        <button
                            onClick={() => setShowAddProject(true)}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                        >
                            + Add Project
                        </button>
                    </div>

                    {projects.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {projects.map((proj) => (
                                <div
                                    key={proj.id}
                                    className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs hover:shadow-sm transition-all flex flex-col justify-between"
                                >
                                    <div>
                                        <div className="flex items-start justify-between gap-2 mb-2">
                                            <h4 className="text-sm font-black text-slate-900 leading-snug">
                                                {proj.title}
                                            </h4>
                                            <span
                                                className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${
                                                    proj.evidence_status === 'Verified'
                                                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                        : proj.evidence_status === 'Under Review'
                                                        ? 'bg-sky-50 text-sky-700 border border-sky-200'
                                                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                                                }`}
                                            >
                                                {proj.evidence_status || 'Submitted'}
                                            </span>
                                        </div>

                                        {proj.problem_statement && (
                                            <div className="mb-2">
                                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                                                    Problem Statement
                                                </span>
                                                <p className="text-xs text-slate-600 line-clamp-2 mt-0.5">
                                                    {proj.problem_statement}
                                                </p>
                                            </div>
                                        )}

                                        {proj.solution && (
                                            <div className="mb-3">
                                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                                                    Solution & Architecture
                                                </span>
                                                <p className="text-xs text-slate-600 line-clamp-2 mt-0.5">
                                                    {proj.solution}
                                                </p>
                                            </div>
                                        )}

                                        {/* Tech Stack */}
                                        <div className="flex flex-wrap gap-1.5 mb-4">
                                            {(proj.technologies || []).map((t, idx) => (
                                                <span
                                                    key={idx}
                                                    className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700"
                                                >
                                                    {t}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Footer Links & Actions */}
                                    <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                                        <div className="flex items-center gap-3">
                                            {proj.github_url && (
                                                <a
                                                    href={proj.github_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-indigo-600 font-bold hover:underline"
                                                >
                                                    GitHub ↗
                                                </a>
                                            )}
                                            {proj.demo_url && (
                                                <a
                                                    href={proj.demo_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-indigo-600 font-bold hover:underline"
                                                >
                                                    Live Demo ↗
                                                </a>
                                            )}
                                            {proj.docs_url && (
                                                <a
                                                    href={proj.docs_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-slate-600 hover:underline"
                                                >
                                                    Docs ↗
                                                </a>
                                            )}
                                        </div>
                                        <button
                                            onClick={() => handleDeleteProject(proj.id)}
                                            className="text-rose-500 hover:text-rose-700 text-[11px] font-semibold cursor-pointer"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-8 rounded-3xl bg-white border border-dashed border-slate-300 text-center">
                            <p className="text-xs text-slate-600 mb-3">No projects added yet.</p>
                            <button
                                onClick={() => setShowAddProject(true)}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                + Add First Project
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* ── TAB 3: CERTIFICATIONS ── */}
            {activeTab === 'certifications' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Industry Certifications
                            </h3>
                            <p className="text-xs text-slate-500">Verified credentials from accredited organizations</p>
                        </div>
                        <button
                            onClick={() => setShowAddCert(true)}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                        >
                            + Add Certification
                        </button>
                    </div>

                    {certifications.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {certifications.map((cert) => (
                                <div
                                    key={cert.id}
                                    className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between"
                                >
                                    <div>
                                        <div className="flex items-start justify-between gap-2 mb-2">
                                            <h4 className="text-sm font-black text-slate-900 leading-snug">
                                                {cert.name}
                                            </h4>
                                            <span
                                                className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${
                                                    cert.verification_status === 'Verified'
                                                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                                                }`}
                                            >
                                                {cert.verification_status || 'Submitted'}
                                            </span>
                                        </div>
                                        <p className="text-xs font-bold text-indigo-600 mb-1">{cert.issuer}</p>
                                        {cert.issue_date && (
                                            <p className="text-[11px] text-slate-500 mb-2">Issued: {cert.issue_date}</p>
                                        )}
                                        {cert.credential_id && (
                                            <p className="text-[11px] text-slate-600 font-mono mb-2">
                                                ID: {cert.credential_id}
                                            </p>
                                        )}

                                        <div className="flex flex-wrap gap-1 mb-3">
                                            {(cert.skills || []).map((s, idx) => (
                                                <span
                                                    key={idx}
                                                    className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
                                                >
                                                    {s}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                                        {cert.credential_url ? (
                                            <a
                                                href={cert.credential_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-indigo-600 font-bold hover:underline"
                                            >
                                                Verify Credential ↗
                                            </a>
                                        ) : (
                                            <span className="text-[11px] text-slate-400">No URL provided</span>
                                        )}
                                        <button
                                            onClick={() => handleDeleteCert(cert.id)}
                                            className="text-rose-500 hover:text-rose-700 text-[11px] font-semibold cursor-pointer"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-8 rounded-3xl bg-white border border-dashed border-slate-300 text-center">
                            <p className="text-xs text-slate-600 mb-3">No certifications added yet.</p>
                            <button
                                onClick={() => setShowAddCert(true)}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                + Add First Certificate
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* ── TAB 4: EXPERIENCE ── */}
            {activeTab === 'experience' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Professional Experience & Internships
                            </h3>
                            <p className="text-xs text-slate-500">Practical organizational exposure and responsibilities</p>
                        </div>
                        <button
                            onClick={() => setShowAddExp(true)}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                        >
                            + Add Experience
                        </button>
                    </div>

                    {experience.length > 0 ? (
                        <div className="space-y-3">
                            {experience.map((exp) => (
                                <div
                                    key={exp.id}
                                    className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs flex flex-col sm:flex-row justify-between gap-4"
                                >
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h4 className="text-sm font-black text-slate-900">{exp.role}</h4>
                                            <span className="text-[10px] font-semibold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-md">
                                                {exp.type}
                                            </span>
                                        </div>
                                        <p className="text-xs font-bold text-slate-700 mb-1">{exp.organization}</p>
                                        <p className="text-[11px] text-slate-500 mb-2">
                                            {exp.start_date || 'N/A'} — {exp.end_date || 'Present'}
                                        </p>
                                        {exp.description && (
                                            <p className="text-xs text-slate-600 mb-3">{exp.description}</p>
                                        )}

                                        <div className="flex flex-wrap gap-1">
                                            {(exp.skills || []).map((s, idx) => (
                                                <span
                                                    key={idx}
                                                    className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 text-slate-700"
                                                >
                                                    {s}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="flex sm:flex-col justify-end items-end">
                                        <button
                                            onClick={() => handleDeleteExperience(exp.id)}
                                            className="text-rose-500 hover:text-rose-700 text-[11px] font-semibold cursor-pointer"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-8 rounded-3xl bg-white border border-dashed border-slate-300 text-center">
                            <p className="text-xs text-slate-600 mb-3">No professional experience added yet.</p>
                            <button
                                onClick={() => setShowAddExp(true)}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                + Add First Experience
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* ── TAB 5: RESEARCH & AWARDS ── */}
            {activeTab === 'research' && (
                <div className="space-y-6">
                    {/* Research Papers Section */}
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    Research Publications
                                </h3>
                                <p className="text-xs text-slate-500">Peer-reviewed conference or journal contributions</p>
                            </div>
                            <button
                                onClick={() => setShowAddResearch(true)}
                                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                + Add Paper
                            </button>
                        </div>

                        {research.length > 0 ? (
                            <div className="space-y-3">
                                {research.map((paper) => (
                                    <div
                                        key={paper.id}
                                        className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs flex justify-between items-start gap-4"
                                    >
                                        <div>
                                            <div className="flex items-center gap-2 mb-1">
                                                <h4 className="text-xs sm:text-sm font-black text-slate-900">
                                                    {paper.title}
                                                </h4>
                                                <span className="text-[10px] font-bold bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">
                                                    {paper.status || 'Published'}
                                                </span>
                                            </div>
                                            <p className="text-xs text-slate-600 mb-1">
                                                <strong>Authors:</strong> {paper.authors} • <strong>Venue:</strong> {paper.journal}
                                            </p>
                                            {paper.doi && (
                                                <p className="text-[11px] font-mono text-slate-500 mb-2">DOI: {paper.doi}</p>
                                            )}
                                            {paper.paper_url && (
                                                <a
                                                    href={paper.paper_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-xs text-indigo-600 font-bold hover:underline"
                                                >
                                                    Read Publication ↗
                                                </a>
                                            )}
                                        </div>
                                        <button
                                            onClick={() => handleDeleteResearch(paper.id)}
                                            className="text-rose-500 hover:text-rose-700 text-[11px] font-semibold cursor-pointer"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-500 italic p-4 bg-slate-50 rounded-2xl border border-slate-200">
                                No research publications added.
                            </p>
                        )}
                    </div>

                    {/* Hackathons & Achievements Section */}
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    Hackathons & Competitive Awards
                                </h3>
                                <p className="text-xs text-slate-500">Academic and coding contest honors</p>
                            </div>
                            <button
                                onClick={() => setShowAddAch(true)}
                                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                + Add Achievement
                            </button>
                        </div>

                        {achievements.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                {achievements.map((ach) => (
                                    <div
                                        key={ach.id}
                                        className="p-4 rounded-2xl bg-white border border-slate-200 shadow-xs flex justify-between items-start gap-3"
                                    >
                                        <div>
                                            <div className="flex items-center gap-1.5 mb-1">
                                                <span className="text-base">🏆</span>
                                                <h4 className="text-xs sm:text-sm font-bold text-slate-900">
                                                    {ach.title}
                                                </h4>
                                            </div>
                                            <p className="text-xs font-semibold text-indigo-600">
                                                {ach.position || 'Honoree'} • {ach.organization}
                                            </p>
                                            <p className="text-[11px] text-slate-500 mt-0.5">{ach.date}</p>
                                            {ach.description && (
                                                <p className="text-xs text-slate-600 mt-1">{ach.description}</p>
                                            )}
                                        </div>
                                        <button
                                            onClick={() => handleDeleteAchievement(ach.id)}
                                            className="text-rose-500 hover:text-rose-700 text-[11px] font-semibold cursor-pointer"
                                        >
                                            Remove
                                        </button>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-500 italic p-4 bg-slate-50 rounded-2xl border border-slate-200">
                                No competition achievements added yet.
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* ── TAB 6: ASSESSMENT HIGHLIGHTS & BADGES ── */}
            {activeTab === 'highlights' && (
                <div className="space-y-6">
                    {/* EDI5 Assessment Highlights */}
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    EDI5 Assessment Highlights
                                </h3>
                                <p className="text-xs text-slate-500">Real performance generated across EDI5 test engines</p>
                            </div>
                            <span className="text-[10px] font-bold bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full border border-indigo-200">
                                Assessment Evidence Backed
                            </span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3.5">
                            {assessment_highlights.map((h, idx) => (
                                <div
                                    key={idx}
                                    className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/70 flex flex-col justify-between"
                                >
                                    <div>
                                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                                            {h.label}
                                        </span>
                                        <div className="flex items-baseline gap-1 my-1">
                                            <span className="text-2xl font-black text-slate-900">
                                                {h.best_score !== null && h.best_score !== undefined
                                                    ? `${h.best_score}%`
                                                    : h.problems_solved !== undefined && h.problems_solved > 0
                                                    ? `${h.problems_solved} Solved`
                                                    : 'Not Taken'}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-500">
                                        <span>Attempts: {h.attempts_count}</span>
                                        <span className="font-semibold text-indigo-600">⚡ Evidence</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Rule-based Badges */}
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <div className="mb-4">
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Institutional Competency Badges
                            </h3>
                            <p className="text-xs text-slate-500">Transparent criteria derived from system activity</p>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5">
                            {badges.map((b) => (
                                <div
                                    key={b.id}
                                    className={`p-4 rounded-2xl border transition-all flex items-start gap-3 ${
                                        b.earned
                                            ? 'bg-emerald-50/50 border-emerald-200 shadow-2xs'
                                            : 'bg-slate-50/50 border-slate-200 opacity-60'
                                    }`}
                                >
                                    <span className="text-2xl">{b.icon}</span>
                                    <div>
                                        <div className="flex items-center gap-1.5 mb-1">
                                            <h4 className="text-xs font-bold text-slate-900">{b.name}</h4>
                                            {b.earned ? (
                                                <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded-sm">
                                                    Earned
                                                </span>
                                            ) : (
                                                <span className="text-[10px] font-semibold text-slate-400">Locked</span>
                                            )}
                                        </div>
                                        <p className="text-[11px] text-slate-500">{b.criteria}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* ── TAB 7: LEARNING JOURNEY ── */}
            {activeTab === 'journey' && (
                <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-xs">
                    <div className="mb-6">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                            Learning Journey & Milestones
                        </h3>
                        <p className="text-xs text-slate-500">Chronological timeline of assessments, credentials, and projects</p>
                    </div>

                    {learning_journey.length > 0 ? (
                        <div className="relative pl-6 border-l-2 border-indigo-200 space-y-6">
                            {learning_journey.map((item, idx) => (
                                <div key={idx} className="relative group">
                                    <div className="absolute -left-[31px] top-0.5 w-4 h-4 rounded-full bg-white border-2 border-indigo-600 group-hover:scale-125 transition-transform"></div>
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600 block">
                                        {item.date}
                                    </span>
                                    <p className="text-xs sm:text-sm font-bold text-slate-900 mt-0.5">{item.event}</p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-slate-500 italic py-4">No milestone activity recorded yet.</p>
                    )}
                </div>
            )}

            {/* ── TAB 8: RESUMES ── */}
            {activeTab === 'resumes' && (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                Uploaded Resumes / CVs ({resumes.length})
                            </h3>
                            <p className="text-xs text-slate-500">Direct integration with stored resume documents</p>
                        </div>
                        <button
                            onClick={() => navigate('/profile')}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                        >
                            + Upload / Manage CVs
                        </button>
                    </div>

                    {resumes.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                            {resumes.map((cv) => (
                                <div
                                    key={cv.id}
                                    className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between"
                                >
                                    <div>
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-xl">📄</span>
                                            <div>
                                                <h4 className="text-xs font-bold text-slate-900 truncate max-w-[170px]">
                                                    {cv.cv_name}
                                                </h4>
                                                <span className="text-[10px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">
                                                    {cv.cv_type}
                                                </span>
                                            </div>
                                        </div>
                                        <p className="text-[11px] text-slate-500 mb-3">
                                            Uploaded: {cv.uploaded_at ? new Date(cv.uploaded_at).toLocaleDateString() : 'Recent'}
                                        </p>
                                    </div>

                                    <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                                        <button
                                            type="button"
                                            onClick={() => viewResumeFile(cv.id)}
                                            className="text-indigo-600 font-bold hover:underline cursor-pointer"
                                        >
                                            View PDF ↗
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => viewResumeFile(cv.id)}
                                            className="text-slate-600 font-semibold hover:text-slate-900 cursor-pointer"
                                        >
                                            Download
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-8 rounded-3xl bg-white border border-dashed border-slate-300 text-center">
                            <p className="text-xs text-slate-600 mb-3">No resumes uploaded yet.</p>
                            <button
                                onClick={() => navigate('/profile')}
                                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all cursor-pointer"
                            >
                                Upload First CV in Profile
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* ── MODALS ── */}
            <EditProfileModal
                isOpen={showEditProfile}
                onClose={() => setShowEditProfile(false)}
                initialData={{ about, external_profiles }}
                onSave={handleUpdateMetadata}
            />

            <AddProjectModal
                isOpen={showAddProject}
                onClose={() => setShowAddProject(false)}
                onSave={handleAddProject}
            />

            <AddCertificationModal
                isOpen={showAddCert}
                onClose={() => setShowAddCert(false)}
                onSave={handleAddCert}
            />

            <AddExperienceModal
                isOpen={showAddExp}
                onClose={() => setShowAddExp(false)}
                onSave={handleAddExperience}
            />

            <AddAchievementModal
                isOpen={showAddAch}
                onClose={() => setShowAddAch(false)}
                onSave={handleAddAchievement}
            />

            <AddResearchModal
                isOpen={showAddResearch}
                onClose={() => setShowAddResearch(false)}
                onSave={handleAddResearch}
            />
        </div>
    );
}
