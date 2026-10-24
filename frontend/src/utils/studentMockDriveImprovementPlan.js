const IMPROVEMENT_ROUNDS = new Set(['aptitude', 'coding', 'technical_interview', 'hr_interview']);

function isFiniteScore(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function buildFallbackRecommendations(report) {
  const recommendations = [];
  const seen = new Set();
  const add = (item) => {
    const key = `${item.round}\u0000${item.topic || ''}\u0000${item.action.trim().toLocaleLowerCase()}`;
    if (seen.has(key)) return;
    seen.add(key);
    recommendations.push(item);
  };

  for (const round of report?.rounds || []) {
    if (round.evaluation_status !== 'evaluated' || !IMPROVEMENT_ROUNDS.has(round.round_type)) continue;

    if (round.round_type === 'aptitude') {
      const missesByTopic = new Map();
      for (const question of round.details?.questions || []) {
        if (question.is_correct !== false) continue;
        const topic = typeof question.topic === 'string' && question.topic.trim()
          ? question.topic.trim()
          : 'Aptitude';
        missesByTopic.set(topic, (missesByTopic.get(topic) || 0) + 1);
      }
      for (const topic of missesByTopic.keys()) {
        add({
          key: `fallback-aptitude-${topic}`,
          round: 'Aptitude',
          topic,
          evidence: 'One or more persisted graded responses in this topic were incorrect.',
          action: `Review the missed graded questions in ${topic}.`,
        });
      }
    }

    if (round.round_type === 'coding') {
      for (const problem of round.details?.problems || []) {
        if (problem.evaluation_status !== 'evaluated'
          || !problem.attempted
          || !isFiniteScore(problem.score)
          || problem.score < 0
          || problem.score >= 1) continue;
        const title = typeof problem.title === 'string' && problem.title.trim()
          ? problem.title.trim()
          : 'this problem';
        add({
          key: `fallback-coding-${problem.problem_id ?? title}`,
          round: 'Coding',
          topic: title,
          evidence: `Finalized best submission score: ${Math.round(problem.score * 100)}% on the persisted normalized scale.`,
          action: `Review the solution approach for ${title}.`,
        });
      }
    }

    if (round.round_type === 'technical_interview' || round.round_type === 'hr_interview') {
      const roundName = round.round_type === 'technical_interview' ? 'Technical interview' : 'HR interview';
      for (const [index, turn] of (round.details?.turns || []).entries()) {
        if (!isFiniteScore(turn.score) || turn.score < 0 || turn.score >= 1) continue;
        const turnNumber = Number.isInteger(turn.turn_number) ? turn.turn_number : index + 1;
        const prompt = typeof turn.question === 'string' && turn.question.trim()
          ? turn.question.trim()
          : `Question ${turnNumber}`;
        add({
          key: `fallback-${round.round_type}-${turnNumber}-${index}`,
          round: roundName,
          topic: prompt,
          evidence: `Persisted evaluation score: ${turn.score} / 1.00.`,
          action: `Review your evaluated response to ${prompt}.`,
        });
      }
    }
  }

  const competencyScoring = report?.competency_scoring;
  if (competencyScoring?.scoring_policy_version === 'd1-v1'
    && ['final', 'provisional'].includes(competencyScoring.overall_score_status)) {
    for (const competency of competencyScoring.competencies || []) {
      if (competency.status !== 'assessed'
        || !isFiniteScore(competency.normalized_score)
        || competency.normalized_score < 0
        || competency.normalized_score >= 100) continue;
      const name = typeof competency.competency_name === 'string' && competency.competency_name.trim()
        ? competency.competency_name.trim()
        : 'this competency';
      add({
        key: `fallback-competency-${competency.competency_id ?? name}`,
        round: 'Competency results',
        topic: name,
        evidence: `Assessed D1 score: ${competency.normalized_score} / 100 from ${competency.evidence_count} persisted evidence item(s).`,
        action: `Review development opportunities for ${name} using the recorded D1 evidence.`,
      });
    }
  }

  return recommendations;
}

export function getStudentMockDriveImprovementPlan(report, insights) {
  const existingPlan = (insights || []).filter((item) => typeof item.action === 'string' && item.action.trim());
  if (existingPlan.length) return existingPlan;
  return buildFallbackRecommendations(report);
}
