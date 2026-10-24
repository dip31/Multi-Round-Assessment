function numericValue(value) {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

/** Classify only from known candidate values; preserve missing profile data. */
export function candidateEligibility(candidate, {
    minimumCgpa = 0,
    maximumBacklogs = 0,
    eligibleBranches = [],
} = {}) {
    const minimum = numericValue(minimumCgpa) ?? 0;
    const maximum = numericValue(maximumBacklogs) ?? 0;
    const cgpa = numericValue(candidate?.cgpa);
    const backlogs = numericValue(candidate?.backlogs_count);
    const branches = Array.isArray(eligibleBranches) ? eligibleBranches.filter(Boolean) : [];
    const department = String(candidate?.department || '').trim().toLocaleLowerCase();

    let unknown = false;
    if (cgpa === null) {
        if (minimum > 0) unknown = true;
    } else if (cgpa < minimum) {
        return 'ineligible';
    }

    if (backlogs === null) unknown = true;
    else if (backlogs > maximum) return 'ineligible';

    if (branches.length) {
        if (!department) unknown = true;
        else if (!branches.some(branch => String(branch).trim().toLocaleLowerCase() === department)) {
            return 'ineligible';
        }
    }

    return unknown ? 'unknown' : 'eligible';
}

export function summarizeEligibility(candidates, requirements) {
    return candidates.reduce((summary, candidate) => {
        summary[candidateEligibility(candidate, requirements)] += 1;
        return summary;
    }, { eligible: 0, ineligible: 0, unknown: 0 });
}
