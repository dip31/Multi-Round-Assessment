import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    formatScore,
    formatCount,
    formatReadinessAverage,
    formatDelta,
    formatPercent,
    kpiDisplay,
    readinessBuckets,
    skillGapRows,
    unassessedSkillRows,
    insightList,
    hasScoredAttempts,
    eligibleSummary,
    READINESS_SECTION2_SUBTITLE,
    readinessNoticeReason,
    unavailableKpiMeta,
    assessmentCoverageKpi,
    candidatesNeedingAssessmentKpi,
    scoringFollowupKpi,
    recommendedActions,
} from './readinessFormatting.js';

const readinessPageSource = await readFile(
    new URL('../pages/TPOReadinessPage.jsx', import.meta.url),
    'utf8',
);
const appSource = await readFile(new URL('../App.jsx', import.meta.url), 'utf8');
const layoutSource = await readFile(
    new URL('../components/TPOLayout.jsx', import.meta.url),
    'utf8',
);

test('formatScore renders one decimal and em-dashes missing values', () => {
    assert.equal(formatScore(71.256), '71.3');
    assert.equal(formatScore(0), '0.0');
    assert.equal(formatScore(null), '—');
    assert.equal(formatScore(undefined), '—');
    assert.equal(formatScore('x'), '—');
});

test('drive-table counts distinguish a real zero from an unavailable count', () => {
    assert.equal(formatCount(0), '0');
    assert.equal(formatCount('2'), '2');
    assert.equal(formatCount(null), '—');
    assert.equal(formatCount(undefined), '—');
    assert.equal(formatCount(''), '—');
    assert.equal(formatCount('  '), '—');
    assert.equal(formatCount('unknown'), '—');
    assert.equal(formatCount(false), '—');
    assert.match(readinessPageSource, /Evidence unavailable/);
    assert.doesNotMatch(readinessPageSource, /No scores/);
});

test('drive readiness averages retain genuine precision and distinguish missing scores', () => {
    assert.equal(formatReadinessAverage(29.0), '29.0');
    assert.equal(formatReadinessAverage(43.89), '43.89');
    assert.equal(formatReadinessAverage(0), '0.0');
    assert.equal(formatReadinessAverage(null), '—');
    assert.equal(formatReadinessAverage(undefined), '—');
    assert.equal(formatReadinessAverage('  '), '—');
    assert.equal(formatReadinessAverage(false), '—');
});

test('formatDelta signs values and em-dashes missing', () => {
    assert.equal(formatDelta(5.24), '+5.2');
    assert.equal(formatDelta(-3.16), '-3.2');
    assert.equal(formatDelta(0), '0.0');
    assert.equal(formatDelta(null), '—');
});

test('formatPercent guards zero denominators', () => {
    assert.equal(formatPercent(1, 4), '25.0%');
    assert.equal(formatPercent(0, 0), '—');
    assert.equal(formatPercent(2, 0), '—');
});

test('kpiDisplay surfaces unavailable reasons instead of fake zeros', () => {
    const unavailable = kpiDisplay({
        available: false,
        value: null,
        reason: 'no placement records',
    });
    assert.equal(unavailable.display, '—');
    assert.equal(unavailable.available, false);
    assert.match(unavailable.meta, /no placement records/);

    const available = kpiDisplay({
        available: true,
        value: 71.25,
        definition: 'weighted competency score',
    });
    assert.equal(available.display, '71.3');
    assert.equal(available.available, true);

    const improvement = kpiDisplay({
        available: true,
        mean_delta: -2.5,
        definition: 'earliest to latest',
    });
    assert.equal(improvement.display, '-2.5');

    assert.equal(kpiDisplay(undefined).display, '—');
});

test('collection helpers tolerate empty payloads', () => {
    assert.deepEqual(readinessBuckets(undefined), []);
    assert.deepEqual(skillGapRows(undefined), []);
    assert.deepEqual(unassessedSkillRows({}), []);
    assert.deepEqual(insightList(undefined), []);
    assert.equal(hasScoredAttempts(undefined), false);
    assert.equal(hasScoredAttempts({ scored_attempts: 0 }), false);
    assert.equal(hasScoredAttempts({ scored_attempts: 2 }), true);
    assert.equal(eligibleSummary(null), 'No coverage data.');
    assert.equal(
        eligibleSummary({ scored_attempts: 3, unique_scored_candidates: 2 }),
        '3 scored attempt(s) across 2 candidate(s)',
    );
});

test('the readiness page wires the readiness overview endpoint and shared layout', () => {
    assert.match(readinessPageSource, /\/report\/admin\/readiness\/overview/);
    assert.match(readinessPageSource, /from '\.\.\/components\/TPOLayout'/);
});

test('Section 2 is titled for assessment evidence and readiness', () => {
    assert.match(readinessPageSource, /Section 2 — Assessment Evidence and Readiness/);
    assert.doesNotMatch(readinessPageSource, /Section 2 — Candidate Readiness and Skill Gaps/);
    assert.match(readinessPageSource, /data-testid="readiness-unavailable-summary"/);
});

test('Section 2 renders one compact status fed by live coverage counters', () => {
    assert.match(readinessPageSource, /data-testid="readiness-evidence-notice"/);
    assert.match(readinessPageSource, /data-testid="readiness-funnel-counts"/);
    // Counts come from the API `coverage` block — never hardcoded literals.
    for (const counter of [
        'completed_contexts',
        'contexts_with_snapshot',
        'contexts_with_configured_competencies',
        'contexts_with_evidence_mappings',
    ]) {
        assert.match(readinessPageSource, new RegExp(`coverage\\?\\.${counter}`));
    }
    assert.doesNotMatch(readinessPageSource, /Of \d+ completed attempt context\(s\) in scope/);
    assert.doesNotMatch(readinessPageSource, /readiness-unavailable-reason/);
});

test('unavailable KPI values are labelled, never replaced by fabricated numbers', () => {
    // The redesign shows an em-dash for any unavailable metric — never a
    // fabricated number and never a hardcoded threshold band.
    assert.equal(assessmentCoverageKpi({ denominator: 0 }).display, '—');
    assert.equal(assessmentCoverageKpi(undefined).display, '—');
    assert.doesNotMatch(readinessPageSource, /75%/); // no hardcoded threshold band
    assert.doesNotMatch(readinessPageSource, /Not configured/);
    assert.doesNotMatch(readinessPageSource, /Not available/);
});

test('the Section 2 subtitle and single-notice reason are the shared copy', () => {
    assert.equal(
        READINESS_SECTION2_SUBTITLE,
        'Readiness metrics are calculated from eligible assessment evidence in the selected period and scope.',
    );
    assert.match(readinessPageSource, /subtitle=\{READINESS_SECTION2_SUBTITLE\}/);
    assert.doesNotMatch(readinessPageSource, /source="Persisted assessment records"/);
    assert.match(readinessPageSource, /readinessNoticeReason\(coverage\)/);
    assert.doesNotMatch(readinessPageSource, /\{avgKpi\.meta\}/);
});

test('the notice reason mirrors backend coverage branches without embedding counts', () => {
    const fixtures = [
        [
            { completed_contexts: 0, contexts_with_snapshot: 0 },
            'because no completed attempts exist in the selected period and scope.',
        ],
        [
            { completed_contexts: 42, contexts_with_snapshot: 0 },
            'because no completed attempt carries a pinned blueprint snapshot.',
        ],
        [
            { completed_contexts: 42, contexts_with_snapshot: 12, contexts_with_configured_competencies: 0 },
            'because no configured competencies have mapped assessment evidence.',
        ],
        [
            {
                completed_contexts: 42,
                contexts_with_snapshot: 12,
                contexts_with_configured_competencies: 3,
                contexts_with_evidence_mappings: 0,
            },
            'because configured competencies have no mapped assessment evidence.',
        ],
        [
            {
                completed_contexts: 42,
                contexts_with_snapshot: 12,
                contexts_with_configured_competencies: 3,
                contexts_with_evidence_mappings: 3,
            },
            'because no completed attempt produced a usable competency readiness score.',
        ],
    ];
    for (const [coverage, expected] of fixtures) {
        assert.equal(readinessNoticeReason(coverage), expected);
    }
    // Missing payload data degrades to the most conservative reason; it never
    // invents counts or asserts evidence that the API did not return.
    assert.equal(
        readinessNoticeReason(undefined),
        'because no completed attempts exist in the selected period and scope.',
    );
    // Counts are rendered once, on their own line — the reason clause must not
    // embed any numbers that could duplicate the coverage line.
    for (const [, expected] of fixtures) {
        assert.doesNotMatch(expected, /\d/);
    }
});

test('unavailable KPI cards use concise honest copy with no repeated explanations', () => {
    // Average Readiness stays silent: the section notice already explains it.
    assert.equal(unavailableKpiMeta('average'), '');
    assert.equal(unavailableKpiMeta('improvement'), 'Requires 2+ eligible scored attempts for a candidate.');
    assert.equal(unavailableKpiMeta('something-else'), '');
    // The page wires the average card through the shared copy.
    assert.match(readinessPageSource, /: unavailableKpiMeta\('average'\)/);
    assert.doesNotMatch(readinessPageSource, /Needs 2\+ eligible scored attempts/);
});

test('the readiness charts are conditional on real scored evidence', () => {
    assert.match(readinessPageSource, /hasScoredEvidence/);
    // Cohort outcomes and intervention depend on scored evidence; skill gaps
    // remain visible with an honest empty state and source filter when present.
    assert.match(readinessPageSource, /Cohort Outcomes/);
    assert.match(readinessPageSource, /Competency Skill Gaps/);
    assert.match(readinessPageSource, /Filter competency gaps by assessment type/);
    assert.match(readinessPageSource, /codingSkillGapPresentation/);
    assert.doesNotMatch(readinessPageSource, /Intervention Impact/);
});

test('competency gaps retain the summary and demonstrated table without the examples section', () => {
    assert.match(readinessPageSource, /Identify competencies that need improvement using mapped evidence from completed assessments\./);
    assert.match(readinessPageSource, /data-testid="skill-gap-summary"/);
    assert.match(readinessPageSource, /Competencies Assessed/);
    assert.match(readinessPageSource, /Competencies Unassessed/);
    assert.match(readinessPageSource, /Average Competency Score/);
    assert.match(readinessPageSource, /Largest Competency Gap/);
    assert.match(readinessPageSource, /No demonstrated competency gaps yet/);
    assert.match(readinessPageSource, /No competencies are configured for this assessment scope\./);
    assert.match(readinessPageSource, /evidence_sources/);
    assert.doesNotMatch(readinessPageSource, /Competency Assessment Examples/);
    assert.doesNotMatch(readinessPageSource, /data-testid="unassessed-competencies"/);
});

test('the readiness page no longer renders the competency assessment examples section', () => {
    assert.doesNotMatch(readinessPageSource, /Illustrative demo rows/);
    assert.doesNotMatch(readinessPageSource, /Actual API data — unassessed/);
    assert.doesNotMatch(readinessPageSource, /competencyGapPresentation/);
});
test('routing and the shared sidebar include the readiness page', () => {
    assert.match(appSource, /path="\/tpo\/readiness"/);
    assert.match(appSource, /<TPOReadinessPage \/>/);
    assert.match(layoutSource, /\/tpo\/readiness/);
    assert.match(layoutSource, /Readiness/);
});

// ── Section 2 KPI derivations (cards 2–4) ───────────────────────────

test('assessment coverage KPI reports the percentage and its audit trail', () => {
    const kpi = assessmentCoverageKpi({ value: 26.2, numerator: 37, denominator: 141 });
    assert.equal(kpi.display, '26.2%');
    assert.equal(kpi.available, true);
    assert.match(kpi.meta, /37 of 141 completed rounds validly scored/);

    // A missing percentage is recomputed from the numerator/denominator.
    const computed = assessmentCoverageKpi({ numerator: 1, denominator: 3 });
    assert.equal(computed.display, '33.3%');
    assert.equal(computed.available, true);

    // No completed rounds in scope: unavailable, never a fake 0%.
    const none = assessmentCoverageKpi({ numerator: 0, denominator: 0 });
    assert.equal(none.display, '—');
    assert.equal(none.available, false);
    assert.match(none.meta, /No completed assessment rounds in scope/);
});

test('candidates needing assessment counts distinct candidates, not attempts', () => {
    const coverage = {
        completed_contexts: 45,
        students_with_contexts: 49,
        unique_scored_candidates: 2,
        candidates_with_completed_no_usable_score: 22,
    };
    const kpi = candidatesNeedingAssessmentKpi(coverage, undefined);
    assert.equal(kpi.display, '22');
    assert.equal(kpi.available, true);
    assert.match(kpi.meta, /Distinct candidates/);

    // Without the explicit backend counter the helper falls back to the
    // students-minus-scored derivation.
    const fallback = candidatesNeedingAssessmentKpi({
        completed_contexts: 45,
        students_with_contexts: 49,
        unique_scored_candidates: 2,
    }, undefined);
    assert.equal(fallback.display, '47');
    assert.equal(fallback.available, true);

    // No completed rounds: unavailable, not "0".
    const none = candidatesNeedingAssessmentKpi({
        completed_contexts: 0,
        candidates_with_completed_no_usable_score: 0,
    }, undefined);
    assert.equal(none.display, '—');
    assert.equal(none.available, false);
});

test('scoring follow-up KPI uses round counts and never fabricates a zero', () => {
    const kpi = scoringFollowupKpi({
        completed_contexts: 45,
        rounds_needing_followup: 43,
    }, { numerator: 37, denominator: 141 });
    assert.equal(kpi.display, '43');
    assert.equal(kpi.available, true);
    assert.match(kpi.meta, /rounds requiring scoring follow-up/);

    // Without the explicit counter the helper derives it from coverage.
    const derived = scoringFollowupKpi(
        { completed_contexts: 45 },
        { numerator: 37, denominator: 141 },
    );
    assert.equal(derived.display, '104');
    assert.equal(derived.available, true);

    // Empty scope: unavailable, not a misleading "0".
    const none = scoringFollowupKpi(
        { completed_contexts: 0, rounds_needing_followup: 0 },
        { numerator: 0, denominator: 0 },
    );
    assert.equal(none.display, '—');
    assert.equal(none.available, false);
});

// ── Recommended Actions ──────────────────────────────────────────────

test('recommended actions are driven by real counters and skip empty buckets', () => {
    const coverage = {
        completed_contexts: 45,
        followup_breakdown: {
            missing_pinned_snapshot: 30,
            no_configured_competencies: 12,
            no_mapped_evidence: 1,
            no_usable_score: 0,
            scoring_error: 0,
        },
    };
    const actions = recommendedActions(coverage, { numerator: 37, denominator: 141 }, undefined);
    const keys = actions.map((a) => a.key);
    assert.deepEqual(keys, ['missing-snapshot', 'no-competencies-config', 'no-mappings']);
    // The action text carries the count so the recommendation is auditable.
    assert.match(actions[0].text, /^30 completed attempt\(s\)/);
    assert.match(actions[1].text, /^12 completed attempt\(s\)/);
    // A zero bucket never produces an action.
    assert.doesNotMatch(actions.map((a) => a.text).join(' '), /\b0 completed attempt/);
});

test('recommended actions report per-assessment scoring gaps', () => {
    const assessment = {
        components: {
            aptitude: {
                key: 'aptitude', label: 'Aptitude', completed_rounds: 68,
                rounds_with_results: 31, rounds_with_valid_scores: 31,
            },
            coding: {
                key: 'coding', label: 'Coding', completed_rounds: 44,
                rounds_with_results: 0, rounds_with_valid_scores: 0,
            },
            interview: {
                key: 'interview', label: 'Interview', completed_rounds: 29,
                rounds_with_results: 1, rounds_with_valid_scores: 0,
            },
        },
    };
    const actions = recommendedActions(
        { completed_contexts: 141, followup_breakdown: {} },
        { numerator: 37, denominator: 141 },
        assessment,
    );
    const keys = actions.map((a) => a.key);
    assert.deepEqual(keys, ['no-results-coding', 'results-not-usable-interview']);
    assert.match(actions[0].text, /Coding: 44 completed round\(s\) have no persisted result/);
    assert.match(actions[1].text, /Interview: results exist but none is usable/);
});

test('recommended actions fall back to the coverage gap and then to all clear', () => {
    // No breakdown but completed rounds lack usable scores.
    const fallback = recommendedActions(
        { completed_contexts: 10, followup_breakdown: {} },
        { numerator: 4, denominator: 10 },
        undefined,
    );
    assert.equal(fallback.length, 1);
    assert.equal(fallback[0].key, 'missing-scores');
    assert.match(fallback[0].text, /^6 completed assessment round\(s\)/);

    // Everything scored: nothing to recommend.
    const clear = recommendedActions(
        { completed_contexts: 10, followup_breakdown: { missing_pinned_snapshot: 0 } },
        { numerator: 10, denominator: 10 },
        undefined,
    );
    assert.deepEqual(clear, []);
});
