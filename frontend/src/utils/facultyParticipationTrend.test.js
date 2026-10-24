import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizePracticeParticipationTrend } from './facultyParticipationTrend.js';

function trendPayload(counts = Array(12).fill(0)) {
  const weeks = counts.map((participating_students, index) => {
    const start = new Date(Date.UTC(2026, 6, 27 + index * 7));
    const end = new Date(start.getTime() + 6 * 24 * 60 * 60 * 1000);
    return {
      week_start: start.toISOString().slice(0, 10),
      week_end: end.toISOString().slice(0, 10),
      participating_students,
    };
  });
  return {
    bucket: 'week',
    timezone: 'UTC',
    range_start: weeks[0].week_start,
    range_end: weeks.at(-1).week_end,
    expected_weeks: 12,
    weeks,
  };
}

test('uses backend weekly participation counts and labels their UTC week starts', () => {
  const payload = trendPayload([0, 3, 1, 0, 2, 0, 0, 4, 0, 0, 0, 1]);
  const chartData = normalizePracticeParticipationTrend(payload);

  assert.equal(chartData.length, 12);
  assert.deepEqual(chartData.map((week) => week.participating_students), payload.weeks.map((week) => week.participating_students));
  assert.equal(chartData[1].week_start, '2026-08-03');
  assert.equal(chartData[1].label, 'Aug 3');
});

test('preserves complete zero-activity weeks without inventing nonzero counts', () => {
  assert.deepEqual(normalizePracticeParticipationTrend(trendPayload()).map((week) => week.participating_students), Array(12).fill(0));
});

test('rejects partial, malformed, non-UTC, and negative-count responses', () => {
  const incomplete = trendPayload();
  incomplete.weeks.pop();
  assert.throws(() => normalizePracticeParticipationTrend(incomplete), /incomplete/);

  const badTimezone = trendPayload();
  badTimezone.timezone = 'local';
  assert.throws(() => normalizePracticeParticipationTrend(badTimezone), /incomplete/);

  const badCount = trendPayload();
  badCount.weeks[0].participating_students = -1;
  assert.throws(() => normalizePracticeParticipationTrend(badCount), /invalid or partial/);
});
