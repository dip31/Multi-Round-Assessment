import test from 'node:test';
import assert from 'node:assert/strict';
import { candidateEligibility, filterAndSortCandidates, summarizeCandidates } from './candidatePool.js';

const candidates = [
    { name: 'Asha', email: 'asha@example.test', roll_number: 'CS01', department: 'Computer Science', cgpa: 8.2, backlogs_count: 0, target_role: 'Engineer' },
    { name: 'Bina', email: 'bina@example.test', roll_number: 'IT02', department: 'IT', cgpa: 6.8, backlogs_count: 2, target_role: 'Analyst' },
    { name: 'Chirag', email: 'chirag@example.test', roll_number: 'CS03', department: 'Computer Science', cgpa: null, backlogs_count: null },
];

test('candidate summary counts loaded records and leaves incomplete eligibility unknown', () => {
    assert.deepEqual(summarizeCandidates(candidates), { total: 3, eligible: 1, conditional: 1, withBacklogs: 1 });
    assert.equal(candidateEligibility(candidates[2]), 'unknown');
});

test('search covers name, email, and roll number and filters can be combined', () => {
    assert.deepEqual(filterAndSortCandidates(candidates, { search: 'IT02' }).map(candidate => candidate.name), ['Bina']);
    assert.deepEqual(filterAndSortCandidates(candidates, { search: 'CHIRAG@EXAMPLE.TEST' }).map(candidate => candidate.name), ['Chirag']);
    assert.deepEqual(filterAndSortCandidates(candidates, { department: 'Computer Science', eligibility: 'eligible', minCgpa: '8', backlogs: 'none' }).map(candidate => candidate.name), ['Asha']);
});

test('CGPA and backlog filters do not classify missing or invalid values as zero', () => {
    assert.deepEqual(filterAndSortCandidates(candidates, { minCgpa: '0' }).map(candidate => candidate.name), ['Asha', 'Bina']);
    assert.deepEqual(filterAndSortCandidates(candidates, { backlogs: 'none' }).map(candidate => candidate.name), ['Asha']);
    assert.deepEqual(filterAndSortCandidates(candidates, { backlogs: 'unknown' }).map(candidate => candidate.name), ['Chirag']);
    assert.deepEqual(filterAndSortCandidates([{ name: 'Bad', cgpa: 'n/a', backlogs_count: 'unknown' }], { maxCgpa: '9' }), []);
});

test('sorting is derived without mutating loaded records', () => {
    const original = [...candidates];
    assert.deepEqual(filterAndSortCandidates(candidates, { sort: 'cgpa', direction: 'desc' }).map(candidate => candidate.name), ['Asha', 'Bina', 'Chirag']);
    assert.deepEqual(candidates, original);
});
