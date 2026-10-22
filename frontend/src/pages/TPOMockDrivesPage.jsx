import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { Toast } from '../components/Toast';
import PageSkeleton from '../components/shared/PageSkeleton';
import TPOLayout, { TPOMenuButton } from '../components/TPOLayout';
import { BarChart3, Target, Ruler, Trash2, Users } from 'lucide-react';
import CompanyPatternModal from '../components/CompanyPatternModal';
import { getConfiguredMockDriveRounds } from '../utils/mockDriveRounds';
import { buildMockDriveEligibilityFields, createEmptyMockDriveForm, loadMockDriveForm } from '../utils/mockDriveForm';
import { getVisibleMockDrives, hideMockDriveFromHistory, sortMockDrivesByCompanyName } from '../utils/mockDriveHistory';
import { rosterRoundLabel, summarizeRoster, scoreStatusLabel, coverageLabel, scoringErrorMessage } from '../utils/mockDriveRoster';

// ── Constants ─────────────────────────────────────────────────────────
const VALID_ROUNDS = [
    { key: 'aptitude',             label: 'Aptitude' },
    { key: 'coding',               label: 'Coding' },
    { key: 'technical_interview',  label: 'Technical Interview' },
    { key: 'hr_interview',         label: 'HR Interview' },
];

const VALID_BRANCHES = [
    'Computer Science',
    'Information Technology',
    'Electronics & Communication',
    'Mechanical Engineering',
    'Civil Engineering',
    'Other',
];

const STATUS_TABS = ['all', 'draft', 'published', 'active', 'completed'];

const STATUS_BADGE = {
    draft:     'bg-slate-100 text-slate-600 border-slate-300',
    published: 'bg-sky-50 text-sky-700 border-sky-200',
    active:    'bg-emerald-50 text-emerald-700 border-emerald-200',
    completed: 'bg-violet-50 text-violet-700 border-violet-200',
};

// ── Helpers ───────────────────────────────────────────────────────────
function normalizeSelectedRounds(raw) {
    if (!raw) return {};
    if (Array.isArray(raw)) {
        return raw.reduce((acc, r) => ({ ...acc, [r]: true }), {});
    }
    if (typeof raw === 'object') {
        return { ...raw };
    }
    return {};
}

function roundsLabel(selected_rounds) {
    if (!selected_rounds) return '—';
    if (Array.isArray(selected_rounds)) {
        return selected_rounds
            .map(k => VALID_ROUNDS.find(r => r.key === k)?.label || k)
            .join(' • ') || '—';
    }
    return VALID_ROUNDS
        .filter(r => selected_rounds?.[r.key])
        .map(r => r.label)
        .join(' • ') || '—';
}

// eslint-disable-next-line no-unused-vars -- helper kept verbatim from TPODashboard (unused there too)
function progressionSequenceLabel(selected_rounds, blueprint) {
    const norm = normalizeSelectedRounds(selected_rounds);
    const enabled = VALID_ROUNDS.filter(r => norm[r.key]).map(r => r.key);
    if (enabled.length === 0) return 'No rounds selected';

    let orderedKeys = [];
    if (blueprint?.blueprint_data?.rounds?.length > 0) {
        const bpOrder = blueprint.blueprint_data.rounds
            .slice()
            .sort((a, b) => (a.round_order || 99) - (b.round_order || 99))
            .map(r => r.round_type)
            .filter(Boolean);
        const bpEnabled = bpOrder.filter(k => enabled.includes(k));
        const extra = enabled.filter(k => !bpEnabled.includes(k));
        orderedKeys = [...bpEnabled, ...extra];
    } else {
        orderedKeys = VALID_ROUNDS.map(r => r.key).filter(k => enabled.includes(k));
    }

    return orderedKeys
        .map(k => VALID_ROUNDS.find(r => r.key === k)?.label || k)
        .join(' → ') || '—';
}

function branchesLabel(eligible_branches) {
    return (eligible_branches || []).join(', ') || 'All branches';
}

export default function TPOMockDrivesPage() {
    const [tpoUser,          setTpoUser]          = useState(null);
    // eslint-disable-next-line no-unused-vars -- load contract kept verbatim from TPODashboard
    const [students,         setStudents]          = useState([]);
    // eslint-disable-next-line no-unused-vars -- load contract kept verbatim from TPODashboard
    const [cohortStats,      setCohortStats]       = useState(null);
    const [loading,          setLoading]           = useState(true);
    const [toast,            setToast]             = useState(null);

    // ── mock drive state ────────────────────────────────────────────
    const [mockDrives,            setMockDrives]            = useState([]);
    const [hiddenMockDriveIds,    setHiddenMockDriveIds]    = useState(() => new Set());
    const [mockDrivesLoading,     setMockDrivesLoading]     = useState(true);
    const [mockDriveStatusFilter, setMockDriveStatusFilter] = useState('all');
    const [publishingId,          setPublishingId]          = useState(null);

    // form / modal state
    const [showForm,     setShowForm]     = useState(false);
    const [editingDrive, setEditingDrive] = useState(null);   // null = create mode
    const [formData,     setFormData]     = useState(createEmptyMockDriveForm);
    const [formSaving,   setFormSaving]   = useState(false);
    const [formErrors,   setFormErrors]   = useState({});

    // Phase 4C: The exact company/role match is attached automatically.
    const [availableBlueprints, setAvailableBlueprints] = useState([]);
    const [blueprintsLoading,   setBlueprintsLoading]   = useState(false);

    // delete confirmation
    const [deleteTarget, setDeleteTarget] = useState(null);

    // derived roster (G4) — read-only view of authoritative records
    const [rosterTarget,  setRosterTarget]  = useState(null);
    const [rosterData,    setRosterData]    = useState(null);
    const [rosterLoading, setRosterLoading] = useState(false);
    const [rosterError,   setRosterError]   = useState(null);

    // company pattern modal (Phase 4A/4B)
    const [showPatternModal, setShowPatternModal] = useState(false);
    const [patternModalTarget, setPatternModalTarget] = useState({ company: '', role: '' });
    const openPatternManager = (company = '', role = '') => {
        setPatternModalTarget({ company, role });
        setShowPatternModal(true);
    };

    const navigate = useNavigate();

    const loadTPOData = useCallback(async () => {
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
        } catch {
            setToast({ type: 'error', message: 'Failed to load TPO dashboard data' });
        } finally {
            setLoading(false);
        }
    }, []);

    const loadMockDrives = useCallback(async () => {
        setMockDrivesLoading(true);
        try {
            const params = mockDriveStatusFilter !== 'all'
                ? { status: mockDriveStatusFilter }
                : {};
            const res = await api.get('/tpo/mock-drives', { params });
            setMockDrives(res.data || []);
        } catch {
            setToast({ type: 'error', message: 'Failed to load mock drives' });
        } finally {
            setMockDrivesLoading(false);
        }
    }, [mockDriveStatusFilter]);

    useEffect(() => { loadTPOData(); }, [loadTPOData]);
    useEffect(() => { loadMockDrives(); }, [loadMockDrives]);

    useEffect(() => {
        if (!showForm) return undefined;
        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = previousOverflow; };
    }, [showForm]);

    // Query only the approved blueprint for this exact company/role identity.
    useEffect(() => {
        if (!showForm || !formData.company_name?.trim() || !formData.target_role?.trim()) {
            setAvailableBlueprints([]);
            setBlueprintsLoading(false);
            return;
        }
        const isOriginalDriveIdentity = editingDrive
            && editingDrive.company_name.trim().toLowerCase() === formData.company_name.trim().toLowerCase()
            && editingDrive.target_role.trim().toLowerCase() === formData.target_role.trim().toLowerCase();
        if (isOriginalDriveIdentity && editingDrive.blueprint_id) {
            setAvailableBlueprints([]);
            setBlueprintsLoading(false);
            return;
        }
        let active = true;
        setAvailableBlueprints([]);
        setBlueprintsLoading(true);
        const fetchBlueprints = async () => {
            try {
                const res = await api.get('/tpo/company-data/blueprint', {
                    params: {
                        company_name: formData.company_name.trim(),
                        target_role: formData.target_role.trim(),
                        status: 'approved',
                    },
                });
                if (active) {
                    const blueprint = res.data?.[0] || null;
                    setAvailableBlueprints(blueprint ? [blueprint] : []);
                    setFormData(prev => {
                        if (!blueprint) {
                            return { ...prev, blueprint_id: null };
                        }
                        const rounds = {};
                        (blueprint.blueprint_data?.rounds || []).forEach(round => {
                            if (round.round_type) rounds[round.round_type] = true;
                        });
                        const roundConfigurations = {};
                        (blueprint.blueprint_data?.rounds || []).forEach(round => {
                            if (round.round_type) roundConfigurations[round.round_type] = {
                                question_count: round.question_count,
                                duration_minutes: round.time_limit_minutes,
                                difficulty_distribution: round.difficulty_distribution,
                            };
                        });
                        return { ...prev, blueprint_id: blueprint.id, selected_rounds: rounds, round_configurations: roundConfigurations };
                    });
                }
            } catch {
                if (active) setAvailableBlueprints([]);
            } finally {
                if (active) setBlueprintsLoading(false);
            }
        };
        const timer = setTimeout(fetchBlueprints, 300);
        return () => {
            active = false;
            clearTimeout(timer);
        };
    }, [showForm, editingDrive, formData.company_name, formData.target_role]);

    // derived values (unchanged)
    const visibleMockDrives = sortMockDrivesByCompanyName(
        getVisibleMockDrives(mockDrives, hiddenMockDriveIds),
    );

    // ── form helpers ───────────────────────────────────────────────
    const openCreate = () => {
        setEditingDrive(null);
        setFormData(createEmptyMockDriveForm());
        setAvailableBlueprints([]);
        setFormErrors({});
        setShowForm(true);
    };

    const openEdit = drive => {
        setEditingDrive(drive);
        const normalizedRounds = normalizeSelectedRounds(getConfiguredMockDriveRounds(drive));
        setFormData(loadMockDriveForm(drive, normalizedRounds));
        setAvailableBlueprints([]);
        setFormErrors({});
        setShowForm(true);
    };

    const closeForm = () => { setShowForm(false); setEditingDrive(null); };

    const setField = (field, value) =>
        setFormData(prev => {
            if ((field === 'company_name' || field === 'target_role') && prev[field] !== value) {
                return { ...prev, [field]: value, blueprint_id: null, selected_rounds: {}, round_configurations: {} };
            }
            return { ...prev, [field]: value };
        });

    const toggleBranch = branch =>
        setField('eligible_branches',
            formData.eligible_branches.includes(branch)
                ? formData.eligible_branches.filter(b => b !== branch)
                : [...formData.eligible_branches, branch]
        );

    const validateForm = () => {
        const errs = {};
        if (!formData.company_name.trim())
            errs.company_name = 'Company name is required.';
        if (!formData.target_role.trim())
            errs.target_role = 'Target role is required.';
        if (!editingDrive && !formData.blueprint_id)
            errs.blueprint_id = 'Generate and approve an assessment blueprint in Pattern Manager before saving a new drive.';
        if (!Object.values(formData.selected_rounds).some(Boolean))
            errs.selected_rounds = 'An approved blueprint with at least one configured round is required.';
        setFormErrors(errs);
        return Object.keys(errs).length === 0;
    };

    const handleSaveDraft = async e => {
        e.preventDefault();
        if (!validateForm()) return;
        setFormSaving(true);
        try {
            const payload = {
                company_name:      formData.company_name.trim(),
                target_role:       formData.target_role.trim(),
                description:       formData.description.trim() || null,
                ...buildMockDriveEligibilityFields(formData),
                eligible_branches: formData.eligible_branches,
                selected_rounds:   formData.selected_rounds,
                round_configurations: formData.round_configurations,
                blueprint_id:      formData.blueprint_id ? parseInt(formData.blueprint_id, 10) : null,
            };

            if (editingDrive) {
                await api.put(`/tpo/mock-drives/${editingDrive.id}`, payload);
                setToast({ type: 'success', message: 'Mock drive updated.' });
            } else {
                await api.post('/tpo/mock-drives', payload);
                setToast({ type: 'success', message: 'Mock drive saved as draft.' });
            }

            closeForm();
            loadMockDrives();
        } catch (err) {
            const detail = err.response?.data?.detail;
            setToast({
                type: 'error',
                message: typeof detail === 'string'
                    ? detail
                    : Array.isArray(detail)
                        ? detail.map(item => item.msg || JSON.stringify(item)).join('; ')
                        : detail?.message || 'Failed to save mock drive.',
            });
        } finally {
            setFormSaving(false);
        }
    };

    // ── delete helpers ─────────────────────────────────────────────

    const confirmDelete = drive => setDeleteTarget(drive);
    const cancelDelete  = ()    => setDeleteTarget(null);

    const handleRemoveFromHistory = () => {
        if (!deleteTarget) return;
        setHiddenMockDriveIds(current => hideMockDriveFromHistory(current, deleteTarget.id));
        setToast({ type: 'success', message: 'Removed from this history view. The Mock Drive remains saved.' });
        setDeleteTarget(null);
    };

    const handlePublish = async (driveId) => {
        setPublishingId(driveId);
        try {
            await api.post(`/tpo/mock-drives/${driveId}/publish`);
            setToast({ type: 'success', message: 'Mock drive published successfully.' });
            loadMockDrives();
        } catch (err) {
            const detail = err.response?.data?.detail;
            const msg = detail?.message || (typeof detail === 'string' ? detail : 'Failed to publish mock drive.');
            const errs = detail?.errors;
            setToast({ type: 'error', message: errs ? `${msg}\n${errs.join(' ')}` : msg });
        } finally {
            setPublishingId(null);
        }
    };

    // ── derived roster (G4) ────────────────────────────────────────

    const openRoster = async (drive) => {
        setRosterTarget(drive);
        setRosterData(null);
        setRosterError(null);
        setRosterLoading(true);
        try {
            const res = await api.get(`/tpo/mock-drives/${drive.id}/roster`);
            setRosterData(summarizeRoster(res.data));
        } catch (err) {
            const detail = err.response?.data?.detail;
            setRosterError(
                typeof detail === 'string' ? detail : 'Failed to load the candidate roster.',
            );
        } finally {
            setRosterLoading(false);
        }
    };

    const closeRoster = () => {
        setRosterTarget(null);
        setRosterData(null);
        setRosterError(null);
    };

    if (loading) return <PageSkeleton variant="light" cardCount={4} />;

    return (
        <TPOLayout>
            {toast && <Toast {...toast} onClose={() => setToast(null)} />}

            <main className="max-w-7xl mx-auto px-6 py-10 space-y-10">

                {/* ── 1. HEADER ──────────────────────────────────────────── */}
                <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
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
                        <br></br>
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
                        <TPOMenuButton />
                        <button
                            onClick={loadTPOData}
                            className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold shadow-sm transition-all"
                        >
                            ↻ Refresh Roster
                        </button>
                    </div>
                </div>

                {/* ── 3. PLACEMENT & MOCK DRIVES ─────────────────────────── */}
                <section>
                    <div className="flex items-center gap-2 mb-6">
                        <h2 className="text-base font-bold text-slate-900">Placement &amp; Mock Drives</h2>
                        <span className="h-px flex-1 bg-slate-200" />
                    </div>


                    {/* 3B — Mock Drives */}
                    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                        {/* header row */}
                        <div className="px-6 py-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm font-bold text-slate-900">Mock Drives</span>
                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-50 text-violet-700 border border-violet-200">
                                        TPO-controlled assessment simulation
                                    </span>
                                </div>
                                <br></br>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    Practice placement drives configured and managed by the TPO.
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => openPatternManager()}
                                    className="flex-shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold border border-indigo-200 transition-all"
                                >
                                    <span><BarChart3 size={14} /></span> Historical Patterns
                                </button>
                                <button
                                    onClick={openCreate}
                                    className="flex-shrink-0 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold shadow-sm transition-all"
                                >
                                    <span>+</span> Create Mock Drive
                                </button>
                            </div>
                        </div>

                        {/* status filter tabs */}
                        <div className="px-6 pt-3 pb-0 flex items-center gap-1 border-b border-slate-100">
                            {STATUS_TABS.map(tab => (
                                <button
                                    key={tab}
                                    onClick={() => setMockDriveStatusFilter(tab)}
                                    className={`px-3 py-2 text-xs font-semibold capitalize border-b-2 transition-all ${
                                        mockDriveStatusFilter === tab
                                            ? 'border-violet-600 text-violet-700'
                                            : 'border-transparent text-slate-500 hover:text-slate-700'
                                    }`}
                                >
                                    {tab === 'all' ? 'All' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                                </button>
                            ))}
                        </div>

                        {/* body */}
                        {mockDrivesLoading ? (
                            <div className="py-12 text-center text-xs text-slate-400 font-medium">
                                Loading mock drives…
                            </div>
                        ) : visibleMockDrives.length === 0 ? (
                            /* empty state */
                            <div className="py-16 px-6 text-center">
                                <div className="w-12 h-12 rounded-2xl bg-violet-50 border border-violet-100 flex items-center justify-center mx-auto mb-4 text-2xl"><Target size={24} /></div>
                                <h3 className="text-sm font-bold text-slate-800 mb-1">
                                    {mockDrives.length > 0 ? 'No mock drives in this history view' : 'No mock drives created yet'}
                                </h3>
                                <p className="text-xs text-slate-500 max-w-sm mx-auto mb-5">
                                    {mockDrives.length > 0
                                        ? 'Removed drives remain saved. Refreshing the page restores them to this view.'
                                        : 'Create a customized practice drive based on company, role, eligibility criteria and selected assessment rounds.'}
                                </p>
                                <button
                                    onClick={openCreate}
                                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold shadow-sm transition-all"
                                >
                                    + Create Mock Drive
                                </button>
                            </div>
                        ) : (
                            /* drive cards */
                            <div className="divide-y divide-slate-100">
                                {visibleMockDrives.map(drive => (
                                    <div key={drive.id} className="px-6 py-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/60 transition-colors">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                <span className="font-bold text-slate-900 text-sm">{drive.company_name}</span>
                                                <span className="text-slate-400 text-xs">—</span>
                                                <span className="text-slate-700 text-xs font-semibold">{drive.target_role}</span>
                                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border capitalize ${STATUS_BADGE[drive.status] || 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                                                    {drive.status}
                                                </span>
                                                {drive.blueprint_id && (
                                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                        <Ruler size={10} /> Blueprint v{drive.blueprint_version || 1}
                                                    </span>
                                                )}
                                            </div>

                                            <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-slate-500">
                                                <span>CGPA ≥ {drive.minimum_cgpa}</span>
                                                <span>Backlogs ≤ {drive.maximum_backlogs}</span>
                                                <span>{branchesLabel(drive.eligible_branches)}</span>
                                            </div>
                                            <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5 flex-wrap">
                                                <span className="text-slate-400">Configured Assessment Rounds:</span>
                                                <span className="font-semibold text-slate-700">
                                                    {roundsLabel(getConfiguredMockDriveRounds(drive))}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0">
                                            {drive.status !== 'draft' && (
                                                <button
                                                    onClick={() => openRoster(drive)}
                                                    className="px-3 py-1.5 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-700 text-xs font-semibold border border-sky-200 transition-all inline-flex items-center gap-1.5"
                                                    title="View the derived candidate roster for this Mock Drive"
                                                >
                                                    <Users size={12} /> Roster
                                                </button>
                                            )}
                                            <button
                                                onClick={() => openPatternManager(drive.company_name, drive.target_role)}
                                                className="px-3 py-1.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold border border-indigo-200 transition-all"
                                                title="View or manage historical assessment pattern"
                                            >
                                                Patterns
                                            </button>
                                            {drive.status === 'draft' && (
                                                <>
                                                    <button
                                                        onClick={() => openEdit(drive)}
                                                        className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 transition-all"
                                                    >
                                                        Edit
                                                    </button>
                                                    <button
                                                        onClick={() => handlePublish(drive.id)}
                                                        disabled={publishingId === drive.id}
                                                        className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold border border-emerald-600 transition-all"
                                                    >
                                                        {publishingId === drive.id ? 'Publishing…' : 'Publish'}
                                                    </button>
                                                </>
                                            )}
                                            <button
                                                type="button"
                                                onClick={() => confirmDelete(drive)}
                                                aria-label={`Remove ${drive.company_name} ${drive.target_role} from history view`}
                                                className="px-3 py-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-600 text-xs font-semibold border border-slate-200 transition-all"
                                            >
                                                Remove
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </section>

            </main>

            {/* ── CREATE / EDIT MOCK DRIVE MODAL ────────────────────────── */}
            {showForm && (
                <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 overflow-hidden overscroll-none">
                    <div className="bg-white border border-slate-200 rounded-3xl max-h-[calc(100dvh-2rem)] max-w-lg w-full shadow-2xl flex flex-col overflow-hidden">
                        <div className="flex-shrink-0 px-8 pt-8">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-4 mb-6">
                            <div>
                                <h3 className="text-xl font-bold text-slate-900">
                                    {editingDrive ? 'Edit Mock Drive' : 'Create Mock Drive'}
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5">Saved as draft until published.</p>
                            </div>
                            <button onClick={closeForm} className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center font-bold text-sm">✕</button>
                        </div>
                        </div>

                        <form onSubmit={handleSaveDraft} className="flex min-h-0 flex-1 flex-col text-xs">
                            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-8 pb-6">
                            <div className="space-y-5">
                            {/* Company */}
                            <div>
                                <label className="block font-semibold text-slate-700 mb-1">Company Name <span className="text-red-500">*</span></label>
                                <input
                                    type="text"
                                    value={formData.company_name}
                                    onChange={e => setField('company_name', e.target.value)}
                                    placeholder="e.g. Citi, Infosys, Barclays"
                                    className={`w-full px-4 py-2.5 rounded-xl border text-slate-900 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-violet-500 ${formErrors.company_name ? 'border-red-400' : 'border-slate-300'}`}
                                />
                                {formErrors.company_name && <p className="text-red-500 mt-1">{formErrors.company_name}</p>}
                            </div>

                            {/* Role */}
                            <div>
                                <label className="block font-semibold text-slate-700 mb-1">Target Role <span className="text-red-500">*</span></label>
                                <input
                                    type="text"
                                    value={formData.target_role}
                                    onChange={e => setField('target_role', e.target.value)}
                                    placeholder="e.g. Data Engineer, Software Developer"
                                    className={`w-full px-4 py-2.5 rounded-xl border text-slate-900 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-violet-500 ${formErrors.target_role ? 'border-red-400' : 'border-slate-300'}`}
                                />
                                {formErrors.target_role && <p className="text-red-500 mt-1">{formErrors.target_role}</p>}
                            </div>

                            {/* Phase 4A Historical Pattern Helper */}
                            {formData.company_name?.trim() && formData.target_role?.trim() && (
                                <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-between">
                                    <div>
                                        <div className="text-[11px] font-bold text-indigo-900">
                                            Review Historical Pattern Sources
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => openPatternManager(formData.company_name, formData.target_role)}
                                        className="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] shadow-sm transition-all"
                                    >
                                        Check Patterns →
                                    </button>
                                </div>
                            )}

                            {/* Description */}
                            <div>
                                <label className="block font-semibold text-slate-700 mb-1">Description / job description <span className="text-slate-400 font-normal">(optional)</span></label>
                                <textarea
                                    value={formData.description}
                                    onChange={e => setField('description', e.target.value)}
                                    rows={2}
                                    placeholder="Drive summary or job description for role-specific assessment context…"
                                    className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-slate-900 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
                                />
                            </div>

                            {/* Eligibility */}
                            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-3">
                                <p className="font-bold text-slate-700">Eligibility</p>
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-slate-600 mb-1">Minimum CGPA</label>
                                        <input
                                            type="number" min="0" max="10" step="0.1"
                                            value={formData.minimum_cgpa}
                                            onChange={e => setField('minimum_cgpa', e.target.value)}
                                            className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-violet-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-slate-600 mb-1">Max Backlogs</label>
                                        <input
                                            type="number" min="0"
                                            value={formData.maximum_backlogs}
                                            onChange={e => setField('maximum_backlogs', e.target.value)}
                                            className="w-full px-3 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-violet-500"
                                        />
                                    </div>
                                </div>
                                <div>
                                    <p className="text-slate-600 mb-2">Eligible Branches</p>
                                    <div className="flex flex-wrap gap-2">
                                        {VALID_BRANCHES.map(branch => (
                                            <button
                                                key={branch}
                                                type="button"
                                                onClick={() => toggleBranch(branch)}
                                                className={`px-3 py-1 rounded-lg border text-[11px] font-semibold transition-all ${
                                                    formData.eligible_branches.includes(branch)
                                                        ? 'bg-violet-600 text-white border-violet-600'
                                                        : 'bg-white text-slate-600 border-slate-300 hover:border-violet-400'
                                                }`}
                                            >
                                                {branch}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            {/* Phase 4C: Approved blueprint is discovered and attached automatically. */}
                            {formData.company_name?.trim() && formData.target_role?.trim() && (
                                <div className="p-4 bg-emerald-50/60 rounded-2xl border border-emerald-200/80 space-y-2.5">
                                    <div className="flex items-center justify-between">
                                        <label className="font-bold text-emerald-900 text-xs flex items-center gap-1.5">
                                            <span><Ruler size={14} /></span> Assessment Blueprint
                                        </label>
                                        {blueprintsLoading && (
                                            <span className="text-[10px] text-emerald-600 font-medium">Checking blueprints…</span>
                                        )}
                                    </div>

                                    {blueprintsLoading ? (
                                        <div className="text-[11px] text-emerald-700">Checking for an approved blueprint…</div>
                                    ) : (availableBlueprints[0] || (editingDrive?.blueprint_id && formData.blueprint_id === editingDrive.blueprint_id)) ? (
                                        <div className="text-[11px] text-emerald-800 bg-emerald-100/60 p-2 rounded-lg border border-emerald-200">
                                            <div className="font-bold">✓ Approved Blueprint v{availableBlueprints[0]?.version || editingDrive?.blueprint_version} attached</div>
                                            <div>Its approved assessment rounds will be pinned to this Mock Drive when saved.</div>
                                            {availableBlueprints[0]?.blueprint_data?.rounds?.map(round => (
                                                <div key={`${round.round_type}-${round.round_order}`} className="mt-1">
                                                    {round.name || round.round_type}: {round.question_count} questions, {round.time_limit_minutes} minutes
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-[11px] text-slate-600 flex flex-col gap-1">
                                            <span>No approved assessment blueprint found for <strong className="text-slate-800">{formData.company_name}</strong> - <strong className="text-slate-800">{formData.target_role}</strong>.</span>
                                            <br></br>
                                            <button type="button" onClick={() => openPatternManager(formData.company_name, formData.target_role)} disabled={blueprintsLoading}
                                                className="self-start px-2.5 py-1.5 rounded-lg bg-violet-600 text-white font-bold disabled:opacity-40">
                                                Generate role assessment from this drive
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}

                            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
                                <div className="font-bold">Assessment rounds</div>
                                {formData.blueprint_id ? <div className="mt-1">{roundsLabel(formData.selected_rounds)} · settings come from the attached approved blueprint.</div> : <div className="mt-1">No approved blueprint is attached yet. Configure and approve one in Pattern Manager to save this new drive.</div>}
                                {(formErrors.blueprint_id || formErrors.selected_rounds) && <p className="mt-2 text-red-600">{formErrors.blueprint_id || formErrors.selected_rounds}</p>}
                            </div>

                            </div>
                            </div>
                            {/* Fixed actions remain available while form content scrolls. */}
                            <div className="flex flex-shrink-0 items-center justify-end gap-3 border-t border-slate-100 bg-white px-8 py-4">
                                <button
                                    type="button"
                                    onClick={closeForm}
                                    className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold transition-all"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={formSaving || blueprintsLoading}
                                    className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-semibold shadow-sm transition-all"
                                >
                                    {formSaving ? 'Saving…' : editingDrive ? 'Save Changes' : 'Save Draft'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* ── DELETE CONFIRMATION MODAL ──────────────────────────────── */}
            {deleteTarget && (
                <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
                    <div role="dialog" aria-modal="true" aria-labelledby="remove-drive-title" className="bg-white border border-slate-200 rounded-3xl p-8 max-w-sm w-full shadow-2xl">
                        <div className="text-center mb-6">
                            <div className="w-12 h-12 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-4 text-2xl"><Trash2 size={24} /></div>
                            <h3 id="remove-drive-title" className="text-base font-bold text-slate-900 mb-1">Remove this drive from the history view?</h3>
                            <p className="text-xs text-slate-500">
                                <span className="font-semibold text-slate-700">{deleteTarget.company_name}</span>
                                {' — '}{deleteTarget.target_role}
                            </p>
                            <p className="text-xs text-slate-500 mt-2">This only removes it from your current history view. It does not delete the Mock Drive or change its saved data.</p>
                        </div>
                        <div className="flex items-center justify-center gap-3">
                            <button
                                onClick={cancelDelete}
                                className="px-5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleRemoveFromHistory}
                                className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold shadow-sm transition-all"
                            >
                                Remove
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── DERIVED CANDIDATE ROSTER (G4) ─────────────────────────── */}
            {rosterTarget && (
                <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 overflow-hidden overscroll-none">
                    <div className="bg-white border border-slate-200 rounded-3xl max-h-[calc(100dvh-2rem)] max-w-3xl w-full shadow-2xl flex flex-col overflow-hidden">
                        <div className="flex-shrink-0 px-8 pt-8">
                            <div className="flex items-start justify-between border-b border-slate-100 pb-4 mb-4">
                                <div>
                                    <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                                        <Users size={18} /> Candidate Roster
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {rosterTarget.company_name} — {rosterTarget.target_role}
                                    </p>
                                    <p className="text-[11px] text-slate-400 mt-1">
                                        Derived from submitted assessment records. Read-only.
                                    </p>
                                </div>
                                <button
                                    onClick={closeRoster}
                                    className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-200 transition-all"
                                >
                                    Close
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto overscroll-contain px-8 pb-8">
                            {rosterLoading && (
                                <p className="text-sm text-slate-500 py-8 text-center">Loading roster…</p>
                            )}

                            {!rosterLoading && rosterError && (
                                <p className="text-sm text-rose-600 py-8 text-center">{rosterError}</p>
                            )}

                            {!rosterLoading && !rosterError && rosterData && (
                                <>
                                    <div className="grid grid-cols-3 gap-3 mb-5">
                                        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                                            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Participants</div>
                                            <div className="text-xl font-bold text-slate-900">{rosterData.total}</div>
                                        </div>
                                        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                                            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-500">In Progress</div>
                                            <div className="text-xl font-bold text-emerald-700">{rosterData.inProgress}</div>
                                        </div>
                                        <div className="rounded-2xl border border-violet-200 bg-violet-50 px-4 py-3">
                                            <div className="text-[10px] font-bold uppercase tracking-wider text-violet-500">Completed</div>
                                            <div className="text-xl font-bold text-violet-700">{rosterData.completed}</div>
                                        </div>
                                    </div>

                                    {rosterData.candidates.length === 0 ? (
                                        <p className="text-sm text-slate-500 py-8 text-center border border-dashed border-slate-200 rounded-2xl">
                                            No candidates have attempted this Mock Drive yet.
                                        </p>
                                    ) : (
                                        <div className="border border-slate-200 rounded-2xl overflow-hidden">
                                            <table className="w-full text-left text-xs">
                                                <thead className="bg-slate-50 text-slate-500">
                                                    <tr>
                                                        <th className="px-4 py-2 font-semibold">Candidate</th>
                                                        <th className="px-4 py-2 font-semibold">Status</th>
                                                        <th className="px-4 py-2 font-semibold">Score</th>
                                                        <th className="px-4 py-2 font-semibold">Competency</th>
                                                        <th className="px-4 py-2 font-semibold">Coverage</th>
                                                        <th className="px-4 py-2 font-semibold">Missing</th>
                                                        {rosterData.enabledRounds.map(r => (
                                                            <th key={r} className="px-4 py-2 font-semibold">{rosterRoundLabel(r)}</th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-100">
                                                    {rosterData.candidates.map(candidate => (
                                                        <tr key={candidate.candidateId} className="hover:bg-slate-50/60">
                                                            <td className="px-4 py-2.5">
                                                                <div className="font-semibold text-slate-800">{candidate.displayName}</div>
                                                                <div className="text-[10px] text-slate-400">#{candidate.candidateId}</div>
                                                            </td>
                                                            <td className="px-4 py-2.5 text-slate-600">{candidate.statusLabel}</td>
                                                            <td className="px-4 py-2.5 font-semibold text-slate-800">{candidate.scoreLabel}</td>
                                                            <td className="px-4 py-2.5">
                                                                <div className="flex flex-col gap-1">
                                                                    {candidate.competencyScoreStatusLabel && (
                                                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                                                            candidate.competencyScoreStatus === 'final' ? 'bg-emerald-50 text-emerald-700' :
                                                                            candidate.competencyScoreStatus === 'provisional' ? 'bg-amber-50 text-amber-700' :
                                                                            'bg-slate-50 text-slate-600'
                                                                        }`}>
                                                                            {candidate.competencyScoreStatusLabel}
                                                                        </span>
                                                                    )}
                                                                    {candidate.scoringError && (
                                                                        <span className="text-[10px] text-rose-600 flex items-center gap-1">
                                                                            <span>⚠</span>
                                                                            {scoringErrorMessage(candidate.scoringError)}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </td>
                                                            <td className="px-4 py-2.5 text-slate-600">{candidate.evidenceCoverageLabel}</td>
                                                            <td className="px-4 py-2.5 text-slate-600">
                                                                {candidate.missingCompetencies && candidate.missingCompetencies.length > 0 ? (
                                                                    <span className="text-rose-600">{candidate.missingCompetencies.join(', ')}</span>
                                                                ) : (
                                                                    <span className="text-emerald-600">—</span>
                                                                )}
                                                            </td>
                                                            {rosterData.enabledRounds.map(r => {
                                                                const round = (candidate.rounds || []).find(x => x.round === r);
                                                                return (
                                                                    <td key={r} className="px-4 py-2.5 text-slate-600">
                                                                        {round ? `${round.status}${round.score != null ? ` · ${round.score}` : ''}` : '—'}
                                                                    </td>
                                                                );
                                                            })}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}

                                    <p className="text-[10px] text-slate-400 mt-3">
                                        Competency scoring uses blueprint weights and persisted evidence. <span className="font-semibold text-amber-700">Provisional</span> scores are informational only — not final or rankable.
                                    </p>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ── Phase 4A Company Historical Data & Pattern Modal ─────── */}
            <CompanyPatternModal
                isOpen={showPatternModal}
                onClose={() => setShowPatternModal(false)}
                initialCompany={patternModalTarget.company}
                initialRole={patternModalTarget.role}
                initialAssessmentConfig={patternModalTarget.driveConfig}
                existingDrives={mockDrives}
                onToast={setToast}
                onBlueprintApproved={blueprint => {
                    if (formData.company_name.trim().toLowerCase() !== blueprint.company_name.trim().toLowerCase()
                        || formData.target_role.trim().toLowerCase() !== blueprint.target_role.trim().toLowerCase()) return;
                    const rounds = {};
                    const round_configurations = {};
                    (blueprint.blueprint_data?.rounds || []).forEach(round => {
                        if (!round.round_type) return;
                        rounds[round.round_type] = true;
                        round_configurations[round.round_type] = {
                            question_count: round.question_count,
                            duration_minutes: round.time_limit_minutes,
                            difficulty_distribution: round.difficulty_distribution,
                        };
                    });
                    setFormData(prev => ({ ...prev, blueprint_id: blueprint.id, selected_rounds: rounds, round_configurations }));
                    setAvailableBlueprints([blueprint]);
                }}
            />
        </TPOLayout>
    );
}
