import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    departmentCompletionTitle,
    draftDriveTitle,
    expiredRoundTitle,
    formatCount,
    getAttentionUnavailableReasons,
    getTpoDashboardAttentionMetrics,
    incompleteSessionTitle,
} from './tpoDashboardAttention.js';

const dashboardSource = await readFile(
    new URL('../pages/TPODashboard.jsx', import.meta.url),
    'utf8',
);

test('attention metrics count only draft drives and unresolved expired rounds', () => {
    const metrics = getTpoDashboardAttentionMetrics({
        drives: [{ status: 'draft' }, { status: 'published' }, { status: 'completed' }],
        rosters: {
            1: { candidates: [
                { context_status: 'active', rounds: [
                    { status: 'expired' },
                    { status: 'active', deadline_passed: true },
                    { status: 'completed', deadline_passed: true },
                ] },
                { context_status: 'completed', rounds: [{ status: 'expired', deadline_passed: true }] },
            ] },
        },
    });

    assert.equal(metrics.draftDriveCount, 1);
    assert.equal(metrics.expiredRoundCount, 2);
});

test('incomplete session count excludes completed, expired, and deadline-passed sessions', () => {
    const metrics = getTpoDashboardAttentionMetrics({
        students: [
            { session_status: 'in_progress', session_time_remaining_seconds: 30 },
            { session_status: 'in_progress', session_time_remaining_seconds: 0 },
            { session_status: 'expired', session_time_remaining_seconds: 0 },
            { session_status: 'completed', session_time_remaining_seconds: 30 },
            { session_status: 'in_progress', session_time_remaining_seconds: null },
        ],
    });

    assert.equal(metrics.incompleteSessionCount, 1);
});

test('department completion uses only eligible students and all three completed rounds', () => {
    const complete = { aptitude: { status: 'completed' }, coding: { status: 'completed' }, interview: { status: 'completed' } };
    const pendingInterview = { ...complete, interview: { status: 'pending' } };
    const eligibleStudents = [
        ...Array.from({ length: 3 }, (_, i) => ({ department: 'Alpha', rounds: i === 0 ? complete : pendingInterview })),
        ...Array.from({ length: 3 }, () => ({ department: 'Beta', rounds: pendingInterview })),
    ];
    const metrics = getTpoDashboardAttentionMetrics({
        eligibleStudents,
        students: [...eligibleStudents, { department: 'Beta', rounds: complete }],
    });

    assert.deepEqual(metrics.departmentCompletion, {
        department: 'Beta', eligible: 3, completed: 0, rate: 0,
    });
    assert.equal(metrics.eligibleStudentCount, 6);
});

test('zero eligible students produces no zero-denominator department alert', () => {
    const metrics = getTpoDashboardAttentionMetrics({ eligibleStudents: [] });
    assert.equal(metrics.eligibleStudentCount, 0);
    assert.equal(metrics.departmentCompletion, null);
});

test('unavailable sources and a zero eligible denominator are disclosed', () => {
    assert.deepEqual(getAttentionUnavailableReasons(null, 0), []);
    assert.deepEqual(getAttentionUnavailableReasons({ drives: false, rosters: false, students: false }, 0), [
        'Draft-drive alerts could not be loaded.',
        'Round and mapping alerts could not be loaded.',
        'Cohort session alerts could not be loaded.',
    ]);
    assert.deepEqual(getAttentionUnavailableReasons({ drives: true, rosters: true, students: true }, 0), [
        'Department completion is unavailable because there are no eligible students.',
    ]);
});

test('attention count labels support singular and plural', () => {
    assert.equal(formatCount(1, 'assessment round'), '1 assessment round');
    assert.equal(formatCount(2, 'assessment round'), '2 assessment rounds');
    assert.equal(draftDriveTitle(1), '1 drive is still a draft');
    assert.equal(draftDriveTitle(2), '2 drives are still drafts');
    assert.equal(expiredRoundTitle(1), '1 assessment round expired');
    assert.equal(expiredRoundTitle(2), '2 assessment rounds expired');
    assert.equal(incompleteSessionTitle(1), '1 assessment session is incomplete');
    assert.equal(incompleteSessionTitle(2), '2 assessment sessions are incomplete');
    assert.equal(departmentCompletionTitle({ department: 'IT', completed: 1, eligible: 1 }), 'IT: 1 of 1 student completed all rounds');
    assert.equal(departmentCompletionTitle({ department: 'IT', completed: 2, eligible: 3 }), 'IT: 2 of 3 students completed all rounds');
});

test('dashboard does not render the superseded attention and readiness insight types', () => {
    assert.doesNotMatch(dashboardSource, /Lowest-scoring competency/);
    assert.doesNotMatch(dashboardSource, /Completion gap:/);
    assert.doesNotMatch(dashboardSource, /without a computable readiness score/);
    assert.doesNotMatch(dashboardSource, /Lowest aptitude topic accuracy/);
    assert.doesNotMatch(dashboardSource, /Repeat Aptitude attempts/);
});
