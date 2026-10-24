const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i;

export function localDateTimeToUtcIso(value) {
    return value ? new Date(value).toISOString() : null;
}

export function parseAvailabilityDate(value) {
    if (!value) return null;
    const timestamp = String(value).trim();
    const date = new Date(hasTimezone.test(timestamp) ? timestamp : `${timestamp}Z`);
    return Number.isNaN(date.getTime()) ? null : date;
}

export function formatAvailabilityDate(value) {
    return parseAvailabilityDate(value)?.toLocaleString() || 'Not available';
}

export function getAssignmentAvailabilityMessage(assignment, now = new Date()) {
    if (assignment.assessment_status === 'cancelled') {
        return 'This assessment was cancelled.';
    }
    if (assignment.assessment_status && assignment.assessment_status !== 'published') {
        return 'This assessment has not been published yet.';
    }

    const nowTimestamp = now instanceof Date ? now.getTime() : new Date(now).getTime();
    const start = parseAvailabilityDate(assignment.availability_start);
    if (start && nowTimestamp < start.getTime()) {
        return `This assessment is not yet available. It opens on ${start.toLocaleString()}.`;
    }

    const end = parseAvailabilityDate(assignment.availability_end);
    if (end && nowTimestamp > end.getTime()) {
        return `This assessment has expired. Its availability window ended on ${end.toLocaleString()}.`;
    }

    if (!assignment.available) {
        return 'This assessment is currently unavailable.';
    }
    return 'No round is currently available to start.';
}
