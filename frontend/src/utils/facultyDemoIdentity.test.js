import assert from 'node:assert/strict';
import test from 'node:test';
import { FACULTY_DEMO_STUDENT_NAMES, facultyStudentDisplayIdentity } from './facultyDemoIdentity.js';
import { buildPracticeReportText } from './facultyPracticeReport.js';

test('development table uses distinct ordered demo names and keeps row assignments stable', () => {
    const assignments = new Map();
    const first = { session_id: 11, round_id: 101, student: { user_id: 1, name: 'Student identity unavailable' } };
    const second = { session_id: 12, round_id: 102, student: { user_id: 2, name: 'Student identity unavailable' } };

    const firstDisplay = facultyStudentDisplayIdentity(first, { isDevelopment: true, assignments });
    const secondDisplay = facultyStudentDisplayIdentity(second, { isDevelopment: true, assignments });

    assert.deepEqual(firstDisplay, { name: 'Aarav Sharma', isDemo: true });
    assert.deepEqual(secondDisplay, { name: 'Ananya Patel', isDemo: true });
    assert.deepEqual(facultyStudentDisplayIdentity(first, { isDevelopment: true, assignments }), firstDisplay);
    assert.equal(first.student.name, 'Student identity unavailable');
    assert.equal(assignments.get('11:101'), 'Aarav Sharma');
    assert.match(buildPracticeReportText({ mode: 'report', record: first, payload: { summary: {} } }), /Student name: Student identity unavailable/);
});

test('verified identity stays unchanged and production never substitutes a fictional name', () => {
    const assignments = new Map();
    const verified = { session_id: 21, round_id: 201, student: { name: 'Verified Student' } };
    const unresolved = { session_id: 22, round_id: 202, student: { name: 'Student identity unavailable' } };

    assert.deepEqual(facultyStudentDisplayIdentity(verified, { isDevelopment: true, assignments }), {
        name: 'Verified Student', isDemo: false,
    });
    assert.deepEqual(facultyStudentDisplayIdentity(unresolved, { isDevelopment: false, assignments }), {
        name: 'Student identity unavailable', isDemo: false,
    });
    assert.equal(assignments.size, 0);
    assert.equal(FACULTY_DEMO_STUDENT_NAMES.length, 20);
});

test('demo names cycle only after the configured list is exhausted', () => {
    const assignments = new Map();
    const displays = Array.from({ length: FACULTY_DEMO_STUDENT_NAMES.length + 1 }, (_, index) => facultyStudentDisplayIdentity({
        session_id: index + 1,
        round_id: 1,
        student: { name: 'Student identity unavailable' },
    }, { isDevelopment: true, assignments }));

    assert.equal(displays[19].name, 'Tanvi Desai');
    assert.equal(displays[20].name, 'Aarav Sharma');
});
