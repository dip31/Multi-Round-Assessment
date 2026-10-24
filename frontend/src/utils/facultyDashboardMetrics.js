export function studentDisplayName(student) {
  const identifiers = new Set([student?.user_id, student?.roll_number]
    .filter((value) => value !== null && value !== undefined)
    .map((value) => String(value).trim().toLocaleLowerCase()));
  const name = [student?.full_name, student?.name]
    .find((value) => typeof value === 'string' && value.trim() && !value.includes('@') && !identifiers.has(value.trim().toLocaleLowerCase()));
  return name?.trim() || 'Name unavailable';
}

export function sessionStatusReason(status) {
  const normalizedStatus = normalizeSessionStatus(status);
  return ({
    in_progress: 'The latest session is in progress.',
    active: 'The latest session is in progress.',
    not_started: 'No assessment session has been started.',
    terminated: 'The latest session did not complete.',
  })[normalizedStatus] || null;
}

function normalizeSessionStatus(status) {
  if (typeof status !== 'string') return null;
  const normalized = status.trim().toLocaleLowerCase().replace(/[\s-]+/gu, '_');
  return normalized === 'active' ? 'in_progress' : normalized;
}

export function resolveCheckInDisplayName(student) {
  const candidates = [student?.full_name, student?.name];
  for (const candidate of candidates) {
    if (typeof candidate !== 'string') continue;
    const name = candidate.trim().replace(/\s+/gu, ' ');
    if (!name || name.includes('@')) continue;

    const nameKey = name.normalize('NFKC').toLocaleLowerCase();
    const placeholder = /^(?:tester|test|test student|demo|demo student|fixture|sample|unknown|unnamed|student|candidate)$/iu;
    const identifierLike = /^(?:stu(?:dent)?|user|candidate|test|demo|fixture)[\s_-]*\d+$/iu;
    const parts = name.split(' ');
    if ([...name].length < 2 || placeholder.test(nameKey) || identifierLike.test(nameKey)
      || parts.every((part) => [...part].length === 1)) continue;

    return name;
  }
  return null;
}

export function selectStudentsNeedingFollowUp(students, limit = 5, preferredNames = []) {
  const selectionLimit = Math.max(0, Number.isFinite(Number(limit)) ? Math.floor(Number(limit)) : 0);
  if (!selectionLimit) return [];
  const priority = { in_progress: 0, active: 0, terminated: 1, not_started: 2 };
  const latestByStudentId = new Map();
  for (const student of students) {
    if (student?.user_id === null || student?.user_id === undefined) continue;
    const key = String(student.user_id);
    const previous = latestByStudentId.get(key);
    const startedAt = Date.parse(student.session_started_at || '');
    const previousStartedAt = Date.parse(previous?.session_started_at || '');
    const sessionId = Number(student.latest_session_id ?? student.session_id);
    const previousSessionId = Number(previous?.latest_session_id ?? previous?.session_id);
    if (!previous || (Number.isFinite(startedAt) && (!Number.isFinite(previousStartedAt) || startedAt > previousStartedAt))
      || (startedAt === previousStartedAt && Number.isFinite(sessionId) && (!Number.isFinite(previousSessionId) || sessionId > previousSessionId))) {
      latestByStudentId.set(key, { ...student, session_status: normalizeSessionStatus(student.session_status) });
    }
  }

  const candidates = [...latestByStudentId.values()]
    .filter((student) => Object.hasOwn(priority, student.session_status))
    .map((student) => ({ student, name: resolveCheckInDisplayName(student) }))
    .filter((candidate) => candidate.name)
    .sort((leftCandidate, rightCandidate) => {
      const left = leftCandidate.student;
      const right = rightCandidate.student;
      const stateDifference = priority[left.session_status] - priority[right.session_status];
      if (stateDifference) return stateDifference;
      const leftParsedTime = Date.parse(left.session_started_at || '');
      const rightParsedTime = Date.parse(right.session_started_at || '');
      const leftTime = Number.isFinite(leftParsedTime) ? leftParsedTime : Number.POSITIVE_INFINITY;
      const rightTime = Number.isFinite(rightParsedTime) ? rightParsedTime : Number.POSITIVE_INFINITY;
      return leftTime - rightTime
        || leftCandidate.name.localeCompare(rightCandidate.name)
        || String(left.user_id).localeCompare(String(right.user_id));
    });

  const preferredOrder = new Map((Array.isArray(preferredNames) ? preferredNames : [])
    .map((name, index) => [String(name || '').normalize('NFKC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase(), index]));
  if (preferredOrder.size) {
    candidates.sort((left, right) => {
      const leftPriority = preferredOrder.get(left.name.normalize('NFKC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase());
      const rightPriority = preferredOrder.get(right.name.normalize('NFKC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase());
      if (leftPriority !== undefined || rightPriority !== undefined) {
        if (leftPriority === undefined) return 1;
        if (rightPriority === undefined) return -1;
        if (leftPriority !== rightPriority) return leftPriority - rightPriority;
      }
      return 0;
    });
  }

  const selected = [];
  const displayedNames = new Set();
  for (const candidate of candidates) {
    const normalizedName = candidate.name.normalize('NFKC').replace(/\s+/gu, ' ').trim().toLocaleLowerCase();
    if (displayedNames.has(normalizedName)) continue;
    displayedNames.add(normalizedName);
    selected.push({ ...candidate.student, checkInDisplayName: candidate.name });
    if (selected.length >= selectionLimit) break;
  }
  return selected;
}

export function summarizeLatestSessionStatuses(students) {
  const counts = new Map([['Completed', 0], ['In progress', 0], ['Not started', 0], ['Terminated', 0]]);
  const studentsById = new Map(students.map((student) => [student.user_id, student]));
  for (const student of studentsById.values()) {
    const status = normalizeSessionStatus(student.session_status);
    const label = ({ completed: 'Completed', in_progress: 'In progress', not_started: 'Not started', terminated: 'Terminated' })[status] || 'Other';
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()].map(([label, count]) => ({ label, count }));
}

export function summarizeLatestSessionScores(students) {
  const groups = [
    { key: 'aptitude', label: 'Aptitude accuracy', max: 100, unit: '%', types: new Set(['aptitude', 'mcq', 'combined', 'technical']) },
    { key: 'coding', label: 'Coding score', max: 1, unit: 'of 1', types: new Set(['coding']) },
    { key: 'interview', label: 'Interview score', max: 1, unit: 'of 1', types: new Set(['interview', 'technical_interview', 'hr_interview', 'communication_interview']) },
  ];
  const collected = new Map(groups.map((group) => [group.key, { scores: [], students: new Set() }]));
  const studentsById = new Map(students.map((student) => [student.user_id, student]));
  for (const student of studentsById.values()) {
    for (const round of student.round_records || []) {
      if (round.status !== 'completed' || round.score === null || round.score === undefined) continue;
      const score = Number(round.score);
      if (!Number.isFinite(score)) continue;
      const group = groups.find((item) => item.types.has(String(round.round_type || '').toLocaleLowerCase()));
      if (!group || score < 0 || score > group.max) continue;
      const result = collected.get(group.key);
      result.scores.push(score);
      result.students.add(student.user_id);
    }
  }
  return groups.map((group) => {
    const result = collected.get(group.key);
    return result.scores.length ? {
      ...group,
      average: result.scores.reduce((total, score) => total + score, 0) / result.scores.length,
      attemptCount: result.scores.length,
      studentCount: result.students.size,
    } : null;
  }).filter(Boolean);
}

export function summarizeStudentsByDepartment(students) {
  const uniqueStudents = new Map();
  for (const student of students || []) {
    if (student?.user_id === null || student?.user_id === undefined) continue;
    uniqueStudents.set(String(student.user_id), student);
  }

  const groups = new Map();
  for (const student of uniqueStudents.values()) {
    const rawDepartment = typeof student.department === 'string' ? student.department : '';
    const normalized = rawDepartment.normalize('NFKC').trim().replace(/\s+/gu, ' ');
    const unknownDepartment = /^(?:unassigned|unspecified|unknown|department not specified)$/iu.test(normalized);
    const department = !normalized || unknownDepartment ? 'Department Not Specified' : normalized;
    const key = department.toLocaleLowerCase();
    const group = groups.get(key) || { department, count: 0, labels: new Map() };
    group.count += 1;
    group.labels.set(department, (group.labels.get(department) || 0) + 1);
    groups.set(key, group);
  }

  const total = uniqueStudents.size;
  return [...groups.values()].map((group) => {
    const department = [...group.labels.entries()]
      .sort((left, right) => right[1] - left[1])[0][0];
    return {
      department,
      count: group.count,
      percentage: total ? (group.count / total) * 100 : 0,
    };
  }).sort((left, right) => right.count - left.count || left.department.localeCompare(right.department));
}

export function summarizeDepartmentCounts(departments, totalStudents) {
  if (!Array.isArray(departments) || !Number.isInteger(totalStudents) || totalStudents < 0) return null;

  const groups = new Map();
  for (const item of departments) {
    const rawDepartment = typeof item?.department === 'string' ? item.department : '';
    const normalized = rawDepartment.normalize('NFKC').trim().replace(/\s+/gu, ' ');
    const unknownDepartment = /^(?:unassigned|unspecified|unknown|department not specified)$/iu.test(normalized);
    const department = !normalized || unknownDepartment ? 'Department Not Specified' : normalized;
    const count = Number(item?.count);
    if (!Number.isInteger(count) || count < 0) return null;
    const key = department.toLocaleLowerCase();
    const group = groups.get(key) || { department, count: 0, labels: new Map() };
    group.count += count;
    group.labels.set(department, (group.labels.get(department) || 0) + count);
    groups.set(key, group);
  }

  const countedStudents = [...groups.values()].reduce((sum, group) => sum + group.count, 0);
  if (countedStudents !== totalStudents) return null;

  return [...groups.values()].map((group) => ({
    department: [...group.labels.entries()].sort((left, right) => right[1] - left[1])[0][0],
    count: group.count,
    percentage: totalStudents ? (group.count / totalStudents) * 100 : 0,
  })).sort((left, right) => right.count - left.count || left.department.localeCompare(right.department));
}
