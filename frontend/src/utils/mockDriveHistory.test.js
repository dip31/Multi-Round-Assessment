import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    getVisibleMockDrives,
    hideMockDriveFromHistory,
    sortMockDrivesByCompanyName,
} from './mockDriveHistory.js';

const dashboardSource = await readFile(
    new URL('../pages/TPOMockDrivesPage.jsx', import.meta.url),
    'utf8',
);

test('removing a drive hides only that drive in local view state', () => {
    const drives = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const hiddenIds = hideMockDriveFromHistory(new Set(), 2);

    assert.deepEqual(getVisibleMockDrives(drives, hiddenIds), [{ id: 1 }, { id: 3 }]);
    assert.deepEqual(drives, [{ id: 1 }, { id: 2 }, { id: 3 }]);
    assert.deepEqual([...hiddenIds], [2]);
});

test('Mock Drives sort by displayed company name case-insensitively without changing source order', () => {
    const drives = [
        { id: 1, company_name: 'zeta Corp', status: 'draft' },
        { id: 2, company_name: 'Alpha Ltd', status: 'draft' },
        { id: 3, company_name: 'beta Inc', status: 'published' },
        { id: 4, company_name: 'ALPHA Group', status: 'published' },
        { id: 5, company_name: 'Zulu Systems', status: 'active' },
        { id: 6, company_name: 'beta Tech', status: 'active' },
        { id: 7, company_name: 'Omega LLC', status: 'completed' },
        { id: 8, company_name: 'beta Works', status: 'completed' },
    ];

    const sorted = sortMockDrivesByCompanyName(drives);

    assert.deepEqual(sorted.map(drive => drive.company_name), [
        'ALPHA Group', 'Alpha Ltd', 'beta Inc', 'beta Tech',
        'beta Works', 'Omega LLC', 'zeta Corp', 'Zulu Systems',
    ]);
    assert.deepEqual(drives.map(drive => drive.company_name), [
        'zeta Corp', 'Alpha Ltd', 'beta Inc', 'ALPHA Group',
        'Zulu Systems', 'beta Tech', 'Omega LLC', 'beta Works',
    ]);
    for (const status of ['draft', 'published', 'active', 'completed']) {
        const statusDrives = drives.filter(drive => drive.status === status);
        assert.deepEqual(
            sortMockDrivesByCompanyName(statusDrives).map(drive => drive.company_name),
            [...statusDrives.map(drive => drive.company_name)].sort((a, b) =>
                a.localeCompare(b, undefined, { sensitivity: 'base' })
            ),
        );
    }
});

test('visible Mock Drives are sorted after the current history filter', () => {
    const drives = [
        { id: 1, company_name: 'Zulu' },
        { id: 2, company_name: 'Bravo' },
        { id: 3, company_name: 'Alpha' },
    ];
    const hiddenIds = new Set([2]);

    assert.deepEqual(
        sortMockDrivesByCompanyName(getVisibleMockDrives(drives, hiddenIds))
            .map(drive => drive.company_name),
        ['Alpha', 'Zulu'],
    );
});

test('Placement & Mock Drives renders the sorted visible drive list', () => {
    assert.match(dashboardSource, /sortMockDrivesByCompanyName\(\s*getVisibleMockDrives\(mockDrives, hiddenMockDriveIds\)/);
    assert.match(dashboardSource, /visibleMockDrives\.map\(drive =>/);
});

test('history removal is confirmed and does not call a Mock Drive DELETE API', () => {
    assert.match(dashboardSource, /Remove this drive from the history view\?/);
    assert.match(dashboardSource, /It does not delete the Mock Drive/);
    assert.match(dashboardSource, /onClick=\{cancelDelete\}/);
    assert.doesNotMatch(dashboardSource, /api\.delete\s*\(\s*[`'"]\/tpo\/mock-drives/);
});

test('create and edit form scrolls internally with fixed footer actions', () => {
    assert.match(dashboardSource, /max-h-\[calc\(100dvh-2rem\)\]/);
    assert.match(dashboardSource, /overflow-y-auto overscroll-contain px-8 pb-6/);
    assert.match(dashboardSource, /flex-shrink-0 items-center justify-end gap-3 border-t/);
    assert.match(dashboardSource, /document\.body\.style\.overflow = 'hidden'/);
});
