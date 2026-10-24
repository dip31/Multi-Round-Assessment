const finiteNumber = (value) => typeof value === 'number' && Number.isFinite(value);

function normalizedPercentage(score, maximum) {
  if (!finiteNumber(score) || !finiteNumber(maximum) || maximum <= 0 || score < 0 || score > maximum) {
    return null;
  }
  return (score / maximum) * 100;
}

export function independentPracticePercentage(record) {
  if (record?.assessment_source !== 'independent_practice' || record.evaluation_status !== 'completed') return null;
  return normalizedPercentage(record.score, record.score_max);
}

export function facultyPracticePercentage(round) {
  if (round?.status !== 'evaluated') return null;
  const evidence = round.evidence || {};
  if (round.round_type === 'aptitude') {
    if (!finiteNumber(evidence.correct) || !finiteNumber(evidence.evaluated_questions) || evidence.evaluated_questions <= 0 || evidence.correct < 0 || evidence.correct > evidence.evaluated_questions) return null;
    return normalizedPercentage(evidence.correct, evidence.evaluated_questions);
  }
  if (round.round_type === 'coding') {
    return normalizedPercentage(round.score, evidence.score_max);
  }
  if (round.round_type === 'interview') {
    if (!finiteNumber(evidence.evaluated_turns) || evidence.evaluated_turns <= 0) return null;
    return normalizedPercentage(round.score, 10);
  }
  return null;
}

export function aggregateStudentPracticeScores(rows) {
  const uniqueResults = new Map();
  for (const row of rows) {
    const studentId = row.studentId;
    const score = row.percentage;
    if (studentId === null || studentId === undefined || row.resultId === null || row.resultId === undefined || !finiteNumber(score) || score < 0 || score > 100) continue;
    const resultKey = String(row.resultId);
    if (!uniqueResults.has(resultKey)) uniqueResults.set(resultKey, { studentId, percentage: score });
  }

  const byStudent = new Map();
  for (const result of uniqueResults.values()) {
    const current = byStudent.get(result.studentId) || { total: 0, count: 0 };
    current.total += result.percentage;
    current.count += 1;
    byStudent.set(result.studentId, current);
  }

  const studentScores = new Map([...byStudent.entries()].map(([id, value]) => [id, value.total / value.count]));
  const average = studentScores.size
    ? [...studentScores.values()].reduce((sum, score) => sum + score, 0) / studentScores.size
    : null;
  return { average, studentCount: studentScores.size, studentScores, studentTotals: byStudent, resultCount: uniqueResults.size };
}

export function aggregatePracticeScoresByType(rows) {
  const byType = new Map();
  for (const row of rows) {
    if (typeof row.roundType !== 'string' || !row.roundType) continue;
    const grouped = byType.get(row.roundType) || [];
    grouped.push(row);
    byType.set(row.roundType, grouped);
  }
  return new Map([...byType.entries()].map(([roundType, grouped]) => [
    roundType,
    aggregateStudentPracticeScores(grouped),
  ]));
}

