import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    DRIVE_ROW_LIMIT,
    formatWeekLabel,
    toDepartmentBars,
    visibleDrives,
    sortDriveRowsAlphabetically,
    toStatusSlices,
    toParticipationPoints,
    toEvidenceCoverageRows,
    toAssessmentEvidenceSummary,
    toEvidenceGaps,
    toAptitudePerformance,
    safeAssessmentLabel,
    safeAssessmentKey,
    formatCoveragePercent,
    codingCoverageSummary,
} from './readinessCharts.js';

const pageSource = await readFile(
    new URL('../pages/TPOReadinessPage.jsx', import.meta.url),
    'utf8',
);
const formattingSource = await readFile(
    new URL('./readinessFormatting.js', import.meta.url),
    'utf8',
);

// ── Week label (still used by participation/drive-activity charts) ────

test('formatWeekLabel turns an ISO week start into a readable label', () => {
    assert.equal(formatWeekLabel('2026-01-05'), 'Jan 5');
    assert.equal(formatWeekLabel('2026-12-28'), 'Dec 28');
    assert.equal(formatWeekLabel('not-a-date'), 'not-a-date');
    assert.equal(formatWeekLabel(null), '');
});

// ── Department readiness ──────────────────────────────────────────────

test('toDepartmentBars keeps real departments with finite averages', () => {
    const rows = toDepartmentBars([
        { department: 'Computer Science', avg_readiness: 71.2, candidates: 4, attempts: 6 },
        { department: 'Unspecified', avg_readiness: null, candidates: 1, attempts: 1 },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].department, 'Computer Science');
    assert.equal(rows[0].avg_readiness, 71.2);
    assert.equal(rows[0].candidates, 4);
    assert.equal(rows[0].attempts, 6);
});

test('toDepartmentBars renders multiple departments independently', () => {
    const rows = toDepartmentBars([
        { department: 'Electronics & Communication', avg_readiness: 29.0, candidates: 1, attempts: 1 },
        { department: 'Computer Science', avg_readiness: 64.5, candidates: 3, attempts: 4 },
    ]);
    assert.equal(rows.length, 2);
    assert.deepEqual(rows.map((r) => r.department), ['Computer Science', 'Electronics & Communication']);
    assert.equal(rows[0].avg_readiness, 64.5);
    assert.equal(rows[1].avg_readiness, 29.0);
});

test('toDepartmentBars sorts departments by display name', () => {
    const rows = toDepartmentBars([
        { department: 'Mechanical', avg_readiness: 50, attempts: 1 },
        { department: 'civil', avg_readiness: 40, attempts: 1 },
        { department: 'Computer Science', avg_readiness: 60, attempts: 1 },
    ]);
    assert.deepEqual(rows.map((r) => r.department), ['civil', 'Computer Science', 'Mechanical']);
});

test('toDepartmentBars groups whitespace/casing variants into one bar', () => {
    const rows = toDepartmentBars([
        { department: 'Computer Science', avg_readiness: 60, candidates: 1, attempts: 1 },
        { department: '  computer   science ', avg_readiness: 80, candidates: 1, attempts: 1 },
        { department: 'COMPUTER SCIENCE', avg_readiness: 70, candidates: 2, attempts: 2 },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].candidates, 4);
    assert.equal(rows[0].attempts, 4);
    // Weighted mean: (60*1 + 80*1 + 70*2) / 4 = 70.
    assert.equal(rows[0].avg_readiness, 70);
    // Display name is a normalized readable spelling, not the raw padded one.
    assert.equal(rows[0].department, 'Computer Science');
});

test('toDepartmentBars maps missing/blank names to Unspecified', () => {
    const rows = toDepartmentBars([
        { department: null, avg_readiness: 30, attempts: 1 },
        { department: '   ', avg_readiness: 50, attempts: 1 },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].department, 'Unspecified');
    assert.equal(rows[0].avg_readiness, 40);
});

test('toDepartmentBars keeps a legitimate zero average', () => {
    const rows = toDepartmentBars([
        { department: 'Civil', avg_readiness: 0, candidates: 1, attempts: 1 },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].avg_readiness, 0);
});

test('toDepartmentBars excludes unscored departments (no fake zero bars)', () => {
    const rows = toDepartmentBars([
        { department: 'Computer Science', avg_readiness: null, candidates: 2, attempts: 0 },
        { department: 'Civil', avg_readiness: 'n/a', candidates: 1, attempts: 1 },
        { department: 'Mechanical', avg_readiness: 55, candidates: 1, attempts: 1 },
    ]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].department, 'Mechanical');
});

test('toDepartmentBars returns [] for empty / missing input', () => {
    assert.deepEqual(toDepartmentBars([]), []);
    assert.deepEqual(toDepartmentBars(null), []);
    assert.deepEqual(toDepartmentBars(undefined), []);
});

// ── Drive table 10-row limit ──────────────────────────────────────────

function makeDrives(n) {
    return Array.from({ length: n }, (_, i) => ({ drive_id: i + 1 }));
}

test('visibleDrives caps the initial view at 10 rows', () => {
    assert.equal(DRIVE_ROW_LIMIT, 10);
    const view = visibleDrives(makeDrives(16), false);
    assert.equal(view.visible.length, 10);
    assert.equal(view.total, 16);
    assert.equal(view.shown, 10);
    assert.equal(view.hiddenCount, 6);
    assert.equal(view.canExpand, true);
});

test('visibleDrives expands to reveal the remaining filtered drives', () => {
    const drives = makeDrives(16);
    const collapsed = visibleDrives(drives, false);
    const expanded = visibleDrives(drives, true);
    assert.equal(expanded.visible.length, 16);
    assert.equal(expanded.shown, 16);
    assert.equal(expanded.hiddenCount, 0);
    // Collapsing back restores exactly the first 10 of the same dataset.
    assert.deepEqual(collapsed.visible.map((d) => d.drive_id), expanded.visible.slice(0, 10).map((d) => d.drive_id));
});

test('visibleDrives hides the toggle when there is nothing more to show', () => {
    const view = visibleDrives(makeDrives(10), false);
    assert.equal(view.canExpand, false);
    assert.equal(view.expanded, false);
    const fewer = visibleDrives(makeDrives(3), true);
    assert.equal(fewer.canExpand, false);
    assert.equal(fewer.expanded, false);
    assert.equal(fewer.visible.length, 3);
});

test('visibleDrives tolerates empty and invalid input', () => {
    assert.equal(visibleDrives(null, false).total, 0);
    assert.deepEqual(visibleDrives(undefined, true).visible, []);
});

// ── Page wiring for the charts and drive controls ─────────────────────

test('the readiness page keeps live charts separate from table-only demo presentation data', () => {
    assert.match(pageSource, /toDepartmentBars\(byDepartment\)/);
    assert.match(pageSource, /visibleDrives\(tableDrives, drivesExpanded\)/);
    assert.match(pageSource, /withReadinessDemoValues\(sortedTableDrives\)/);
    assert.match(pageSource, /Illustrative readiness values fill rows without eligible results/);
});

test('Cohort Outcomes keeps only Department Readiness and its empty state', () => {
    // Regression: the two removed graphs and their chart/empty containers must
    // no longer be rendered anywhere on the page.
    assert.match(pageSource, /data-testid="readiness-by-department"/);
    assert.match(pageSource, /data-testid="department-chart"/);
    assert.match(pageSource, /data-testid="department-empty"/);
    assert.doesNotMatch(pageSource, /data-testid="readiness-over-time"/);
    assert.doesNotMatch(pageSource, /data-testid="readiness-distribution"/);
    assert.doesNotMatch(pageSource, /data-testid="over-time-chart"/);
    assert.doesNotMatch(pageSource, /data-testid="distribution-chart"/);
    assert.doesNotMatch(pageSource, /data-testid="over-time-empty"/);
    assert.doesNotMatch(pageSource, /data-testid="distribution-empty"/);
    assert.doesNotMatch(pageSource, /Cohort Readiness Over Time/);
    assert.doesNotMatch(pageSource, /Readiness Distribution/);
});

test('the drive table exposes a View All / Show Less toggle', () => {
    assert.match(pageSource, /data-testid="drive-toggle"/);
    assert.match(pageSource, /aria-expanded=\{drivesExpanded\}/);
    assert.match(pageSource, /View All Drives/);
    assert.match(pageSource, /Show Less/);
    assert.match(pageSource, /driveView\.visible\.map/);
});

test('filters and refresh reset the drive table to 10 rows', () => {
    // setFilter resets, and a successful fetchData resets too.
    const resetCount = (pageSource.match(/setDrivesExpanded\(false\)/g) || []).length;
    assert.ok(resetCount >= 2, `expected >=2 resets, found ${resetCount}`);
});

test('charts use a fixed measurable height so containers never collapse', () => {
    assert.match(pageSource, /style=\{\{ height: Math\.max\(200, deptBars\.length \* 56\) \}\}/);
});

// ── Drive activity: status distribution ────────────────────────────────

test('toStatusSlices mirrors the real status column and flags excluded drafts', () => {
    const slices = toStatusSlices({
        total: 3,
        rows: [
            { status: 'published', drives: 1, pct: 33.3, analysed: true },
            { status: 'draft', drives: 1, pct: 33.3, analysed: false },
            { status: 'completed', drives: 1, pct: 33.4, analysed: true },
        ],
    });
    assert.equal(slices.length, 3);
    // Model order is preserved: draft, published, active, completed.
    assert.deepEqual(slices.map((s) => s.key), ['draft', 'published', 'completed']);
    assert.equal(slices[0].analysed, false);
    assert.equal(slices[1].analysed, true);
    assert.equal(slices[2].drives, 1);
});

test('toStatusSlices never invents a slice for a status that does not exist', () => {
    assert.deepEqual(toStatusSlices({ total: 1, rows: [{ status: 'active', drives: 0 }] }), []);
    assert.deepEqual(toStatusSlices({ rows: [] }), []);
    assert.deepEqual(toStatusSlices(undefined), []);
    assert.deepEqual(toStatusSlices({}), []);
    assert.equal(toStatusSlices({ rows: [{ status: 'active', drives: '2', pct: 'x' }] })[0].drives, 2);
    assert.equal(toStatusSlices({ rows: [{ status: 'active', drives: '2', pct: 'x' }] })[0].pct, 0);
});

// ── Assessment evidence helpers (Section 2, EDI5) ─────────────────────

const ASSESSMENT_FIXTURE = {
    summary: {
        evidence_coverage: {
            available: true,
            value: 25.0,
            numerator: 1,
            denominator: 4,
            by_type: [
                {
                    type: 'aptitude', label: 'Aptitude',
                    completed_rounds: 2, rounds_with_results: 2,
                    rounds_with_valid_scores: 1, coverage_pct: 50.0,
                },
                {
                    type: 'coding', label: 'Coding',
                    completed_rounds: 2, rounds_with_results: 1,
                    rounds_with_valid_scores: 0, coverage_pct: 0.0,
                },
                {
                    type: 'interview', label: 'Interview',
                    completed_rounds: 0, rounds_with_results: 0,
                    rounds_with_valid_scores: 0, coverage_pct: null,
                },
            ],
        },
    },
    components: {
        aptitude: {
            key: 'aptitude', label: 'Aptitude', available: true,
            completed_rounds: 2, rounds_with_results: 2, rounds_with_valid_scores: 1,
            candidates: 1, avg_score: 60.0, min_score: 60.0, max_score: 60.0,
            scale: { min: 0, max: 100, unit: 'accuracy %', description: 'x' },
            reason: null,
        },
        coding: {
            key: 'coding', label: 'Coding', available: false,
            completed_rounds: 2, rounds_with_results: 1, rounds_with_valid_scores: 0,
            candidates: 0, avg_score: null, min_score: null, max_score: null,
            scale: { min: 0, max: 1, unit: 'score', description: 'y' },
            reason: 'none usable',
        },
        interview: {
            key: 'interview', label: 'Interview', available: false,
            completed_rounds: 0, rounds_with_results: 0, rounds_with_valid_scores: 0,
            candidates: 0, avg_score: null, min_score: null, max_score: null,
            scale: { min: 0, max: 1, unit: 'score', description: 'z' },
            reason: 'no rounds',
        },
    },
    topic_performance: {
        available: true,
        rows: [
            { topic: 'Data Interpretation', responses: 60, correct: 13, accuracy: 21.7, candidates: 1 },
            { topic: 'Verbal Ability', responses: 20, correct: 2, accuracy: 10.0, candidates: 2 },
        ],
    },
};

test('toEvidenceCoverageRows merges coverage counts without inventing values', () => {
    const rows = toEvidenceCoverageRows(ASSESSMENT_FIXTURE);
    assert.equal(rows.length, 3);
    assert.equal(rows[0].type, 'aptitude');
    assert.equal(rows[0].missing, 1);
    assert.equal(rows[0].coveragePct, 50.0);
    assert.equal(rows[0].candidates, 1);
    assert.equal(rows[1].coveragePct, 0.0);
    assert.equal(rows[2].completed, 0);
    assert.equal(rows[2].coveragePct, null); // zero denominator -> unavailable
    assert.deepEqual(toEvidenceCoverageRows(null), []);
});

test('toAssessmentEvidenceSummary reports the real numerator and denominator', () => {
    const summary = toAssessmentEvidenceSummary(ASSESSMENT_FIXTURE);
    assert.equal(summary.available, true);
    assert.equal(summary.value, 25.0);
    assert.equal(summary.numerator, 1);
    assert.equal(summary.denominator, 4);
    assert.equal(summary.rows.length, 3);
    assert.equal(toAssessmentEvidenceSummary(null).available, false);
});

test('toEvidenceGaps separates missing evidence from a zero score', () => {
    const gaps = toEvidenceGaps(ASSESSMENT_FIXTURE);
    const coding = gaps.find((g) => g.type === 'coding');
    assert.equal(coding.completed, 2);
    assert.equal(coding.valid, 0);
    assert.equal(coding.missing, 2);
    assert.equal(coding.missingPct, 100.0);
    // Types with no completed rounds are not gap rows.
    assert.equal(gaps.some((g) => g.type === 'interview'), false);
});

test('toAptitudePerformance reports mean and pooled accuracy separately', () => {
    const aptitude = toAptitudePerformance(ASSESSMENT_FIXTURE);
    assert.equal(aptitude.available, true);
    assert.equal(aptitude.mean, 60.0);
    assert.equal(aptitude.responses, 80);
    assert.equal(aptitude.correct, 15);
    assert.equal(aptitude.pooled, 18.8); // 15 / 80 * 100, one decimal
    assert.equal(aptitude.candidates, 1);
    assert.equal(toAptitudePerformance(null).available, false);
});

test('assessment labels use safe fallbacks and never concatenate', () => {
    assert.equal(safeAssessmentLabel(null, 'coding'), 'Coding');
    assert.equal(safeAssessmentLabel(undefined, 'interview'), 'Interview');
    assert.equal(safeAssessmentLabel('', 'aptitude'), 'Aptitude');
    assert.equal(safeAssessmentLabel('  ', 'coding'), 'Coding');
    assert.equal(safeAssessmentLabel('Custom Label', 'coding'), 'Custom Label');
    const key = safeAssessmentKey(null, 'coding');
    assert.equal(key, 'coding');
    assert.equal(safeAssessmentKey('', 'interview'), 'interview');
});

test('coverage percent and coding summary use denominator-based calculation', () => {
    assert.equal(formatCoveragePercent(5, 44), 11.4);
    assert.equal(formatCoveragePercent(0, 0), null);
    const summary = codingCoverageSummary({
        completed: 44,
        withResults: 5,
        valid: 5,
        coveragePct: 11.4,
        candidates: 1,
        available: true,
        reason: null,
    });
    assert.equal(summary.completed, 44);
    assert.equal(summary.valid, 5);
    assert.equal(summary.coveragePct, 11.4);
    assert.equal(summary.candidates, 1);
});

test('toEvidenceCoverageRows never produces concatenated labels', () => {
    const assessment = {
        summary: {
            evidence_coverage: {
                by_type: [
                    { type: 'coding', label: null, completed_rounds: 44, rounds_with_results: 5, rounds_with_valid_scores: 5, coverage_pct: 11.4 },
                    { type: 'interview', label: undefined, completed_rounds: 29, rounds_with_results: 1, rounds_with_valid_scores: 1, coverage_pct: 3.4 },
                    { type: 'aptitude', label: '', completed_rounds: 68, rounds_with_results: 31, rounds_with_valid_scores: 31, coverage_pct: 45.6 },
                ],
            },
        },
        components: {
            coding: { key: 'coding', label: null, candidates: 1, avg_score: 0.0, available: true },
            interview: { key: 'interview', label: undefined, candidates: 1, avg_score: 0.34, available: true },
            aptitude: { key: 'aptitude', label: '', candidates: 2, avg_score: 18.25, available: true },
        },
    };
    const rows = toEvidenceCoverageRows(assessment);
    assert.equal(rows.length, 3);
    for (const row of rows) {
        assert.ok(row.label);
        assert.ok(row.label.length > 0);
        assert.doesNotMatch(row.label, /available$/i);
        assert.doesNotMatch(row.label, /Codingavailable/i);
        assert.doesNotMatch(row.label, /Interviewavailable/i);
    }
    const coding = rows.find((r) => r.type === 'coding');
    assert.equal(coding.label, 'Coding');
    assert.equal(coding.valid, 5);
    assert.equal(coding.completed, 44);
});

test('toParticipationPoints plots only buckets with a real event', () => {
    const points = toParticipationPoints([
        { bucket_start: '2026-10-05', registrations: 0, completions: 0 },
        { bucket_start: '2026-10-03', registrations: 73, completions: 23 },
        { bucket_start: '2026-10-04', registrations: 5, completions: 0 },
    ]);
    assert.equal(points.length, 2); // the empty bucket is not interpolated
    assert.deepEqual(points.map((p) => p.key), ['2026-10-03', '2026-10-04']);
    assert.equal(points[0].label, 'Oct 3');
    assert.equal(points[0].registrations, 73);
    assert.equal(points[1].completions, 0);
    assert.deepEqual(toParticipationPoints(undefined), []);
    assert.deepEqual(toParticipationPoints('nope'), []);
});

// ── Page wiring for the two-section layout ─────────────────────────────

test('the page separates drive activity from candidate readiness', () => {
    assert.match(pageSource, /data-testid="section-drive-activity"/);
    assert.match(pageSource, /data-testid="section-readiness"/);
    assert.match(pageSource, /data-testid="activity-kpis"/);
    assert.match(pageSource, /Section 1 — Drive Activity/);
    assert.match(pageSource, /Section 2 — Assessment Evidence and Readiness/);
    assert.match(pageSource, /data-testid="readiness-evidence-notice"/);
});

test('the two unwanted by-drive charts are removed from the page', () => {
    assert.doesNotMatch(pageSource, /data-testid="completion-by-drive-card"/);
    assert.doesNotMatch(pageSource, /data-testid="completion-rate-card"/);
    assert.doesNotMatch(pageSource, /activityDriveRows/);
    assert.doesNotMatch(pageSource, /toCompletionStackRows/);
    assert.doesNotMatch(pageSource, /toRateRows/);
});

test('every remaining drive activity chart is wired to the drive_activity payload', () => {
    assert.match(pageSource, /toStatusSlices\(activityStatus\)/);
    assert.match(pageSource, /toParticipationPoints\(activityOverTime\?\.points\)/);
    assert.match(pageSource, /data\?\.drive_activity/);
    assert.match(pageSource, /drive_activity: data\.drive_activity/);
});

test('each remaining drive activity chart has a fixed container and an honest empty state', () => {
    for (const id of ['drive-status', 'participation']) {
        assert.match(pageSource, new RegExp(`data-testid="${id}-chart"`));
        assert.match(pageSource, new RegExp(`data-testid="${id}-empty"`));
    }
});

test('a zero completion-rate denominator is disclosed as unavailable, never 0%', () => {
    assert.match(pageSource, /never rendered as 0%/);
    assert.match(pageSource, /activityRate == null \? '—'/);
    assert.match(pageSource, /No participants — rate unavailable, not 0%/);
});

test('drive rows sort alphabetically before the visible-row limit without merging duplicates', () => {
    const input = [
        { drive_id: 7, company_name: ' xyc comp ', target_role: 'Analyst' },
        { drive_id: 9, company_name: 'abcde', target_role: 'Z Engineer' },
        { drive_id: 6, company_name: 'ABCDE', target_role: 'A Engineer' },
        { drive_id: 8, company_name: 'TestCo', target_role: 'Analyst' },
        { drive_id: 5, company_name: ' testco ', target_role: 'Analyst' },
    ];
    const sorted = sortDriveRowsAlphabetically(input);
    assert.deepEqual(sorted.map((row) => row.drive_id), [6, 9, 5, 8, 7]);
    assert.equal(sorted[0].company_name, 'ABCDE');
    assert.equal(sorted[2].company_name, ' testco ');
    assert.equal(input[0].drive_id, 7); // sorting keeps the source array unchanged
    assert.deepEqual(sortDriveRowsAlphabetically(undefined), []);

    const visible = visibleDrives(sorted, false, 3);
    assert.deepEqual(visible.visible.map((row) => row.drive_id), [6, 9, 5]);
    assert.equal(visible.hiddenCount, 2);
});

test('the drive table shows every filtered drive in sorted order', () => {
    assert.match(pageSource, /visibleDrives\(tableDrives, drivesExpanded\)/);
    assert.match(pageSource, /sortDriveRowsAlphabetically\(byDrive\)/);
    assert.doesNotMatch(pageSource, /Number\(b\?\.enrolled\).*Number\(a\?\.enrolled\)/s);
    assert.doesNotMatch(pageSource, />\s*Demo\s*</);
    assert.match(pageSource, /sr-only.*Illustrative display-only value/s);
    assert.match(pageSource, /not an assessment result and not persisted/);
    assert.doesNotMatch(pageSource, /byDrive\.filter\(\(d\) => d\.enrolled > 0\)/);
    assert.match(pageSource, /Participants/);
    assert.match(pageSource, /Contexts/);
    assert.match(pageSource, /Scored attempts/);
    assert.match(pageSource, /attempt-weighted/);
    assert.match(pageSource, /data-testid="drive-table-basis-note"/);
});

test('the page renders the assessment evidence sections and exports them', () => {
    assert.match(pageSource, /data-testid="assessment-coverage"/);
    assert.match(pageSource, /data-testid="aptitude-performance"/);
    // The old aptitude topic table (data-testid="topic-performance") was intentionally
    // replaced by the Aptitude Assessment Insights panel in EDI5. Assert the new panel.
    assert.match(pageSource, /data-testid="aptitude-assessment-insights"/);
    assert.match(pageSource, /data-testid="assessment-type-status"/);
    assert.match(pageSource, /data-testid="evidence-gaps"/);
    assert.match(pageSource, /data-testid="readiness-unavailable-summary"/);
    assert.match(pageSource, /assessment_performance: data\.assessment_performance/);
    assert.match(pageSource, /toAssessmentEvidenceSummary\(assessment\)/);
    assert.match(pageSource, /toEvidenceGaps\(assessment\)/);
    assert.match(pageSource, /toAptitudePerformance\(assessment\)/);
    // toTopicPerformance is no longer called from the page — the topic table was replaced
    // by the Aptitude Assessment Insights panel. Assert the new panel heading instead.
    assert.match(pageSource, /Aptitude Assessment Insights/);
});

test('Assessment Completion & Scoring uses the required compact headers', () => {
    assert.match(pageSource, /Assessment Completion & Scoring/);
    assert.doesNotMatch(pageSource, /Assessment Evidence Performance/);
    assert.match(pageSource, /Completion & Scoring Summary/);
    assert.match(pageSource, /completed round\(s\) with valid scores/);
    for (const header of [
        'Completed Rounds',
        'Valid Scores',
        'Score Coverage',
        'Candidates Assessed',
        'Average Score',
    ]) {
        assert.match(pageSource, new RegExp(header));
    }
});

test('Recommended Actions is data-driven and shows an all-clear when clean', () => {
    assert.match(pageSource, /data-testid="recommended-actions"/);
    assert.match(pageSource, /recommendedActionList/);
    assert.match(pageSource, /recommendedActions/);
    assert.match(pageSource, /All clear — no follow-up actions identified in scope/);
    // Actions are derived from real backend counters, never hardcoded counts.
    // The follow-up reason keys live in the shared, unit-tested util module.
    for (const key of [
        'missing_pinned_snapshot',
        'no_configured_competencies',
        'no_mapped_evidence',
        'no_usable_score',
        'scoring_error',
    ]) {
        assert.match(formattingSource, new RegExp(key));
    }
    assert.match(formattingSource, /followup_breakdown/);
});

test('Section 2 keeps one compact data-driven readiness status, no duplicated warnings', () => {
    // The redundant provenance chip is removed; the subtitle alone states the
    // data basis, and no internal table/service names are exposed.
    assert.doesNotMatch(pageSource, /source="Persisted assessment records"/);
    assert.doesNotMatch(pageSource, /assessment_performance · score_session_competencies/);
    assert.match(pageSource, /subtitle=\{READINESS_SECTION2_SUBTITLE\}/);
    assert.doesNotMatch(pageSource, /All values are computed from persisted assessment records/);
    assert.doesNotMatch(pageSource, /Persisted performance results for completed mock-drive assessment rounds/);
    // The single status message is fed by live coverage counters (never hardcoded).
    assert.match(pageSource, /data-testid="readiness-funnel-counts"/);
    for (const counter of [
        'completed_contexts',
        'contexts_with_snapshot',
        'contexts_with_configured_competencies',
        'contexts_with_evidence_mappings',
    ]) {
        // Each coverage counter still feeds the single notice (the redesign
        // adds no duplicate warning paragraphs that repeat them).
        assert.match(pageSource, new RegExp(`coverage\\?\\.${counter}`));
    }
    assert.equal(pageSource.split('data-testid="readiness-evidence-notice"').length - 1, 1);
    assert.equal(pageSource.split('data-testid="readiness-funnel-counts"').length - 1, 1);
    assert.doesNotMatch(pageSource, /\{avgKpi\.meta\}/);
    assert.doesNotMatch(pageSource, /No scored competency attempts in scope/);
    assert.doesNotMatch(pageSource, /Needs 2\+ eligible scored attempts/);
    // Removed duplicated warning layers.
    assert.doesNotMatch(pageSource, /Readiness cannot be derived from participation or raw activity counts/);
    assert.doesNotMatch(pageSource, /data-testid="readiness-unavailable-reason"/);
    assert.doesNotMatch(pageSource, /Competency Readiness — Unavailable/);
    assert.doesNotMatch(pageSource, /data-testid="assessment-performance-note"/);
});

test('the redesigned KPI cards are backend-driven with no fabricated metrics', () => {
    // Card 1 — Average Readiness keeps the authoritative backend value.
    assert.match(pageSource, /avgKpi\.display/);
    // Card 2 — Assessment Coverage uses the existing evidence-coverage summary.
    assert.match(pageSource, /testId="kpi-assessment-coverage"/);
    assert.match(pageSource, /assessmentCoverageKpi\.display/);
    // Card 3 — Candidates Needing Assessment uses distinct-candidate coverage.
    assert.match(pageSource, /testId="kpi-candidates-needing-assessment"/);
    assert.match(pageSource, /needingAssessmentKpi\.display/);
    // Card 4 — Scoring Follow-up uses the follow-up round count.
    assert.match(pageSource, /testId="kpi-scoring-followup"/);
    assert.match(pageSource, /scoringFollowupKpi\.display/);
    // The derivations live in the shared, unit-tested util module.
    assert.match(pageSource, /from '\.\.\/utils\/readinessFormatting'/);
    assert.match(pageSource, /assessmentCoverageKpi as assessmentCoverageKpiValue/);
    assert.match(pageSource, /candidatesNeedingAssessmentKpi/);
    assert.match(pageSource, /scoringFollowupKpi as scoringFollowupKpiValue/);
    // The three replaced cards and their helpers are gone.
    assert.doesNotMatch(pageSource, /testId="kpi-attempt-improvement"/);
    assert.doesNotMatch(pageSource, /testId="kpi-threshold"/);
    assert.doesNotMatch(pageSource, /testId="kpi-placement-rate"/);
    assert.doesNotMatch(pageSource, /thresholdKpi/);
    assert.doesNotMatch(pageSource, /placementKpi/);
    assert.doesNotMatch(pageSource, /improveKpi/);
    // Long unavailable labels render smaller so cards keep an even height.
    assert.match(pageSource, /const longText = typeof value === 'string' && value\.length > 6/);
});

// Regression: a helper used in the page but dropped from the import block
// throws `ReferenceError: <helper> is not defined` during render, which blanks
// the whole Readiness page (Vite does not fail builds on undefined globals).
test('every readiness chart helper called by the page is imported', async () => {
    const chartsSource = await readFile(
        new URL('./readinessCharts.js', import.meta.url),
        'utf8',
    );
    const exported = new Set(
        [...chartsSource.matchAll(/export function (\w+)/g)].map((m) => m[1]),
    );
    const importMatch = /import\s*\{([^}]*)\}\s*from\s*'\.\.\/utils\/readinessCharts'/.exec(pageSource);
    assert.ok(importMatch, 'expected the page to import readinessCharts helpers');
    const imported = new Set(
        importMatch[1].split(',').map((name) => name.trim()).filter(Boolean),
    );
    const called = new Set(
        [...pageSource.matchAll(/\b(to[A-Z][A-Za-z0-9]*)\(/g)]
            .map((m) => m[1])
            .filter((name) => exported.has(name)),
    );
    assert.ok(called.size > 0, 'expected the page to call chart helpers');
    for (const name of called) {
        assert.ok(imported.has(name), `${name} is called in TPOReadinessPage but not imported from readinessCharts`);
    }
});
