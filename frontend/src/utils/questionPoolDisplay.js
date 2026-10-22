// Drive-facing presentation for the Generated Question Pool section.
//
// Internally, validated reusable pools are larger than any single drive
// (POOL_SIZES: aptitude 30, coding 10, technical_interview 10, hr_interview 10).
// Those capacities stay on the internal question-pool status payload
// (required_count / pool_size) and are never mutated here. What the TPO sees in
// the Generated Question Pool section is always the CURRENT DRIVE's configured
// question_count for that round — the drive is what selects N questions out of
// the validated pool.
//
// Count source, in order:
//   1. the matched Mock Drive's round_configurations[round].question_count
//   2. the approved blueprint round's question_count (what a new drive copies)
// Never the pool capacity.

export function getDriveQuestionCount(roundType, driveRoundConfigurations, blueprintRounds) {
    const fromDrive = Number(driveRoundConfigurations?.[roundType]?.question_count);
    if (Number.isFinite(fromDrive) && fromDrive > 0) return fromDrive;

    const blueprintRound = (blueprintRounds || []).find(r => r?.round_type === roundType);
    const fromBlueprint = Number(blueprintRound?.question_count);
    if (Number.isFinite(fromBlueprint) && fromBlueprint > 0) return fromBlueprint;

    return null;
}

export function buildDriveFacingPoolRounds({ poolRounds = [], driveRoundConfigurations = {}, blueprintRounds = [] } = {}) {
    return (poolRounds || []).map(round => ({
        ...round,
        drive_count: getDriveQuestionCount(round.round_type, driveRoundConfigurations, blueprintRounds),
        pool_capacity: round.required_count ?? round.pool_size ?? null,
    }));
}
