import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getPublicPortfolio } from '../services/portfolioService';

export default function PublicPortfolio() {
    const { shareToken } = useParams();
    const [portfolio, setPortfolio] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await getPublicPortfolio(shareToken);
                setPortfolio(data);
            } catch (err) {
                console.error('Failed to load public portfolio:', err);
                if (err.response?.status === 404) {
                    setError('This portfolio is not available or has been made private.');
                } else {
                    setError('Unable to load portfolio. Please try again later.');
                }
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [shareToken]);

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
                <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-xs animate-pulse space-y-6 max-w-4xl w-full">
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
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
                <div className="bg-white border border-rose-200 rounded-3xl p-8 shadow-xs text-center max-w-md w-full">
                    <div className="w-16 h-16 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-4 text-2xl font-bold">
                        [Lock]
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mb-2">Portfolio Not Available</h3>
                    <p className="text-sm text-slate-500 mb-6">{error}</p>
                    <p className="text-xs text-slate-400">The candidate may have disabled public sharing or the link has expired.</p>
                </div>
            </div>
        );
    }

    if (!portfolio) {
        return null;
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
        assessment_highlights = [],
        badges = [],
        learning_journey = [],
        external_profiles = {},
        completeness = { score: 0, completed_sections: [], missing_sections: [] },
    } = portfolio;

    const initials = (profile.name || 'Candidate')
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase();

    const skillCategories = ['All', 'Programming', 'Development', 'Core CS', 'AI/ML', 'Tools'];
    const [selectedSkillCategory, setSelectedSkillCategory] = useState('All');

    const filteredSkills =
        selectedSkillCategory === 'All'
            ? skills
            : skills.filter((s) => s.category?.toLowerCase() === selectedSkillCategory.toLowerCase());

    return (
        <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-5xl mx-auto space-y-8">
                {/* Header */}
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
                                        Public Portfolio
                                    </span>
                                </div>
                                <p className="text-xs sm:text-sm font-semibold text-indigo-600 mb-1">
                                    {profile.target_role || 'Software Engineer'} • {profile.department}
                                </p>
                                <p className="text-xs text-slate-500 font-medium">
                                    Class of {profile.graduation_year || 2026} • {profile.institution}
                                </p>

                                {/* External Links */}
                                <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
                                    {external_profiles.github && (
                                        <a
                                            href={external_profiles.github}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors"
                                        >
                                            <span>[GitHub]</span> GitHub ↗
                                        </a>
                                    )}
                                    {external_profiles.linkedin && (
                                        <a
                                            href={external_profiles.linkedin}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 font-medium transition-colors border border-sky-100"
                                        >
                                            <span>[LinkedIn]</span> LinkedIn ↗
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
                                </div>
                            </div>
                        </div>

                        {/* Completeness Badge */}
                        <div className="text-center md:text-right">
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
                                Profile Completeness
                            </span>
                            <div className="flex items-center justify-end gap-2 mt-0.5">
                                <span className="text-xl font-black text-slate-900">{completeness.score}%</span>
                                <div className="w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
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
                    </div>
                </div>

                {/* Evidence Legend */}
                <div className="p-4 rounded-2xl bg-indigo-50/70 border border-indigo-100 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2 text-indigo-900 font-bold">
                        <span>[Shield]</span>
                        <span>EDI5 Evidence-Aware Verification:</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-4 text-slate-600">
                        <span className="inline-flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                            <strong className="text-slate-800">Student Claim:</strong> Self-declared
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                            <strong className="text-slate-800">Assessment Evidence:</strong> Test-backed
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                            <strong className="text-slate-800">Verified:</strong> Faculty/TPO validated
                        </span>
                    </div>
                </div>

                {/* About Section */}
                {about && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3">
                            Professional Summary
                        </h3>
                        <p className="text-sm text-slate-700 leading-relaxed bg-slate-50/70 p-4 rounded-2xl border border-slate-200/60">
                            {about}
                        </p>
                    </div>
                )}

                {/* Education */}
                {education.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Education
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
                                            CGPA
                                        </span>
                                        <span className="text-lg font-black text-slate-900">
                                            {edu.cgpa ? Number(edu.cgpa).toFixed(2) : '—'} / 10.0
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Skills */}
                {skills.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                                    Verified Technical Competencies ({skills.length})
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Only skills with assessment evidence or faculty verification are shown
                                </p>
                            </div>
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

                                        {/* Evidence Indicators */}
                                        <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-slate-100 text-[10px]">
                                            <div className="flex items-center gap-1.5">
                                                <span className={sk.assessment_evidence ? 'text-indigo-600 font-bold' : 'text-slate-400'}>
                                                    {sk.assessment_evidence ? '✓' : '—'}
                                                </span>
                                                <span className="text-slate-600">Assessment</span>
                                            </div>
                                            <div className="flex items-center gap-1.5">
                                                <span className={sk.verified ? 'text-emerald-600 font-bold' : 'text-slate-400'}>
                                                    {sk.verified ? '✓' : '—'}
                                                </span>
                                                <span className="text-slate-600">Verified</span>
                                            </div>
                                            {sk.score !== null && sk.score !== undefined && (
                                                <div className="flex items-center gap-1.5 col-span-2">
                                                    <span className="text-indigo-600 font-bold">●</span>
                                                    <span className="text-slate-600">Score: {sk.score}</span>
                                                    {sk.confidence !== null && sk.confidence !== undefined && (
                                                        <span className="text-slate-500 ml-2">(Conf: {Math.round(sk.confidence * 100)}%)</span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-xs text-slate-500 italic py-4">No skills in this category.</p>
                        )}
                    </div>
                )}

                {/* Projects */}
                {projects.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Verified Projects ({projects.length})
                        </h3>
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
                                            <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider shrink-0 bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                Verified
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
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Certifications */}
                {certifications.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Verified Certifications ({certifications.length})
                        </h3>
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
                                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                Verified
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
                                            <span className="text-[11px] text-slate-400">Verified by Institution</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Experience */}
                {experience.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Professional Experience ({experience.length})
                        </h3>
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
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Assessment Highlights */}
                {assessment_highlights.some(h => h.best_score !== null && h.best_score !== undefined) && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Assessment Highlights
                        </h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {assessment_highlights
                                .filter(h => h.best_score !== null && h.best_score !== undefined)
                                .map((highlight) => (
                                    <div
                                        key={highlight.round_type}
                                        className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/70"
                                    >
                                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                                            {highlight.label}
                                        </span>
                                        <div className="flex items-baseline gap-1 mb-1">
                                            <span className="text-2xl font-black text-indigo-600">
                                                {highlight.best_score}%
                                            </span>
                                        </div>
                                        <p className="text-[11px] text-slate-500">
                                            {highlight.attempts_count} attempt{highlight.attempts_count !== 1 ? 's' : ''}
                                            {highlight.problems_solved !== undefined && highlight.problems_solved !== null && (
                                                <> • {highlight.problems_solved} solved</>
                                            )}
                                        </p>
                                    </div>
                                ))}
                        </div>
                    </div>
                )}

                {/* Badges */}
                {badges.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Achievements & Badges ({badges.length})
                        </h3>
                        <div className="flex flex-wrap gap-3">
                            {badges.map((badge) => (
                                <div
                                    key={badge.id}
                                    className="px-4 py-2.5 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center gap-2 text-xs"
                                >
                                    <span className="text-base">{badge.icon}</span>
                                    <span className="font-bold text-indigo-700">{badge.name}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Learning Journey */}
                {learning_journey.length > 0 && (
                    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs">
                        <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">
                            Learning Journey
                        </h3>
                        <div className="space-y-4">
                            {learning_journey.slice(0, 10).map((event, idx) => (
                                <div
                                    key={idx}
                                    className="flex items-start gap-3 p-3 rounded-xl bg-slate-50/50 border border-slate-100"
                                >
                                    <div className="w-2 h-2 rounded-full bg-indigo-500 mt-2 shrink-0"></div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-medium text-slate-900">{event.event}</p>
                                        <p className="text-[11px] text-slate-500 mt-0.5">{event.date}</p>
                                    </div>
                                    <span className="text-[10px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full shrink-0">
                                        {event.type}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Footer */}
                <div className="text-center text-xs text-slate-400 py-8 border-t border-slate-200">
                    <p>This portfolio is shared publicly by the candidate via EDI5 Placement Readiness Platform.</p>
                    <p className="mt-1">Last updated: {new Date().toLocaleDateString()}</p>
                </div>
            </div>
        </div>
    );
}