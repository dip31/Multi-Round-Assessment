import test from 'node:test';
import assert from 'node:assert/strict';
import { getStudentMockDriveImprovementPlan } from './studentMockDriveImprovementPlan.js';

const evaluated = (round_type, details) => ({ round_type, evaluation_status: 'evaluated', details });

test('keeps an existing working plan unchanged and in its existing order', () => {
  const existing = [
    { key: 'second', action: 'Second recommendation', round: 'Coding' },
    { key: 'first', action: 'First recommendation', round: 'Aptitude' },
  ];
  assert.deepEqual(getStudentMockDriveImprovementPlan({ rounds: [] }, existing), existing);
});

test('uses a single graded aptitude miss even when other questions are unanswered or ungraded', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [evaluated('aptitude', { questions: [
    { topic: 'Reasoning', is_correct: false },
    { topic: 'Reasoning', is_correct: null, response_status: 'ungraded' },
    { topic: 'Data', is_correct: null, response_status: 'unanswered' },
  ] })] }, []);
  assert.equal(plan.length, 1);
  assert.equal(plan[0].topic, 'Reasoning');
  assert.match(plan[0].action, /missed graded questions/);
});

test('uses finalized coding scores only, excluding pending and unattempted problems', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [evaluated('coding', { problems: [
    { problem_id: 1, title: 'Valid', attempted: true, evaluation_status: 'evaluated', score: 0.5 },
    { problem_id: 2, title: 'Pending', attempted: true, evaluation_status: 'pending', score: null },
    { problem_id: 3, title: 'Not attempted', attempted: false, evaluation_status: 'unavailable', score: null },
    { problem_id: 4, title: 'Perfect', attempted: true, evaluation_status: 'evaluated', score: 1 },
  ] })] }, []);
  assert.equal(plan.length, 1);
  assert.equal(plan[0].topic, 'Valid');
});

test('uses persisted interview scores for either phase without inventing feedback', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [
    evaluated('technical_interview', { turns: [
      { turn_number: 1, question: 'Explain indexing', score: 0.6 },
      { turn_number: 2, question: 'Pending answer', score: null },
    ] }),
    evaluated('hr_interview', { turns: [{ turn_number: 1, question: 'Describe teamwork', score: 0.8 }] }),
  ] }, []);
  assert.equal(plan.length, 2);
  assert.deepEqual(plan.map((item) => item.round), ['Technical interview', 'HR interview']);
  assert.match(plan[0].action, /evaluated response/);
  assert.match(plan[0].evidence, /0.6 \/ 1.00/);
});

test('combines findings from every eligible round when no prior plan exists', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [
    evaluated('aptitude', { questions: [{ topic: 'Logic', is_correct: false }] }),
    evaluated('coding', { problems: [{ problem_id: 5, title: 'Arrays', attempted: true, evaluation_status: 'evaluated', score: 0.4 }] }),
    evaluated('technical_interview', { turns: [{ turn_number: 1, score: 0.7 }] }),
  ] }, []);
  assert.deepEqual(plan.map((item) => item.round), ['Aptitude', 'Coding', 'Technical interview']);
});

test('an unevaluated missing round does not suppress evidence from an evaluated round', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [
    evaluated('aptitude', { questions: [{ topic: 'Quantitative', is_correct: false }] }),
    { round_type: 'coding', evaluation_status: 'pending', details: { problems: [{ score: 0 }] } },
    { round_type: 'hr_interview', evaluation_status: 'unavailable', details: { turns: [] } },
  ] }, []);
  assert.equal(plan.length, 1);
  assert.equal(plan[0].round, 'Aptitude');
});

test('uses only D1 assessed competency results with an eligible scoring status', () => {
  const report = {
    rounds: [],
    competency_scoring: {
      scoring_policy_version: 'd1-v1', overall_score_status: 'provisional',
      competencies: [
        { competency_id: 'c1', competency_name: 'Problem solving', status: 'assessed', normalized_score: 60, evidence_count: 2 },
        { competency_id: 'c2', competency_name: 'Communication', status: 'not_assessed', normalized_score: null },
      ],
    },
  };
  assert.equal(getStudentMockDriveImprovementPlan(report, []).length, 1);
  report.competency_scoring.scoring_policy_version = 'unknown';
  assert.deepEqual(getStudentMockDriveImprovementPlan(report, []), []);
});

test('retains the empty state when there are no supported improvement findings', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [
    evaluated('aptitude', { questions: [{ topic: 'Logic', is_correct: true }, { topic: 'Logic', is_correct: null }] }),
    evaluated('coding', { problems: [{ attempted: false, evaluation_status: 'unavailable', score: null }] }),
    { round_type: 'technical_interview', evaluation_status: 'pending', details: { turns: [{ score: 0.2 }] } },
  ] }, []);
  assert.deepEqual(plan, []);
});

test('deduplicates duplicate evidence while retaining distinct topics', () => {
  const plan = getStudentMockDriveImprovementPlan({ rounds: [
    evaluated('aptitude', { questions: [
      { topic: 'Logic', is_correct: false },
      { topic: 'Logic', is_correct: false },
      { topic: 'Quantitative', is_correct: false },
    ] }),
  ] }, []);
  assert.deepEqual(plan.map((item) => item.topic), ['Logic', 'Quantitative']);
});
