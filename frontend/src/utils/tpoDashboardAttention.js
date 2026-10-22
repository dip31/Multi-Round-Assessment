const REQUIRED_ASSESSMENT_ROUNDS = ['aptitude', 'coding', 'interview'];

export function getTpoDashboardAttentionMetrics({
    drives = [],
    students = [],
    eligibleStudents = [],
    rosters = {},
}) {
    let expiredRoundCount = 0;
    let failedMappings = 0;
    let pendingMappings = 0;

    Object.values(rosters || {}).forEach((roster) => {
        (roster?.candidates || []).forEach((candidate) => {
            if (candidate.competency_mapping_status === 'failed') failedMappings += 1;
            else if (candidate.competency_mapping_status === 'pending') pendingMappings += 1;

            if (candidate.context_status !== 'completed') {
                (candidate.rounds || []).forEach((round) => {
                    if (round?.status !== 'completed' && (round?.status === 'expired' || round?.deadline_passed === true)) {
                        expiredRoundCount += 1;
                    }
                });
            }
        });
    });

    const byDepartment = new Map();
    eligibleStudents.forEach((student) => {
        const department = student.department || 'General';
        const counts = byDepartment.get(department) || { eligible: 0, completed: 0 };
        counts.eligible += 1;
        const rounds = student.rounds || {};
        if (REQUIRED_ASSESSMENT_ROUNDS.every((round) => rounds[round]?.status === 'completed')) {
            counts.completed += 1;
        }
        byDepartment.set(department, counts);
    });

    const sizedDepartments = [...byDepartment.entries()]
        .filter(([, counts]) => counts.eligible >= 3)
        .map(([department, counts]) => ({
            department,
            ...counts,
            rate: counts.completed / counts.eligible,
        }));
    const departmentCompletion = sizedDepartments.length >= 2
        ? sizedDepartments
            .sort((a, b) => a.rate - b.rate || b.eligible - a.eligible)[0]
        : null;

    return {
        draftDriveCount: drives.filter((drive) => drive.status === 'draft').length,
        expiredRoundCount,
        incompleteSessionCount: students.filter((student) =>
            student.session_status === 'in_progress'
            && Number.isFinite(student.session_time_remaining_seconds)
            && student.session_time_remaining_seconds > 0
        ).length,
        failedMappings,
        pendingMappings,
        eligibleStudentCount: eligibleStudents.length,
        departmentCompletion: departmentCompletion?.rate < 0.5 ? departmentCompletion : null,
    };
}

export function formatCount(count, singular, plural = `${singular}s`) {
    return `${count} ${count === 1 ? singular : plural}`;
}

export function draftDriveTitle(count) {
    return count === 1 ? '1 drive is still a draft' : `${count} drives are still drafts`;
}

export function expiredRoundTitle(count) {
    return `${formatCount(count, 'assessment round')} expired`;
}

export function incompleteSessionTitle(count) {
    return count === 1 ? '1 assessment session is incomplete' : `${count} assessment sessions are incomplete`;
}

export function departmentCompletionTitle({ department, completed, eligible }) {
    return `${department}: ${completed} of ${eligible} ${eligible === 1 ? 'student' : 'students'} completed all rounds`;
}

export function getAttentionUnavailableReasons(availability, eligibleStudentCount) {
    if (!availability) return [];
    const reasons = [];
    if (!availability.drives) reasons.push('Draft-drive alerts could not be loaded.');
    if (!availability.rosters) reasons.push('Round and mapping alerts could not be loaded.');
    if (!availability.students) reasons.push('Cohort session alerts could not be loaded.');
    if (availability.students && eligibleStudentCount === 0) {
        reasons.push('Department completion is unavailable because there are no eligible students.');
    }
    return reasons;
}
