import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeFacultyImprovementTrend } from './facultyImprovementTrend.js';

test('normalizes valid aggregate points in chronological sequence without inventing values', () => {
  const points = normalizeFacultyImprovementTrend({
    available: true,
    points: [
      { attempt_number: 2, average_score: 68.5, distinct_students: 4, comparable_series: 5, score_change_percentage_points: 8.5 },
      { attempt_number: 1, average_score: 60, distinct_students: 4, comparable_series: 5, score_change_percentage_points: null },
    ],
  });
  assert.deepEqual(points.map(({ label, average_score, distinct_students, score_change_percentage_points }) => ({
    label, average_score, distinct_students, score_change_percentage_points,
  })), [
    { label: 'Attempt 1', average_score: 60, distinct_students: 4, score_change_percentage_points: null },
    { label: 'Attempt 2', average_score: 68.5, distinct_students: 4, score_change_percentage_points: 8.5 },
  ]);
});

test('returns no trend for insufficient data and drops malformed or duplicate attempts', () => {
  assert.deepEqual(normalizeFacultyImprovementTrend({ available: false, points: [] }), []);
  assert.deepEqual(normalizeFacultyImprovementTrend({
    available: true,
    points: [
      { attempt_number: 1, average_score: 45, distinct_students: 2, comparable_series: 2 },
      { attempt_number: 1, average_score: 99, distinct_students: 3, comparable_series: 3 },
      { attempt_number: 2, average_score: null, distinct_students: 2, comparable_series: 2 },
      { attempt_number: 3, average_score: 50, distinct_students: 0, comparable_series: 1 },
    ],
  }).map((point) => point.label), ['Attempt 1']);
});
