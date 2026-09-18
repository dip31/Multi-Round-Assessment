import React, { useState } from 'react';

// ── Edit Profile & External Links Modal ──────────────────────────────
export function EditProfileModal({ initialData, isOpen, onClose, onSave }) {
    const [about, setAbout] = useState(initialData?.about || '');
    const [github, setGithub] = useState(initialData?.external_profiles?.github || '');
    const [linkedin, setLinkedin] = useState(initialData?.external_profiles?.linkedin || '');
    const [leetcode, setLeetcode] = useState(initialData?.external_profiles?.leetcode || '');
    const [hackerrank, setHackerrank] = useState(initialData?.external_profiles?.hackerrank || '');
    const [kaggle, setKaggle] = useState(initialData?.external_profiles?.kaggle || '');
    const [website, setWebsite] = useState(initialData?.external_profiles?.website || '');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await onSave({
                about,
                external_profiles: {
                    github: github.trim(),
                    linkedin: linkedin.trim(),
                    leetcode: leetcode.trim(),
                    hackerrank: hackerrank.trim(),
                    kaggle: kaggle.trim(),
                    website: website.trim(),
                },
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-xl w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-5">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Edit Summary & External Profiles</h3>
                        <p className="text-xs text-slate-500">Update your professional statement and online profiles</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                            About Me / Professional Summary
                        </label>
                        <textarea
                            rows={4}
                            value={about}
                            onChange={(e) => setAbout(e.target.value)}
                            placeholder="Write a concise overview of your technical focus, career interests, and competencies..."
                            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">GitHub Profile</label>
                            <input
                                type="url"
                                value={github}
                                onChange={(e) => setGithub(e.target.value)}
                                placeholder="https://github.com/username"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">LinkedIn Profile</label>
                            <input
                                type="url"
                                value={linkedin}
                                onChange={(e) => setLinkedin(e.target.value)}
                                placeholder="https://linkedin.com/in/username"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">LeetCode Profile</label>
                            <input
                                type="url"
                                value={leetcode}
                                onChange={(e) => setLeetcode(e.target.value)}
                                placeholder="https://leetcode.com/username"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">HackerRank Profile</label>
                            <input
                                type="url"
                                value={hackerrank}
                                onChange={(e) => setHackerrank(e.target.value)}
                                placeholder="https://hackerrank.com/username"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Kaggle / Other</label>
                            <input
                                type="url"
                                value={kaggle}
                                onChange={(e) => setKaggle(e.target.value)}
                                placeholder="https://kaggle.com/username"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Personal Portfolio / Website</label>
                            <input
                                type="url"
                                value={website}
                                onChange={(e) => setWebsite(e.target.value)}
                                placeholder="https://yourportfolio.dev"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Saving...' : 'Save Changes'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Add / Edit Project Modal ─────────────────────────────────────────
export function AddProjectModal({ isOpen, onClose, onSave, editItem = null }) {
    const [title, setTitle] = useState(editItem?.title || '');
    const [problemStatement, setProblemStatement] = useState(editItem?.problem_statement || '');
    const [solution, setSolution] = useState(editItem?.solution || '');
    const [technologies, setTechnologies] = useState((editItem?.technologies || []).join(', '));
    const [role, setRole] = useState(editItem?.role || 'Developer');
    const [teamType, setTeamType] = useState(editItem?.individual_or_team || 'Individual');
    const [duration, setDuration] = useState(editItem?.duration || '');
    const [githubUrl, setGithubUrl] = useState(editItem?.github_url || '');
    const [demoUrl, setDemoUrl] = useState(editItem?.demo_url || '');
    const [docsUrl, setDocsUrl] = useState(editItem?.docs_url || '');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const techArray = technologies
                .split(',')
                .map((t) => t.trim())
                .filter(Boolean);

            await onSave({
                title,
                problem_statement: problemStatement,
                solution,
                technologies: techArray,
                role,
                individual_or_team: teamType,
                duration,
                github_url: githubUrl.trim(),
                demo_url: demoUrl.trim(),
                docs_url: docsUrl.trim(),
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-xl w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">
                            {editItem ? 'Edit Project' : 'Add Technical Project'}
                        </h3>
                        <p className="text-xs text-slate-500">
                            Showcase practical engineering work with architecture and source links
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3.5">
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Project Title *</label>
                        <input
                            type="text"
                            required
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="e.g. AI-Based Vulnerability Detection System"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Problem Statement</label>
                        <textarea
                            rows={2}
                            value={problemStatement}
                            onChange={(e) => setProblemStatement(e.target.value)}
                            placeholder="What core challenge or operational gap did this project address?"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Solution & Implementation</label>
                        <textarea
                            rows={2}
                            value={solution}
                            onChange={(e) => setSolution(e.target.value)}
                            placeholder="Architecture, key algorithms, libraries, or system designs implemented..."
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">
                            Technologies (comma-separated) *
                        </label>
                        <input
                            type="text"
                            required
                            value={technologies}
                            onChange={(e) => setTechnologies(e.target.value)}
                            placeholder="e.g. Python, FastAPI, React, PostgreSQL, Docker"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Your Role</label>
                            <input
                                type="text"
                                value={role}
                                onChange={(e) => setRole(e.target.value)}
                                placeholder="Lead Developer"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Type</label>
                            <select
                                value={teamType}
                                onChange={(e) => setTeamType(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            >
                                <option value="Individual">Individual</option>
                                <option value="Team">Team (2-5)</option>
                                <option value="Capstone">College Capstone</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Duration</label>
                            <input
                                type="text"
                                value={duration}
                                onChange={(e) => setDuration(e.target.value)}
                                placeholder="3 Months"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">GitHub Repo URL</label>
                            <input
                                type="url"
                                value={githubUrl}
                                onChange={(e) => setGithubUrl(e.target.value)}
                                placeholder="https://github.com/..."
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Live Demo URL</label>
                            <input
                                type="url"
                                value={demoUrl}
                                onChange={(e) => setDemoUrl(e.target.value)}
                                placeholder="https://..."
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Documentation</label>
                            <input
                                type="url"
                                value={docsUrl}
                                onChange={(e) => setDocsUrl(e.target.value)}
                                placeholder="Docs or PDF link"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Saving...' : editItem ? 'Update Project' : 'Save Project'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Add Certification Modal ──────────────────────────────────────────
export function AddCertificationModal({ isOpen, onClose, onSave }) {
    const [name, setName] = useState('');
    const [issuer, setIssuer] = useState('');
    const [issueDate, setIssueDate] = useState('');
    const [credentialId, setCredentialId] = useState('');
    const [credentialUrl, setCredentialUrl] = useState('');
    const [skills, setSkills] = useState('');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const skillArray = skills
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);

            await onSave({
                name,
                issuer,
                issue_date: issueDate,
                credential_id: credentialId.trim(),
                credential_url: credentialUrl.trim(),
                skills: skillArray,
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Add Verified Certification</h3>
                        <p className="text-xs text-slate-500">Provide credential details from industry certifying bodies</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Certification Name *</label>
                        <input
                            type="text"
                            required
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g. AWS Certified Solutions Architect - Associate"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Issuing Organization *</label>
                            <input
                                type="text"
                                required
                                value={issuer}
                                onChange={(e) => setIssuer(e.target.value)}
                                placeholder="e.g. Amazon Web Services (AWS)"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Issue Date</label>
                            <input
                                type="month"
                                value={issueDate}
                                onChange={(e) => setIssueDate(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Credential ID</label>
                            <input
                                type="text"
                                value={credentialId}
                                onChange={(e) => setCredentialId(e.target.value)}
                                placeholder="e.g. AWS-10293847"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Credential Verification URL</label>
                            <input
                                type="url"
                                value={credentialUrl}
                                onChange={(e) => setCredentialUrl(e.target.value)}
                                placeholder="https://www.credly.com/..."
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Skills Validated (comma-separated)</label>
                        <input
                            type="text"
                            value={skills}
                            onChange={(e) => setSkills(e.target.value)}
                            placeholder="e.g. Cloud Computing, EC2, S3, IAM, VPC"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Adding...' : 'Add Certificate'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Add Experience Modal ─────────────────────────────────────────────
export function AddExperienceModal({ isOpen, onClose, onSave }) {
    const [organization, setOrganization] = useState('');
    const [role, setRole] = useState('');
    const [type, setType] = useState('Internship');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [description, setDescription] = useState('');
    const [skills, setSkills] = useState('');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const skillArray = skills
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);

            await onSave({
                organization,
                role,
                type,
                start_date: startDate,
                end_date: endDate,
                description,
                skills: skillArray,
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Add Professional Experience</h3>
                        <p className="text-xs text-slate-500">Document internships, research fellowships, or industry roles</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Organization *</label>
                            <input
                                type="text"
                                required
                                value={organization}
                                onChange={(e) => setOrganization(e.target.value)}
                                placeholder="e.g. Acme Innovations Ltd."
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Role *</label>
                            <input
                                type="text"
                                required
                                value={role}
                                onChange={(e) => setRole(e.target.value)}
                                placeholder="e.g. Software Development Intern"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Type</label>
                            <select
                                value={type}
                                onChange={(e) => setType(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            >
                                <option value="Internship">Internship</option>
                                <option value="Industry Project">Industry Project</option>
                                <option value="Research Fellow">Research Fellow</option>
                                <option value="Freelance">Freelance</option>
                                <option value="Part-time">Part-time</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Start Date</label>
                            <input
                                type="month"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">End Date</label>
                            <input
                                type="month"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Key Responsibilities / Impact</label>
                        <textarea
                            rows={3}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Architected REST APIs, built automated tests, optimized database queries..."
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Skills Demonstrated (comma-separated)</label>
                        <input
                            type="text"
                            value={skills}
                            onChange={(e) => setSkills(e.target.value)}
                            placeholder="Python, React, Redis, Agile"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Adding...' : 'Save Experience'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Add Achievement Modal ────────────────────────────────────────────
export function AddAchievementModal({ isOpen, onClose, onSave }) {
    const [title, setTitle] = useState('');
    const [organization, setOrganization] = useState('');
    const [date, setDate] = useState('');
    const [position, setPosition] = useState('');
    const [description, setDescription] = useState('');
    const [evidenceUrl, setEvidenceUrl] = useState('');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await onSave({
                title,
                organization,
                date,
                position,
                description,
                evidence_url: evidenceUrl.trim(),
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Add Achievement / Hackathon</h3>
                        <p className="text-xs text-slate-500">Record competitive coding placements, hackathons, and awards</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Achievement / Event Title *</label>
                        <input
                            type="text"
                            required
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="e.g. Smart India Hackathon Finalist"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Organizing Body</label>
                            <input
                                type="text"
                                value={organization}
                                onChange={(e) => setOrganization(e.target.value)}
                                placeholder="e.g. Ministry of Education"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Result / Position</label>
                            <input
                                type="text"
                                value={position}
                                onChange={(e) => setPosition(e.target.value)}
                                placeholder="e.g. 1st Runner Up / Top 5"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Year / Date</label>
                            <input
                                type="text"
                                value={date}
                                onChange={(e) => setDate(e.target.value)}
                                placeholder="e.g. 2026"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Proof URL / Certificate Link</label>
                            <input
                                type="url"
                                value={evidenceUrl}
                                onChange={(e) => setEvidenceUrl(e.target.value)}
                                placeholder="https://..."
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Brief Description</label>
                        <textarea
                            rows={2}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Built a real-time smart agriculture IoT monitoring dashboard..."
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Adding...' : 'Save Achievement'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Add Research / Publication Modal ─────────────────────────────────
export function AddResearchModal({ isOpen, onClose, onSave }) {
    const [title, setTitle] = useState('');
    const [authors, setAuthors] = useState('');
    const [journal, setJournal] = useState('');
    const [publicationStatus, setPublicationStatus] = useState('Published');
    const [doi, setDoi] = useState('');
    const [area, setArea] = useState('');
    const [paperUrl, setPaperUrl] = useState('');
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await onSave({
                title,
                authors,
                journal,
                status: publicationStatus,
                doi: doi.trim(),
                area: area.trim(),
                paper_url: paperUrl.trim(),
            });
            onClose();
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
            <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-lg w-full border border-slate-200 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Add Research Paper</h3>
                        <p className="text-xs text-slate-500">IEEE, Springer, Scopus or peer-reviewed publication</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm"
                    >
                        ✕
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Paper Title *</label>
                        <input
                            type="text"
                            required
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="e.g. Robust Deep Learning for Adversarial Attack Mitigation"
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Authors</label>
                            <input
                                type="text"
                                value={authors}
                                onChange={(e) => setAuthors(e.target.value)}
                                placeholder="e.g. R. Lahoti, Dr. S. Sharma"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Journal / Conference</label>
                            <input
                                type="text"
                                value={journal}
                                onChange={(e) => setJournal(e.target.value)}
                                placeholder="e.g. IEEE Xplore / Springer LNCS"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">Status</label>
                            <select
                                value={publicationStatus}
                                onChange={(e) => setPublicationStatus(e.target.value)}
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none bg-white"
                            >
                                <option value="Published">Published</option>
                                <option value="Under Review">Under Review</option>
                                <option value="Accepted">Accepted / In Press</option>
                                <option value="Submitted">Submitted</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-semibold text-slate-700 mb-1">DOI / Accession</label>
                            <input
                                type="text"
                                value={doi}
                                onChange={(e) => setDoi(e.target.value)}
                                placeholder="e.g. 10.1109/ACCESS.2026.12345"
                                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Paper Link / PDF URL</label>
                        <input
                            type="url"
                            value={paperUrl}
                            onChange={(e) => setPaperUrl(e.target.value)}
                            placeholder="https://ieeexplore.ieee.org/..."
                            className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-slate-800 text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 outline-none"
                        />
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                        <button
                            type="button"
                            onClick={onClose}
                            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition-all disabled:opacity-50"
                        >
                            {saving ? 'Adding...' : 'Save Publication'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
