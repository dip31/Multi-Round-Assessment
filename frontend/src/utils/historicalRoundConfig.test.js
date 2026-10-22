import assert from 'node:assert/strict';
import test from 'node:test';
import { deriveHistoricalRoundConfig, buildHistoricalRoundPayload } from './historicalRoundConfig.js';

test('evidence rounds are prefilled and enabled from persisted pattern data', () => {
    const { config, addedRounds } = deriveHistoricalRoundConfig({
        assessment_rounds: ['aptitude', 'coding'],
        evidence_rounds: ['aptitude', 'coding'],
        round_patterns: {
            aptitude: { question_count: 20, duration_minutes: 30, focus_areas: ['Quantitative Aptitude'], round_origin: 'evidence' },
            coding: { question_count: 5, duration_minutes: 60, focus_areas: ['Arrays'], round_origin: 'evidence' },
        },
    });

    assert.equal(config.aptitude.enabled, true);
    assert.equal(config.aptitude.question_count, 20);
    assert.deepEqual(config.coding.focus_areas, ['Arrays']);
    assert.deepEqual(addedRounds, []);
});

test('a deselected evidence round is disabled, not absent', () => {
    const { config } = deriveHistoricalRoundConfig({
        assessment_rounds: ['aptitude'],
        evidence_rounds: ['aptitude', 'coding'],
        round_patterns: {
            aptitude: { question_count: 20, duration_minutes: 30, round_origin: 'evidence' },
        },
        tpo_configuration: {
            version: 1,
            rounds: [
                { round_type: 'aptitude', enabled: true, round_origin: 'evidence', question_count: 20, duration_minutes: 30 },
                { round_type: 'coding', enabled: false, round_origin: 'evidence', question_count: 5, duration_minutes: 60 },
            ],
        },
    });

    assert.equal(config.coding.enabled, false);
    // The last known values are still shown so re-selecting is lossless.
    assert.equal(config.coding.question_count, 5);
});

test('TPO-added rounds are enabled and reported as added', () => {
    const { config, addedRounds } = deriveHistoricalRoundConfig({
        assessment_rounds: ['aptitude', 'hr_interview'],
        evidence_rounds: ['aptitude'],
        round_patterns: {
            aptitude: { question_count: 20, duration_minutes: 30, round_origin: 'evidence' },
            hr_interview: { round_origin: 'tpo_added' },
        },
        tpo_configuration: {
            version: 1,
            rounds: [{ round_type: 'hr_interview', enabled: true, round_origin: 'tpo_added' }],
        },
    });

    assert.equal(config.hr_interview.enabled, true);
    assert.equal(config.hr_interview.round_origin, 'tpo_added');
    assert.deepEqual(addedRounds, ['hr_interview']);
});

test('payload distinguishes explicit deselection from absence', () => {
    const { config } = deriveHistoricalRoundConfig({
        assessment_rounds: ['aptitude', 'coding'],
        evidence_rounds: ['aptitude', 'coding'],
        round_patterns: {
            aptitude: { question_count: 20, duration_minutes: 30, round_origin: 'evidence' },
            coding: { question_count: 5, duration_minutes: 60, round_origin: 'evidence' },
        },
    });
    config.coding.enabled = false;

    const payload = buildHistoricalRoundPayload(config);
    assert.deepEqual(payload.deselectedRounds, ['coding']);
    assert.deepEqual(payload.configuredRounds.map(r => r.round_type), ['aptitude']);
    assert.deepEqual(payload.addedRounds, []);
});

test('payload includes TPO-added rounds in added_rounds', () => {
    const { config } = deriveHistoricalRoundConfig({
        assessment_rounds: ['aptitude', 'hr_interview'],
        evidence_rounds: ['aptitude'],
        round_patterns: {
            aptitude: { question_count: 20, duration_minutes: 30, round_origin: 'evidence' },
            hr_interview: { round_origin: 'tpo_added', question_count: 3, duration_minutes: 30, difficulty_distribution: { easy: 0.25, medium: 0.5, hard: 0.25 }, focus_areas: [] },
        },
        tpo_configuration: {
            version: 1,
            rounds: [{ round_type: 'hr_interview', enabled: true, round_origin: 'tpo_added' }],
        },
    });

    const payload = buildHistoricalRoundPayload(config);
    assert.deepEqual(payload.addedRounds, ['hr_interview']);
    assert.deepEqual(payload.configuredRounds.map(r => r.round_type), ['aptitude', 'hr_interview']);
});
