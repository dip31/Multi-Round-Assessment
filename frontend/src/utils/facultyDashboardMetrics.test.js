import assert from 'node:assert/strict';
import test from 'node:test';
import {
  resolveCheckInDisplayName,
  selectStudentsNeedingFollowUp,
  summarizeDepartmentCounts,
  studentDisplayName,
  summarizeStudentsByDepartment,
  summarizeLatestSessionScores,
  summarizeLatestSessionStatuses,
} from './facultyDashboardMetrics.js';

test('uses roster names and a neutral fallback for blank or identifier-only names', () => {
  assert.equal(studentDisplayName({ full_name: '  Priya Rao  ', user_id: 7 }), 'Priya Rao');
  assert.equal(studentDisplayName({ full_name: '7', name: 'person@college.edu', user_id: 7, roll_number: '7' }), 'Name unavailable');
  assert.equal(studentDisplayName({ name: 'Test Student', user_id: 8 }), 'Test Student');
  assert.equal(studentDisplayName({ name: 'Stu3961765', user_id: 9 }), 'Stu3961765');
});

test('status distribution counts distinct students and preserves real session states', () => {
  const counts = summarizeLatestSessionStatuses([
    { user_id: 1, session_status: 'completed' },
    { user_id: 1, session_status: 'completed' },
    { user_id: 2, session_status: 'active' },
    { user_id: 3, session_status: 'not_started' },
  ]);
  assert.deepEqual(counts, [
    { label: 'Completed', count: 1 },
    { label: 'In progress', count: 1 },
    { label: 'Not started', count: 1 },
    { label: 'Terminated', count: 0 },
  ]);
});

test('prioritizes active, terminated, then not-started follow-ups, with oldest sessions first', () => {
  const selected = selectStudentsNeedingFollowUp([
    { user_id: 1, name: 'Newest active', session_status: 'in_progress', session_started_at: '2026-02-01T00:00:00Z' },
    { user_id: 2, name: 'Not started', session_status: 'not_started' },
    { user_id: 3, name: 'Oldest active', session_status: 'in_progress', session_started_at: '2026-01-01T00:00:00Z' },
    { user_id: 4, name: 'Terminated', session_status: 'terminated', session_started_at: '2025-12-01T00:00:00Z' },
    { user_id: 5, name: 'Completed', session_status: 'completed' },
  ]);
  assert.deepEqual(selected.map((student) => student.user_id), [3, 1, 4, 2]);
});

test('uses a complete authoritative name and rejects incomplete or identifier-like names for check-ins', () => {
  assert.equal(resolveCheckInDisplayName({ full_name: '  Ana   María Ruiz  ', name: 'Other Name' }), 'Ana María Ruiz');
  assert.equal(resolveCheckInDisplayName({ full_name: 'S', name: '  Noor   Hassan ' }), 'Noor Hassan');
  assert.equal(resolveCheckInDisplayName({ full_name: 'Stu3961765', name: 'Tester' }), null);
  assert.equal(resolveCheckInDisplayName({ full_name: '   ', name: 'person@example.edu' }), null);
  assert.equal(resolveCheckInDisplayName({ full_name: '王小明' }), '王小明');
});

test('deduplicates roster rows by student ID and repeated names using follow-up priority', () => {
  const selected = selectStudentsNeedingFollowUp([
    { user_id: 1, full_name: '  Alex   Kim ', session_status: 'terminated', session_started_at: '2026-01-01T00:00:00Z' },
    { user_id: 2, name: 'ALEX KIM', session_status: 'in_progress', session_started_at: '2026-02-01T00:00:00Z' },
    { user_id: 2, name: 'Alex Kim', session_status: 'terminated', session_started_at: '2025-01-01T00:00:00Z' },
    { user_id: 3, name: 'Morgan Chen', session_status: 'not_started' },
    { user_id: 4, name: 'Unique Person', session_status: 'completed' },
    { user_id: 5, name: 'Stu3961765', session_status: 'in_progress' },
  ]);

  assert.deepEqual(selected.map(({ user_id, checkInDisplayName }) => ({ user_id, checkInDisplayName })), [
    { user_id: 2, checkInDisplayName: 'ALEX KIM' },
    { user_id: 3, checkInDisplayName: 'Morgan Chen' },
  ]);
});

test('limits check-in suggestions to five eligible named students without padding missing entries', () => {
  const students = Array.from({ length: 7 }, (_, index) => ({
    user_id: index + 1,
    name: `Student Person ${index + 1}`,
    session_status: 'not_started',
  }));
  assert.equal(selectStudentsNeedingFollowUp(students).length, 5);
  assert.equal(selectStudentsNeedingFollowUp(students.slice(0, 2)).length, 2);
  assert.deepEqual(selectStudentsNeedingFollowUp(students, 0), []);
});

test('normalizes backend session status variants and selects by actual status priority', () => {
  const selected = selectStudentsNeedingFollowUp([
    { user_id: 1, name: 'Terminated Student', session_status: ' TERMINATED ', session_started_at: '2026-01-01T00:00:00Z' },
    { user_id: 2, name: 'Active Student', session_status: 'Active', session_started_at: '2026-02-01T00:00:00Z' },
    { user_id: 3, name: 'In Progress Student', session_status: 'IN PROGRESS', session_started_at: '2026-03-01T00:00:00Z' },
    { user_id: 4, name: 'Completed Student', session_status: 'completed' },
    { user_id: 5, name: 'Unknown Status Student', session_status: null },
  ]);
  assert.deepEqual(selected.map(({ user_id, session_status }) => [user_id, session_status]), [
    [2, 'in_progress'],
    [3, 'in_progress'],
    [1, 'terminated'],
  ]);
});

test('uses the latest session per student, excludes a newer completed session, and does not invent missing status', () => {
  assert.deepEqual(selectStudentsNeedingFollowUp([
    { user_id: 1, name: 'Older Active Student', session_status: 'in_progress', session_started_at: '2026-01-01T00:00:00Z', session_id: 10 },
    { user_id: 1, name: 'Newest Completed Student', session_status: 'completed', session_started_at: '2026-02-01T00:00:00Z', session_id: 11 },
    { user_id: 2, name: 'No History Evidence Student', session_status: null },
    { user_id: 3, name: 'No Session Student', session_status: 'not_started' },
  ]).map(({ user_id, checkInDisplayName }) => [user_id, checkInDisplayName]), [
    [3, 'No Session Student'],
  ]);
});

test('prioritizes Aksha when present and fills remaining spots from the My Students roster', () => {
  const requestedNames = ['Aksha', 'Aarav Sharma', 'Ananya Patel', 'Rohan Deshmukh', 'Priya Kulkarni'];
  const students = [
    { user_id: 1, name: 'Aarav Sharma', session_status: 'not_started' },
    { user_id: 2, name: 'Aksha', session_status: 'terminated' },
    { user_id: 3, name: 'Ananya Patel', session_status: 'not_started' },
    { user_id: 4, name: 'Rohan Deshmukh', session_status: 'not_started' },
    { user_id: 5, name: 'Priya Kulkarni', session_status: 'not_started' },
    { user_id: 6, name: 'Another Roster Student', session_status: 'not_started' },
  ];
  assert.deepEqual(selectStudentsNeedingFollowUp(students, 5, requestedNames).map(({ checkInDisplayName }) => checkInDisplayName), [
    'Aksha', 'Aarav Sharma', 'Ananya Patel', 'Rohan Deshmukh', 'Priya Kulkarni',
  ]);
});

test('returns exactly one student when exactly one named student is eligible', () => {
  const selected = selectStudentsNeedingFollowUp([
    { user_id: 1, name: 'Eligible Student', session_status: 'terminated' },
    { user_id: 2, name: 'Completed Student', session_status: 'completed' },
    { user_id: 3, name: 'S', session_status: 'in_progress' },
  ]);
  assert.deepEqual(selected.map(({ user_id, session_status }) => [user_id, session_status]), [[1, 'terminated']]);
});

test('shows duplicate normalized names once without merging account identities', () => {
  const selected = selectStudentsNeedingFollowUp([
    { user_id: 1, name: ' Alex   Kim ', session_status: 'not_started' },
    { user_id: 2, name: 'ALEX KIM', session_status: 'not_started' },
    { user_id: 3, name: 'Morgan Chen', session_status: 'not_started' },
  ]);
  assert.deepEqual(selected.map(({ user_id, checkInDisplayName }) => [user_id, checkInDisplayName]), [
    [1, 'Alex Kim'],
    [3, 'Morgan Chen'],
  ]);
});

test('keeps evaluated score averages separate by engine scale and excludes missing scores', () => {
  const scores = summarizeLatestSessionScores([
    { user_id: 1, round_records: [
      { round_type: 'aptitude', status: 'completed', score: 80 },
      { round_type: 'coding', status: 'completed', score: 0.75 },
      { round_type: 'interview', status: 'completed', score: 0.8 },
      { round_type: 'aptitude', status: 'completed', score: null },
      { round_type: 'coding', status: 'in_progress', score: 0.5 },
    ] },
    { user_id: 2, round_records: [{ round_type: 'aptitude', status: 'completed', score: 60 }] },
  ]);
  assert.deepEqual(scores.map(({ key, average, attemptCount, studentCount }) => ({ key, average, attemptCount, studentCount })), [
    { key: 'aptitude', average: 70, attemptCount: 2, studentCount: 2 },
    { key: 'coding', average: 0.75, attemptCount: 1, studentCount: 1 },
    { key: 'interview', average: 0.8, attemptCount: 1, studentCount: 1 },
  ]);
});

test('preserves a verified aptitude zero as a measured percentage', () => {
  assert.deepEqual(summarizeLatestSessionScores([
    { user_id: 41, round_records: [{ round_type: 'aptitude', status: 'completed', score: 0 }] },
  ]).map(({ average, attemptCount, studentCount, unit }) => ({ average, attemptCount, studentCount, unit })), [
    { average: 0, attemptCount: 1, studentCount: 1, unit: '%' },
  ]);
});

test('summarizes distinct students by normalized department and includes missing values in percentages', () => {
  assert.deepEqual(summarizeStudentsByDepartment([
    { user_id: 1, department: 'Computer Science' },
    { user_id: 1, department: 'Computer Science' },
    { user_id: 2, department: ' computer   science ' },
    { user_id: 3, department: 'Information Technology' },
    { user_id: 4, department: null },
    { user_id: 5, department: '   ' },
    { user_id: 6, department: 'Unassigned' },
  ]).map(({ department, count, percentage }) => ({ department, count, percentage: Number(percentage.toFixed(1)) })), [
    { department: 'Department Not Specified', count: 3, percentage: 50 },
    { department: 'Computer Science', count: 2, percentage: 33.3 },
    { department: 'Information Technology', count: 1, percentage: 16.7 },
  ]);
});

test('keeps similarly named departments distinct and returns an empty distribution for no students', () => {
  const groups = summarizeStudentsByDepartment([
    { user_id: 1, department: 'Computer Science' },
    { user_id: 2, department: 'Computer Science and Engineering' },
    { user_id: 3, department: 'COMPUTER SCIENCE' },
  ]);
  assert.deepEqual(groups.map(({ department, count, percentage }) => ({ department, count, percentage: Number(percentage.toFixed(1)) })), [
    { department: 'Computer Science', count: 2, percentage: 66.7 },
    { department: 'Computer Science and Engineering', count: 1, percentage: 33.3 },
  ]);
  assert.deepEqual(summarizeStudentsByDepartment([]), []);
});

test('combines normalized aggregate categories and computes percentages using the authorized total', () => {
  assert.deepEqual(summarizeDepartmentCounts([
    { department: 'Computer Science', count: 2 },
    { department: ' computer   science ', count: 1 },
    { department: 'Information Technology', count: 1 },
    { department: null, count: 1 },
  ], 5).map(({ department, count, percentage }) => ({ department, count, percentage: Number(percentage.toFixed(1)) })), [
    { department: 'Computer Science', count: 3, percentage: 60 },
    { department: 'Department Not Specified', count: 1, percentage: 20 },
    { department: 'Information Technology', count: 1, percentage: 20 },
  ]);
});

test('rejects aggregate department data whose category counts do not match its total', () => {
  assert.equal(summarizeDepartmentCounts([{ department: 'Computer Science', count: 4 }], 5), null);
});
