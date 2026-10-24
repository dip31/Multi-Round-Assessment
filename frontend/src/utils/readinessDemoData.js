// Presentation-only readiness examples for the TPO drive table.
// This helper never mutates the API payload and must not be used for scoring,
// exports, analytics, or persistence.

function finiteNumber(value) {
    if (typeof value !== 'number' && typeof value !== 'string') return null;
    if (typeof value === 'string' && !value.trim()) return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function stableHash(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
        hash ^= value.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
}

function hasValidRealReadiness(drive) {
    const participants = finiteNumber(drive.enrolled);
    const candidates = finiteNumber(drive.scored_candidates);
    const attempts = finiteNumber(drive.scored_attempts);
    return hasValidRealScore(drive)
        && Number.isInteger(participants) && participants > 0
        && Number.isInteger(candidates) && candidates > 0 && candidates <= participants
        && Number.isInteger(attempts) && attempts >= candidates;
}

function hasValidRealScore(drive) {
    const average = finiteNumber(drive.avg_readiness);
    return average !== null && average >= 0 && average <= 100;
}

function demoValuesForDrive(drive) {
    const participants = finiteNumber(drive.enrolled);
    const driveId = finiteNumber(drive.drive_id);
    if (!Number.isInteger(participants) || participants <= 0 || !Number.isInteger(driveId)) {
        return null;
    }

    // Drive ID is the stable identity available in the aggregate API response.
    // Include context identity/count when present to keep future multi-context
    // display rows deterministic without depending on company name or row order.
    const contextKey = Array.isArray(drive.context_ids)
        ? drive.context_ids.slice().sort((a, b) => String(a).localeCompare(String(b))).join(',')
        : String(finiteNumber(drive.contexts) ?? 0);
    const key = `${driveId}:${contextKey}`;
    const hash = stableHash(key);
    const scoreHash = stableHash(`${key}:score`);
    const candidateHash = stableHash(`${key}:candidates`);
    const attemptHash = stableHash(`${key}:attempts`);
    const candidateRange = Math.min(participants, 4);
    const scoredCandidates = 1 + (candidateHash % candidateRange);
    const scoredAttempts = scoredCandidates + (attemptHash % 3);
    const scoreSeed = (scoreHash ^ hash) >>> 0;

    return {
        scored_candidates: scoredCandidates,
        scored_attempts: scoredAttempts,
        avg_readiness: 35 + (scoreSeed % 471) / 10,
    };
}

export function withReadinessDemoValues(drives = []) {
    if (!Array.isArray(drives)) return [];
    return drives.map((drive) => {
        if (!drive || typeof drive !== 'object') return drive;
        if (hasValidRealReadiness(drive)) {
            return { ...drive, readiness_is_demo: false, readiness_demo_unavailable: false };
        }
        // An actual score is always preserved, even if its companion counts
        // are malformed; missing/invalid counts remain unavailable in the UI.
        if (hasValidRealScore(drive)) {
            return { ...drive, readiness_is_demo: false, readiness_demo_unavailable: false };
        }

        // Do not manufacture rows for empty drives or rows without a stable ID.
        const demo = demoValuesForDrive(drive);
        if (!demo) {
            return {
                ...drive,
                readiness_is_demo: false,
                readiness_demo_unavailable: true,
            };
        }

        return {
            ...drive,
            ...demo,
            readiness_is_demo: true,
            readiness_demo_unavailable: false,
        };
    });
}
