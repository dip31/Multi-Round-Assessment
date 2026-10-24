import { assessmentStatusLabel } from './facultyAssessmentActivity.js';

const defaultDateLabel = (value) => value && !Number.isNaN(new Date(value).getTime())
    ? new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
    : 'Not available';

export function escapePracticeReportHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[character]));
}

const scoreLabel = (item) => item.score === null || item.score === undefined
    ? (['awaiting_evaluation', 'evaluation_in_progress'].includes(item.evaluation_status) ? 'Not evaluated' : 'Not available')
    : item.score_max !== null && item.score_max !== undefined
        ? `${item.score} / ${item.score_max}`
        : `${item.score} ${item.score_scale || ''}`;
const roundNameLabel = (value) => {
    const title = String(value || 'Assessment round').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
    if (title === 'No Round Recorded') return 'No round recorded';
    return /\bassessment\b/i.test(title) ? title : `${title} Assessment`;
};
const roundStatusLabel = (value) => ({ active: 'In progress', in_progress: 'In progress', completed: 'Completed', pending: 'Not started', not_started: 'Not started', terminated: 'Incomplete', expired: 'Expired' }[value] || String(value || 'Not available').replaceAll('_', ' '));
const summaryLabels = {
    practice_sessions: 'Practice sessions',
    rounds_with_participation: 'Rounds with attempts or submissions',
    completed_rounds: 'Completed rounds',
    question_attempts: 'Question attempts',
    correct_answers: 'Correct answers',
    coding_submissions: 'Coding submissions',
    interview_responses: 'Interview responses',
    evaluated_round_results: 'Evaluated round results',
    pending_evaluations: 'Pending evaluations',
};

export function buildPracticeReportText({ mode, record, payload, selectedEvidenceId, dateLabel = defaultDateLabel }) {
    const student = payload?.student || record?.student || {};
    const lines = [
        mode === 'report' ? 'Student Performance Report' : 'Submission Details',
        `Student name: ${student.name || 'Student name unavailable'}`,
        ...(student.roll_number ? [`Roll number: ${student.roll_number}`] : []),
        `Department: ${student.department || 'Not available'}`,
    ];
    if (mode === 'report') {
        const summary = payload?.summary || {};
        lines.push('', 'Assessment type: Practice Assessment', '', 'Overall practice activity');
        Object.entries(summary).forEach(([key, value]) => lines.push(`${summaryLabels[key] || key.replaceAll('_', ' ')}: ${value}`));
        if (payload?.data_notes?.length) {
            lines.push('', 'Data notes');
            payload.data_notes.forEach((note) => lines.push(`- ${note}`));
        }
        lines.push('', 'Progress interpretation', payload?.progress_message || 'Progress cannot yet be assessed reliably because there are not enough comparable evaluated practice attempts.');
        (payload?.comparisons || []).forEach((item) => lines.push(
            `${roundNameLabel(item.round_type)}: ${item.first_score} to ${item.latest_score} (${item.change > 0 ? '+' : ''}${item.change} ${item.score_scale}); ${dateLabel(item.first_date)} to ${dateLabel(item.latest_date)}`,
        ));
        lines.push('', 'Assessment history');
        (payload?.history || []).forEach((item) => lines.push(
            `Assessment type: ${item.assessment_name} | Session: ${item.session_name} | Round: ${roundNameLabel(item.round_name)} | Date: ${dateLabel(item.date)} | Round status: ${roundStatusLabel(item.round_status)} | Evaluation: ${assessmentStatusLabel(item.evaluation_status)} | Activity: ${item.activity_label} | Score: ${scoreLabel(item)}`,
        ));
        (payload?.session_level_interviews || []).forEach((interview) => {
            lines.push('', `Session-level interview (${interview.phase || 'phase unavailable'}): ${interview.response_count} responses, ${interview.evaluated_response_count} evaluated responses. Turns are not linked to a specific assessment round.`);
            interview.turns.forEach((turn) => lines.push(
                `Turn ${turn.turn_number}${turn.is_followup ? ' (follow-up)' : ''}: ${turn.question_text} | Response: ${turn.candidate_response || 'No response persisted'} | Content score: ${turn.content_score === null || turn.content_score === undefined ? 'Not available' : `${turn.content_score} / 1`} | Final score: ${turn.final_score === null || turn.final_score === undefined ? 'Not available' : `${turn.final_score} / 1`} | ${dateLabel(turn.created_at)}`,
            ));
        });
    } else {
        lines.push(`Assessment type: ${payload?.assessment_name || record?.assessment_name || 'Practice Assessment'}`);
        lines.push(`Session: ${payload?.session_name || record?.session_name || 'Not available'}`);
        lines.push(`Round: ${payload?.round_name || record?.round_name || 'Not available'}`);
        lines.push(`Round status: ${roundStatusLabel(payload?.round_status)}`);
        lines.push(`Evaluation status: ${assessmentStatusLabel(payload?.evaluation_status)}`);
        lines.push(`Score: ${scoreLabel(payload || {})}`);
        if (payload?.detail_note) lines.push('', payload.detail_note);
        const answer = payload?.answers?.find((item) => `attempt:${item.attempt_id ?? item.sequence}` === selectedEvidenceId);
        const submission = payload?.submissions?.find((item) => `submission:${item.id}` === selectedEvidenceId);
        if (answer) lines.push(`Question attempt ${answer.sequence}: ${answer.question_text || 'Question unavailable'} | Answer: ${answer.selected_option || 'Not answered'} | Correct: ${answer.is_correct === null || answer.is_correct === undefined ? 'Not evaluated' : answer.is_correct ? 'Yes' : 'No'} | ${dateLabel(answer.attempted_at)}`);
        if (submission) lines.push(`Coding submission ${submission.id}: ${submission.status} | ${dateLabel(submission.submitted_at)} | ${submission.score === null || submission.score === undefined ? 'Not evaluated' : `${submission.score} (scale unavailable)`} | ${submission.language || 'Language unavailable'}\n${submission.code || 'No code persisted'}`);
    }
    return lines.join('\n');
}
