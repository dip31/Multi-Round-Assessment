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

// Weekly trend points. Only weeks with a finite average readiness survive.
export function toTrendPoints(series) {
    if (!Array.isArray(series)) return [];
    const points = [];
    for (const row of series) {
        if (!row || typeof row !== 'object') continue;
        const score = toNumber(row.avg_readiness);
        if (score === null) continue;
        points.push({
            key: String(row.bucket_start ?? ''),
            label: formatWeekLabel(row.bucket_start),
            avg_readiness: score,
            attempts: toNumber(row.attempts) ?? 0,
            candidates: toNumber(row.candidates) ?? 0,
        });
    }
    points.sort((a, b) => a.key.localeCompare(b.key));
    return points;
}

// Distribution bars. Returns [] when there are no scored attempts, so an
// all-zero chart is never rendered as if it held observations.
export function toDistributionBars(distribution) {
    if (!distribution || !Array.isArray(distribution.buckets)) return [];
    const total = toNumber(distribution.total) ?? 0;
    if (total <= 0) return [];
    return distribution.buckets.map((bucket, index) => ({
        key: String(bucket?.label ?? index),
        label: String(bucket?.label ?? ''),
        count: toNumber(bucket?.count) ?? 0,
        pct: toNumber(bucket?.pct) ?? 0,
        min: toNumber(bucket?.min),
        max: toNumber(bucket?.max),
    }));
}

// Department bars. Only departments with a finite average readiness survive.
export function toDepartmentBars(byDepartment) {
    if (!Array.isArray(byDepartment)) return [];
    const rows = [];
    for (const entry of byDepartment) {
        if (!entry || typeof entry !== 'object') continue;
        const avg = toNumber(entry.avg_readiness);
        if (avg === null) continue;
        rows.push({
            key: String(entry.department ?? ''),
            department: String(entry.department ?? 'Unspecified'),
            avg_readiness: avg,
            candidates: toNumber(entry.candidates) ?? 0,
            attempts: toNumber(entry.attempts) ?? 0,
        });
    }
    return rows;
}

// Slice the already-loaded, already-filtered drive list for display. Nothing is
// fetched here â€” expansion reveals rows from the same in-memory dataset.
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

// â”€â”€ Drive activity (operational counts â€” no readiness values) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
//
// Everything below renders the `drive_activity` block of the readiness
// overview payload: drive statuses, participant completion buckets and event
// timestamps. None of these helpers ever turns a count into a score or a
// status into a historical trend.

// How many drives the by-drive activity charts show at once. The complete
// filtered dataset stays available in the drive table.
export const ACTIVITY_ROW_LIMIT = 8;

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

// Pick which drives the by-drive activity charts render: only drives with at
// least one real participant, top-N by participants (or exactly one drive when
// the user selects it). Never issues a request â€” it reuses the loaded payload.
export function activityDriveRows(rows, options = {}) {
    const limit = Number.isFinite(options.limit) && options.limit > 0
        ? options.limit
        : ACTIVITY_ROW_LIMIT;
    const all = (Array.isArray(rows) ? rows : []).filter(
        (row) => row && typeof row === 'object' && (toNumber(row.participants) ?? 0) > 0,
    );
    const selectedId = options.selectedId === null || options.selectedId === undefined
        ? ''
        : String(options.selectedId);

    if (selectedId) {
        const id = Number(selectedId);
        const picked = Number.isFinite(id)
            ? all.filter((row) => toNumber(row.drive_id) === id)
            : [];
        return { rows: picked, total: all.length, shown: picked.length, capped: false };
    }

    const sorted = all.slice().sort((a, b) => {
        const byPeople = (toNumber(b.participants) ?? 0) - (toNumber(a.participants) ?? 0);
        if (byPeople !== 0) return byPeople;
        return (toNumber(a.drive_id) ?? 0) - (toNumber(b.drive_id) ?? 0);
    });
    const picked = sorted.slice(0, limit);
    return {
        rows: picked,
        total: all.length,
        shown: picked.length,
        capped: sorted.length > picked.length,
    };
}

function driveLabel(row) {
    const company = row.company_name ? String(row.company_name) : 'Drive';
    const role = row.target_role ? String(row.target_role) : '';
    return {
        key: String(row.drive_id ?? ''),
        drive_id: toNumber(row.drive_id),
        label: company,
        tooltipLabel: role ? `${company} â€” ${role}` : company,
        status: row.status ? String(row.status) : '',
    };
}

// Stacked enrollment/completion bars. The three buckets are mutually
// exclusive and come from the backend already summed per participant.
export function toCompletionStackRows(rows) {
    if (!Array.isArray(rows)) return [];
    return rows.map((row) => ({
        ...driveLabel(row),
        participants: toNumber(row.participants) ?? 0,
        completed: toNumber(row.completed_participants) ?? 0,
        in_progress: toNumber(row.in_progress_participants) ?? 0,
        not_started: toNumber(row.not_started_participants) ?? 0,
    }));
}

// Completion-rate rows. A zero denominator yields null and is dropped from the
// chart rather than rendered as a fabricated 0% bar; the caller surfaces those
// drives as explicitly unavailable.
export function toRateRows(rows) {
    if (!Array.isArray(rows)) return [];
    const out = [];
    for (const row of rows) {
        if (!row || typeof row !== 'object') continue;
        const participants = toNumber(row.participants) ?? 0;
        if (participants <= 0) continue;
        const rate = toNumber(row.completion_rate);
        if (rate === null) continue;
        out.push({
            ...driveLabel(row),
            rate,
            rateLabel: `${rate}% (n=${participants})`,
            completed: toNumber(row.completed_participants) ?? 0,
            participants,
        });
    }
    return out;
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
