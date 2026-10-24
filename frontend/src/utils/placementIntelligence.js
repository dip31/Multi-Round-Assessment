function unresolvedDeadlineRisk(rosters) {
    let hasOverdueStep = false;

    Object.values(rosters || {}).forEach((roster) => {
        (roster?.candidates || []).forEach((candidate) => {
            if (candidate?.context_status === 'completed') return;
            if ((candidate?.rounds || []).some((round) => (
                round?.status !== 'completed'
                && (round?.status === 'expired' || round?.deadline_passed === true)
            ))) {
                hasOverdueStep = true;
            }
        });
    });

    if (!hasOverdueStep) return null;
    return {
        id: 'unresolved-deadline-steps',
        title: 'Assessment completion needs attention',
        meaning: 'Some candidates have unfinished assessment rounds that have passed their deadlines.',
        action: 'Open the affected Mock Drives, review candidate progress, and decide whether to send a reminder or reschedule a round.',
        href: '/tpo/mock-drives',
        linkText: 'Review affected drives',
        priority: 1,
    };
}

function pendingInterviewEvaluation(rosters) {
    const hasPendingEvaluation = Object.values(rosters || {}).some((roster) => (
        (roster?.candidates || []).some((candidate) => (
            (candidate?.rounds || []).some((round) => {
                const type = String(round?.round_type || '').toLowerCase();
                return round?.status === 'completed'
                    && ['interview', 'technical_interview', 'hr_interview', 'communication_interview'].includes(type)
                    && round?.score == null;
            })
        ))
    ));
    if (!hasPendingEvaluation) return null;
    return {
        id: 'pending-interview-evaluation',
        title: 'Assessment evaluations are pending',
        meaning: 'Some completed interview rounds do not yet have an evaluated result.',
        action: 'Coordinate with the interview evaluators to review and submit the outstanding assessments.',
        href: '/tpo/mock-drives',
        linkText: 'Review Mock Drives',
        priority: 2,
    };
}

function publishedDrivesWithoutAssignments(drives, rosters) {
    const hasUnassignedPublishedDrive = drives.some((drive) => (
        drive?.status === 'published'
        && Array.isArray(rosters?.[drive.id]?.candidates)
        && rosters[drive.id].candidates.length === 0
    ));
    if (!hasUnassignedPublishedDrive) return null;
    return {
        id: 'published-drive-without-assignments',
        title: 'Placement drive readiness needs review',
        meaning: 'A published Mock Drive has no candidates assigned in its roster.',
        action: 'Review the drive and assign the intended candidates before its assessments begin.',
        href: '/tpo/mock-drives',
        linkText: 'Review drive assignments',
        priority: 2,
    };
}

function targetedPreparation(readiness) {
    const gaps = readiness?.skill_gaps?.competencies;
    const average = readiness?.kpis?.average_readiness?.value;
    const hasBackendFinding = readiness?.insights?.some((insight) => (
        insight?.id === 'competency-patterns'
        && insight?.action?.route === '/tpo/analytics'
    ));
    if (!Array.isArray(gaps) || !Number.isFinite(average) || !hasBackendFinding) return null;

    const repeatedlyAssessed = gaps.filter((gap) => gap.unique_candidates >= 2);
    if (repeatedlyAssessed.length < 2) return null;
    const developmentAreas = repeatedlyAssessed
        .filter((gap) => Number.isFinite(gap.avg_score) && gap.avg_score < average)
        .map((gap) => gap.competency_name)
        .filter(Boolean);
    if (!developmentAreas.length) return null;

    return {
        id: 'targeted-preparation',
        title: 'Candidates may need targeted preparation',
        meaning: `Evaluated results show development areas in ${developmentAreas.join(', ')} compared with the overall scored readiness average.`,
        action: 'Review the competency evidence and arrange focused practice or training in these areas.',
        href: '/tpo/analytics',
        linkText: 'Review competency evidence',
        priority: 3,
    };
}

export function buildPlacementIntelligence({
    drives = [],
    rosters = {},
    drivesAvailable = false,
    rostersAvailable = false,
    readiness = null,
    readinessAvailable = false,
} = {}) {
    const findings = [];
    if (drivesAvailable && rostersAvailable) {
        const risk = unresolvedDeadlineRisk(rosters);
        if (risk) findings.push(risk);
        const evaluation = pendingInterviewEvaluation(rosters);
        if (evaluation) findings.push(evaluation);
        const driveSetup = publishedDrivesWithoutAssignments(drives, rosters);
        if (driveSetup) findings.push(driveSetup);
    }
    if (readinessAvailable) {
        const preparation = targetedPreparation(readiness);
        if (preparation) findings.push(preparation);
    }
    return findings.sort((a, b) => a.priority - b.priority);
}

export function placementIntelligenceUnavailable(availability) {
    if (!availability) return [];
    const messages = [];
    if (!availability.drives) messages.push('Mock Drive information could not be loaded.');
    else if (!availability.rosters) messages.push('Assessment progress could not be loaded for the available Mock Drives.');
    if (!availability.readiness) messages.push('Evaluated competency information could not be loaded.');
    return messages;
}
