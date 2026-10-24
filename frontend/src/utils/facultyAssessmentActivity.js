export const ASSESSMENT_FILTER_DEFAULTS = Object.freeze({
    search: '',
    session_id: '',
    round_type: '',
    evaluation_status: '',
    date_from: '',
    date_to: '',
    needs_attention: false,
});

export function buildAssessmentActivityParams(filters, page = 1, pageSize = 20) {
    const params = { page, page_size: pageSize };
    for (const [key, value] of Object.entries(filters || {})) {
        if (value !== '' && value !== false && value !== null && value !== undefined) {
            params[key] = value;
        }
    }
    return params;
}

export function assessmentStatusLabel(value) {
    const labels = {
        in_progress: 'In progress',
        evaluation_in_progress: 'In progress',
        not_started: 'Not available',
        awaiting_evaluation: 'Awaiting evaluation',
        completed: 'Results available',
        failed: 'Evaluation failed',
        unavailable: 'Not available',
    };
    return labels[value] || String(value || 'Unavailable').replaceAll('_', ' ');
}

const startedRoundStatuses = new Set(['active', 'in_progress', 'completed', 'terminated', 'expired']);
const attentionRoundStatuses = new Set(['failed', 'terminated', 'expired']);

export function groupAssessmentActivity(records) {
    const groups = new Map();
    for (const record of records || []) {
        const key = [record.student?.user_id, record.assessment_source, record.assessment_id ?? '', record.session_id].join(':');
        const group = groups.get(key) || {
            ...record,
            rounds: [],
            last_activity: null,
        };
        group.rounds.push(record);
        const timestamp = record.last_activity && !Number.isNaN(Date.parse(record.last_activity))
            ? record.last_activity
            : null;
        if (timestamp && (!group.last_activity || Date.parse(timestamp) > Date.parse(group.last_activity))) {
            group.last_activity = timestamp;
        }
        groups.set(key, group);
    }

    return [...groups.values()].map((group) => {
        const statuses = group.rounds.map((round) => String(round.round_status || '').toLowerCase());
        const evaluations = group.rounds.map((round) => round.evaluation_status);
        const started = statuses.some((status) => startedRoundStatuses.has(status));
        const failed = evaluations.includes('failed') || statuses.some((status) => attentionRoundStatuses.has(status));
        const allCompleted = statuses.length > 0 && statuses.every((status) => status === 'completed');
        const assessment_status = failed ? 'failed' : allCompleted ? 'completed' : started ? 'in_progress' : 'not_started';

        const activity = [];
        const aptitude = group.rounds.filter((round) => ['aptitude', 'aptitude_test'].includes(round.round_type));
        if (aptitude.length) {
            const summaries = aptitude.map((round) => round.attempt_summary || {});
            const count = summaries.reduce((sum, item) => sum + (Number(item.question_attempts) || 0), 0);
            const evaluated = summaries.reduce((sum, item) => sum + (Number(item.evaluated_answers) || 0), 0);
            const correct = summaries.reduce((sum, item) => sum + (Number(item.correct_answers) || 0), 0);
            if (count) activity.push(`${count} question${count === 1 ? '' : 's'} attempted; ${correct} correct${evaluated < count ? `, ${count - evaluated} awaiting evaluation` : ''}`);
        }
        const coding = group.rounds.filter((round) => round.round_type === 'coding');
        if (coding.length) {
            const count = coding.reduce((sum, round) => sum + (Number(round.attempt_summary?.coding_submissions) || 0), 0);
            if (count) activity.push(`${count} coding submission${count === 1 ? '' : 's'} recorded`);
        }
        for (const interview of group.rounds.filter((round) => ['interview', 'ai_interview'].includes(round.round_type))) {
            if (interview.activity_label === 'Interview responses available at session level') activity.push('Interview responses recorded (count unavailable)');
        }
        const hasUnavailableActivity = group.rounds.some((round) => ['No response data available', 'No round recorded'].includes(round.activity_label));
        const knownNoActivity = group.rounds.length > 0 && group.rounds.every((round) => [
            'No attempt recorded', 'No submission recorded', 'No interview response recorded',
        ].includes(round.activity_label));
        group.activity = activity.length ? activity.join('; ') : knownNoActivity ? 'No activity recorded' : hasUnavailableActivity ? 'Activity unavailable' : 'No activity recorded';
        group.assessment_status = assessment_status;
        group.evaluation_statuses = [...new Set(evaluations)];
        group.round_names = [...new Set(group.rounds.map((round) => round.round_name).filter(Boolean))];
        group.has_submission_details = group.rounds.some((round) => round.has_submission_details);
        group.details_record = group.rounds.find((round) => round.has_submission_details) || group.rounds[0];
        group.assessment_name = group.assessment_source === 'faculty_assignment'
            ? (group.rounds.find((round) => round.assessment_name !== 'Practice Assessment')?.assessment_name || 'Practice Assessment')
            : 'Practice Assessment';
        return group;
    }).sort((a, b) => Date.parse(b.last_activity || 0) - Date.parse(a.last_activity || 0));
}

export function filterAssessmentGroups(groups, filters) {
    const search = String(filters.search || '').trim().toLowerCase();
    return (groups || []).filter((group) => {
        if (filters.session_id && String(group.session_id) !== String(filters.session_id)) return false;
        if (search && ![group.student?.name, group.student?.roll_number, group.assessment_name, group.session_name,
            ...group.rounds.map((round) => round.round_name)].some((value) => String(value || '').toLowerCase().includes(search))) return false;
        if (filters.round_type && !group.rounds.some((round) => round.round_type === filters.round_type)) return false;
        if (filters.evaluation_status && !group.evaluation_statuses.includes(filters.evaluation_status)) return false;
        if (filters.needs_attention && group.assessment_status !== 'failed' && !group.evaluation_statuses.some((status) => ['in_progress', 'evaluation_in_progress', 'awaiting_evaluation', 'failed'].includes(status))) return false;
        if (filters.date_from || filters.date_to) {
            const timestamps = group.rounds.map((round) => Date.parse(round.last_activity)).filter(Number.isFinite);
            const start = filters.date_from ? new Date(`${filters.date_from}T00:00:00`).getTime() : -Infinity;
            const end = filters.date_to ? new Date(`${filters.date_to}T00:00:00`).getTime() + 86400000 : Infinity;
            if (!timestamps.some((value) => value >= start && value < end)) return false;
        }
        return true;
    });
}

export function assessmentCsv(records) {
    const headers = ['Student', 'Student identifier', 'Activity source', 'Assessment', 'Session', 'Rounds', 'Assessment status', 'Persisted activity', 'Evaluation status', 'Last activity'];
    const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;
    const lines = records.map((row) => [
        row.student?.name,
        row.student?.roll_number,
        row.assessment_source === 'faculty_assignment' ? 'Faculty assignment' : 'Independent practice',
        row.assessment_name,
        row.session_name,
        (row.round_names || [row.round_name]).join('; '),
        ({ completed: 'Completed', in_progress: 'In Progress', not_started: 'Not Started', failed: 'Needs Attention' })[row.assessment_status] || assessmentStatusLabel(row.assessment_status || row.evaluation_status),
        row.activity || row.activity_label,
        (row.evaluation_statuses || [row.evaluation_status]).map(assessmentStatusLabel).join('; '),
        row.last_activity,
    ]);
    return [headers, ...lines].map((line) => line.map(escape).join(',')).join('\r\n');
}
