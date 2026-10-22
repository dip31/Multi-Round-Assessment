import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildDriveFacingPoolRounds, getDriveQuestionCount } from './questionPoolDisplay.js';
import { isRoleAssessmentProvenance, resolveBlueprintGenerationRequest } from './blueprintGeneration.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const modalSource = readFileSync(path.join(here, '../components/CompanyPatternModal.jsx'), 'utf8');
const publishServiceSource = readFileSync(
    path.join(here, '../../../app/services/question_pool_generation_service.py'),
    'utf8',
);
const driveServiceSource = readFileSync(
    path.join(here, '../../../app/services/mock_drive_service.py'),
    'utf8',
);

// Internal validated reusable pool capacities (POOL_SIZES) as they arrive from
// GET .../question-pool/status. The card must show the DRIVE counts instead.
const poolStatusRounds = [
    { round_type: 'aptitude', status: 'complete', validated_count: 30, required_count: 30, pool_size: 30 },
    { round_type: 'coding', status: 'complete', validated_count: 10, required_count: 10, pool_size: 10 },
    { round_type: 'technical_interview', status: 'complete', validated_count: 10, required_count: 10, pool_size: 10 },
];

const driveRoundConfigurations = {
    aptitude: { question_count: 15 },
    coding: { question_count: 5 },
    technical_interview: { question_count: 7 },
};

test('pool card shows the drive-facing counts 15/5/7, not the pool capacity 30/10/10', () => {
    const rounds = buildDriveFacingPoolRounds({
        poolRounds: poolStatusRounds,
        driveRoundConfigurations,
        blueprintRounds: [],
    });

    assert.deepEqual(rounds.map(r => r.drive_count), [15, 5, 7]);
    assert.deepEqual(rounds.map(r => r.pool_capacity), [30, 10, 10]);
    assert.ok(!rounds.some(r => r.drive_count === r.pool_capacity && r.drive_count !== null && r.drive_count > 25));
    rounds.forEach((round, index) => {
        assert.notEqual(round.drive_count, poolStatusRounds[index].required_count);
    });
});

test('the internal pool status payload keeps knowing 30/10/10 and is never mutated', () => {
    const snapshot = JSON.parse(JSON.stringify(poolStatusRounds));
    const rounds = buildDriveFacingPoolRounds({
        poolRounds: poolStatusRounds,
        driveRoundConfigurations,
        blueprintRounds: [],
    });

    assert.deepEqual(poolStatusRounds, snapshot);
    assert.deepEqual(poolStatusRounds.map(r => r.required_count), [30, 10, 10]);
    assert.deepEqual(poolStatusRounds.map(r => r.validated_count), [30, 10, 10]);
    assert.deepEqual(rounds.map(r => r.required_count), [30, 10, 10]);
});

test('a round without a drive count falls back to the blueprint count, never to the pool size', () => {
    const rounds = buildDriveFacingPoolRounds({
        poolRounds: [{ round_type: 'hr_interview', status: 'not_generated', validated_count: 0, required_count: 10, pool_size: 10 }],
        driveRoundConfigurations: {},
        blueprintRounds: [{ round_type: 'hr_interview', question_count: 3 }],
    });

    assert.equal(rounds[0].drive_count, 3);
    assert.equal(rounds[0].pool_capacity, 10);

    const noSource = buildDriveFacingPoolRounds({
        poolRounds: [{ round_type: 'aptitude', status: 'complete', required_count: 30, pool_size: 30 }],
        driveRoundConfigurations: {},
        blueprintRounds: [],
    });

    assert.equal(noSource[0].drive_count, null);
    assert.equal(getDriveQuestionCount('aptitude', {}, []), null);
});

test('a drive count changes (15 then 20) are read straight from the drive configuration', () => {
    assert.equal(getDriveQuestionCount('aptitude', { aptitude: { question_count: 15 } }, []), 15);
    assert.equal(getDriveQuestionCount('aptitude', { aptitude: { question_count: 20 } }, []), 20);
    assert.equal(getDriveQuestionCount('coding', { coding: { question_count: 5 } }, []), 5);
});

test('an LLM role-assessment blueprint already present is never re-requested (409 scenario)', () => {
    const provenance = { generation_method: 'llm_role_assessment', empirical_source_count: 0 };
    assert.equal(isRoleAssessmentProvenance(provenance), true);

    for (const force of [false, true]) {
        const decision = resolveBlueprintGenerationRequest({ hasBlueprint: true, force, provenance });
        assert.equal(decision.allowed, false);
        assert.equal(decision.reason, 'role_assessment_blueprint_immutable');
        assert.ok(decision.message.length > 0);
    }

    const classificationOnly = resolveBlueprintGenerationRequest({
        hasBlueprint: true,
        force: true,
        provenance: { classification: 'llm_role_assessment' },
    });
    assert.equal(classificationOnly.allowed, false);
});

test('first-time generation and evidence-based recalculation stay allowed', () => {
    const llmProvenance = { generation_method: 'llm_role_assessment' };
    const evidenceProvenance = { generation_method: 'company_specific_historical_evidence' };

    assert.equal(
        resolveBlueprintGenerationRequest({ hasBlueprint: false, force: false, provenance: llmProvenance }).allowed,
        true,
    );
    const evidence = resolveBlueprintGenerationRequest({ hasBlueprint: true, force: true, provenance: evidenceProvenance });
    assert.equal(evidence.allowed, true);
    assert.equal(evidence.force, true);
    assert.equal(resolveBlueprintGenerationRequest({ hasBlueprint: true, force: true }).allowed, true);
    assert.equal(resolveBlueprintGenerationRequest({ hasBlueprint: true, force: true, provenance: null }).allowed, true);
});

test('pool card renders drive counts and no longer renders validated-pool capacity', () => {
    assert.match(modalSource, /buildDriveFacingPoolRounds/);
    assert.match(modalSource, /round\.drive_count/);
    assert.ok(modalSource.includes('questions available from the validated pool'));
    assert.ok(
        !modalSource.includes('validated_count || 0} / {round.required_count || round.pool_size'),
        'pool capacity must not be shown as the configured count',
    );
});

test('the pool card explanatory sentence is removed', () => {
    assert.ok(
        !modalSource.includes('Role-specific questions are generated before any candidate runs.'),
        'explanatory sentence should be removed from the Generated Question Pool card',
    );
    assert.ok(modalSource.includes('Generated Question Pool'));
});

test('navigating to the Blueprint tab never triggers an automatic generate request', () => {
    assert.ok(
        !modalSource.includes('if (!blueprint) handleGenerateBlueprint'),
        'tab navigation must not call handleGenerateBlueprint',
    );
    const generateCalls = modalSource.match(/handleGenerateBlueprint\((true|false)?\)/g) || [];
    assert.ok(generateCalls.length > 0, 'explicit generate buttons must remain');
});

test('the backend publish gate is still enforced by the drive service', () => {
    assert.match(publishServiceSource, /def publish_blocking_errors/);
    assert.match(driveServiceSource, /publish_blocking_errors\(db, drive\)/);
});
