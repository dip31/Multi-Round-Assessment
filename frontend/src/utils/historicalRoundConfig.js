// Pure helpers for the historical assessment round configuration panel.
//
// The backend is the single source of truth: `pattern_data` carries
// `assessment_rounds` (effective rounds), `evidence_rounds` (pure historical
// evidence) and `tpo_configuration` (explicit TPO selections/deselections).
// These helpers derive the editable panel state from that one persisted source
// so the UI never has to merge/guess, and build the save payload including
// explicit deselections.

export const ROUND_KEYS = ['aptitude', 'coding', 'technical_interview', 'hr_interview'];

export function normalizeRoundKey(value) {
    return String(value ?? '').trim().toLowerCase().replace(/\s+/g, '_');
}

function firstDefined(...values) {
    for (const value of values) {
        if (value !== undefined && value !== null && value !== '') return value;
    }
    return '';
}

/**
 * Derive the panel configuration from persisted pattern data.
 *
 * Returns `{ config, addedRounds }` where every supported round that is either
 * an effective round, a historical evidence round, or carries an explicit TPO
 * decision gets an initialized entry. `enabled` reflects the effective pattern
 * (a deselected round is `enabled: false`, not absent), so an explicit
 * deselection is always distinguishable from an unspecified round.
 */
export function deriveHistoricalRoundConfig(patternData) {
    const data = patternData || {};
    const roundPatterns = data.round_patterns || {};
    const assessmentRounds = (data.assessment_rounds || []).map(normalizeRoundKey);
    const evidenceRounds = (data.evidence_rounds || Object.keys(roundPatterns)).map(normalizeRoundKey);
    const tpoEntries = (data.tpo_configuration?.rounds || []).reduce((acc, entry) => {
        const key = normalizeRoundKey(entry?.round_type);
        if (key) acc[key] = entry;
        return acc;
    }, {});

    const keys = new Set();
    ROUND_KEYS.forEach(key => {
        if (assessmentRounds.includes(key) || evidenceRounds.includes(key) || tpoEntries[key]) {
            keys.add(key);
        }
    });
    Object.keys(roundPatterns).forEach(key => keys.add(normalizeRoundKey(key)));
    Object.keys(tpoEntries).forEach(key => keys.add(key));

    const config = {};
    const addedRounds = [];
    [...keys].forEach(key => {
        if (!ROUND_KEYS.includes(key)) return;
        const rp = roundPatterns[key] || {};
        const entry = tpoEntries[key] || {};
        const origin = entry.round_origin || rp.round_origin || (evidenceRounds.includes(key) ? 'evidence' : 'tpo_added');
        const enabled = assessmentRounds.includes(key);
        config[key] = {
            initialized: true,
            enabled,
            question_count: firstDefined(entry.question_count, rp.question_count, rp.avg_question_count, ''),
            duration_minutes: firstDefined(entry.duration_minutes, rp.duration_minutes, rp.avg_duration_minutes, ''),
            difficulty_distribution: entry.difficulty_distribution || rp.difficulty_distribution || null,
            focus_areas: entry.focus_areas || rp.focus_areas || [],
            round_origin: origin,
            evidence_question_count: rp.question_count || rp.avg_question_count || null,
            evidence_duration_minutes: rp.duration_minutes || rp.avg_duration_minutes || null,
            evidence_difficulty_distribution: rp.difficulty_distribution || null,
        };
        if (enabled && origin === 'tpo_added') addedRounds.push(key);
    });

    return { config, addedRounds };
}

/**
 * Build the `/pattern/generate` payload from the editable panel configuration.
 *
 * Enabled rounds become `round_configuration`; every initialized round that is
 * currently unchecked becomes an explicit `deselected_rounds` entry (an
 * unspecified round has no entry at all). TPO-added rounds are listed in
 * `added_rounds` so they are appended even before they carry full settings.
 */
export function buildHistoricalRoundPayload(config) {
    const configuredRounds = [];
    const deselectedRounds = [];
    const addedRounds = [];

    ROUND_KEYS.forEach(key => {
        const cfg = config?.[key];
        if (!cfg || !cfg.initialized) return;
        if (cfg.enabled) {
            configuredRounds.push({
                round_type: key,
                question_count: cfg.question_count === '' || cfg.question_count === null ? null : Number(cfg.question_count),
                duration_minutes: cfg.duration_minutes === '' || cfg.duration_minutes === null ? null : Number(cfg.duration_minutes),
                difficulty_distribution: cfg.difficulty_distribution || null,
                focus_areas: cfg.focus_areas || [],
            });
            if (cfg.round_origin === 'tpo_added') addedRounds.push(key);
        } else {
            deselectedRounds.push(key);
        }
    });

    return { configuredRounds, deselectedRounds, addedRounds };
}
