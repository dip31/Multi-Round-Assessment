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

export function hideMockDriveFromHistory(hiddenDriveIds, driveId) {
    return new Set([...hiddenDriveIds, driveId]);
}
