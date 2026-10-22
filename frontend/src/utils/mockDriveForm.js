export function createEmptyMockDriveForm() {
    return {
        company_name: '',
        target_role: '',
        description: '',
        minimum_cgpa: 6.0,
        maximum_backlogs: 0,
        eligible_branches: [],
        selected_rounds: {},
        round_configurations: {},
        blueprint_id: null,
    };
}

export function loadMockDriveForm(drive, selectedRounds) {
    return {
        company_name: drive.company_name,
        target_role: drive.target_role,
        description: drive.description || '',
        minimum_cgpa: drive.minimum_cgpa,
        maximum_backlogs: drive.maximum_backlogs,
        eligible_branches: drive.eligible_branches || [],
        selected_rounds: selectedRounds,
        round_configurations: drive.round_configurations || {},
        blueprint_id: drive.blueprint_id || null,
    };
}

export function buildMockDriveEligibilityFields(formData) {
    const fields = {};
    const minimumCgpa = parseFloat(formData.minimum_cgpa);
    if (Number.isFinite(minimumCgpa)) {
        fields.minimum_cgpa = minimumCgpa;
    }
    const maximumBacklogs = parseInt(formData.maximum_backlogs, 10);
    if (Number.isFinite(maximumBacklogs)) {
        fields.maximum_backlogs = maximumBacklogs;
    }
    return fields;
}
