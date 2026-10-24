// Presentation helpers for the derived Mock Drive roster (G4).
//
// The backend derives the roster from authoritative assessment records; this
// module only normalises that payload for display. It never computes scores,
// rankings, or eligibility rules.

export const ROSTER_ROUND_LABELS = {
    aptitude: 'Aptitude',
    coding: 'Coding',
    technical_interview: 'Technical',
    hr_interview: 'HR',
};

export const SCORE_STATUS_LABELS = {
    final: 'Final',
    provisional: 'Provisional',
    unavailable: 'Unavailable',
};

export const SCORING_ERROR_MESSAGES = {
    blueprint_snapshot_unavailable: 'A valid blueprint snapshot is not available.',
    no_configured_competencies: 'Blueprint competencies are not configured.',
    invalid_competency_weights: 'Blueprint competency weights must total 100%.',
};

export function scoringErrorMessage(errorCode) {
    if (!errorCode) return 'Competency scoring is unavailable due to a configuration issue.';
    // Check for known error prefixes
    for (const [key, message] of Object.entries(SCORING_ERROR_MESSAGES)) {
        if (errorCode.startsWith(key)) return message;
    }
    return 'Competency scoring is unavailable due to a configuration issue.';
}

export function rosterRoundLabel(roundKey) {
    return ROSTER_ROUND_LABELS[roundKey] || roundKey;
}

export function scoreStatusLabel(status) {
    return SCORE_STATUS_LABELS[status] || status;
}

export function participantStatusLabel(entry) {
    if (!entry) return 'Unknown';
    if (entry.context_status === 'completed') return 'Completed';
    if (entry.session_status === 'expired') return 'Expired';
    if (entry.session_status === 'not_started') return 'Not started';
    if (entry.session_status === 'in_progress' || entry.context_status === 'active') {
        return 'In progress';
    }
    if (!entry.session_id) return 'Not started';
    return 'Not started';
}

export function rosterScoreLabel(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
    return value.toFixed(1);
}

export function coverageLabel(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable';
    return `${Math.round(value * 100)}%`;
}

export function roundStatusLabel(status) {
    const labels = {
        completed: 'Completed',
        active: 'In progress',
        in_progress: 'In progress',
        expired: 'Expired',
        not_started: 'Not started',
        pending: 'Pending',
        unavailable: 'Unavailable',
        not_applicable: 'Not applicable',
    };
    if (labels[status]) return labels[status];
    return status ? String(status).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Unavailable';
}

function competencySummary(competencies = []) {
    return competencies
        .filter((item) => item?.status === 'assessed'
            && item.competency_name
            && typeof item.normalized_score === 'number'
            && Number.isFinite(item.normalized_score))
        .map((item) => ({
            name: item.competency_name,
            score: item.normalized_score.toFixed(1),
        }));
}

// Normalise the GET /tpo/mock-drives/{id}/roster payload for rendering.
export function summarizeRoster(payload) {
    const candidates = (payload?.candidates || []).map((entry) => ({
        ...entry,
        candidateId: entry.candidate_id,
        displayName: entry.name || entry.email || `Candidate #${entry.candidate_id}`,
        sessionId: entry.session_id ?? null,
        statusLabel: participantStatusLabel(entry),
            scoreLabel: ['final', 'provisional'].includes(entry.overall_score_status)
                ? rosterScoreLabel(entry.overall_score)
                : 'Unavailable',
        competencyScoreStatus: entry.overall_score_status,
        competencyScoreStatusLabel: scoreStatusLabel(entry.overall_score_status),
        evidenceCoverage: entry.evidence_coverage,
        evidenceCoverageLabel: coverageLabel(entry.evidence_coverage),
        assessedCompetencyCount: entry.assessed_competency_count,
        requiredCompetencyCount: entry.required_competency_count,
        missingCompetencies: Array.isArray(entry.missing_competencies) ? entry.missing_competencies : [],
        scoringError: entry.scoring_error || null,
        competencySummary: competencySummary(Array.isArray(entry.competencies) ? entry.competencies : []),
        rounds: Array.isArray(entry.rounds) ? entry.rounds : [],
    }));

    return {
        candidates,
        enabledRounds: payload?.enabled_rounds || [],
        total: payload?.total_participants ?? candidates.length,
        inProgress: payload?.in_progress_count ?? 0,
        completed: payload?.completed_count ?? 0,
        hasOverallScores: candidates.some((candidate) => candidate.scoreLabel !== 'Unavailable'),
        hasCompetencyMetrics: candidates.some((candidate) => (
            candidate.competencySummary.length > 0
            || (typeof candidate.evidenceCoverage === 'number' && Number.isFinite(candidate.evidenceCoverage))
            || (typeof candidate.requiredCompetencyCount === 'number' && candidate.requiredCompetencyCount > 0)
        )),
    };
}
