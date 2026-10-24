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
    roundStatusLabel,
    rosterScoreLabel,
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
                session_id: 70,
                competencies: [
                    { competency_name: 'Problem solving', status: 'assessed', normalized_score: 82.25 },
                    { competency_name: 'Communication', status: 'not_assessed', normalized_score: null },
                ],
                rounds: [{ round: 'coding', status: 'completed', score: 0.8, max_score: 1 }],
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
    assert.equal(summary.candidates[0].sessionId, 70);
    assert.equal(summary.candidates[0].displayName, 'Ada Lovelace');
    assert.equal(summary.candidates[0].statusLabel, 'Completed');
    assert.equal(summary.candidates[0].scoreLabel, '82.5');
    assert.equal(summary.candidates[0].competencyScoreStatus, 'final');
    assert.equal(summary.candidates[0].competencyScoreStatusLabel, 'Final');
    assert.equal(summary.candidates[0].evidenceCoverage, 1.0);
    assert.equal(summary.candidates[0].evidenceCoverageLabel, '100%');
    assert.equal(summary.candidates[0].missingCompetencies.length, 0);
    assert.deepEqual(summary.candidates[0].competencySummary, [
        { name: 'Problem solving', score: '82.3' },
    ]);
    assert.equal(summary.candidates[0].rounds[0].score, 0.8);
    assert.equal(summary.hasOverallScores, true);
    assert.equal(summary.hasCompetencyMetrics, true);

    // Missing name falls back to email; empty score renders as an em dash.
    assert.equal(summary.candidates[1].displayName, 'grace@example.com');
    assert.equal(summary.candidates[1].statusLabel, 'In progress');
    assert.equal(summary.candidates[1].scoreLabel, 'Unavailable');
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
    assert.equal(summary.hasOverallScores, false);
    assert.equal(summary.hasCompetencyMetrics, false);
});

test('participantStatusLabel distinguishes completed, expired and active', () => {
    assert.equal(participantStatusLabel({ context_status: 'completed' }), 'Completed');
    assert.equal(
        participantStatusLabel({ context_status: 'active', session_status: 'expired' }),
        'Expired',
    );
    assert.equal(participantStatusLabel({ context_status: 'active' }), 'In progress');
    assert.equal(participantStatusLabel({ context_status: 'active', session_id: 2, session_status: 'in_progress' }), 'In progress');
    assert.equal(participantStatusLabel({ context_status: 'active', session_status: 'not_started' }), 'Not started');
});

test('round statuses map explicitly without using identifiers or scores as status values', () => {
    assert.equal(roundStatusLabel('completed'), 'Completed');
    assert.equal(roundStatusLabel('active'), 'In progress');
    assert.equal(roundStatusLabel('not_started'), 'Not started');
    assert.equal(roundStatusLabel('not_applicable'), 'Not applicable');
    assert.equal(roundStatusLabel('pending'), 'Pending');
    assert.equal(roundStatusLabel(null), 'Unavailable');
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
    assert.equal(coverageLabel(null), 'Unavailable');
    assert.equal(coverageLabel(undefined), 'Unavailable');
});

test('score formatting preserves genuine zero and rejects status or empty-string values', () => {
    assert.equal(rosterScoreLabel(0), '0.0');
    assert.equal(rosterScoreLabel(null), 'Unavailable');
    assert.equal(rosterScoreLabel(''), 'Unavailable');
    assert.equal(rosterScoreLabel('Completed'), 'Unavailable');
    const summary = summarizeRoster({ candidates: [{
        candidate_id: 9,
        context_status: 'completed',
        overall_score: 88,
        overall_score_status: 'unavailable',
    }] });
    assert.equal(summary.candidates[0].statusLabel, 'Completed');
    assert.equal(summary.candidates[0].scoreLabel, 'Unavailable');
});

test('scoringErrorMessage handles known and unknown error codes', () => {
    assert.equal(
        scoringErrorMessage('no_configured_competencies'),
        'Blueprint competencies are not configured.'
    );
    assert.equal(
        scoringErrorMessage('invalid_competency_weights: competency weights must sum to 100 (got 95)'),
        'Blueprint competency weights must total 100%.'
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

test('roster table uses explicit matching columns and places identifiers only in Candidate', () => {
    assert.match(drivesPageSource, /Candidate ID: \{candidate\.candidateId\}/);
    assert.match(drivesPageSource, /\{candidate\.statusLabel\}/);
    assert.match(drivesPageSource, /\{candidate\.scoreLabel\}/);
    assert.match(drivesPageSource, /rosterData\.hasOverallScores && <th[^>]*>Overall Score/);
    assert.match(drivesPageSource, /rosterData\.hasCompetencyMetrics && <>/);
    assert.match(drivesPageSource, /typeof round\?\.score === 'number'/);
    assert.match(drivesPageSource, /Score unavailable/);
    assert.match(drivesPageSource, /table-fixed/);
    assert.match(drivesPageSource, /overflow-x-auto/);
    assert.doesNotMatch(drivesPageSource, /<td[^>]*>\s*#\{candidate\.candidateId\}.*?candidate\.statusLabel/s);
});
