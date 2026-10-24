import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    filterMockDrives,
    getVisibleMockDrives,
    hideMockDriveFromHistory,
    mockDriveCgpaOptions,
    mockDriveEmptyState,
    mockDriveRole,
    mockDriveRoleOptions,
    sortMockDrivesByCompanyName,
} from './mockDriveHistory.js';

const dashboardSource = await readFile(
    new URL('../pages/TPOMockDrivesPage.jsx', import.meta.url),
    'utf8',
);
const historySource = await readFile(new URL('./mockDriveHistory.js', import.meta.url), 'utf8');

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

const filterFixtures = [
    { id: 1, company_name: 'Acme', target_role: 'Software Engineer', status: 'draft', minimum_cgpa: 7 },
    { id: 2, company_name: 'Beta', target_role: 'Data Engineer', status: 'published', minimum_cgpa: '8.0' },
    { id: 3, company_name: 'Citi', target_role: 'Software Engineer', status: 'active', minimum_cgpa: 7.5 },
    { id: 4, company_name: 'Delta', position: 'Data Engineer', status: 'completed', minimum_cgpa: null },
    { id: 5, company_name: 'Echo', status: 'published', minimum_cgpa: 'not-a-number' },
];

test('side-panel status results match each existing horizontal status value', () => {
    for (const status of ['draft', 'published', 'active', 'completed']) {
        const horizontalTabResults = filterFixtures.filter(drive => drive.status === status);
        assert.deepEqual(filterMockDrives(filterFixtures, { status }), horizontalTabResults);
    }
    assert.deepEqual(filterMockDrives(filterFixtures, { status: 'all' }), filterFixtures);
});

test('role and position options use loaded fields and tolerate missing roles', () => {
    assert.equal(mockDriveRole(filterFixtures[3]), 'Data Engineer');
    assert.equal(mockDriveRole(filterFixtures[4]), '');
    assert.deepEqual(mockDriveRoleOptions(filterFixtures), ['Data Engineer', 'Software Engineer']);
    assert.deepEqual(filterMockDrives(filterFixtures, { role: 'Software Engineer' }).map(d => d.id), [1, 3]);
});

test('configured minimum CGPA filtering handles numeric strings and missing or invalid values', () => {
    assert.deepEqual(mockDriveCgpaOptions(filterFixtures), [7, 7.5, 8]);
    assert.deepEqual(filterMockDrives(filterFixtures, { minimumCgpa: '8' }).map(d => d.id), [2]);
    assert.deepEqual(filterMockDrives(filterFixtures, { minimumCgpa: '7' }).map(d => d.id), [1]);
    assert.deepEqual(filterMockDrives(filterFixtures, { minimumCgpa: '9' }), []);
    assert.deepEqual(filterMockDrives(filterFixtures), filterFixtures);
});

test('status, role, text search, and CGPA filters combine without mutating source data', () => {
    const result = filterMockDrives(filterFixtures, {
        status: 'published', role: 'Data Engineer', search: 'beta', minimumCgpa: '8',
    });
    assert.deepEqual(result.map(drive => drive.id), [2]);
    assert.equal(filterMockDrives(filterFixtures, {
        status: 'published', role: 'Data Engineer', search: 'beta', minimumCgpa: '7',
    }).length, 0);
    assert.equal(filterFixtures.length, 5);
});

test('Clear Filters restores all loaded drives and empty states distinguish filters from removed history', () => {
    assert.deepEqual(filterMockDrives(filterFixtures, { status: 'all' }), filterFixtures);
    assert.equal(mockDriveEmptyState({
        loadedDrives: filterFixtures, visibleDrives: filterFixtures, status: 'published',
        search: '', role: '', minimumCgpa: '',
    }), 'filters');
    assert.equal(mockDriveEmptyState({
        loadedDrives: filterFixtures, visibleDrives: [], status: 'all',
        search: '', role: '', minimumCgpa: '',
    }), 'history');
    assert.equal(mockDriveEmptyState({
        loadedDrives: [], visibleDrives: [], status: 'all', search: '', role: '', minimumCgpa: '',
    }), 'empty');
});

test('Placement & Mock Drives renders the sorted visible drive list', () => {
    assert.match(dashboardSource, /sortMockDrivesByCompanyName\(\s*getVisibleMockDrives\(mockDrives, hiddenMockDriveIds\)/);
    assert.match(dashboardSource, /displayedMockDrives\.map\(drive =>/);
    assert.match(dashboardSource, /filterMockDrives\(visibleMockDrives, \{/);
    assert.match(historySource, /search\)\.trim\(\)\.toLocaleLowerCase\(\)/);
    assert.match(dashboardSource, /status: mockDriveStatusFilter/);
    assert.match(dashboardSource, /Date\.parse\(a\.created_at\) - Date\.parse\(b\.created_at\)/);
    const loader = dashboardSource.split('const loadMockDrives = useCallback')[1]?.split('useEffect')[0];
    assert.match(loader, /api\.get\('\/tpo\/mock-drives', \{ params \}\)/);
    assert.doesNotMatch(loader, /driveSearch|driveSort|driveRoleFilter|driveCgpaFilter/);
    assert.match(dashboardSource, /aria-controls="mock-drive-side-filters"/);
    assert.match(dashboardSource, /setMockDriveStatusFilter\('all'\)/);
    assert.match(dashboardSource, /mockDriveEmptyState\(/);
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
