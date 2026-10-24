import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    buildPlacementIntelligence,
    placementIntelligenceUnavailable,
} from './placementIntelligence.js';

const dashboardSource = await readFile(new URL('../pages/TPODashboard.jsx', import.meta.url), 'utf8');
const routesSource = await readFile(new URL('../App.jsx', import.meta.url), 'utf8');

test('overdue unfinished assessment rounds produce an urgent text-only insight', () => {
    const findings = buildPlacementIntelligence({
        drivesAvailable: true,
        rostersAvailable: true,
        rosters: { drive: { candidates: [
            { context_status: 'active', rounds: [
                { status: 'expired' },
                { status: 'active', deadline_passed: true },
                { status: 'completed', deadline_passed: true },
            ] },
            { context_status: 'completed', rounds: [{ status: 'expired' }] },
        ] } },
    });

    assert.equal(findings.length, 1);
    assert.equal(findings[0].title, 'Assessment completion needs attention');
    assert.match(findings[0].meaning, /unfinished assessment rounds/);
    assert.match(findings[0].action, /review candidate progress/);
    assert.equal(findings[0].href, '/tpo/mock-drives');
    assert.doesNotMatch(findings.map(({ title, meaning, action, linkText }) => (
        `${title} ${meaning} ${action} ${linkText}`
    )).join(' '), /\d|%/);
});

test('targeted preparation uses only evaluated competencies selected by the existing readiness rule', () => {
    const findings = buildPlacementIntelligence({
        readinessAvailable: true,
        readiness: {
            kpis: { average_readiness: { value: 70 } },
            skill_gaps: { competencies: [
                { competency_name: 'Problem solving', avg_score: 55, unique_candidates: 3 },
                { competency_name: 'Communication', avg_score: 65, unique_candidates: 2 },
                { competency_name: 'Unassessed area', avg_score: null, unique_candidates: 8 },
            ] },
            insights: [{ id: 'competency-patterns', action: { route: '/tpo/analytics' } }],
        },
    });

    assert.equal(findings.length, 1);
    assert.equal(findings[0].title, 'Candidates may need targeted preparation');
    assert.match(findings[0].meaning, /Problem solving, Communication/);
    assert.equal(findings[0].href, '/tpo/analytics');
    assert.doesNotMatch(`${findings[0].title} ${findings[0].meaning} ${findings[0].action}`, /\d|%/);
});

test('pending, unassessed, or unsupported competency data does not create preparation insight', () => {
    const readiness = {
        kpis: { average_readiness: { value: 70 } },
        skill_gaps: { competencies: [
            { competency_name: 'Unassessed', avg_score: null, unique_candidates: 5 },
        ] },
        insights: [],
    };
    assert.deepEqual(buildPlacementIntelligence({ readinessAvailable: true, readiness }), []);
});

test('completed or non-overdue rounds do not create an insight', () => {
    assert.deepEqual(buildPlacementIntelligence({
        drivesAvailable: true,
        rostersAvailable: true,
        rosters: { drive: { candidates: [
            { context_status: 'active', rounds: [{ status: 'active', deadline_passed: false }] },
        ] } },
    }), []);
});

test('completed interviews without evaluated scores create an evaluation follow-up insight', () => {
    const findings = buildPlacementIntelligence({
        drivesAvailable: true,
        rostersAvailable: true,
        rosters: { drive: { candidates: [
            { context_status: 'completed', rounds: [
                { round_type: 'technical_interview', status: 'completed', score: null },
                { round_type: 'coding', status: 'completed', score: null },
            ] },
        ] } },
    });
    assert.equal(findings.length, 1);
    assert.equal(findings[0].title, 'Assessment evaluations are pending');
    assert.match(findings[0].action, /evaluators/);
    assert.equal(findings[0].href, '/tpo/mock-drives');
});

test('published drives with verified empty rosters need readiness review', () => {
    const findings = buildPlacementIntelligence({
        drives: [{ id: 12, status: 'published' }, { id: 13, status: 'active' }],
        drivesAvailable: true,
        rostersAvailable: true,
        rosters: {
            12: { candidates: [] },
            13: { candidates: [] },
        },
    });
    assert.equal(findings.length, 1);
    assert.equal(findings[0].title, 'Placement drive readiness needs review');
    assert.match(findings[0].meaning, /no candidates assigned/);
    assert.equal(findings[0].href, '/tpo/mock-drives');
});

test('overdue insight is withheld when drive or roster data is unavailable', () => {
    const params = { rosters: { drive: { candidates: [
        { context_status: 'active', rounds: [{ status: 'expired' }] },
    ] } } };
    assert.deepEqual(buildPlacementIntelligence({ ...params, drivesAvailable: false, rostersAvailable: true }), []);
    assert.deepEqual(buildPlacementIntelligence({ ...params, drivesAvailable: true, rostersAvailable: false }), []);
    assert.deepEqual(placementIntelligenceUnavailable({ drives: true, rosters: false }), [
        'Assessment progress could not be loaded for the available Mock Drives.',
        'Evaluated competency information could not be loaded.',
    ]);
});

test('Placement Intelligence provides the existing Mock Drives link and clear empty and unavailable states', () => {
    assert.match(routesSource, /path="\/tpo\/mock-drives"/);
    assert.match(dashboardSource, /data-testid="placement-intelligence"/);
    assert.match(dashboardSource, /Everything looks up to date/);
    assert.match(dashboardSource, /Placement information could not be loaded/);
    assert.doesNotMatch(dashboardSource, /data-testid="needs-attention"/);
});
