// Pure chart-data derivation for the TPO Readiness Analytics page.
//
// These helpers turn the backend readiness overview payload into chart-ready
// rows. They never invent values: rows with missing/non-finite scores are
// dropped (the chart shows an honest empty state instead of a fake point), and
// counts are coerced to finite integers. Kept dependency-free so it is unit
// testable with `node --test`.

export const DRIVE_ROW_LIMIT = 10;

const MONTHS = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function isFiniteNumber(value) {
    if (typeof value === 'number') return Number.isFinite(value);
    if (value === null || value === undefined || value === '') return false;
    return Number.isFinite(Number(value));
}

function toNumber(value) {
    return isFiniteNumber(value) ? Number(value) : null;
}

// Turn an ISO date (e.g. "2026-01-05", the Monday of an ISO week) into a short
// readable label ("Jan 5"). Unparseable input is returned unchanged.
export function formatWeekLabel(value) {
    if (typeof value !== 'string') return value === null || value === undefined ? '' : String(value);
    const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    if (!match) return value;
    const month = Number(match[2]);
    const day = Number(match[3]);
    if (!Number.isFinite(month) || !Number.isFinite(day) || month < 1 || month > 12) {
        return value;
    }
    return `${MONTHS[month - 1]} ${day}`;
}

// Normalize a department name for grouping: trim, collapse internal whitespace
// and case-fold, so " computer  science " and "Computer Science" are one bar.
// Returns null when the entry carries no usable name (caller maps to Unspecified).
function normalizeDepartmentKey(value) {
    if (value === null || value === undefined) return null;
    const collapsed = String(value).replace(/\s+/g, ' ').trim();
    if (!collapsed) return null;
    return collapsed.toLowerCase();
}

// Department bars. Groups departments case/whitespace-insensitively, keeping a
// readable display name and computing a weighted average from the backend's
// authoritative per-department figures. Only departments with a finite average
// readiness survive, so an unscored department never renders as a fake zero bar.
// Rows are sorted by display name for a stable order.
export function toDepartmentBars(byDepartment) {
    if (!Array.isArray(byDepartment)) return [];
    const groups = new Map();
    for (const entry of byDepartment) {
        if (!entry || typeof entry !== 'object') continue;
        const avg = toNumber(entry.avg_readiness);
        if (avg === null) continue;
        const rawName = String(entry.department ?? '').replace(/\s+/g, ' ').trim();
        const display = rawName || 'Unspecified';
        const key = normalizeDepartmentKey(rawName) ?? 'unspecified';
        const candidates = toNumber(entry.candidates) ?? 0;
        const attempts = toNumber(entry.attempts) ?? 0;
        if (!groups.has(key)) {
            groups.set(key, {
                key,
                department: display,
                candidates,
                attempts,
                weightedSum: avg * attempts,
            });
            continue;
        }
        const group = groups.get(key);
        group.candidates += candidates;
        group.attempts += attempts;
        group.weightedSum += avg * attempts;
        // Prefer the longest observed spelling as the readable display name.
        if (display.length > group.department.length) group.department = display;
    }
    const rows = Array.from(groups.values()).map((group) => ({
        key: group.key,
        department: group.department,
        candidates: group.candidates,
        attempts: group.attempts,
        avg_readiness: roundTo(group.weightedSum, group.attempts),
    }));
    rows.sort((a, b) => a.department.localeCompare(b.department));
    return rows;
}

// Weighted mean to 2dp when attempts are known, else keep the group mean.
function roundTo(weightedSum, attempts) {
    if (attempts > 0) {
        return Math.round((weightedSum / attempts) * 100) / 100;
    }
    return Math.round(weightedSum * 100) / 100;
}

// Slice the already-loaded, already-filtered drive list for display. Nothing is
// fetched here — expansion reveals rows from the same in-memory dataset.
export function visibleDrives(drives, expanded, limit = DRIVE_ROW_LIMIT) {
    const all = Array.isArray(drives) ? drives : [];
    const total = all.length;
    const cap = Number.isFinite(limit) && limit > 0 ? limit : DRIVE_ROW_LIMIT;
    const visible = expanded ? all : all.slice(0, cap);
    return {
        visible,
        total,
        shown: visible.length,
        hiddenCount: Math.max(0, total - visible.length),
        canExpand: total > cap,
        expanded: Boolean(expanded) && total > cap,
    };
}

// Sort the complete filtered drive list before applying the visible-row limit.
// Trim only for comparison; the original company and role values remain intact.
export function sortDriveRowsAlphabetically(drives) {
    if (!Array.isArray(drives)) return [];
    const compareText = (left, right) => String(left ?? '').trim().localeCompare(
        String(right ?? '').trim(),
        undefined,
        { sensitivity: 'base' },
    );
    return drives.slice().sort((a, b) => (
        compareText(a?.company_name, b?.company_name)
        || compareText(a?.target_role, b?.target_role)
        || ((toNumber(a?.drive_id) ?? 0) - (toNumber(b?.drive_id) ?? 0))
    ));
}

// ── Drive activity (operational counts — no readiness values) ───────────
//
// Everything below renders the `drive_activity` block of the readiness
// overview payload: drive statuses, participant completion buckets and event
// timestamps. None of these helpers ever turns a count into a score or a
// status into a historical trend.

const STATUS_ORDER = ['draft', 'published', 'active', 'completed'];

// Drive status donut slices from the authoritative `status` column.
export function toStatusSlices(statusDistribution) {
    if (!statusDistribution || !Array.isArray(statusDistribution.rows)) return [];
    const slices = [];
    for (const row of statusDistribution.rows) {
        if (!row || typeof row !== 'object') continue;
        const drives = toNumber(row.drives) ?? 0;
        if (drives <= 0) continue;
        slices.push({
            key: String(row.status ?? ''),
            label: String(row.status ?? ''),
            drives,
            pct: toNumber(row.pct) ?? 0,
            analysed: row.analysed !== false,
        });
    }
    slices.sort(
        (a, b) => STATUS_ORDER.indexOf(a.key) - STATUS_ORDER.indexOf(b.key),
    );
    return slices;
}

// Assessment preparation progress: usable scored results trend (weekly/monthly).
export function toProgressPoints(points) {
    if (!Array.isArray(points)) return [];
    const out = [];
    for (const row of points) {
        if (!row || typeof row !== 'object') continue;
        const key = String(row.bucket_start ?? '');
        const avg = toNumber(row.avg_score);
        if (!key || avg === null) continue;
        out.push({
            key,
            label: row.bucket_start && row.bucket_start.includes('-') && row.bucket_start.length === 7
                ? row.bucket_start
                : formatWeekLabel(key),
            avg_score: avg,
            attempts: toNumber(row.attempts) ?? 0,
            candidates: toNumber(row.candidates) ?? 0,
        });
    }
    out.sort((a, b) => a.key.localeCompare(b.key));
    return out;
}

// Aptitude topic performance bars: responses >= 1.
export function toTopicBars(rows) {
    if (!Array.isArray(rows)) return [];
    const out = [];
    for (const row of rows) {
        if (!row || typeof row !== 'object') continue;
        const responses = toNumber(row.responses) ?? 0;
        if (responses <= 0) continue;
        out.push({
            key: String(row.topic ?? ''),
            topic: String(row.topic ?? 'Untagged'),
            accuracy: toNumber(row.accuracy) ?? 0,
            responses,
            correct: toNumber(row.correct) ?? 0,
            candidates: toNumber(row.candidates) ?? 0,
        });
    }
    return out;
}
export function toParticipationPoints(points) {
  if (!Array.isArray(points)) return [];
  const out = [];
  for (const row of points) {
    if (!row || typeof row !== 'object') continue;
    const key = String(row.bucket_start ?? '');
    const reg = toNumber(row.registrations) ?? 0;
    const comp = toNumber(row.completions) ?? 0;
    if (!key || (reg <= 0 && comp <= 0)) continue;
    out.push({ key, label: formatWeekLabel(key), registrations: reg, completions: comp });
  }
  out.sort((a, b) => a.key.localeCompare(b.key));
  return out;
}

// ── Assessment evidence (Section 2, EDI5) ──────────────────────────────
//
// These helpers turn the `assessment_performance` block of the readiness
// payload into honest, denominator-carrying rows. A completed round without a
// usable result is reported as *missing* evidence, never as a scored zero, and
// no participation count is ever promoted to a performance value.

function nonNegative(value) {
    const n = toNumber(value);
    return n !== null && n >= 0 ? n : 0;
}

// Coverage helpers reused by Section 2 cards/panels.
export function formatCoveragePercent(numerator, denominator) {
    if (!denominator || denominator <= 0) return null;
    return Math.round((numerator / denominator) * 1000) / 10;
}

export function codingCoverageSummary(row) {
    if (!row) {
        return {
            completed: 0,
            withResults: 0,
            valid: 0,
            coveragePct: null,
            candidates: 0,
            available: false,
            reason: null,
        };
    }
    const completed = nonNegative(row.completed);
    const valid = nonNegative(row.valid);
    const coveragePct = row.coveragePct !== null && row.coveragePct !== undefined
        ? row.coveragePct
        : formatCoveragePercent(valid, completed);
    return {
        completed,
        withResults: nonNegative(row.withResults),
        valid,
        coveragePct,
        candidates: nonNegative(row.candidates),
        available: row.available === true || valid > 0,
        reason: row.reason || null,
    };
}

export { safeAssessmentLabel, safeAssessmentKey };

function safeAssessmentLabel(value, type) {
    const t = String(type || '').toLowerCase();
    if (value !== null && value !== undefined && String(value).trim()) {
        return String(value).trim();
    }
    if (t === 'aptitude') return 'Aptitude';
    if (t === 'coding') return 'Coding';
    if (t === 'interview') return 'Interview';
    if (t) return t.charAt(0).toUpperCase() + t.slice(1);
    return 'Assessment';
}

function safeAssessmentKey(value, type) {
    if (value !== null && value !== undefined && String(value).trim()) {
        return String(value).trim().toLowerCase().replace(/\s+/g, '-');
    }
    const t = String(type || '').toLowerCase();
    return t || 'assessment';
}

// One row per assessment type, merging the coverage counts with the
// per-type performance component (scale, candidates, average, reason).
export function toEvidenceCoverageRows(assessment) {
    const coverage = assessment?.summary?.evidence_coverage;
    const components = assessment?.components;
    if (!coverage || !Array.isArray(coverage.by_type)) return [];
    const rows = [];
    for (const entry of coverage.by_type) {
        if (!entry || typeof entry !== 'object') continue;
        const type = String(entry.type ?? '');
        const comp = components && typeof components === 'object'
            ? components[type]
            : null;
        const completed = nonNegative(entry.completed_rounds);
        const valid = nonNegative(entry.rounds_with_valid_scores);
        const coveragePct = toNumber(entry.coverage_pct);
        const label = safeAssessmentLabel(entry.label ?? comp?.label, type);
        rows.push({
            key: safeAssessmentKey(entry.type ?? comp?.key, type),
            type,
            label,
            completed,
            withResults: nonNegative(entry.rounds_with_results),
            valid,
            missing: Math.max(0, completed - valid),
            coveragePct: coveragePct !== null ? coveragePct : formatCoveragePercent(valid, completed),
            candidates: nonNegative(comp?.candidates),
            avgScore: toNumber(comp?.avg_score),
            minScore: toNumber(comp?.min_score),
            maxScore: toNumber(comp?.max_score),
            available: comp?.available === true,
            scale: comp?.scale || null,
            reason: comp?.reason || null,
        });
    }
    return rows;
}

// Overall evidence coverage (numerator / denominator) plus its per-type rows.
export function toAssessmentEvidenceSummary(assessment) {
    const rows = toEvidenceCoverageRows(assessment);
    const coverage = assessment?.summary?.evidence_coverage;
    if (!coverage || typeof coverage !== 'object') {
        return { available: false, value: null, numerator: 0, denominator: 0, rows };
    }
    return {
        available: coverage.available === true,
        value: toNumber(coverage.value),
        numerator: nonNegative(coverage.numerator),
        denominator: nonNegative(coverage.denominator),
        rows,
    };
}

// Completed rounds whose result is not usable scored evidence. `missing` is an
// absence of evidence and must never be rendered or averaged as a zero.
export function toEvidenceGaps(assessment) {
    return toEvidenceCoverageRows(assessment)
        .filter((row) => row.completed > 0)
        .map((row) => ({
            key: row.key,
            type: row.type,
            label: row.label,
            completed: row.completed,
            withResults: row.withResults,
            valid: row.valid,
            missing: row.missing,
            missingPct: formatCoveragePercent(row.missing, row.completed),
            reason: row.reason,
        }));
}

// Aptitude is the only assessment type on a 0-100 accuracy scale. Report both
// the mean scored-round result and the pooled accuracy (all graded responses),
// each with its own denominator so the two can never be confused.
export function toAptitudePerformance(assessment) {
    const comp = assessment?.components?.aptitude;
    const topics = toTopicBars(assessment?.topic_performance?.rows || []);
    const responses = topics.reduce((sum, topic) => sum + topic.responses, 0);
    const correct = topics.reduce((sum, topic) => sum + topic.correct, 0);
    if (!comp || typeof comp !== 'object') {
        return {
            available: false,
            mean: null,
            pooled: null,
            candidates: 0,
            responses: 0,
            correct: 0,
            min: null,
            max: null,
            validRounds: 0,
            completedRounds: 0,
            reason: null,
        };
    }
    return {
        available: comp.available === true,
        mean: toNumber(comp.avg_score),
        pooled: formatCoveragePercent(correct, responses),
        candidates: nonNegative(comp.candidates),
        responses,
        correct,
        min: toNumber(comp.min_score),
        max: toNumber(comp.max_score),
        validRounds: nonNegative(comp.rounds_with_valid_scores),
        completedRounds: nonNegative(comp.completed_rounds),
        reason: comp.reason || null,
    };
}

// Topic rows sorted by evidence volume so the largest samples lead; ties fall
// back to the lowest accuracy. Every row keeps its response and candidate
// counts so a tiny sample is visible rather than implied.
export function toTopicPerformance(assessment) {
    const rows = toTopicBars(assessment?.topic_performance?.rows || []);
    rows.sort((a, b) => (b.responses - a.responses) || (a.accuracy - b.accuracy));
    return rows;
}
