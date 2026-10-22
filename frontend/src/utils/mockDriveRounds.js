const ROUND_ORDER = ['aptitude', 'coding', 'technical_interview', 'hr_interview'];

export function getConfiguredMockDriveRounds(drive) {
    const selected = drive?.selected_rounds;
    const selectedRounds = Array.isArray(selected)
        ? selected
        : selected && typeof selected === 'object'
            ? Object.keys(selected).filter(round => selected[round])
            : [];

    if (selectedRounds.length > 0) {
        const orderedRounds = [
            ...(Array.isArray(drive.rounds) ? drive.rounds : []),
            ...ROUND_ORDER,
        ];
        return orderedRounds.filter((round, index) =>
            selectedRounds.includes(round) && orderedRounds.indexOf(round) === index
        );
    }

    if (Array.isArray(drive?.rounds)) return drive.rounds;
    return selectedRounds;
}
