import React, { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';
import { getConfiguredMockDriveRounds } from '../utils/mockDriveRounds';
import { buildDriveFacingPoolRounds } from '../utils/questionPoolDisplay';
import { resolveBlueprintGenerationRequest, isRoleAssessmentProvenance } from '../utils/blueprintGeneration';
import { deriveHistoricalRoundConfig, buildHistoricalRoundPayload } from '../utils/historicalRoundConfig';

const SUPPORTED_EXTS = '.pdf,.docx,.csv,.xlsx,.json';
const ROUND_OPTIONS = [
    { key: 'aptitude', label: 'Aptitude' },
    { key: 'coding', label: 'Coding' },
    { key: 'technical_interview', label: 'Technical Interview' },
    { key: 'hr_interview', label: 'HR Interview' },
];

const DEFAULT_ROUND_SETTINGS = {
    aptitude: [25, 45], coding: [2, 60], technical_interview: [3, 45], hr_interview: [3, 30],
};
const DEFAULT_DIFFICULTY = { easy: 0.25, medium: 0.5, hard: 0.25 };

function addDisplayOnlyLegacyProvenance(record, dataKey, sourceRefs, currentSources) {
    const data = record?.[dataKey];
    if (!data || data.source_provenance) return record;
    const refIds = new Set((sourceRefs || []).map(source => source.id));
    const usedSources = currentSources.filter(source => refIds.has(source.id));
    const hasSeed = usedSources.some(source => source.source_type === 'pre_seeded');
    const classification = hasSeed
        ? 'source_unverified'
        : usedSources.length
            ? 'company_specific_historical_evidence'
            : 'source_unverified';
    return {
        ...record,
        [dataKey]: {
            ...data,
            source_provenance: {
                classification,
                selection_status: hasSeed ? 'legacy_source_unverified' : 'role_compatible_evidence_found',
                empirical_source_count: usedSources.filter(source => source.source_type !== 'pre_seeded').length,
                legacy_display_only: true,
            },
        },
    };
}

function formatApiErrorDetail(detail, fallback) {
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
        const messages = detail
            .map(item => (typeof item === 'string' ? item : item?.msg))
            .filter(Boolean);
        if (messages.length) return messages.join(' ');
    }
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
        return detail.message;
    }
    return fallback;
}

export default function CompanyPatternModal({
    isOpen,
    onClose,
    initialCompany = '',
    initialRole = '',
    initialAssessmentConfig = null,
    onBlueprintApproved,
    existingDrives = [],
    onToast,
}) {
    const [companyName, setCompanyName] = useState(initialCompany);
    const [targetRole, setTargetRole] = useState(initialRole);
    const [jobDescription, setJobDescription] = useState('');
    const [roundSettings, setRoundSettings] = useState(() => Object.fromEntries(ROUND_OPTIONS.map(({ key }) => {
        const [question_count, duration_minutes] = DEFAULT_ROUND_SETTINGS[key];
        return [key, { enabled: false, question_count, duration_minutes, difficulty_distribution: DEFAULT_DIFFICULTY }];
    })));
    // TPO configuration for historical (evidence-based) patterns. Keyed by round;
    // prefilled from evidence-derived values where present, left blank (shown as
    // "—") where the evidence provides nothing.
    const [historicalConfig, setHistoricalConfig] = useState({});
    // Assessment rounds the TPO explicitly added that were NOT in the evidence.
    // Sent as `added_rounds` on save so they join assessment_rounds as TPO-added.
    const [addedRounds, setAddedRounds] = useState([]);
    // Whether the "+ Add Assessment Round" chooser is expanded.
    const [showAddRoundMenu, setShowAddRoundMenu] = useState(false);
    // True when the panel holds unsaved edits. Set by user edits, cleared on a
    // successful save or when the panel is re-derived from the server, so the
    // save button reflects real persistence rather than always-looking-dirty.
    const [configDirty, setConfigDirty] = useState(false);

    const [activeTab, setActiveTab] = useState('pattern'); // 'pattern' | 'blueprint' | 'sources' | 'add_manual' | 'upload_file'
    const [loading, setLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);

    const [sources, setSources] = useState([]);
    const [pattern, setPattern] = useState(null);
    const [blueprint, setBlueprint] = useState(null);

    // Guard against stale in-flight loads clobbering freshly set state
    const loadReqRef = useRef(0);

    // Form: Manual historical drive
    const [manualForm, setManualForm] = useState({
        label: 'Historical Campus Drive',
        year: new Date().getFullYear(),
        rounds: ['aptitude', 'coding'],
        topics: '',
        difficulty: 'medium',
        question_types: ['MCQ', 'Coding'],
        duration_minutes: 90,
        notes: '',
    });

    // Form: File upload
    const [uploadFile, setUploadFile] = useState(null);
    const [uploadLabel, setUploadLabel] = useState('');

    // Review pattern notes
    const [reviewNotes, setReviewNotes] = useState('');

    // Blueprint edit draft state
    const [blueprintDraft, setBlueprintDraft] = useState(null);
    const [blueprintCompetencies, setBlueprintCompetencies] = useState([]);
    const [blueprintNotes, setBlueprintNotes] = useState('');

    // Competency generation state
    const [competencyGenerating, setCompetencyGenerating] = useState(false);

    // Computed total competency weight
    const weightTotal = blueprintCompetencies.reduce((sum, c) => sum + (Number(c.weight_pct) || 0), 0);

    // Question pool generation state (approved blueprints only)
    const [poolStatus, setPoolStatus] = useState({ rounds: [], blueprint_version: null });
    const [poolLoading, setPoolLoading] = useState(false);
    const [poolGenerating, setPoolGenerating] = useState(false);

    // Prepopulate when initial company/role change
    useEffect(() => {
        if (initialCompany) setCompanyName(initialCompany);
        if (initialRole) setTargetRole(initialRole);
        setJobDescription(initialAssessmentConfig?.job_description || '');
    }, [initialCompany, initialRole, initialAssessmentConfig]);

    // Question pool: status + generation (pre-candidate LLM pools)
    const loadPoolStatus = useCallback(async () => {
        const c = companyName?.trim();
        const r = targetRole?.trim();
        if (!c || !r) return;
        setPoolLoading(true);
        try {
            const res = await api.get(`/tpo/company-data/blueprint/${encodeURIComponent(c)}/${encodeURIComponent(r)}/question-pool/status`);
            setPoolStatus(res.data || { rounds: [], blueprint_version: null });
        } catch (err) {
            if (err.response?.status !== 404) {
                console.error('Failed to load question pool status', err);
            }
            setPoolStatus({ rounds: [], blueprint_version: null });
        } finally {
            setPoolLoading(false);
        }
    }, [companyName, targetRole]);

    useEffect(() => {
        if (isOpen && blueprint?.status === 'approved') {
            loadPoolStatus();
        }
    }, [isOpen, blueprint?.id, blueprint?.version, blueprint?.status, loadPoolStatus]);

    // Prefill the historical round-configuration panel from evidence-derived
    // values when a pattern is generated/loaded. Every evidence-derived (or
    // previously TPO-added) assessment round gets an editable entry seeded with
    // the round's evidence values so the TPO can review and edit them; previously
    // captured TPO edits survive pattern recalculations so input is never lost.
    // Rebuild the historical round-configuration panel from the persisted
    // pattern (the single source of truth). `assessment_rounds`, `evidence_rounds`
    // and the durable `tpo_configuration` block are read directly so explicit
    // selections and deselections are always reflected, and a deselected round is
    // shown as unchecked rather than silently missing.
    useEffect(() => {
        const patternData = pattern?.pattern_data;
        if (!patternData || isRoleAssessmentProvenance(patternData)) {
            setHistoricalConfig({});
            setAddedRounds([]);
            return;
        }
        const { config, addedRounds: derivedAdded } = deriveHistoricalRoundConfig(patternData);
        setHistoricalConfig(config);
        setAddedRounds(addedRoundsValue => {
            // Keep not-yet-saved locally added rounds from being dropped.
            const localOnly = addedRoundsValue.filter(key => !(key in config));
            return [...new Set([...derivedAdded, ...localOnly])];
        });
        setConfigDirty(false);
    }, [pattern]);

    // Any user edit marks the panel dirty; a successful save / server re-derive
    // clears it.
    const editHistoricalConfig = useCallback((updater) => {
        setHistoricalConfig(updater);
        setConfigDirty(true);
    }, []);

    const POOL_ROUND_LABELS = {
        aptitude: 'Aptitude',
        coding: 'Coding',
        technical_interview: 'Technical Interview',
        hr_interview: 'HR Interview',
    };
    const POOL_STATUS_CHIP = {
        complete: { label: 'Complete ✓', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
        in_progress: { label: 'Generating…', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
        incomplete: { label: 'Incomplete', cls: 'bg-rose-50 text-rose-700 border-rose-200' },
        failed: { label: 'Failed', cls: 'bg-rose-50 text-rose-700 border-rose-200' },
        not_generated: { label: 'Not Generated', cls: 'bg-slate-100 text-slate-600 border-slate-300' },
    };

    // Load data whenever company & role are present and modal is open
    const loadCompanyData = useCallback(async (comp, role) => {
        const c = comp?.trim();
        const r = role?.trim();
        if (!c || !r) return;

        const reqId = ++loadReqRef.current;
        const isCurrent = () => reqId === loadReqRef.current;
        setLoading(true);
        try {
            // Fetch historical sources
            const histRes = await api.get('/tpo/company-data/historical', {
                params: { company_name: c, target_role: r },
            });
            const matchedSources = (histRes.data || []).filter(
                s => s.company_name.toLowerCase() === c.toLowerCase() &&
                     s.target_role.toLowerCase() === r.toLowerCase()
            );
            if (!isCurrent()) return;
            setSources(matchedSources);

            // Fetch pattern if exists
            try {
                const patRes = await api.get(`/tpo/company-data/pattern/${encodeURIComponent(c)}/${encodeURIComponent(r)}`);
                if (!isCurrent()) return;
                setPattern(addDisplayOnlyLegacyProvenance(
                    patRes.data,
                    'pattern_data',
                    patRes.data.pattern_data?.sources_summary,
                    matchedSources,
                ));
            } catch (err) {
                if (err.response?.status === 404 && isCurrent()) {
                    setPattern(null);
                }
            }

            // Fetch blueprint if exists
            try {
                const bpRes = await api.get(`/tpo/company-data/blueprint/${encodeURIComponent(c)}/${encodeURIComponent(r)}`);
                const displayBlueprint = addDisplayOnlyLegacyProvenance(
                    bpRes.data,
                    'blueprint_data',
                    bpRes.data.blueprint_data?.source_references,
                    matchedSources,
                );
                if (!isCurrent()) return;
                setBlueprint(displayBlueprint);
                setBlueprintDraft(displayBlueprint.blueprint_data?.rounds || []);
                setBlueprintCompetencies(displayBlueprint.blueprint_data?.competencies || []);
                setBlueprintNotes(bpRes.data.review_notes || '');
            } catch (err) {
                if (err.response?.status === 404 && isCurrent()) {
                    setBlueprint(null);
                    setBlueprintDraft(null);
                }
            }
        } catch (err) {
            console.error('Failed to load company historical data', err);
        } finally {
            if (isCurrent()) setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isOpen && companyName && targetRole) {
            loadCompanyData(companyName, targetRole);
        }
    }, [isOpen, companyName, targetRole, loadCompanyData]);

    // Keep the round selector in sync with the current LLM role-assessment
    // pattern so the TPO can add/remove/configure rounds before approval.
    // Recalculation re-runs role assessment generation with exactly these
    // selected/configured rounds.
    useEffect(() => {
        if (!pattern || pattern.pattern_data?.source_provenance?.classification !== 'llm_role_assessment') return;
        const pd = pattern.pattern_data || {};
        const rounds = pd.assessment_rounds || [];
        const rps = pd.round_patterns || {};
        setRoundSettings(prev => {
            const next = { ...prev };
            for (const { key } of ROUND_OPTIONS) {
                const rp = rps[key] || {};
                next[key] = {
                    enabled: rounds.includes(key),
                    question_count: rp.question_count || prev[key].question_count,
                    duration_minutes: rp.duration_minutes || prev[key].duration_minutes,
                    difficulty_distribution: rp.difficulty_distribution || prev[key].difficulty_distribution,
                };
            }
            return next;
        });
    }, [pattern]);

    const hasCompatibleHistoricalSource = sources.some(source => {
        const raw = source.raw_data || {};
        if (raw.source_provenance?.classification === 'generic_fallback') return false;
        if (source.source_type !== 'pre_seeded') return true;
        return !String(raw.benchmark_reference || '').toLowerCase().startsWith('generic benchmark -');
    });

    if (!isOpen) return null;

    // Handle Quick Select from existing drives
    const handleSelectDrive = (drive) => {
        setCompanyName(drive.company_name);
        setTargetRole(drive.target_role);
        loadCompanyData(drive.company_name, drive.target_role);
    };

    // ── Generate / Recalculate Pattern ────────────────────────────────────
    const handleGeneratePattern = async (allowFallback = false) => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }
        setActionLoading(true);
        try {
            const res = await api.post('/tpo/company-data/pattern/generate', {
                company_name: companyName.trim(),
                target_role: targetRole.trim(),
                use_fallback: allowFallback,
            });
            setPattern(res.data);
            setActiveTab('pattern');
            onToast?.({
                type: 'success',
                message: ['generic_fallback', 'pre_seeded_benchmark'].includes(res.data.pattern_data?.source_provenance?.classification)
                    ? 'Generated pattern using EDI5 benchmark fallback.'
                    : 'Structured pattern generated successfully from evidence.',
            });
            loadCompanyData(companyName, targetRole);
        } catch (err) {
            onToast?.({
                type: 'error',
                message: formatApiErrorDetail(err.response?.data?.detail, 'Failed to generate pattern.'),
            });
        } finally {
            setActionLoading(false);
        }
    };

    const handleConfigureHistoricalRounds = async () => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }
        const { configuredRounds, deselectedRounds, addedRounds: payloadAddedRounds } = buildHistoricalRoundPayload(historicalConfig);
        if (!configuredRounds.length && !deselectedRounds.length) {
            onToast?.({
                type: 'error',
                message: 'Select and configure at least one assessment round, or deselect every round explicitly.',
            });
            return;
        }
        const incompleteRounds = configuredRounds.filter(
            r => !r.question_count || !r.duration_minutes || !r.difficulty_distribution
        );
        if (incompleteRounds.length) {
            onToast?.({
                type: 'error',
                message: `Round(s) ${incompleteRounds.map(r => r.round_type.replace('_', ' ')).join(', ')} still require question count, duration and difficulty before saving.`,
            });
            return;
        }
        setActionLoading(true);
        try {
            const res = await api.post('/tpo/company-data/pattern/generate', {
                company_name: companyName.trim(),
                target_role: targetRole.trim(),
                added_rounds: [...new Set([...addedRounds, ...payloadAddedRounds])],
                round_configuration: configuredRounds,
                deselected_rounds: deselectedRounds,
            });
            setPattern(res.data);
            setActiveTab('pattern');
            setConfigDirty(false);
            const stillBlockedLabels = ROUND_OPTIONS
                .filter(({ key }) => historicalConfig[key]?.enabled)
                .filter(({ key }) => res.data?.pattern_data?.round_patterns?.[key]?.requires_tpo_configuration)
                .map(({ label }) => label);
            if (stillBlockedLabels.length) {
                onToast?.({
                    type: 'warning',
                    message: `Round settings saved, but ${stillBlockedLabels.join(', ')} still need more details (question count, duration, difficulty and topics) before the blueprint can be generated.`,
                });
            } else {
                onToast?.({
                    type: 'success',
                    message: 'Assessment rounds saved.',
                });
            }
            await loadCompanyData(companyName, targetRole);
        } catch (err) {
            onToast?.({
                type: 'error',
                message: formatApiErrorDetail(err.response?.data?.detail, 'Failed to configure historical pattern rounds.'),
            });
        } finally {
            setActionLoading(false);
        }
    };

    const handleGenerateRoleAssessment = async () => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company and role are required.' });
            return;
        }
        const configuredRounds = ROUND_OPTIONS.filter(({ key }) => roundSettings[key].enabled).map(({ key }) => ({
            round_type: key,
            question_count: Number(roundSettings[key].question_count),
            duration_minutes: Number(roundSettings[key].duration_minutes),
            difficulty_distribution: roundSettings[key].difficulty_distribution,
        }));
        if (!configuredRounds.length) {
            onToast?.({ type: 'error', message: 'Select and configure at least one assessment round.' });
            return;
        }
        setActionLoading(true);
        try {
            const res = await api.post('/tpo/company-data/role-assessment/generate', {
                company_name: companyName.trim(),
                target_role: targetRole.trim(),
                rounds: configuredRounds,
                job_description: jobDescription.trim() || null,
            });
            setPattern(res.data);
            setActiveTab('pattern');
            onToast?.({ type: 'success', message: 'Role assessment generated as a draft pattern. TPO review is required.' });
            await loadCompanyData(companyName, targetRole);
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({ type: 'error', message: typeof detail === 'string' ? detail : (detail?.message || 'Role assessment generation failed.') });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Review & Approve Pattern ──────────────────────────────────────────
    const handleReviewPattern = async (statusVal) => {
        if (!pattern) return;
        setActionLoading(true);
        try {
            const res = await api.post(
                `/tpo/company-data/pattern/${encodeURIComponent(companyName.trim())}/${encodeURIComponent(targetRole.trim())}/review`,
                {
                    status: statusVal,
                    notes: reviewNotes.trim() || undefined,
                }
            );
            setPattern(res.data);
            onToast?.({
                type: 'success',
                message: statusVal === 'approved' ? 'Pattern reviewed and approved for blueprints ✓' : 'Pattern flagged for revision.',
            });
            await loadCompanyData(companyName, targetRole);
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to review pattern.',
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Phase 4B: Generate Assessment Blueprint ───────────────────────────
    const handleGenerateBlueprint = async (force = false) => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }
        // Never request a generation the backend always refuses with 409: an LLM
        // role-assessment blueprint already exists and is never overwritten.
        const decision = resolveBlueprintGenerationRequest({
            hasBlueprint: Boolean(blueprint),
            force,
            provenance: blueprint?.blueprint_data?.source_provenance
                || pattern?.pattern_data?.source_provenance
                || null,
        });
        if (!decision.allowed) {
            onToast?.({ type: 'warning', message: decision.message });
            return;
        }
        setActionLoading(true);
        try {
            const res = await api.post('/tpo/company-data/blueprint/generate', {
                company_name: companyName.trim(),
                target_role: targetRole.trim(),
                force: force,
            });
            setBlueprint(res.data);
            setBlueprintDraft(res.data.blueprint_data?.rounds || []);
            setBlueprintCompetencies(res.data.blueprint_data?.competencies || []);
            setBlueprintNotes(res.data.review_notes || '');
            setActiveTab('blueprint');
            onToast?.({
                type: 'success',
                message: `Assessment Blueprint (v${res.data.version}) generated successfully from approved pattern.`,
            });
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : (detail?.message || 'Failed to generate assessment blueprint.'),
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Phase 4B: Save Blueprint Draft Edits ──────────────────────────────
    const handleSaveBlueprintDraft = async () => {
        if (!blueprint || !blueprintDraft) return;
        setActionLoading(true);
        try {
            const res = await api.put(
                `/tpo/company-data/blueprint/${encodeURIComponent(companyName.trim())}/${encodeURIComponent(targetRole.trim())}`,
                {
                    rounds: blueprintDraft,
                    review_notes: blueprintNotes.trim() || undefined,
                    competencies: blueprintCompetencies.length > 0 ? blueprintCompetencies : undefined,
                }
            );
            setBlueprint(res.data);
            onToast?.({ type: 'success', message: 'Blueprint changes saved successfully.' });
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to save blueprint edits.',
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Phase 4B: Approve Assessment Blueprint ────────────────────────────
    const handleApproveBlueprint = async () => {
        if (!blueprint) return;
        setActionLoading(true);
        try {
            const res = await api.post(
                `/tpo/company-data/blueprint/${encodeURIComponent(companyName.trim())}/${encodeURIComponent(targetRole.trim())}/approve`,
                {
                    status: 'approved',
                    notes: blueprintNotes.trim() || undefined,
                }
            );
            setBlueprint(res.data);
            onBlueprintApproved?.(res.data);
            onToast?.({ type: 'success', message: 'Assessment Blueprint approved for company drives ✓' });
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to approve blueprint.',
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Question Pool: generation handler (status fetch lives above) ──────
    const handleGenerateQuestionPools = async () => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }
        setPoolGenerating(true);
        try {
            const res = await api.post(`/tpo/company-data/blueprint/${encodeURIComponent(companyName.trim())}/${encodeURIComponent(targetRole.trim())}/question-pool/generate`);
            setPoolStatus(res.data || { rounds: [], blueprint_version: null });
            const incomplete = (res.data?.rounds || []).filter(r => r.status === 'incomplete' || r.status === 'failed');
            if (incomplete.length > 0) {
                onToast?.({
                    type: 'error',
                    message: 'Question pools generated with errors. Review the round statuses below.',
                });
            } else {
                onToast?.({ type: 'success', message: 'Question pools generated and validated successfully ✓' });
            }
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : (detail?.message || 'Failed to generate question pools.'),
            });
        } finally {
            setPoolGenerating(false);
        }
    };

    // ── Generate Competency Suggestions ────────────────────────────────────
    const handleGenerateCompetencies = async () => {
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }
        if (!blueprint) {
            onToast?.({ type: 'error', message: 'No blueprint available. Generate a blueprint first.' });
            return;
        }
        if (blueprintCompetencies.length > 0) {
            const confirmed = window.confirm(
                'This will replace your current unsaved competency draft with generated suggestions. Continue?'
            );
            if (!confirmed) return;
        }
        setCompetencyGenerating(true);
        try {
            const res = await api.post(
                `/tpo/company-data/blueprint/${encodeURIComponent(companyName.trim())}/${encodeURIComponent(targetRole.trim())}/competencies/generate`
            );
            const suggestions = res.data?.competencies || [];
            if (!suggestions.length) {
                onToast?.({ type: 'warning', message: 'No competency suggestions were generated.' });
                return;
            }
            // Validate weights sum to 100 before populating
            const totalWeight = suggestions.reduce((sum, c) => sum + (Number(c.weight_pct) || 0), 0);
            if (Math.abs(totalWeight - 100) > 0.1) {
                onToast?.({ type: 'error', message: `Generated weights sum to ${totalWeight}%, not 100%. Please report this issue.` });
                return;
            }
            // Check for duplicate names/ids
            const names = new Set(suggestions.map(c => c.name?.toLowerCase()));
            const ids = new Set(suggestions.map(c => c.id?.toLowerCase()));
            if (names.size !== suggestions.length || ids.size !== suggestions.length) {
                onToast?.({ type: 'error', message: 'Generated competencies contain duplicate names or IDs.' });
                return;
            }
            setBlueprintCompetencies(suggestions);
            onToast?.({ type: 'success', message: `Generated ${suggestions.length} competency suggestions. Review and save.` });
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : (detail?.message || 'Failed to generate competency suggestions.'),
            });
        } finally {
            setCompetencyGenerating(false);
        }
    };

    // ── Save Manual Record ────────────────────────────────────────────────
    const handleSaveManualRecord = async (e) => {
        e.preventDefault();
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }

        setActionLoading(true);
        try {
            const topicsList = manualForm.topics
                .split(',')
                .map(t => t.trim())
                .filter(Boolean);

            await api.post('/tpo/company-data/historical', {
                company_name: companyName.trim(),
                target_role: targetRole.trim(),
                label: manualForm.label.trim() || 'Historical Campus Drive',
                raw_data: {
                    year: Number(manualForm.year) || new Date().getFullYear(),
                    rounds: manualForm.rounds,
                    topics: topicsList,
                    difficulty: manualForm.difficulty,
                    question_types: manualForm.question_types,
                    duration_minutes: Number(manualForm.duration_minutes) || 90,
                    notes: manualForm.notes.trim(),
                },
            });

            onToast?.({ type: 'success', message: 'Historical drive entry added.' });
            setManualForm({
                label: 'Historical Campus Drive',
                year: new Date().getFullYear(),
                rounds: ['aptitude', 'coding'],
                topics: '',
                difficulty: 'medium',
                question_types: ['MCQ', 'Coding'],
                duration_minutes: 90,
                notes: '',
            });
            await loadCompanyData(companyName, targetRole);
            setActiveTab('sources');
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to save historical drive.',
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Upload File ──────────────────────────────────────────────────────
    const handleUploadFile = async (e) => {
        e.preventDefault();
        if (!uploadFile) {
            onToast?.({ type: 'error', message: 'Please select a file to upload.' });
            return;
        }
        if (!companyName.trim() || !targetRole.trim()) {
            onToast?.({ type: 'error', message: 'Company name and target role are required.' });
            return;
        }

        setActionLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', uploadFile);
            formData.append('company_name', companyName.trim());
            formData.append('target_role', targetRole.trim());
            formData.append('label', uploadLabel.trim() || uploadFile.name);

            await api.post('/tpo/company-data/historical/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            onToast?.({ type: 'success', message: `Extracted & normalized '${uploadFile.name}' successfully.` });
            setUploadFile(null);
            setUploadLabel('');
            await loadCompanyData(companyName, targetRole);
            setActiveTab('sources');
        } catch (err) {
            const detail = err.response?.data?.detail;
            onToast?.({
                type: 'error',
                message: typeof detail === 'string' ? detail : 'Failed to upload historical file.',
            });
        } finally {
            setActionLoading(false);
        }
    };

    // ── Delete Source ────────────────────────────────────────────────────
    const handleDeleteSource = async (sourceId) => {
        if (!window.confirm('Delete this historical data source?')) return;
        try {
            await api.delete(`/tpo/company-data/historical/${sourceId}`);
            onToast?.({ type: 'success', message: 'Historical source deleted.' });
            loadCompanyData(companyName, targetRole);
        } catch (err) {
            onToast?.({ type: 'error', message: 'Failed to delete historical source.' });
        }
    };

    const patternData = pattern?.pattern_data || {};
    const isPatternApproved = patternData.review_status === 'approved';
    const isBlueprintApproved = blueprint?.status === 'approved';
    const isRoleAssessmentBlueprint = isRoleAssessmentProvenance(blueprint?.blueprint_data?.source_provenance);
    const isLlmpattern = patternData.source_provenance?.classification === 'llm_role_assessment';
    const llmPendingPattern = Boolean(pattern && isLlmpattern && !isPatternApproved);
    // Historical patterns always surface the Assessment Rounds area so the TPO can
    // review evidence-derived rounds, edit details, and explicitly add a round.
    const historicalPattern = Boolean(pattern && !isLlmpattern);

    const matchedDrive = (existingDrives || []).find(
        d => d.company_name?.toLowerCase() === companyName?.toLowerCase() &&
             d.target_role?.toLowerCase() === targetRole?.toLowerCase()
    );

    const driveRounds = getConfiguredMockDriveRounds(matchedDrive);

    // Generated Question Pool card shows the DRIVE's configured counts (15/5/7),
    // never the internal validated-pool capacity (30/10/10).
    const driveFacingPoolRounds = buildDriveFacingPoolRounds({
        poolRounds: poolStatus.rounds || [],
        driveRoundConfigurations: matchedDrive?.round_configurations || {},
        blueprintRounds: blueprint?.blueprint_data?.rounds || [],
    });

    const patternRounds = patternData.assessment_rounds || [];
    // Only this pattern's rounds (evidence-derived or TPO-added) are presented
    // as stages; a round that was never in the evidence is never shown unless
    // the TPO explicitly added it.
    const progressionRounds = patternRounds.length > 0 ? patternRounds : driveRounds;

    // Build a blueprint round from the structured pattern's own data so a round
    // added on the Blueprint tab is never empty: it inherits this round's
    // role-specific topics, weights, and configuration from the pattern (the
    // single source of truth). Falls back to per-round defaults only when the
    // pattern has no data at all for that round.
    const blueprintRoundFromPattern = (rKey, roundOrder) => {
        const roundDefaults = {
            aptitude: { name: 'Aptitude Assessment', duration: 45, count: 25, types: ['MCQ'] },
            coding: { name: 'Coding Assessment', duration: 60, count: 2, types: ['Coding'] },
            technical_interview: { name: 'Technical Interview', duration: 45, count: 3, types: ['System Design', 'Core CS'] },
            hr_interview: { name: 'HR & Behavioral Interview', duration: 30, count: 3, types: ['Behavioral'] },
        };
        const def = roundDefaults[rKey] || { name: rKey.replace('_', ' '), duration: 45, count: 3, types: ['General'] };
        const rp = patternData.round_patterns?.[rKey] || {};
        const focusAreas = rp.focus_areas && rp.focus_areas.length > 0
            ? rp.focus_areas
            : (patternData.topic_frequency || [])
                .filter(f => f.typical_round === rKey)
                .map(f => f.topic);
        const weights = rp.topic_weights || {};
        const topics = [...new Set(focusAreas)].slice(0, 6).map(name => {
            const tf = (patternData.topic_frequency || []).find(
                f => String(f.topic).toLowerCase() === String(name).toLowerCase()
            );
            return {
                topic: name,
                weight_pct: typeof weights[name] === 'number'
                    ? Math.round(weights[name] * 10) / 10
                    : (tf?.frequency_pct
                        ? Math.round(tf.frequency_pct * 10) / 10
                        : Math.round((100 / Math.max(focusAreas.length, 1)) * 10) / 10),
                category: tf?.category || 'General',
                is_default: false,
            };
        });
        return {
            round_type: rKey,
            round_order: roundOrder,
            round_name: def.name,
            time_limit_minutes: rp.duration_minutes || def.duration,
            question_count: rp.question_count || def.count,
            question_types: def.types,
            topics,
            difficulty_distribution: rp.difficulty_distribution || { easy: 0.25, medium: 0.50, hard: 0.25 },
            is_default_fallback: false,
        };
    };

    // Shared round-selection + configuration panel for starting a new LLM role
    // assessment. Every round starts OFF; the TPO owns counts, duration and
    // difficulty — the LLM only fills role-specific topics for these rounds.
    // Shown only once the TPO has provided the target company and role.
    const roleAssessmentPanel = companyName.trim() && targetRole.trim() ? (
        <React.Fragment>
            <div className="w-full max-w-xl text-left rounded-xl border border-slate-200 p-4 space-y-3">
                <h4 className="text-xs font-bold text-slate-800">Configured Assessment Rounds</h4>
                {ROUND_OPTIONS.map(({ key, label }) => {
                    const setting = roundSettings[key];
                    return <div key={key} className="rounded-lg border border-slate-200 p-3">
                        <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                            <input type="checkbox" checked={setting.enabled} onChange={event => setRoundSettings(prev => ({ ...prev, [key]: { ...prev[key], enabled: event.target.checked } }))} />{label}
                        </label>
                        {setting.enabled && <div className="mt-2 grid grid-cols-3 gap-2">
                            <label className="text-[10px] text-slate-500">Questions<input type="number" min="1" max="100" value={setting.question_count} onChange={event => setRoundSettings(prev => ({ ...prev, [key]: { ...prev[key], question_count: event.target.value } }))} className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800" /></label>
                            <label className="text-[10px] text-slate-500">Minutes<input type="number" min="5" max="300" value={setting.duration_minutes} onChange={event => setRoundSettings(prev => ({ ...prev, [key]: { ...prev[key], duration_minutes: event.target.value } }))} className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800" /></label>
                            <label className="text-[10px] text-slate-500">Difficulty<select value={setting.difficulty_distribution.easy === 1 ? 'easy' : setting.difficulty_distribution.medium === 1 ? 'medium' : setting.difficulty_distribution.hard === 1 ? 'hard' : 'mixed'} onChange={event => { const distributions = { easy: { easy: 1, medium: 0, hard: 0 }, medium: { easy: 0, medium: 1, hard: 0 }, hard: { easy: 0, medium: 0, hard: 1 }, mixed: DEFAULT_DIFFICULTY }; setRoundSettings(prev => ({ ...prev, [key]: { ...prev[key], difficulty_distribution: distributions[event.target.value] } })); }} className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800"><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="mixed">Mixed</option></select></label>
                        </div>}
                    </div>;
                })}
            </div>
            <textarea value={jobDescription} onChange={event => setJobDescription(event.target.value)} maxLength={12000} placeholder="Optional job description or role context" aria-label="Optional job description" className="w-full max-w-xl px-3 py-2 rounded-lg border border-slate-300 text-xs text-slate-800" rows={3} />
            <button
                onClick={handleGenerateRoleAssessment}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-xs font-bold shadow-sm transition-all"
            >
                {actionLoading ? 'Synthesizing role assessment…' : llmPendingPattern ? 'Recalculate Pattern' : 'Generate Role Assessment'}
            </button>
        </React.Fragment>
    ) : (
        <p className="text-xs text-slate-500 max-w-xl text-left">
            Enter the target company and role to configure assessment rounds.
        </p>
    );

    const patternAssessmentRounds = patternData.assessment_rounds || [];
    // A round is configurable when the panel has an entry for it (enabled or
    // explicitly deselected) — not only when it is currently enabled.
    const hasConfigurableRounds = ROUND_OPTIONS.some(({ key }) => historicalConfig[key]?.initialized);
    // Rounds the TPO can still explicitly add (not already shown in the panel,
    // not already evidence-derived and not already queued as TPO-added).
    const addableRounds = ROUND_OPTIONS.filter(
        ({ key }) => !patternAssessmentRounds.includes(key) && !historicalConfig[key]?.initialized && !addedRounds.includes(key)
    );

    const handleAddAssessmentRound = (key) => {
        setAddedRounds(prev => (prev.includes(key) ? prev : [...prev, key]));
        editHistoricalConfig(prev => (prev[key] && prev[key].initialized
            ? prev
            : {
                ...prev,
                [key]: {
                    initialized: true,
                    enabled: true,
                    question_count: '',
                    duration_minutes: '',
                    difficulty_distribution: null,
                    focus_areas: [],
                    round_origin: 'tpo_added',
                    evidence_question_count: null,
                    evidence_duration_minutes: null,
                    evidence_difficulty_distribution: null,
                },
            }));
        setShowAddRoundMenu(false);
    };

    // Panel: review and configure the assessment rounds (evidence-derived or
    // TPO-added) on the historical pattern. Evidence values are prefilled and
    // editable; fields the evidence does not provide are shown as "—" for the
    // TPO to fill in. The configuration is persisted back through
    // /pattern/generate (round_configuration + added_rounds).
    const historicalConfigPanel = historicalPattern ? (
        <React.Fragment>
            <div className="w-full max-w-xl text-left rounded-xl border border-indigo-100 p-4 space-y-3">
                {ROUND_OPTIONS.map(({ key, label }) => {
                    const cfg = historicalConfig[key];
                    if (!cfg) return null;
                    const isEvidenceRound = cfg.round_origin === 'evidence';
                    const selectedTopics = cfg.focus_areas || [];
                    // Topics the TPO may choose for this round: taxonomy-attributed
                    // topics PLUS any topics the document already supported for this
                    // round (contextual enrichment, e.g. Software Engineering &
                    // Design Patterns under Coding). Topics outside that set are
                    // rejected by the backend and therefore not offered.
                    const availableTopics = (pattern?.pattern_data?.topic_frequency || [])
                        .filter(item => item.typical_round === key || selectedTopics.includes(item.topic))
                        .map(item => item.topic);
                    return (
                        <div key={key} className="rounded-lg border border-slate-200 p-3">
                            <div className="flex items-center justify-between gap-2">
                                <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                                    <input type="checkbox" checked={cfg.enabled}
                                        onChange={event => editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], enabled: event.target.checked } }))} />
                                    {label}
                                </label>
                                <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${isEvidenceRound ? 'bg-emerald-50 text-emerald-700' : 'bg-violet-50 text-violet-700'}`}>
                                    {isEvidenceRound ? 'From evidence' : 'Added by TPO'}
                                </span>
                            </div>
                            {cfg.enabled && (<>
                                <div className="mt-2 grid grid-cols-3 gap-2">
                                    <label className="text-[10px] text-slate-500">
                                        Questions
                                        <input type="number" min="1" max="100" value={cfg.question_count}
                                            placeholder="—"
                                            onChange={event => editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], question_count: event.target.value } }))}
                                            className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800" />
                                    </label>
                                    <label className="text-[10px] text-slate-500">
                                        Duration (mins)
                                        <input type="number" min="5" max="300" value={cfg.duration_minutes}
                                            placeholder="—"
                                            onChange={event => editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], duration_minutes: event.target.value } }))}
                                            className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800" />
                                    </label>
                                    <label className="text-[10px] text-slate-500">
                                        Difficulty
                                        <select
                                            value={!cfg.difficulty_distribution ? '' : cfg.difficulty_distribution.easy === 1 ? 'easy' : cfg.difficulty_distribution.medium === 1 ? 'medium' : cfg.difficulty_distribution.hard === 1 ? 'hard' : 'mixed'}
                                            onChange={event => {
                                                const distributions = { easy: { easy: 1, medium: 0, hard: 0 }, medium: { easy: 0, medium: 1, hard: 0 }, hard: { easy: 0, medium: 0, hard: 1 }, mixed: DEFAULT_DIFFICULTY };
                                                editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], difficulty_distribution: distributions[event.target.value] || null } }));
                                            }}
                                            className="mt-1 w-full rounded border px-2 py-1 text-xs text-slate-800">
                                            <option value="" disabled>—</option>
                                            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="mixed">Mixed</option>
                                        </select>
                                    </label>
                                </div>
                                <div className="mt-3">
                                    <span className="text-[10px] text-slate-500">Topics</span>
                                    {availableTopics.length ? (
                                        <>
                                            <div className="mt-1 flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                                                {availableTopics.map(topic => (
                                                    <label key={topic} className="inline-flex items-center gap-1 text-[10px] border border-slate-200 rounded px-1.5 py-0.5 cursor-pointer bg-white text-slate-700">
                                                        <input
                                                            type="checkbox"
                                                            value={topic}
                                                            checked={selectedTopics.includes(topic)}
                                                            onChange={event => {
                                                                editHistoricalConfig(prev => {
                                                                    const current = prev[key]?.focus_areas || [];
                                                                    const nextTopics = event.target.checked
                                                                        ? [...current, event.target.value]
                                                                        : current.filter(t => t !== event.target.value);
                                                                    return { ...prev, [key]: { ...prev[key], focus_areas: nextTopics } };
                                                                });
                                                            }}
                                                            className="accent-indigo-600"
                                                        />
                                                        {topic}
                                                    </label>
                                                ))}
                                            </div>
                                            <div className="mt-1 flex gap-2">
                                                <button type="button" onClick={() => editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], focus_areas: availableTopics } }))} className="text-[9px] text-indigo-600 underline">Select all</button>
                                                <button type="button" onClick={() => editHistoricalConfig(prev => ({ ...prev, [key]: { ...prev[key], focus_areas: [] } }))} className="text-[9px] text-slate-500 underline">Clear selection</button>
                                            </div>
                                        </>
                                    ) : (
                                        <p className="mt-1 text-[10px] text-slate-500">
                                            No topics were mentioned in this document for this round.
                                        </p>
                                    )}
                                </div>
                            </>)}
                        </div>
                    );
                })}
                {addableRounds.length > 0 && (
                    <div className="pt-1">
                        <button
                            type="button"
                            onClick={() => setShowAddRoundMenu(prev => !prev)}
                            className="text-[11px] font-bold text-indigo-600 border border-indigo-200 rounded-lg px-3 py-1.5 hover:bg-indigo-50"
                        >
                            + Add Assessment Round
                        </button>
                        {showAddRoundMenu && (
                            <div className="mt-2 flex flex-wrap gap-2">
                                {addableRounds.map(({ key, label }) => (
                                    <button
                                        key={key}
                                        type="button"
                                        onClick={() => handleAddAssessmentRound(key)}
                                        className="text-[11px] font-medium text-slate-700 border border-slate-300 rounded-lg px-3 py-1.5 hover:bg-slate-50"
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
            <button
                onClick={handleConfigureHistoricalRounds}
                disabled={actionLoading || !hasConfigurableRounds || !configDirty}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all disabled:opacity-50"
            >
                {actionLoading ? 'Saving configuration…' : (configDirty ? 'Save Round Configuration' : 'Saved')}
            </button>
        </React.Fragment>
    ) : null;

    return (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
            <div className="bg-white border border-slate-200 rounded-3xl shadow-2xl w-full max-w-5xl my-8 overflow-hidden flex flex-col max-h-[92vh]">

                {/* ── Modal Header ────────────────────────────────────────── */}
                <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs text-slate-300 font-medium">
                                Company Historical Patterns &amp; Assessment Blueprints
                            </span>
                        </div>
                        <h2 className="text-xl font-bold tracking-tight">
                            Company Assessment Blueprint &amp; Historical Foundation
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white flex items-center justify-center text-sm font-bold transition-all"
                    >
                        ✕
                    </button>
                </div>

                {/* ── Company + Role Selector Bar ─────────────────────────── */}
                <div className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full md:w-2/3">
                        <div>
                            <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                                Target Company
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Google, Amazon, Microsoft, TCS"
                                value={companyName}
                                onChange={e => setCompanyName(e.target.value)}
                                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                        <div>
                            <label className="block text-[11px] font-bold text-slate-600 uppercase mb-1">
                                Target Role
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Software Engineer, SDE-1, Digital / Prime"
                                value={targetRole}
                                onChange={e => setTargetRole(e.target.value)}
                                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                        </div>
                    </div>

                    {/* Quick Select from existing drives */}
                    {existingDrives.length > 0 && (
                        <div className="w-full md:w-1/3">
                            <label className="block text-[11px] font-bold text-slate-500 uppercase mb-1">
                                Quick Fill From Drives
                            </label>
                            <select
                                onChange={e => {
                                    const dr = existingDrives.find(d => String(d.id) === e.target.value);
                                    if (dr) handleSelectDrive(dr);
                                }}
                                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none"
                                defaultValue=""
                            >
                                <option value="" disabled>Select existing drive...</option>
                                {existingDrives.map(d => (
                                    <option key={d.id} value={d.id}>
                                        {d.company_name} — {d.target_role}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                {/* ── Sub Navigation Tabs ─────────────────────────────────── */}
                <div className="px-6 border-b border-slate-200 flex items-center justify-between bg-white flex-wrap gap-2">
                    <div className="flex items-center gap-1 sm:gap-2">
                        {[
                            { id: 'pattern', label: `Structured Pattern ${pattern ? (isPatternApproved ? '✓' : '●') : ''}` },
                            { id: 'blueprint', label: `Assessment Blueprint ${blueprint ? (isBlueprintApproved ? '✓ (Approved)' : '● (Draft)') : ''}` },
                            { id: 'sources', label: `Evidence Sources (${sources.length})` },
                            { id: 'add_manual', label: '+ Log Past Drive' },
                            { id: 'upload_file', label: '📁 Upload File' },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`px-3 sm:px-4 py-3 text-xs font-bold border-b-2 transition-all ${
                                    activeTab === tab.id
                                        ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50'
                                        : 'border-transparent text-slate-500 hover:text-slate-800'
                                }`}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2 py-2">
                        {activeTab === 'blueprint' ? (
                            <button
                                onClick={() => handleGenerateBlueprint(true)}
                                disabled={actionLoading || !pattern || !isPatternApproved || isRoleAssessmentBlueprint}
                                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"
                            >
                                <span>⚡</span>
                                {actionLoading ? 'Synthesizing…' : blueprint ? 'Recalculate Blueprint' : 'Generate Blueprint'}
                            </button>
                        ) : (
                            <button
                                onClick={() => handleGeneratePattern(false)}
                                disabled={actionLoading || sources.length === 0}
                                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"
                            >
                                <span>⚡</span>
                                {actionLoading ? 'Synthesizing…' : pattern ? 'Recalculate Pattern' : 'Generate Pattern'}
                            </button>
                        )}
                    </div>
                </div>

                {/* ── Modal Body Content ──────────────────────────────────── */}
                <div className="p-6 overflow-y-auto flex-1 bg-slate-50/50">

                    {/* 1. PATTERN VIEW ────────────────────────────────────── */}
                    {activeTab === 'pattern' && (
                        <div>
                            {loading ? (
                                <div className="text-center py-16 text-slate-400 text-xs">Loading structured pattern...</div>
                            ) : pattern ? (
                                <div className="space-y-6">
                                    {pattern.pattern_data?.source_provenance?.classification === 'generic_fallback' && !blueprint && (
                                        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
                                            <span className="text-xs text-amber-900">This existing pattern uses the generic benchmark. Generate a role-specific draft to replace this pattern; its historical source record will remain unchanged.</span>
                                            {roleAssessmentPanel}
                                        </div>
                                    )}
                                    {pattern.pattern_data?.role_understanding && (
                                        <section className="bg-indigo-50 border border-indigo-200 rounded-2xl p-5 space-y-2">
                                            <div className="text-xs font-bold uppercase tracking-wide text-indigo-800">LLM role understanding</div>
                                            <p className="text-sm text-slate-700">{pattern.pattern_data.role_understanding.summary}</p>
                                            <div className="text-xs text-slate-600"><strong>Responsibilities:</strong> {(pattern.pattern_data.role_understanding.responsibilities || []).join(' · ')}</div>
                                            <div className="text-xs text-slate-600"><strong>Core skills:</strong> {(pattern.pattern_data.role_understanding.core_skills || []).join(' · ')}</div>
                                            <div className="text-[11px] text-indigo-700">Generated assessment; no historical company evidence was used. Review before approval.</div>
                                        </section>
                                    )}
                                    {/* Pattern Overview Banner */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
                                        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                                            <div>
                                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                    <span className="text-base font-bold text-slate-900">
                                                        {pattern.company_name} — {pattern.target_role}
                                                    </span>
                                                    {patternData.source_provenance?.classification === 'source_unverified' ? (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">Legacy Source Unverified</span>
                                                    ) : patternData.source_provenance?.pre_seeded_source_count > 0 && patternData.source_provenance?.empirical_source_count > 0 ? (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">Historical + Benchmark Sources</span>
                                                    ) : patternData.is_fallback || ['generic_fallback', 'pre_seeded_benchmark'].includes(patternData.source_provenance?.classification) ? (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">
                                                            {patternData.source_provenance?.classification === 'generic_fallback' ? 'Generic Benchmark Fallback' : 'Pre-seeded Benchmark'}
                                                        </span>
                                                    ) : patternData.source_provenance?.classification === 'llm_role_assessment' ? (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-violet-50 text-violet-700 border border-violet-300">
                                                            LLM Role Assessment
                                                        </span>
                                                    ) : (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                            Evidence Pattern Active
                                                        </span>
                                                    )}
                                                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                                                        patternData.confidence_level?.includes('high')
                                                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                            : patternData.confidence_level?.includes('medium')
                                                            ? 'bg-sky-50 text-sky-700 border-sky-200'
                                                            : 'bg-slate-100 text-slate-700 border-slate-300'
                                                    }`}>
                                                        Confidence: {String(patternData.confidence_level || 'Medium').split(' (')[0]}
                                                    </span>
                                                    {isPatternApproved ? (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                                            TPO Approved ✓
                                                        </span>
                                                    ) : (
                                                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                                                            Pending TPO Review
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-xs text-slate-500">
                                                    {patternData.source_provenance?.classification === 'source_unverified'
                                                        ? 'Legacy pattern provenance is unverified. Recalculate it from compatible evidence before generating a blueprint.'
                                                        : patternData.source_provenance?.pre_seeded_source_count > 0 && patternData.source_provenance?.empirical_source_count > 0
                                                            ? `Combines ${patternData.source_provenance.empirical_source_count} historical source(s) with ${patternData.source_provenance.pre_seeded_source_count} pre-seeded benchmark source(s).`
                                                        : ['generic_fallback', 'pre_seeded_benchmark'].includes(patternData.source_provenance?.classification)
                                                        ? `Generated from benchmark source(s), not company-specific historical evidence (${pattern.source_count} source(s)).`
                                                        : patternData.source_provenance?.classification === 'llm_role_assessment'
                                                        ? 'Role-specific assessment generated by LLM'
                                                        : `Based on ${patternData.source_provenance?.empirical_source_count ?? pattern.source_count} historical source(s)${patternData.evidence_count > 0 ? ` • ${patternData.evidence_count} evidence datapoints` : ''}${patternData.year_range?.length === 2 ? ` • Drives ${patternData.year_range[0]} – ${patternData.year_range[1]}` : ''}.`}
                                                </p>
                                            </div>

                                            <div className="flex items-center gap-3 text-xs">
                                                {isPatternApproved && (
                                                    <button
                                                        onClick={() => setActiveTab('blueprint')}
                                                        className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-sm flex items-center gap-1.5 transition-all"
                                                    >
                                                        <span>📋</span>
                                                        <span>Assessment Blueprint ➔</span>
                                                    </button>
                                                )}
                                                <div className="text-right pl-2 border-l border-slate-200">
                                                    <div className="text-[10px] uppercase font-bold text-slate-400">Difficulty</div>
                                                    <span className="font-extrabold capitalize text-indigo-700 text-sm">
                                                        {patternData.avg_difficulty || 'Medium'}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        {patternData.confidence_reasons && (
                                            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-600 flex items-center justify-between gap-3">
                                                <div className="flex items-center gap-2">
                                                    <span className="text-indigo-600 font-bold">ℹ️ Assessment Evidence:</span>
                                                    <span>{patternData.confidence_reasons}</span>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Progression Rounds */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                Standard Assessment Progression
                                            </div>
                                            <span className="text-[11px] text-slate-400">
                                                {progressionRounds.length} Sequential Rounds
                                            </span>
                                        </div>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                                            {progressionRounds.map((rnd, idx) => {
                                                const details = patternData.round_patterns?.[rnd] || {};
                                                // Explicit TPO-configured/evidence-exact values win over
                                                // evidence averages (historical patterns store avg_*).
                                                const stageQuestions = details.question_count || details.avg_question_count;
                                                const stageDuration = details.duration_minutes || details.avg_duration_minutes;
                                                const isEvidenceRound = details.round_origin === 'evidence';
                                                return (
                                                    <div key={rnd} className="bg-indigo-50/40 border border-indigo-100 rounded-xl p-3.5 flex flex-col justify-between">
                                                        <div>
                                                            <div className="flex items-center justify-between mb-1">
                                                                <span className="text-[10px] font-bold text-indigo-500 uppercase">
                                                                    Stage {idx + 1}
                                                                </span>
                                                                <span className="text-[10px] font-semibold text-slate-500">
                                                                    {stageDuration ? `${stageDuration} mins` : '—'}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center justify-between gap-1 mb-1">
                                                                <div className="text-xs font-bold text-slate-900 capitalize">
                                                                    {rnd.replace('_', ' ')}
                                                                </div>
                                                                <span className={`shrink-0 text-[8px] font-semibold px-1 py-0.5 rounded ${isEvidenceRound ? 'bg-emerald-50 text-emerald-700' : 'bg-violet-50 text-violet-700'}`}>
                                                                    {isEvidenceRound ? 'Evidence' : 'TPO-added'}
                                                                </span>
                                                            </div>
                                                            <div className="text-[11px] text-slate-500">
                                                                {stageQuestions ? `${stageQuestions} Questions` : '—'}
                                                            </div>
                                                        </div>
                                                        {details.focus_areas && details.focus_areas.length > 0 && (
                                                            <div className="mt-3 pt-2 border-t border-indigo-100/60 flex flex-wrap gap-1">
                                                                {details.focus_areas.map(f => (
                                                                    <span key={f} className="text-[9px] bg-white border border-indigo-200 text-indigo-700 px-1.5 py-0.5 rounded font-medium">
                                                                        {f}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {historicalPattern && (
                                        <div className="bg-white border border-dashed border-indigo-300 rounded-2xl p-4 space-y-3">
                                            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                Assessment Rounds
                                            </div>
                                            <p className="text-[11px] text-slate-500">
                                                Review the rounds identified from your historical data. You can edit the details or add another round.
                                            </p>
                                            {historicalConfigPanel}
                                        </div>
                                    )}

                                    {llmPendingPattern && (
                                        <div className="bg-white border border-dashed border-violet-300 rounded-2xl p-4">
                                            <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                                Add Round...
                                            </div>
                                            <p className="text-[11px] text-slate-500 mb-3">
                                                Toggle rounds on/off and configure counts, duration and difficulty, then click Recalculate Pattern. Unselected rounds are removed from the pattern and blueprint.
                                            </p>
                                            {roleAssessmentPanel}
                                        </div>
                                    )}

                                    {/* Topics & Difficulty */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                    Normalized Topic Frequency
                                                </div>
                                                <span className="text-[10px] text-slate-400">Canonical Taxonomy</span>
                                            </div>
                                            {patternData.topic_frequency && patternData.topic_frequency.length > 0 ? (
                                                <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                                                    {patternData.topic_frequency.map(tf => (
                                                        <div key={`${tf.typical_round || 'any'}:${tf.topic}`} className="flex items-center justify-between text-xs pb-1.5 border-b border-slate-100">
                                                            <div>
                                                                <div className="font-semibold text-slate-800">{tf.topic}</div>
                                                                <div className="text-[10px] text-slate-400 flex items-center gap-1.5">
                                                                    <span>{tf.category}</span>
                                                                    <span>•</span>
                                                                    <span>In {tf.sources_count || 1} source(s)</span>
                                                                </div>
                                                            </div>
                                                            <div className="flex items-center gap-2">
                                                                <span className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 font-bold text-[10px]">
                                                                    {tf.frequency_pct}%
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="text-xs text-slate-400">No specific topics extracted.</div>
                                            )}
                                        </div>

                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
                                            <div>
                                                <div className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                                                    Difficulty Distribution
                                                </div>
                                                <div className="flex h-3 rounded-full overflow-hidden bg-slate-100 border border-slate-200 mb-2">
                                                    <div style={{ width: `${(patternData.difficulty_distribution?.easy || 0) * 100}%` }} className="bg-emerald-500" title="Easy" />
                                                    <div style={{ width: `${(patternData.difficulty_distribution?.medium || 0) * 100}%` }} className="bg-amber-400" title="Medium" />
                                                    <div style={{ width: `${(patternData.difficulty_distribution?.hard || 0) * 100}%` }} className="bg-rose-500" title="Hard" />
                                                </div>
                                                <div className="flex items-center justify-between text-[11px] text-slate-500">
                                                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"/> Easy: {Math.round((patternData.difficulty_distribution?.easy || 0) * 100)}%</span>
                                                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block"/> Medium: {Math.round((patternData.difficulty_distribution?.medium || 0) * 100)}%</span>
                                                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-500 inline-block"/> Hard: {Math.round((patternData.difficulty_distribution?.hard || 0) * 100)}%</span>
                                                </div>
                                            </div>

                                            {/* TPO Pattern Review Action */}
                                            <div className="p-4 bg-indigo-50/50 rounded-xl border border-indigo-100 space-y-2.5">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-xs font-bold text-slate-800">TPO Verification Status</span>
                                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                                        isPatternApproved ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'
                                                    }`}>
                                                        {isPatternApproved ? 'Approved for Blueprints ✓' : 'Needs Review'}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2 pt-1">
                                                    {!isPatternApproved ? (
                                                        <button
                                                            onClick={() => handleReviewPattern('approved')}
                                                            disabled={actionLoading}
                                                            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition-all"
                                                        >
                                                            Approve Pattern ✓
                                                        </button>
                                                    ) : (
                                                        <button
                                                            onClick={() => handleReviewPattern('needs_revision')}
                                                            disabled={actionLoading}
                                                            className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold border border-slate-300 transition-all"
                                                        >
                                                            Flag for Revision
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center shadow-sm">
                                    <div className="text-4xl mb-3">📊</div>
                                    <h3 className="text-base font-bold text-slate-800 mb-1">
                                        No Structured Pattern Computed Yet
                                    </h3>
                                    <p className="text-xs text-slate-500 max-w-md mx-auto mb-5">
                                        {hasCompatibleHistoricalSource
                                            ? `You have ${sources.length} historical data source(s) logged for ${companyName} (${targetRole}). Click 'Generate Pattern' to synthesize rounds, skills, and difficulties.`
                                            : `No compatible historical evidence is available for ${companyName || 'this company'} and ${targetRole || 'this role'}. Generate a role-specific assessment draft or add historical evidence.`}
                                    </p>
                                    {hasCompatibleHistoricalSource ? (
                                        <button
                                            onClick={() => handleGeneratePattern(false)}
                                            disabled={actionLoading}
                                            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all"
                                        >
                                            ⚡ Generate Structured Pattern Now
                                        </button>
                                    ) : (
                                        <div className="flex flex-wrap items-center justify-center gap-3">
                                            {roleAssessmentPanel}
                                            <button
                                                onClick={() => setActiveTab('add_manual')}
                                                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold border border-slate-300 transition-all"
                                            >
                                                + Log Past Drive Manually
                                            </button>
                                            <button
                                                onClick={() => setActiveTab('upload_file')}
                                                className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold border border-slate-300 transition-all"
                                            >
                                                📁 Upload History File
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 2. PHASE 4B: ASSESSMENT BLUEPRINT VIEW ──────────────── */}
                    {activeTab === 'blueprint' && (
                        <div className="space-y-6">
                            {blueprint ? (
                                <div className="space-y-6">
                                    {/* Blueprint Header Card */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
                                        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                                            <div>
                                                <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                    <span className="text-base font-bold text-slate-900">
                                                        {blueprint.company_name} — {blueprint.target_role}
                                                    </span>
                                                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                                                        isBlueprintApproved
                                                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                            : 'bg-amber-50 text-amber-700 border-amber-200'
                                                    }`}>
                                                        {isBlueprintApproved ? 'Approved Blueprint ✓' : 'Draft Blueprint'}
                                                    </span>
                                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                                        Version {blueprint.version}
                                                    </span>
                                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">
                                                        Confidence: {String(blueprint.confidence_level || 'Medium').split(' (')[0]}
                                                    </span>
                                                </div>
                                                <p className="text-xs text-slate-500">
                                                    {blueprint.blueprint_data?.source_provenance?.classification === 'source_unverified'
                                                        ? 'This saved blueprint has legacy source provenance that cannot be verified. Its saved snapshot remains unchanged.'
                                                        : blueprint.blueprint_data?.source_provenance?.pre_seeded_source_count > 0 && blueprint.blueprint_data?.source_provenance?.empirical_source_count > 0
                                                            ? `Blueprint derived from historical and pre-seeded benchmark sources (${blueprint.blueprint_data.source_provenance.empirical_source_count} historical source(s)).`
                                                        : blueprint.blueprint_data?.source_provenance?.classification === 'generic_fallback'
                                                        ? 'Blueprint derived from an explicitly selected generic benchmark; it is not company-specific historical evidence.'
                                                        : blueprint.blueprint_data?.source_provenance?.classification === 'pre_seeded_benchmark'
                                                            ? 'Blueprint derived from a pre-seeded role-compatible benchmark, not company-specific historical evidence.'
                                                        : blueprint.blueprint_data?.source_provenance?.classification === 'llm_role_assessment'
                                                        ? 'Blueprint derived from the LLM role assessment for this role'
                                                            : `Authoritative specification derived from historical evidence (${blueprint.evidence_sources_count} source(s)).`}
                                                </p>
                                            </div>

                                            <div className="flex items-center gap-2">
                                                {!isBlueprintApproved && (
                                                    <button
                                                        onClick={handleSaveBlueprintDraft}
                                                        disabled={actionLoading}
                                                        className="px-3.5 py-1.5 rounded-xl bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-bold transition-all"
                                                    >
                                                        Save Changes
                                                    </button>
                                                )}
                                                {!isBlueprintApproved ? (
                                                    <button
                                                        onClick={handleApproveBlueprint}
                                                        disabled={actionLoading}
                                                        className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"
                                                    >
                                                        <span>✓</span>
                                                        <span>Approve Blueprint</span>
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() => handleGenerateBlueprint(true)}
                                                        disabled={actionLoading || isRoleAssessmentBlueprint}
                                                        title={isRoleAssessmentBlueprint ? 'Role-assessment blueprints are never recalculated; the approved version is kept.' : undefined}
                                                        className="px-3.5 py-1.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 disabled:opacity-40 text-indigo-700 text-xs font-bold border border-indigo-200 transition-all"
                                                    >
                                                        Recalculate (New Version)
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Generated Question Pool (pre-candidate LLM) */}
                                    {isBlueprintApproved && (
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
                                            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                                                <div>
                                                    <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                        Generated Question Pool
                                                    </h3>
                                                </div>
                                                <button
                                                    onClick={handleGenerateQuestionPools}
                                                    disabled={poolGenerating}
                                                    className="px-3.5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 disabled:opacity-40 text-white text-xs font-bold shadow-sm transition-all flex items-center gap-1.5"
                                                >
                                                    <span>{poolGenerating ? '⏳' : '⚡'}</span>
                                                    {poolGenerating ? 'Generating Pools…' : 'Generate Question Pools'}
                                                </button>
                                            </div>
                                            {poolLoading ? (
                                                <div className="text-center py-8 text-slate-400 text-xs">Loading pool status...</div>
                                            ) : (
                                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                                                    {driveFacingPoolRounds.map(round => {
                                                        const chip = POOL_STATUS_CHIP[round.status] || POOL_STATUS_CHIP.not_generated;
                                                        return (
                                                            <div key={round.round_type} className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2">
                                                                <div className="flex items-center justify-between gap-2">
                                                                    <span className="text-xs font-bold text-slate-800 capitalize">
                                                                        {POOL_ROUND_LABELS[round.round_type] || round.round_type.replace('_', ' ')}
                                                                    </span>
                                                                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${chip.cls}`}>
                                                                        {chip.label}
                                                                    </span>
                                                                </div>
                                                                <div className="text-[11px] text-slate-500">
                                                                    {round.drive_count == null
                                                                        ? 'No question count configured for this round'
                                                                        : round.status === 'complete'
                                                                            ? `${round.drive_count} questions available from the validated pool`
                                                                            : `${round.drive_count} questions configured for this drive`}
                                                                </div>
                                                                {round.generation_error && (
                                                                    <div className="text-[10px] text-rose-600 break-words leading-snug" title={round.generation_error}>
                                                                        {round.generation_error}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                    {(poolStatus.rounds || []).length === 0 && (
                                                        <p className="text-xs text-slate-400 col-span-full">
                                                            No rounds in the approved blueprint to generate pools for.
                                                        </p>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Rounds Specification Grid */}
                                    <div className="space-y-4">
                                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                                            <div>
                                                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                    Configured Assessment Rounds ({blueprintDraft?.length || 0})
                                                </h3>
                                                <span className="text-[11px] text-slate-400">
                                                    Round weights and parameters
                                                </span>
                                            </div>
                                            {!isBlueprintApproved && (
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    {driveRounds.some(dr => (patternData.assessment_rounds || []).includes(dr) && !(blueprintDraft || []).some(r => r.round_type === dr)) && (
                                                        <button
                                                            type="button"
                                                            onClick={() => {
                                                                const missing = driveRounds.filter(dr => (patternData.assessment_rounds || []).includes(dr) && !(blueprintDraft || []).some(r => r.round_type === dr));
                                                                const nextRounds = [...(blueprintDraft || [])];
                                                                missing.forEach((rKey) => {
                                                                    nextRounds.push(blueprintRoundFromPattern(rKey, nextRounds.length + 1));
                                                                });
                                                                setBlueprintDraft(nextRounds);
                                                            }}
                                                            className="px-2.5 py-1 bg-violet-50 hover:bg-violet-100 text-violet-700 text-xs font-semibold rounded-lg border border-violet-200 transition-all flex items-center gap-1"
                                                        >
                                                            <span>↻</span> Sync from Drive Draft
                                                        </button>
                                                    )}
                                                    {(() => {
                                                        const candidates = (patternData.assessment_rounds || [])
                                                            .filter(k => !(blueprintDraft || []).some(r => r.round_type === k));
                                                        if (candidates.length === 0) return null;
                                                        return (
                                                            <select
                                                                id="blueprint-add-round"
                                                                defaultValue=""
                                                                onChange={e => {
                                                                    const rKey = e.target.value;
                                                                    if (!rKey) return;
                                                                    setBlueprintDraft([
                                                                        ...(blueprintDraft || []),
                                                                        blueprintRoundFromPattern(rKey, (blueprintDraft?.length || 0) + 1),
                                                                    ]);
                                                                    e.target.value = '';
                                                                }}
                                                                className="px-2.5 py-1 bg-white border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 focus:outline-none"
                                                            >
                                                                <option value="" disabled>+ Add Round...</option>
                                                                {candidates.map(k => (
                                                                    <option key={k} value={k}>+ Add {k.replace('_', ' ').toUpperCase()}</option>
                                                                ))}
                                                            </select>
                                                        );
                                                    })()}
                                                </div>
                                            )}
                                        </div>

                                        <div className="space-y-4">
                                            {(blueprintDraft || []).map((round, rIdx) => (
                                                <div key={round.round_type} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
                                                    <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pb-3 border-b border-slate-100">
                                                        <div className="flex items-center gap-3">
                                                            <span className="w-7 h-7 rounded-xl bg-indigo-600 text-white text-xs font-bold flex items-center justify-center">
                                                                {round.round_order || rIdx + 1}
                                                            </span>
                                                            <div>
                                                                <h4 className="text-sm font-bold text-slate-900">
                                                                    {round.round_name}
                                                                </h4>
                                                                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                                                                    <span className="capitalize font-semibold text-indigo-600">{round.round_type.replace('_', ' ')}</span>
                                                                    <span>•</span>
                                                                    <span>Types: {(round.question_types || []).join(', ')}</span>
                                                                    {round.is_default_fallback && (
                                                                        <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-[9px] font-bold">
                                                                            Fallback Default
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* Duration & Questions (Editable if draft) */}
                                                        <div className="flex items-center gap-3 text-xs">
                                                            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                                                                <span className="text-slate-500 font-medium">Time Limit:</span>
                                                                {!isBlueprintApproved ? (
                                                                    <input
                                                                        type="number"
                                                                        min="5"
                                                                        max="300"
                                                                        value={round.time_limit_minutes}
                                                                        onChange={e => {
                                                                            const val = Number(e.target.value);
                                                                            const next = [...blueprintDraft];
                                                                            next[rIdx].time_limit_minutes = val;
                                                                            setBlueprintDraft(next);
                                                                        }}
                                                                        className="w-14 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-xs font-bold text-slate-800 text-center"
                                                                    />
                                                                ) : (
                                                                    <span className="font-bold text-slate-800">{round.time_limit_minutes}</span>
                                                                )}
                                                                <span className="text-slate-500">mins</span>
                                                            </div>

                                                            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
                                                                <span className="text-slate-500 font-medium">Questions:</span>
                                                                {!isBlueprintApproved ? (
                                                                    <input
                                                                        type="number"
                                                                        min="1"
                                                                        max="100"
                                                                        value={round.question_count}
                                                                        onChange={e => {
                                                                            const val = Number(e.target.value);
                                                                            const next = [...blueprintDraft];
                                                                            next[rIdx].question_count = val;
                                                                            setBlueprintDraft(next);
                                                                        }}
                                                                        className="w-12 bg-white border border-slate-300 rounded px-1.5 py-0.5 text-xs font-bold text-slate-800 text-center"
                                                                    />
                                                                ) : (
                                                                    <span className="font-bold text-slate-800">{round.question_count}</span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Topic Distribution & Weights */}
                                                    <div>
                                                        <div className="text-[11px] font-bold text-slate-600 uppercase mb-2">
                                                            Topic Distribution &amp; Target Weights
                                                        </div>
                                                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                                                            {(round.topics || []).map((t, tIdx) => (
                                                                <div key={t.topic} className="bg-slate-50 border border-slate-200 rounded-xl p-2.5 flex items-center justify-between">
                                                                    <div>
                                                                        <div className="text-xs font-semibold text-slate-800">{t.topic}</div>
                                                                        <div className="text-[10px] text-slate-400">{t.category}</div>
                                                                    </div>
                                                                    <span className="px-2 py-0.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 font-bold text-xs">
                                                                        {t.weight_pct}%
                                                                    </span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Competency Configuration (Phase 4C) */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                                Role Competencies (Additive Layer)
                                            </h3>
                                            <span className="text-[10px] text-slate-500">
                                                Weights must sum to 100%. Topics reference canonical taxonomy.
                                            </span>
                                        </div>

                                        <div className="space-y-3">
                                            {blueprintCompetencies.length > 0 ? (
                                                blueprintCompetencies.map((comp, cIdx) => (
                                                    <div key={comp.id || comp.name || cIdx} className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                                                        <div className="flex items-center justify-between">
                                                            <h4 className="text-sm font-semibold text-slate-800">Competency {cIdx + 1}</h4>
                                                            {!isBlueprintApproved && (
                                                                <button
                                                                    type="button"
                                                                    onClick={() => {
                                                                        const next = blueprintCompetencies.filter((_, i) => i !== cIdx);
                                                                        setBlueprintCompetencies(next);
                                                                    }}
                                                                    className="text-rose-600 hover:text-rose-800 text-xs font-medium"
                                                                    title="Remove competency"
                                                                >
                                                                    Remove
                                                                </button>
                                                            )}
                                                        </div>

                                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                                            <label className="text-[10px] text-slate-500">
                                                                Name
                                                                <input
                                                                    type="text"
                                                                    value={comp.name}
                                                                    onChange={e => {
                                                                        const next = [...blueprintCompetencies];
                                                                        next[cIdx] = { ...next[cIdx], name: e.target.value };
                                                                        setBlueprintCompetencies(next);
                                                                    }}
                                                                    disabled={isBlueprintApproved}
                                                                    placeholder="e.g. Problem Solving"
                                                                    className="mt-1 w-full px-2 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                                                                    required
                                                                />
                                                            </label>
                                                            <label className="text-[10px] text-slate-500">
                                                                Weight (%)
                                                                <input
                                                                    type="number"
                                                                    min="1"
                                                                    max="100"
                                                                    step="0.1"
                                                                    value={comp.weight_pct}
                                                                    onChange={e => {
                                                                        const next = [...blueprintCompetencies];
                                                                        next[cIdx] = { ...next[cIdx], weight_pct: Number(e.target.value) || 0 };
                                                                        setBlueprintCompetencies(next);
                                                                    }}
                                                                    disabled={isBlueprintApproved}
                                                                    className="mt-1 w-full px-2 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                                                                    required
                                                                />
                                                            </label>
                                                            <label className="text-[10px] text-slate-500">
                                                                Stable ID (optional)
                                                                <input
                                                                    type="text"
                                                                    value={comp.id || ''}
                                                                    onChange={e => {
                                                                        const next = [...blueprintCompetencies];
                                                                        next[cIdx] = { ...next[cIdx], id: e.target.value.trim() || undefined };
                                                                        setBlueprintCompetencies(next);
                                                                    }}
                                                                    disabled={isBlueprintApproved}
                                                                    placeholder="Auto-generated from name"
                                                                    className="mt-1 w-full px-2 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                                                                />
                                                            </label>
                                                        </div>

                                                        <div>
                                                            <label className="block text-[10px] text-slate-500 mb-1">
                                                                Topics (canonical taxonomy names, one per line)
                                                            </label>
                                                            <textarea
                                                                value={Array.isArray(comp.topics) ? comp.topics.join('\n') : ''}
                                                                onChange={e => {
                                                                    const next = [...blueprintCompetencies];
                                                                    next[cIdx] = {
                                                                        ...next[cIdx],
                                                                        topics: e.target.value.split('\n').map(t => t.trim()).filter(Boolean)
                                                                    };
                                                                    setBlueprintCompetencies(next);
                                                                }}
                                                                disabled={isBlueprintApproved}
                                                                rows="3"
                                                                placeholder="Data Structures & Algorithms&#10;Dynamic Programming&#10;System Design"
                                                                className="w-full px-2 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                                                            />
                                                            <p className="text-[9px] text-slate-400 mt-1">
                                                                Enter canonical topic names from the taxonomy above. One per line.
                                                            </p>
                                                        </div>
                                                    </div>
                                                ))
                                            ) : (
                                                <p className="text-xs text-slate-400 text-center py-4">
                                                    No competencies configured. Add a competency to enable competency-based scoring.
                                                </p>
                                            )}

                                            {!isBlueprintApproved && (
                                                <div className="flex flex-col sm:flex-row gap-2 justify-center">
                                                    <button
                                                        type="button"
                                                        onClick={handleGenerateCompetencies}
                                                        disabled={competencyGenerating || !blueprint}
                                                        className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg border border-indigo-200 transition-all flex items-center gap-1.5 mx-auto disabled:opacity-50"
                                                    >
                                                        {competencyGenerating ? (
                                                            <>
                                                                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                                                                Generating…
                                                            </>
                                                        ) : (
                                                            <>
                                                                <span>⚡</span> Generate Competencies & Weights
                                                            </>
                                                        )}
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            setBlueprintCompetencies([
                                                                ...blueprintCompetencies,
                                                                { name: '', weight_pct: 0, topics: [] }
                                                            ]);
                                                        }}
                                                        className="px-3 py-1.5 bg-violet-50 hover:bg-violet-100 text-violet-700 text-xs font-semibold rounded-lg border border-violet-200 transition-all flex items-center gap-1.5 mx-auto"
                                                    >
                                                        <span>+</span> Add Competency
                                                    </button>
                                                </div>
                                            )}

                                            {blueprintCompetencies.length > 0 && (
                                                <div className={`text-xs text-center p-2 rounded ${weightTotal === 100 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200'}`}>
                                                    Total Weight: {weightTotal}% {weightTotal !== 100 && '— must equal 100% to save'}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Review Notes Area */}
                                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
                                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                                            Blueprint Notes &amp; Verification
                                        </label>
                                        <textarea
                                            value={blueprintNotes}
                                            onChange={e => setBlueprintNotes(e.target.value)}
                                            rows="2"
                                            placeholder="TPO notes regarding this blueprint approval..."
                                            disabled={isBlueprintApproved}
                                            className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-75"
                                        />
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center shadow-sm">
                                    <div className="text-4xl mb-3">📋</div>
                                    <h3 className="text-base font-bold text-slate-800 mb-1">
                                        No Assessment Blueprint Generated Yet
                                    </h3>
                                    <p className="text-xs text-slate-500 max-w-md mx-auto mb-5">
                                        {isPatternApproved
                                            ? `An approved structured pattern exists for ${companyName} (${targetRole}). Generate the formal Assessment Blueprint to configure exact round time limits, question counts, and topic weights.`
                                            : pattern
                                            ? `A structured pattern exists for ${companyName} (${targetRole}), but it must be approved by TPO on the Pattern tab first before generating the assessment blueprint.`
                                            : `No pattern exists for ${companyName || 'this company'}. Please generate and approve a Phase 4A pattern first.`}
                                    </p>
                                    {isPatternApproved ? (
                                        <button
                                            onClick={() => handleGenerateBlueprint(false)}
                                            disabled={actionLoading || loading}
                                            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all"
                                        >
                                            ⚡ Generate Assessment Blueprint from Approved Pattern
                                        </button>
                                    ) : pattern ? (
                                        <button
                                            onClick={() => setActiveTab('pattern')}
                                            className="px-4 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold border border-indigo-200 transition-all"
                                        >
                                            Go to Pattern Tab to Review &amp; Approve ➔
                                        </button>
                                    ) : (
                                        <button
                                            onClick={() => setActiveTab('pattern')}
                                            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-sm transition-all"
                                        >
                                            Go to Pattern Tab to Initialize Pattern
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 3. HISTORICAL SOURCES LIST ─────────────────────────── */}
                    {activeTab === 'sources' && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                                    Raw Historical Evidence Sources ({sources.length})
                                </h3>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => setActiveTab('add_manual')}
                                        className="px-3 py-1.5 rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-all"
                                    >
                                        + Manual Entry
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('upload_file')}
                                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-all"
                                    >
                                        📁 Upload File
                                    </button>
                                </div>
                            </div>

                            {sources.length === 0 ? (
                                <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center text-xs text-slate-500">
                                    No historical data sources recorded for {companyName || 'this company'} ({targetRole || 'this role'}).
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {sources.map(src => {
                                        const rdata = src.raw_data || {};
                                        return (
                                            <div key={src.id} className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                                                <div className="space-y-1">
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <span className="font-bold text-slate-900 text-xs">{src.label}</span>
                                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                                            src.source_type === 'pre_seeded'
                                                                ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                                                                : src.source_type === 'file_upload'
                                                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                                                : 'bg-sky-50 text-sky-700 border-sky-200'
                                                        }`}>
                                                            {src.source_type === 'pre_seeded' ? 'EDI5 Benchmark' : src.source_type === 'file_upload' ? `File: ${src.file_name || 'Upload'}` : 'Manual Entry'}
                                                        </span>
                                                        {rdata.year && (
                                                            <span className="text-[11px] font-medium text-slate-500">
                                                                Year: {rdata.year}
                                                            </span>
                                                        )}
                                                    </div>

                                                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                                        {(rdata.rounds || []).map(r => (
                                                            <span key={r} className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold capitalize">
                                                                {r.replace('_', ' ')}
                                                            </span>
                                                        ))}
                                                        {(rdata.topics || []).slice(0, 5).map(t => (
                                                            <span key={t} className="px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 text-[10px] font-medium">
                                                                {t}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <button
                                                        onClick={() => handleDeleteSource(src.id)}
                                                        className="px-2.5 py-1 text-slate-400 hover:text-rose-600 text-xs font-semibold rounded-lg hover:bg-rose-50 transition-all"
                                                    >
                                                        Delete
                                                    </button>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 4. LOG PAST DRIVE FORM ─────────────────────────────── */}
                    {activeTab === 'add_manual' && (
                        <form onSubmit={handleSaveManualRecord} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">
                                Log Past Placement Drive Manually
                            </h3>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">
                                        Drive Label / Title
                                    </label>
                                    <input
                                        type="text"
                                        value={manualForm.label}
                                        onChange={e => setManualForm({ ...manualForm, label: e.target.value })}
                                        placeholder="e.g. 2024 On-Campus Drive"
                                        className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">
                                        Year
                                    </label>
                                    <input
                                        type="number"
                                        value={manualForm.year}
                                        onChange={e => setManualForm({ ...manualForm, year: e.target.value })}
                                        className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-2">
                                    Assessment Rounds Included
                                </label>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                    {ROUND_OPTIONS.map(r => {
                                        const isChecked = manualForm.rounds.includes(r.key);
                                        return (
                                            <label
                                                key={r.key}
                                                className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-semibold cursor-pointer transition-all ${
                                                    isChecked
                                                        ? 'bg-indigo-50 border-indigo-300 text-indigo-900'
                                                        : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                                                }`}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={isChecked}
                                                    onChange={e => {
                                                        const next = e.target.checked
                                                            ? [...manualForm.rounds, r.key]
                                                            : manualForm.rounds.filter(k => k !== r.key);
                                                        setManualForm({ ...manualForm, rounds: next });
                                                    }}
                                                    className="rounded text-indigo-600"
                                                />
                                                {r.label}
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1">
                                    Topics / Skills (comma separated)
                                </label>
                                <input
                                    type="text"
                                    value={manualForm.topics}
                                    onChange={e => setManualForm({ ...manualForm, topics: e.target.value })}
                                    placeholder="e.g. Arrays, Dynamic Programming, SQL, System Design, Operating Systems"
                                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                />
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">
                                        Overall Difficulty
                                    </label>
                                    <select
                                        value={manualForm.difficulty}
                                        onChange={e => setManualForm({ ...manualForm, difficulty: e.target.value })}
                                        className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                    >
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-700 mb-1">
                                        Estimated Total Duration (Minutes)
                                    </label>
                                    <input
                                        type="number"
                                        value={manualForm.duration_minutes}
                                        onChange={e => setManualForm({ ...manualForm, duration_minutes: e.target.value })}
                                        className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1">
                                    Notes &amp; Observations
                                </label>
                                <textarea
                                    value={manualForm.notes}
                                    onChange={e => setManualForm({ ...manualForm, notes: e.target.value })}
                                    rows="2"
                                    placeholder="Any candidate feedback, cutoff criteria, or interview focus areas..."
                                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                />
                            </div>

                            <div className="flex items-center justify-end gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab('sources')}
                                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={actionLoading}
                                    className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold shadow-sm transition-all"
                                >
                                    {actionLoading ? 'Saving…' : 'Save Historical Drive'}
                                </button>
                            </div>
                        </form>
                    )}

                    {/* 5. UPLOAD FILE FORM ────────────────────────────────── */}
                    {activeTab === 'upload_file' && (
                        <form onSubmit={handleUploadFile} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">
                                Upload Historical Assessment Documents
                            </h3>
                            <p className="text-xs text-slate-500">
                                Upload placement drive documents, job descriptions, or past test summaries. The system deterministically extracts rounds, skills, topics, and difficulties.
                            </p>

                            <div>
                                <label className="block text-xs font-bold text-slate-700 mb-1">
                                    Document Label / Name
                                </label>
                                <input
                                    type="text"
                                    value={uploadLabel}
                                    onChange={e => setUploadLabel(e.target.value)}
                                    placeholder="e.g. 2024 On-Campus Assessment Format PDF"
                                    className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-900 focus:outline-none"
                                />
                            </div>

                            <div className="border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-2xl p-8 text-center transition-all bg-slate-50/50">
                                <input
                                    type="file"
                                    id="file_upload_input"
                                    accept={SUPPORTED_EXTS}
                                    onChange={e => {
                                        const file = e.target.files?.[0];
                                        if (file) {
                                            setUploadFile(file);
                                            if (!uploadLabel) setUploadLabel(file.name);
                                        }
                                    }}
                                    className="hidden"
                                />
                                <label htmlFor="file_upload_input" className="cursor-pointer block">
                                    <div className="text-3xl mb-2">📄</div>
                                    <div className="text-xs font-bold text-indigo-600 mb-1">
                                        {uploadFile ? uploadFile.name : 'Click to select or drop document'}
                                    </div>
                                    <div className="text-[11px] text-slate-400">
                                        Supports PDF, DOCX, CSV, XLSX, JSON (Max 20MB)
                                    </div>
                                    {uploadFile && (
                                        <div className="text-[11px] font-semibold text-emerald-600 mt-2">
                                            ✓ Ready: {(uploadFile.size / 1024).toFixed(1)} KB
                                        </div>
                                    )}
                                </label>
                            </div>

                            <div className="flex items-center justify-end gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab('sources')}
                                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={actionLoading || !uploadFile}
                                    className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-xs font-bold shadow-sm transition-all"
                                >
                                    {actionLoading ? 'Uploading & Parsing…' : 'Upload & Extract Pattern'}
                                </button>
                            </div>
                        </form>
                    )}

                </div>

                {/* ── Footer ──────────────────────────────────────────────── */}
                <div className="px-6 py-4 bg-slate-100 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
                    <div>
                        Target Company: <span className="font-bold text-slate-800">{companyName || '—'}</span> / Role: <span className="font-bold text-slate-800">{targetRole || '—'}</span>
                    </div>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-xl bg-white hover:bg-slate-200 text-slate-700 font-semibold border border-slate-300 transition-all"
                    >
                        Close
                    </button>
                </div>

            </div>
        </div>
    );
}
