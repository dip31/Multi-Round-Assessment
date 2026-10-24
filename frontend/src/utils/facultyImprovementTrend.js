export function normalizeFacultyImprovementTrend(payload) {
  if (!payload?.available || !Array.isArray(payload.points)) return [];

  const seenAttempts = new Set();
  return payload.points
    .filter((point) => {
      if (!Number.isInteger(point?.attempt_number) || point.attempt_number < 1
        || seenAttempts.has(point.attempt_number)
        || !Number.isFinite(point.average_score) || point.average_score < 0 || point.average_score > 100
        || !Number.isInteger(point.distinct_students) || point.distinct_students < 1
        || !Number.isInteger(point.comparable_series) || point.comparable_series < 1) return false;
      seenAttempts.add(point.attempt_number);
      return true;
    })
    .sort((left, right) => left.attempt_number - right.attempt_number)
    .map((point) => ({
      ...point,
      label: `Attempt ${point.attempt_number}`,
      score_change_percentage_points: Number.isFinite(point.score_change_percentage_points)
        ? point.score_change_percentage_points
        : null,
    }));
}
