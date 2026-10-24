// Coding-only presentation examples for the TPO Competency Skill Gaps section.
// These values are not assessment results and must never be persisted or scored.
export const CODING_SKILL_GAP_DEMO_ROWS = [
    {
        competency_id: 'demo-coding-problem-solving',
        competency_name: 'Problem-solving and algorithmic thinking',
        avg_score: 60.0,
        gap_to_100: 40.0,
        assessed_attempts: 2,
        eligible_attempts: 3,
        coverage_percent: 66.7,
        evidence_items: 12,
        evidence_sources: ['coding'],
    },
    {
        competency_id: 'demo-coding-data-structures',
        competency_name: 'Data structures and algorithms',
        avg_score: 63.0,
        gap_to_100: 37.0,
        assessed_attempts: 2,
        eligible_attempts: 3,
        coverage_percent: 66.7,
        evidence_items: 10,
        evidence_sources: ['coding'],
    },
    {
        competency_id: 'demo-coding-correctness-testing',
        competency_name: 'Code correctness and testing',
        avg_score: 67.0,
        gap_to_100: 33.0,
        assessed_attempts: 2,
        eligible_attempts: 3,
        coverage_percent: 66.7,
        evidence_items: 9,
        evidence_sources: ['coding'],
    },
    {
        competency_id: 'demo-coding-quality-maintainability',
        competency_name: 'Code quality and maintainability',
        avg_score: 68.0,
        gap_to_100: 32.0,
        assessed_attempts: 1,
        eligible_attempts: 1,
        coverage_percent: 100,
        evidence_items: 5,
        evidence_sources: ['coding'],
    },
];

const CODING_SKILL_GAP_DEMO = {
    available: true,
    competencies: CODING_SKILL_GAP_DEMO_ROWS,
    unassessed: [],
    summary: {
        competencies_assessed: 4,
        competencies_unassessed: 1,
        average_competency_score: 64.5,
        largest_competency_gap: 40.0,
    },
};

export function codingSkillGapPresentation(skillGaps, assessmentType, demoEnabled = false) {
    if (demoEnabled && assessmentType === 'coding') {
        return CODING_SKILL_GAP_DEMO;
    }
    return assessmentType === 'all'
        ? skillGaps
        : skillGaps?.by_assessment_type?.[assessmentType];
}
