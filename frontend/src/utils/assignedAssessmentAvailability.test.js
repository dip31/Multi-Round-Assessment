import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    formatAvailabilityDate,
    getAssignmentAvailabilityMessage,
    localDateTimeToUtcIso,
    parseAvailabilityDate,
} from './assignedAssessmentAvailability.js';

const baseAssignment = {
    assessment_status: 'published',
    available: false,
    availability_start: '2026-10-28T05:59:00',
    availability_end: '2026-10-30T05:59:00',
};

test('a published assessment before its start explains when it opens', () => {
    const message = getAssignmentAvailabilityMessage(
        baseAssignment,
        new Date('2026-10-24T06:22:56Z'),
    );
    assert.equal(
        message,
        `This assessment is not yet available. It opens on ${new Date('2026-10-28T05:59:00Z').toLocaleString()}.`,
    );
});

test('an unavailable assessment inside its window gets a neutral message', () => {
    assert.equal(
        getAssignmentAvailabilityMessage(baseAssignment, new Date('2026-10-29T00:00:00Z')),
        'This assessment is currently unavailable.',
    );
    assert.equal(
        getAssignmentAvailabilityMessage({ ...baseAssignment, available: true }, new Date('2026-10-29T00:00:00Z')),
        'No round is currently available to start.',
    );
});

test('a published assessment after its end explains when the window ended', () => {
    const message = getAssignmentAvailabilityMessage(
        baseAssignment,
        new Date('2026-10-31T00:00:00Z'),
    );
    assert.equal(
        message,
        `This assessment has expired. Its availability window ended on ${new Date('2026-10-30T05:59:00Z').toLocaleString()}.`,
    );
});

test('explicit unpublished and cancelled assessment states are reported', () => {
    assert.equal(
        getAssignmentAvailabilityMessage({ ...baseAssignment, assessment_status: 'draft' }, new Date('2026-10-29T00:00:00Z')),
        'This assessment has not been published yet.',
    );
    assert.equal(
        getAssignmentAvailabilityMessage({ ...baseAssignment, assessment_status: 'cancelled' }, new Date('2026-10-29T00:00:00Z')),
        'This assessment was cancelled.',
    );
});

test('UTC-naive API timestamps are parsed as UTC and formatted in local time', () => {
    const date = parseAvailabilityDate('2026-10-28T05:59:00');
    assert.equal(date.toISOString(), '2026-10-28T05:59:00.000Z');
    assert.equal(formatAvailabilityDate('2026-10-28T05:59:00'), date.toLocaleString());
});

test('timezone-aware API timestamps preserve their instant without double conversion', () => {
    const utc = parseAvailabilityDate('2026-10-28T05:59:00Z');
    const offset = parseAvailabilityDate('2026-10-28T11:29:00+05:30');
    assert.equal(utc.getTime(), Date.parse('2026-10-28T05:59:00Z'));
    assert.equal(offset.getTime(), utc.getTime());
    assert.equal(formatAvailabilityDate('2026-10-28T11:29:00+05:30'), utc.toLocaleString());
});

test('Asia/Kolkata builder times round-trip through UTC without shifting the displayed time', () => {
    const previousTimezone = globalThis.process.env.TZ;
    globalThis.process.env.TZ = 'Asia/Kolkata';
    try {
        const start = localDateTimeToUtcIso('2026-10-28T12:01');
        const end = localDateTimeToUtcIso('2026-10-28T16:59');
        assert.equal(start, '2026-10-28T06:31:00.000Z');
        assert.equal(end, '2026-10-28T11:29:00.000Z');
        assert.equal(parseAvailabilityDate(start).getHours(), 12);
        assert.equal(parseAvailabilityDate(start).getMinutes(), 1);
        assert.equal(parseAvailabilityDate(end).getHours(), 16);
        assert.equal(parseAvailabilityDate(end).getMinutes(), 59);
        const midnight = localDateTimeToUtcIso('2026-10-24T00:01');
        assert.equal(midnight, '2026-10-23T18:31:00.000Z');
        assert.equal(parseAvailabilityDate(midnight).getDate(), 24);
        assert.equal(parseAvailabilityDate(midnight).getHours(), 0);
    } finally {
        if (previousTimezone === undefined) delete globalThis.process.env.TZ;
        else globalThis.process.env.TZ = previousTimezone;
    }
});

test('faculty assessment list formats returned UTC values and omits Last Activity', () => {
    const workspace = readFileSync(new URL('../components/FacultyPracticeAssessmentWorkspace.jsx', import.meta.url), 'utf8');
    assert.match(workspace, /formatAvailabilityDate\(item\.availability_start\)/);
    assert.match(workspace, /formatAvailabilityDate\(item\.availability_end\)/);
    assert.doesNotMatch(workspace, /Last activity|dateTime\(item\.last_activity\)/i);
    assert.match(workspace, /\['Assessment', 'Rounds', 'Assigned students', 'Availability', 'Progress', 'Status', 'Action'\]/);
    assert.match(workspace, /colSpan=\{7\}/);
});
