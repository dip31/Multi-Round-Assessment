const DAY_MS = 24 * 60 * 60 * 1000;

function parseUtcDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00.000Z`);
  return Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value ? null : date;
}

function formatUtcWeek(date) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function normalizePracticeParticipationTrend(payload) {
  if (payload?.bucket !== 'week' || payload?.timezone !== 'UTC' || payload?.expected_weeks !== 12 || !Array.isArray(payload.weeks) || payload.weeks.length !== 12) {
    throw new Error('Historical practice activity is incomplete.');
  }

  const rangeStart = parseUtcDate(payload.range_start);
  const rangeEnd = parseUtcDate(payload.range_end);
  if (!rangeStart || !rangeEnd) throw new Error('Historical practice activity has invalid date boundaries.');

  const weeks = payload.weeks.map((week, index) => {
    const start = parseUtcDate(week.week_start);
    const end = parseUtcDate(week.week_end);
    const expectedStart = new Date(rangeStart.getTime() + index * 7 * DAY_MS);
    if (!start || !end || start.getTime() !== expectedStart.getTime() || start.getUTCDay() !== 1
      || end.getTime() !== start.getTime() + 6 * DAY_MS
      || !Number.isInteger(week.participating_students) || week.participating_students < 0) {
      throw new Error('Historical practice activity has invalid or partial weekly data.');
    }
    return {
      week_start: week.week_start,
      label: formatUtcWeek(start),
      participating_students: week.participating_students,
    };
  });

  if (weeks[0].week_start !== payload.range_start
    || rangeEnd.getTime() !== parseUtcDate(weeks.at(-1).week_start).getTime() + 6 * DAY_MS) {
    throw new Error('Historical practice activity range does not match its weekly buckets.');
  }

  return weeks;
}
