import test from 'node:test';
import assert from 'node:assert/strict';
import {
  aggregateStudentPracticeScores,
  aggregatePracticeScoresByType,
  facultyPracticePercentage,
  independentPracticePercentage,
} from './practicePerformance.js';

test('normalizes only completed independent practice scores with valid maxima', () => {
  assert.equal(independentPracticePercentage({ assessment_source: 'independent_practice', evaluation_status: 'completed', score: 8, score_max: 10 }), 80);
  assert.equal(independentPracticePercentage({ assessment_source: 'faculty_assignment', evaluation_status: 'completed', score: 8, score_max: 10 }), null);
  assert.equal(independentPracticePercentage({ assessment_source: 'independent_practice', evaluation_status: 'in_progress', score: 8, score_max: 10 }), null);
  assert.equal(independentPracticePercentage({ assessment_source: 'independent_practice', evaluation_status: 'completed', score: null, score_max: 10 }), null);
});

test('normalizes evaluated assigned round evidence by each engine scale', () => {
  assert.equal(facultyPracticePercentage({ status: 'evaluated', round_type: 'aptitude', evidence: { correct: 3, evaluated_questions: 4 } }), 75);
  assert.equal(facultyPracticePercentage({ status: 'evaluated', round_type: 'coding', score: 1.5, evidence: { score_max: 2 } }), 75);
  assert.equal(facultyPracticePercentage({ status: 'evaluated', round_type: 'interview', score: 7.5, evidence: { evaluated_turns: 2 } }), 75);
  assert.equal(facultyPracticePercentage({ status: 'evaluation_pending', round_type: 'aptitude', evidence: { correct: 0, evaluated_questions: 2 } }), null);
  assert.equal(facultyPracticePercentage({ status: 'evaluated', round_type: 'interview', score: 7.5, evidence: { evaluated_turns: 0 } }), null);
});

test("deduplicates result IDs and weights each student's mean equally", () => {
  const results = aggregateStudentPracticeScores([
    { studentId: 1, resultId: 'a', percentage: 100 },
    { studentId: 1, resultId: 'a', percentage: 100 },
    { studentId: 1, resultId: 'b', percentage: 100 },
    { studentId: 2, resultId: 'c', percentage: 0 },
    { studentId: 3, resultId: 'bad', percentage: 120 },
  ]);
  assert.equal(results.studentCount, 2);
  assert.equal(results.resultCount, 3);
  assert.equal(results.average, 50);
});

test('keeps averages separate by engine type and weights students equally', () => {
  const scores = aggregatePracticeScoresByType([
    { studentId: 1, resultId: 'p1', roundType: 'aptitude', percentage: 80 },
    { studentId: 1, resultId: 'p2', roundType: 'aptitude', percentage: 100 },
    { studentId: 2, resultId: 'p3', roundType: 'aptitude', percentage: 40 },
    { studentId: 1, resultId: 'p4', roundType: 'coding', percentage: 60 },
  ]);
  assert.equal(scores.get('aptitude').studentCount, 2);
  assert.equal(scores.get('aptitude').average, 65);
  assert.equal(scores.get('coding').studentCount, 1);
  assert.equal(scores.get('coding').average, 60);
});

