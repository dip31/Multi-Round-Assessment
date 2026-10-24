import test from 'node:test';
import assert from 'node:assert/strict';
import { candidateEligibility, summarizeEligibility } from './candidateEligibility.js';

const baseline = { minimumCgpa: 7, maximumBacklogs: 0 };

test('preserves genuine zero values and marks missing required values unknown', () => {
    assert.equal(candidateEligibility({ cgpa: 0, backlogs_count: 0 }, baseline), 'ineligible');
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: 0 }, baseline), 'eligible');
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: null }, baseline), 'unknown');
    assert.equal(candidateEligibility({ cgpa: null, backlogs_count: 0 }, baseline), 'unknown');
});

test('a known failing criterion is ineligible even when another criterion is missing', () => {
    assert.equal(candidateEligibility({ cgpa: 6.9, backlogs_count: null }, baseline), 'ineligible');
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: 2 }, baseline), 'ineligible');
});

test('optional CGPA requirement does not make a missing CGPA unknown', () => {
    assert.equal(candidateEligibility({ cgpa: null, backlogs_count: 0 }, { minimumCgpa: 0 }), 'eligible');
});

test('branch requirements require known matching department', () => {
    const requirements = { minimumCgpa: 0, maximumBacklogs: 0, eligibleBranches: ['Computer Science'] };
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: 0 }, requirements), 'unknown');
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: 0, department: 'computer science' }, requirements), 'eligible');
    assert.equal(candidateEligibility({ cgpa: 8, backlogs_count: 0, department: 'Physics' }, requirements), 'ineligible');
});

test('summary separates eligible, ineligible, and unknown students', () => {
    const summary = summarizeEligibility([
        { cgpa: 8, backlogs_count: 0 },
        { cgpa: 6, backlogs_count: 0 },
        { cgpa: 8, backlogs_count: null },
    ], baseline);
    assert.deepEqual(summary, { eligible: 1, ineligible: 1, unknown: 1 });
});
