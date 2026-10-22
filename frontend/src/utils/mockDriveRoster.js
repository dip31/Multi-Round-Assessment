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
    no_configured_competencies: 'This drive\'s pinned blueprint has no competency configuration. Save competencies to the blueprint, then create a new drive to enable competency scoring.',
    invalid_competency_weights: 'The competency weights in the pinned blueprint do not sum to 100%. Please correct the blueprint configuration and create a new drive.',
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
    if (entry.session_status === 'in_progress' || entry.context_status === 'active') {
        return 'In progress';
    }
    return 'Not started';
}

export function rosterScoreLabel(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    return Number(value).toFixed(1);
}

export function coverageLabel(value) {
    if (value === null || value === undefined) return '—';
    return `${Math.round(value * 100)}%`;
}

// Normalise the GET /tpo/mock-drives/{id}/roster payload for rendering.
export function summarizeRoster(payload) {
    const candidates = (payload?.candidates || []).map((entry) => ({
        ...entry,
        candidateId: entry.candidate_id,
        displayName: entry.name || entry.email || `Candidate #${entry.candidate_id}`,
        statusLabel: participantStatusLabel(entry),
        scoreLabel: entry.overall_score == null
            ? '—'
            : Number(entry.overall_score).toFixed(1),
        competencyScoreStatus: entry.overall_score_status,
        competencyScoreStatusLabel: scoreStatusLabel(entry.overall_score_status),
        evidenceCoverage: entry.evidence_coverage,
        evidenceCoverageLabel: coverageLabel(entry.evidence_coverage),
        assessedCompetencyCount: entry.assessed_competency_count,
        requiredCompetencyCount: entry.required_competency_count,
        missingCompetencies: entry.missing_competencies || [],
        scoringError: entry.scoring_error || null,
        rounds: entry.rounds || [],
    }));

    return {
        candidates,
        enabledRounds: payload?.enabled_rounds || [],
        total: payload?.total_participants ?? candidates.length,
        inProgress: payload?.in_progress_count ?? 0,
        completed: payload?.completed_count ?? 0,
    };
}
