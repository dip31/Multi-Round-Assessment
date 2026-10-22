const DAY_MS = 24 * 60 * 60 * 1000;
const COMPARISON_DAYS = 30;

function formatCount(count, singular) {
    return `${count} ${singular}${count === 1 ? '' : 's'}`;
}

function driveCreationTrend(drives, now) {
    const currentEnd = now.getTime();
    const currentStart = currentEnd - COMPARISON_DAYS * DAY_MS;
    const previousStart = currentStart - COMPARISON_DAYS * DAY_MS;
    const timestamps = drives
        .map((drive) => Date.parse(drive?.created_at))
        .filter(Number.isFinite);

    if (timestamps.length === 0) return null;

    const recent = timestamps.filter((time) => time > currentStart && time <= currentEnd).length;
    const previous = timestamps.filter((time) => time > previousStart && time <= currentStart).length;
    if (recent === previous) return null;

    const direction = recent > previous ? 'increased' : 'decreased';
    return {
        id: 'drive-creation-trend',
        category: 'Drive activity',
        priority: 2,
        title: `Mock Drive creation ${direction}`,
        result: `${formatCount(recent, 'Mock Drive')} · ${formatCount(previous, 'Mock Drive')}`,
        summary: `Creation counts ${direction} from ${previous} to ${recent} across two equal 30-day periods. This describes drive setup activity, not placement outcomes.`,
        evidence: `${timestamps.length} recorded Mock Drives with valid creation dates · Recent 30 days compared with the prior 30 days`,
        href: '/tpo/mock-drives',
        action: 'Review Mock Drives',
    };
}

function unresolvedDeadlineRisk(rosters) {
    let roundCount = 0;
    const candidates = new Set();
    const drives = new Set();

    Object.entries(rosters || {}).forEach(([driveId, roster]) => {
        (roster?.candidates || []).forEach((candidate) => {
            if (candidate?.context_status === 'completed') return;
            (candidate?.rounds || []).forEach((round) => {
                if (round?.status === 'completed' || !(round?.status === 'expired' || round?.deadline_passed === true)) return;
                roundCount += 1;
                drives.add(driveId);
                if (candidate.candidate_id != null) candidates.add(candidate.candidate_id);
            });
        });
    });

    if (!roundCount) return null;
    return {
        id: 'unresolved-deadline-steps',
        category: 'Current operational risk',
        priority: 1,
        title: 'Incomplete assessment steps are past their deadline',
        result: `${formatCount(roundCount, 'step')} · ${formatCount(candidates.size, 'candidate')} · ${formatCount(drives.size, 'drive')}`,
        summary: 'These assessment steps have passed their deadline and remain unfinished. Review the affected rosters and decide whether candidates need follow-up or a rescheduled round.',
        evidence: `Across ${Object.keys(rosters).length} available non-draft drive rosters (the dashboard checks up to six)`,
        href: '/tpo/mock-drives',
        action: 'Review affected drives',
    };
}

export function buildPlacementIntelligence({
    drives = [],
    rosters = {},
    drivesAvailable = false,
    rostersAvailable = false,
    now = new Date(),
} = {}) {
    const findings = [];
    if (drivesAvailable) {
        const trend = driveCreationTrend(drives, now);
        if (trend) findings.push(trend);
    }
    if (drivesAvailable && rostersAvailable) {
        const risk = unresolvedDeadlineRisk(rosters);
        if (risk) findings.push(risk);
    }
    return findings.sort((a, b) => a.priority - b.priority);
}

export function placementIntelligenceUnavailable(availability) {
    if (!availability) return [];
    const messages = [];
    if (!availability.drives) messages.push('Mock Drive activity could not be loaded.');
    else if (!availability.rosters) messages.push('Current drive-roster checks could not be completed.');
    return messages;
}
