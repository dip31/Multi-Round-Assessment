const numericValue = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
};

// Matches the existing Candidate Pool tier rule while keeping incomplete records unknown.
export function candidateEligibility(student) {
    const cgpa = numericValue(student?.cgpa);
    const backlogs = numericValue(student?.backlogs_count);
    if (cgpa === null || backlogs === null) return 'unknown';
    return cgpa >= 7 && backlogs === 0 ? 'eligible' : 'conditional';
}

export function summarizeCandidates(students = []) {
    return students.reduce((summary, student) => {
        summary.total += 1;
        const eligibility = candidateEligibility(student);
        if (eligibility === 'eligible') summary.eligible += 1;
        if (eligibility === 'conditional') summary.conditional += 1;
        const backlogs = numericValue(student?.backlogs_count);
        if (backlogs !== null && backlogs > 0) summary.withBacklogs += 1;
        return summary;
    }, { total: 0, eligible: 0, conditional: 0, withBacklogs: 0 });
}

export function filterAndSortCandidates(students = [], filters = {}) {
    const search = (filters.search || '').trim().toLocaleLowerCase();
    const minCgpa = numericValue(filters.minCgpa);
    const maxCgpa = numericValue(filters.maxCgpa);
    const filtered = students.filter(student => {
        const searchable = [student?.name, student?.email, student?.roll_number]
            .filter(value => typeof value === 'string').join(' ').toLocaleLowerCase();
        if (search && !searchable.includes(search)) return false;
        if (filters.department && (student?.department || '') !== filters.department) return false;
        if (filters.eligibility && candidateEligibility(student) !== filters.eligibility) return false;
        const cgpa = numericValue(student?.cgpa);
        if ((minCgpa !== null || maxCgpa !== null) && cgpa === null) return false;
        if (minCgpa !== null && cgpa < minCgpa) return false;
        if (maxCgpa !== null && cgpa > maxCgpa) return false;
        const backlogs = numericValue(student?.backlogs_count);
        if (filters.backlogs === 'has' && !(backlogs !== null && backlogs > 0)) return false;
        if (filters.backlogs === 'none' && backlogs !== 0) return false;
        if (filters.backlogs === 'unknown' && backlogs !== null) return false;
        return true;
    });

    const field = filters.sort || 'name';
    const direction = filters.direction === 'desc' ? -1 : 1;
    return filtered.sort((a, b) => {
        const av = field === 'cgpa' ? numericValue(a?.cgpa)
            : field === 'backlogs' ? numericValue(a?.backlogs_count)
                : String(a?.[field] ?? '').toLocaleLowerCase();
        const bv = field === 'cgpa' ? numericValue(b?.cgpa)
            : field === 'backlogs' ? numericValue(b?.backlogs_count)
                : String(b?.[field] ?? '').toLocaleLowerCase();
        if (av === null || av === '') return bv === null || bv === '' ? 0 : 1;
        if (bv === null || bv === '') return -1;
        return (av < bv ? -1 : av > bv ? 1 : 0) * direction;
    });
}
