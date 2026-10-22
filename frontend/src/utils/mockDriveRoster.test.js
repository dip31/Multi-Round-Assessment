import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    participantStatusLabel,
    rosterRoundLabel,
    summarizeRoster,
    scoreStatusLabel,
    coverageLabel,
    scoringErrorMessage,
} from './mockDriveRoster.js';

const drivesPageSource = await readFile(
    new URL('../pages/TPOMockDrivesPage.jsx', import.meta.url),
    'utf8',
);

test('summarizeRoster normalises derived counts and candidates', () => {
    const summary = summarizeRoster({
        enabled_rounds: ['coding', 'hr_interview'],
        total_participants: 2,
        in_progress_count: 1,
        completed_count: 1,
        candidates: [
            {
                candidate_id: 7,
                name: 'Ada Lovelace',
                email: 'ada@example.com',
                context_status: 'completed',
                overall_score: 82.456,
                overall_score_status: 'final',
                evidence_coverage: 1.0,
                assessed_competency_count: 3,
                required_competency_count: 3,
                missing_competencies: [],
                rounds: [{ round: 'coding', status: 'completed', max_score: 100 }],
            },
            {
                candidate_id: 8,
                name: null,
                email: 'grace@example.com',
                context_status: 'active',
                overall_score: null,
                overall_score_status: 'provisional',
                evidence_coverage: 0.5,
                assessed_competency_count: 1,
                required_competency_count: 2,
                missing_competencies: ['Algorithms'],
                rounds: [],
            },
        ],
    });

    assert.deepEqual(summary.enabledRounds, ['coding', 'hr_interview']);
    assert.equal(summary.total, 2);
    assert.equal(summary.inProgress, 1);
    assert.equal(summary.completed, 1);

    assert.equal(summary.candidates[0].candidateId, 7);
    assert.equal(summary.candidates[0].displayName, 'Ada Lovelace');
    assert.equal(summary.candidates[0].statusLabel, 'Completed');
    assert.equal(summary.candidates[0].scoreLabel, '82.5');
    assert.equal(summary.candidates[0].competencyScoreStatus, 'final');
    assert.equal(summary.candidates[0].competencyScoreStatusLabel, 'Final');
    assert.equal(summary.candidates[0].evidenceCoverage, 1.0);
    assert.equal(summary.candidates[0].evidenceCoverageLabel, '100%');
    assert.equal(summary.candidates[0].missingCompetencies.length, 0);

    // Missing name falls back to email; empty score renders as an em dash.
    assert.equal(summary.candidates[1].displayName, 'grace@example.com');
    assert.equal(summary.candidates[1].statusLabel, 'In progress');
    assert.equal(summary.candidates[1].scoreLabel, '—');
    assert.equal(summary.candidates[1].competencyScoreStatus, 'provisional');
    assert.equal(summary.candidates[1].competencyScoreStatusLabel, 'Provisional');
    assert.equal(summary.candidates[1].evidenceCoverage, 0.5);
    assert.equal(summary.candidates[1].evidenceCoverageLabel, '50%');
    assert.equal(summary.candidates[1].missingCompetencies.length, 1);
    assert.equal(summary.candidates[1].missingCompetencies[0], 'Algorithms');
});

test('summarizeRoster tolerates an empty payload', () => {
    const summary = summarizeRoster(undefined);
    assert.deepEqual(summary.candidates, []);
    assert.deepEqual(summary.enabledRounds, []);
    assert.equal(summary.total, 0);
    assert.equal(summary.inProgress, 0);
    assert.equal(summary.completed, 0);
});

test('participantStatusLabel distinguishes completed, expired and active', () => {
    assert.equal(participantStatusLabel({ context_status: 'completed' }), 'Completed');
    assert.equal(
        participantStatusLabel({ context_status: 'active', session_status: 'expired' }),
        'Expired',
    );
    assert.equal(participantStatusLabel({ context_status: 'active' }), 'In progress');
});

test('rosterRoundLabel maps known rounds and preserves unknown keys', () => {
    assert.equal(rosterRoundLabel('coding'), 'Coding');
    assert.equal(rosterRoundLabel('hr_interview'), 'HR');
    assert.equal(rosterRoundLabel('group_discussion'), 'group_discussion');
});

test('scoreStatusLabel maps states and preserves unknown', () => {
    assert.equal(scoreStatusLabel('final'), 'Final');
    assert.equal(scoreStatusLabel('provisional'), 'Provisional');
    assert.equal(scoreStatusLabel('unavailable'), 'Unavailable');
    assert.equal(scoreStatusLabel('unknown'), 'unknown');
});

test('coverageLabel formats fractions as percentages', () => {
    assert.equal(coverageLabel(1.0), '100%');
    assert.equal(coverageLabel(0.5), '50%');
    assert.equal(coverageLabel(0.333), '33%');
    assert.equal(coverageLabel(null), '—');
    assert.equal(coverageLabel(undefined), '—');
});

test('scoringErrorMessage handles known and unknown error codes', () => {
    assert.equal(
        scoringErrorMessage('no_configured_competencies'),
        'This drive\'s pinned blueprint has no competency configuration. Save competencies to the blueprint, then create a new drive to enable competency scoring.'
    );
    assert.equal(
        scoringErrorMessage('invalid_competency_weights: competency weights must sum to 100 (got 95)'),
        'The competency weights in the pinned blueprint do not sum to 100%. Please correct the blueprint configuration and create a new drive.'
    );
    assert.equal(
        scoringErrorMessage('some_unknown_error'),
        'Competency scoring is unavailable due to a configuration issue.'
    );
    assert.equal(scoringErrorMessage(null), 'Competency scoring is unavailable due to a configuration issue.');
    assert.equal(scoringErrorMessage(undefined), 'Competency scoring is unavailable due to a configuration issue.');
});

test('the drives page wires the derived roster endpoint and util', () => {
    assert.match(drivesPageSource, /from '\.\.\/utils\/mockDriveRoster'/);
    assert.match(
        drivesPageSource,
        /\/tpo\/mock-drives\/\$\{[^}]+\}\/roster/,
    );
});
