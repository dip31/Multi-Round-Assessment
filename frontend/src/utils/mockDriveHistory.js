export function getVisibleMockDrives(drives, hiddenDriveIds) {
    return drives.filter(drive => !hiddenDriveIds.has(drive.id));
}

export function sortMockDrivesByCompanyName(drives) {
    return [...drives].sort((left, right) =>
        String(left.company_name || '').localeCompare(
            String(right.company_name || ''),
            undefined,
            { sensitivity: 'base' },
        )
    );
}

export function mockDriveRole(drive) {
    return String(drive?.target_role || drive?.job_role || drive?.position || '').trim();
}

export function mockDriveRoleOptions(drives) {
    return [...new Set(drives.map(mockDriveRole).filter(Boolean))]
        .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
}

export function mockDriveCgpaOptions(drives) {
    return [...new Set(drives
        .map(drive => {
            if (drive?.minimum_cgpa == null || drive.minimum_cgpa === '') return null;
            const value = Number(drive.minimum_cgpa);
            return Number.isFinite(value) ? value : null;
        })
        .filter(value => value !== null))]
        .sort((left, right) => left - right);
}

export function filterMockDrives(drives, { status = 'all', search = '', role = '', minimumCgpa = '' } = {}) {
    const query = String(search).trim().toLocaleLowerCase();
    const selectedRole = String(role).trim().toLocaleLowerCase();
    const selectedCgpa = minimumCgpa === '' ? null : Number(minimumCgpa);

    return drives.filter(drive => {
        if (status !== 'all' && drive?.status !== status) return false;
        const driveRole = mockDriveRole(drive);
        if (selectedRole && driveRole.toLocaleLowerCase() !== selectedRole) return false;
        if (query) {
            const searchable = `${drive?.company_name || ''} ${driveRole}`.toLocaleLowerCase();
            if (!searchable.includes(query)) return false;
        }
        if (selectedCgpa !== null) {
            const configured = drive?.minimum_cgpa == null || drive.minimum_cgpa === ''
                ? NaN : Number(drive.minimum_cgpa);
            if (!Number.isFinite(selectedCgpa) || !Number.isFinite(configured) || configured !== selectedCgpa) {
                return false;
            }
        }
        return true;
    });
}

export function mockDriveEmptyState({ loadedDrives, visibleDrives, status, search, role, minimumCgpa }) {
    if (visibleDrives.length === 0 && loadedDrives.length > 0) return 'history';
    if (status !== 'all' || search || role || minimumCgpa) return 'filters';
    if (loadedDrives.length === 0) return 'empty';
    return null;
}

export function hideMockDriveFromHistory(hiddenDriveIds, driveId) {
    return new Set([...hiddenDriveIds, driveId]);
}
