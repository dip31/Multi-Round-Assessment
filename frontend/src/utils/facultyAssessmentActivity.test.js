import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    ASSESSMENT_FILTER_DEFAULTS,
    assessmentCsv,
    assessmentStatusLabel,
    buildAssessmentActivityParams,
    filterAssessmentGroups,
    groupAssessmentActivity,
} from './facultyAssessmentActivity.js';
import { buildPracticeReportText, escapePracticeReportHtml } from './facultyPracticeReport.js';

test('practice assessment filters create backend parameters and omit empty defaults', () => {
    const params = buildAssessmentActivityParams({
        ...ASSESSMENT_FILTER_DEFAULTS,
        search: 'Ada',
        needs_attention: true,
        evaluation_status: 'failed',
    }, 3, 20);
    assert.deepEqual(params, {
        page: 3,
        page_size: 20,
        search: 'Ada',
        needs_attention: true,
        evaluation_status: 'failed',
    });
});

test('assessment status labels distinguish pending work from evaluated results', () => {
    assert.equal(assessmentStatusLabel('awaiting_evaluation'), 'Awaiting evaluation');
    assert.equal(assessmentStatusLabel('failed'), 'Evaluation failed');
    assert.equal(assessmentStatusLabel('completed'), 'Results available');
    assert.equal(assessmentStatusLabel('unavailable'), 'Not available');
});

test('faculty results use one semantic table row with six required columns in order', () => {
    const source = readFileSync(new URL('../components/FacultyAssessmentsSection.jsx', import.meta.url), 'utf8');
    const resultsTable = source.slice(source.indexOf('aria-label="Practice Assessment results"'));
    assert.equal((resultsTable.match(/<table\b/g) || []).length, 1);
    assert.match(resultsTable, /\['Student', 'Assessment \/ Session', 'Activity', 'Assessment Status', 'Last Activity', 'Actions'\]/);
    assert.match(source, /isDevelopment:\s*import\.meta\.env\.DEV/);
    assert.match(resultsTable, /<StudentIdentityCell record=\{record\}/);
    const rowStart = resultsTable.indexOf('pageRecords.map((record) => <tr');
    assert.notEqual(rowStart, -1);
    const rowEnd = resultsTable.indexOf('</tr>', rowStart);
    const rowMarkup = resultsTable.slice(rowStart, rowEnd);
    assert.equal((rowMarkup.match(/<td\b/g) || []).length, 5);
});

test('assessment monitoring renders the activity table without mounting the workspace', () => {
    const workspace = readFileSync(new URL('../components/FacultyPracticeAssessmentWorkspace.jsx', import.meta.url), 'utf8');
    const dashboard = readFileSync(new URL('../pages/FacultyDashboard.jsx', import.meta.url), 'utf8');
    const activity = readFileSync(new URL('../components/FacultyAssessmentsSection.jsx', import.meta.url), 'utf8');
    assert.match(dashboard, /const renderAssessments = \(\) => <FacultyAssessmentsSection \/>;/);
    assert.match(dashboard, /const renderDrives = \(\) => <FacultyPracticeAssessmentWorkspace \/>;/);
    assert.match(workspace, /const TABS = \['Create Assessment', 'Assigned Assessments', 'Review Results'\]/);
    assert.doesNotMatch(workspace, /data-testid="assessment-activity"/);
    assert.doesNotMatch(workspace, /tab === 'Assessment Activity'/);
    assert.match(activity, /One row per authorized student and actual practice session/);
    assert.match(activity, /onOpenAssignment\(record\.assessment_id\)/);
    assert.match(activity, /assessment_source === 'faculty_assignment'/);
});

test('groups all rounds from one student session and rolls up completed, pending, activity, and latest date', () => {
    const records = [
        { student: { user_id: 3, name: 'Ada' }, assessment_source: 'independent_practice', session_id: 12, assessment_name: 'Practice Assessment', session_name: 'Practice Session #12', round_id: 1, round_type: 'aptitude', round_name: 'Aptitude', round_status: 'completed', evaluation_status: 'completed', attempt_summary: { question_attempts: 10, evaluated_answers: 10, correct_answers: 7 }, activity_label: '10 questions attempted; 7 correct', last_activity: '2026-10-01T12:00:00' },
        { student: { user_id: 3, name: 'Ada' }, assessment_source: 'independent_practice', session_id: 12, assessment_name: 'Practice Assessment', session_name: 'Practice Session #12', round_id: 2, round_type: 'coding', round_name: 'Coding', round_status: 'completed', evaluation_status: 'awaiting_evaluation', attempt_summary: { coding_submissions: 2 }, activity_label: '2 submissions', last_activity: '2026-10-01T13:00:00' },
        { student: { user_id: 3, name: 'Ada' }, assessment_source: 'faculty_assignment', assessment_id: 9, session_id: 12, assessment_name: 'Assigned', session_name: 'Practice Session #12', round_id: 3, round_type: 'interview', round_name: 'Interview', round_status: 'active', evaluation_status: 'unavailable', attempt_summary: {}, activity_label: 'Interview responses available at session level', last_activity: '2026-10-01T14:00:00' },
    ];
    const groups = groupAssessmentActivity(records);
    assert.equal(groups.length, 2, 'same student/session does not merge independent and assigned sources');
    const independent = groups.find((group) => group.assessment_source === 'independent_practice');
    assert.equal(independent.rounds.length, 2);
    assert.equal(independent.assessment_status, 'completed');
    assert.equal(independent.activity, '10 questions attempted; 7 correct; 2 coding submissions recorded');
    assert.equal(independent.last_activity, '2026-10-01T13:00:00');
    assert.deepEqual(independent.evaluation_statuses, ['completed', 'awaiting_evaluation']);
    assert.equal(groups.find((group) => group.assessment_source === 'faculty_assignment').assessment_status, 'in_progress');
});

test('session rollup handles not started, partial, failed, and known no-activity states', () => {
    const base = { student: { user_id: 1, name: 'Student' }, session_name: 'Session', assessment_name: 'Practice Assessment', assessment_source: 'independent_practice', round_type: 'coding', round_name: 'Coding', attempt_summary: { coding_submissions: 0 }, activity_label: 'No submission recorded', last_activity: null };
    const make = (session_id, round_status, evaluation_status = 'unavailable') => ({ ...base, session_id, round_id: session_id, round_status, evaluation_status });
    const groups = groupAssessmentActivity([
        make(1, 'pending'), make(2, 'completed', 'awaiting_evaluation'), make(3, 'active', 'in_progress'), make(4, 'terminated', 'failed'),
    ]);
    assert.equal(groups.find((item) => item.session_id === 1).assessment_status, 'not_started');
    assert.equal(groups.find((item) => item.session_id === 1).activity, 'No activity recorded');
    assert.equal(groups.find((item) => item.session_id === 2).assessment_status, 'completed');
    assert.equal(groups.find((item) => item.session_id === 3).assessment_status, 'in_progress');
    assert.equal(groups.find((item) => item.session_id === 4).assessment_status, 'failed');
});

test('filters and grouped CSV work at session granularity', () => {
    const groups = groupAssessmentActivity([{ student: { user_id: 8, name: 'Lin' }, assessment_source: 'independent_practice', session_id: 22, assessment_name: 'Practice Assessment', session_name: 'Session 22', round_id: 1, round_type: 'coding', round_name: 'Coding', round_status: 'active', evaluation_status: 'in_progress', attempt_summary: { coding_submissions: 3 }, activity_label: '3 submissions', last_activity: '2026-10-02T00:00:00' }]);
    assert.equal(filterAssessmentGroups(groups, { ...ASSESSMENT_FILTER_DEFAULTS, search: 'Lin', round_type: 'coding' }).length, 1);
    assert.equal(filterAssessmentGroups(groups, { ...ASSESSMENT_FILTER_DEFAULTS, search: 'absent' }).length, 0);
    const csv = assessmentCsv(groups);
    assert.match(csv, /"3 coding submissions recorded"/);
    assert.match(csv, /"In Progress"/);
});

test('assessment CSV preserves absent scores as empty values and escapes text', () => {
    const csv = assessmentCsv([{
        student: { name: 'Ava "A"', roll_number: 'R-1' },
        assessment_name: 'Mock Drive',
        session_name: 'Example company',
        round_name: 'Coding',
        round_status: 'completed',
        evaluation_status: 'awaiting_evaluation',
        score: null,
        score_scale: null,
        attempt_count: 0,
        last_activity: null,
    }]);
    assert.match(csv, /"Ava ""A"""/);
    assert.match(csv, /"Awaiting evaluation","","Awaiting evaluation",""/);
});

test('full report export contains full history while submission export contains one selected attempt', () => {
    const payload = {
        student: { name: 'Ava', roll_number: null, department: 'Computer Science' },
        summary: { practice_sessions: 2, rounds_with_participation: 1 },
        count_definitions: { rounds_with_participation: 'Rounds with persisted question attempts or coding submissions.' },
        progress_message: 'Not enough comparable evaluated practice attempts to assess progress reliably.',
        history: [
            { assessment_name: 'Practice Assessment', session_name: 'Practice Session #7', round_name: 'Aptitude', round_status: 'completed', activity_label: '2 questions attempted; 1 correct', date: '2026-10-01', evaluation_status: 'completed', score: 50, score_max: 100 },
            { assessment_name: 'Practice Assessment', session_name: 'Practice Session #8', round_name: 'Coding', round_status: 'completed', activity_label: 'No submission recorded', date: '2026-10-02', evaluation_status: 'unavailable', score: null },
        ],
        comparisons: [],
        session_level_interviews: [],
        answers: [
            { attempt_id: 101, sequence: 1, question_text: 'Question one', selected_option: 'A', is_correct: true },
            { attempt_id: 102, sequence: 2, question_text: 'Question two', selected_option: 'B', is_correct: false },
        ],
        submissions: [],
        evaluation_status: 'completed',
    };
    const dateLabel = (value) => value || 'Not available';
    const report = buildPracticeReportText({ mode: 'report', payload, dateLabel });
    assert.match(report, /Assessment type: Practice Assessment \| Session: Practice Session #7 \| Round: Aptitude Assessment/);
    assert.match(report, /Session: Practice Session #8/);
    assert.doesNotMatch(report, /Count definitions|StudentProfile/);
    const details = buildPracticeReportText({ mode: 'details', payload, selectedEvidenceId: 'attempt:102', dateLabel });
    assert.match(details, /Question attempt 2: Question two/);
    assert.doesNotMatch(details, /Question one/);
    assert.equal(escapePracticeReportHtml('<script>"x"</script>'), '&lt;script&gt;&quot;x&quot;&lt;/script&gt;');
});
