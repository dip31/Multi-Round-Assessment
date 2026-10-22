import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    buildPlacementIntelligence,
    placementIntelligenceUnavailable,
} from './placementIntelligence.js';

const dashboardSource = await readFile(new URL('../pages/TPODashboard.jsx', import.meta.url), 'utf8');
const routesSource = await readFile(new URL('../App.jsx', import.meta.url), 'utf8');
const now = new Date('2026-10-22T12:00:00Z');

test('drive creation insight compares actual equal 30-day periods', () => {
    const findings = buildPlacementIntelligence({
        drivesAvailable: true,
        now,
        drives: [
            { created_at: '2026-10-10T00:00:00Z' },
            { created_at: '2026-10-01T00:00:00Z' },
            { created_at: '2026-09-10T00:00:00Z' },
            { created_at: null },
        ],
    });

    assert.equal(findings.length, 1);
    assert.equal(findings[0].id, 'drive-creation-trend');
    assert.match(findings[0].title, /increased/);
    assert.equal(findings[0].result, '2 Mock Drives · 1 Mock Drive');
    assert.match(findings[0].evidence, /3 recorded Mock Drives/);
    assert.equal(findings[0].href, '/tpo/mock-drives');
});

test('unchanged or unavailable creation dates do not create a trend', () => {
    assert.deepEqual(buildPlacementIntelligence({
        drivesAvailable: true,
        now,
        drives: [{ created_at: '2026-10-01T00:00:00Z' }, { created_at: '2026-09-01T00:00:00Z' }],
    }), []);
    assert.deepEqual(buildPlacementIntelligence({
        drivesAvailable: true,
        now,
        drives: [{ created_at: null }, { created_at: 'not a date' }],
    }), []);
    assert.deepEqual(buildPlacementIntelligence({
        drivesAvailable: false,
        now,
        drives: [{ created_at: '2026-10-01T00:00:00Z' }],
    }), []);
});

test('current operational risk counts only unresolved expired steps in non-completed contexts', () => {
    const findings = buildPlacementIntelligence({
        drivesAvailable: true,
        rostersAvailable: true,
        now,
        rosters: {
            10: { candidates: [
                { candidate_id: 1, context_status: 'active', rounds: [
                    { status: 'expired' },
                    { status: 'active', deadline_passed: true },
                    { status: 'completed', deadline_passed: true },
                ] },
                { candidate_id: 1, context_status: 'completed', rounds: [{ status: 'expired' }] },
            ] },
            11: { candidates: [
                { candidate_id: 1, context_status: 'active', rounds: [{ status: 'expired' }] },
            ] },
        },
    });

    assert.equal(findings.length, 1);
    assert.equal(findings[0].id, 'unresolved-deadline-steps');
    assert.equal(findings[0].result, '3 steps · 1 candidate · 2 drives');
    assert.equal(findings[0].priority, 1);
    assert.equal(findings[0].href, '/tpo/mock-drives');
});

test('a roster risk is withheld when drive or roster data is unavailable', () => {
    const params = { rosters: { 1: { candidates: [
        { candidate_id: 1, context_status: 'active', rounds: [{ status: 'expired' }] },
    ] } } };
    assert.deepEqual(buildPlacementIntelligence({ ...params, drivesAvailable: false, rostersAvailable: true }), []);
    assert.deepEqual(buildPlacementIntelligence({ ...params, drivesAvailable: true, rostersAvailable: false }), []);
    assert.deepEqual(placementIntelligenceUnavailable({ drives: true, rosters: false }), [
        'Current drive-roster checks could not be completed.',
    ]);
});

test('Placement Intelligence actions use the existing Mock Drives route and replaces old section', () => {
    assert.match(routesSource, /path="\/tpo\/mock-drives"/);
    assert.match(dashboardSource, /data-testid="placement-intelligence"/);
    assert.match(dashboardSource, /Placement Intelligence/);
    assert.match(dashboardSource, /No significant placement patterns or actionable risks identified in the available data\./);
    assert.doesNotMatch(dashboardSource, /data-testid="needs-attention"/);
});
