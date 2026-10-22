import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
    buildMockDriveEligibilityFields,
    createEmptyMockDriveForm,
    loadMockDriveForm,
} from './mockDriveForm.js';

const dashboardSource = await readFile(
    new URL('../pages/TPOMockDrivesPage.jsx', import.meta.url),
    'utf8',
);

test('unset eligibility fields are omitted instead of becoming NaN', () => {
    assert.deepEqual(buildMockDriveEligibilityFields({ minimum_cgpa: '', maximum_backlogs: '' }), {});
    assert.deepEqual(buildMockDriveEligibilityFields({ minimum_cgpa: null, maximum_backlogs: undefined }), {});
    assert.deepEqual(buildMockDriveEligibilityFields({ minimum_cgpa: NaN, maximum_backlogs: NaN }), {});
    assert.deepEqual(buildMockDriveEligibilityFields({}), {});
});

test('omitted eligibility fields never serialize NaN into the payload', () => {
    const form = createEmptyMockDriveForm();
    form.minimum_cgpa = '';
    form.maximum_backlogs = '';

    const payload = { company_name: 'Infosys', ...buildMockDriveEligibilityFields(form) };
    const serialized = JSON.stringify(payload);

    assert.equal(serialized.includes('NaN'), false);
    assert.equal('minimum_cgpa' in payload, false);
    assert.equal('maximum_backlogs' in payload, false);
    assert.deepEqual(JSON.parse(serialized), { company_name: 'Infosys' });
});

test('valid CGPA and backlog values are preserved as numbers', () => {
    assert.deepEqual(
        buildMockDriveEligibilityFields({ minimum_cgpa: '7.5', maximum_backlogs: '2' }),
        { minimum_cgpa: 7.5, maximum_backlogs: 2 },
    );
    assert.deepEqual(
        buildMockDriveEligibilityFields({ minimum_cgpa: 6.0, maximum_backlogs: 0 }),
        { minimum_cgpa: 6.0, maximum_backlogs: 0 },
    );

    const loaded = loadMockDriveForm(
        { company_name: 'Citi', target_role: 'DE', minimum_cgpa: 8.2, maximum_backlogs: 1 },
        {},
    );
    assert.deepEqual(
        buildMockDriveEligibilityFields(loaded),
        { minimum_cgpa: 8.2, maximum_backlogs: 1 },
    );
});

test('TPOMockDrivesPage builds eligibility payload through the finite-number helper', () => {
    assert.match(dashboardSource, /\.\.\.buildMockDriveEligibilityFields\(formData\)/);
    assert.doesNotMatch(dashboardSource, /minimum_cgpa:\s*parseFloat\(/);
    assert.doesNotMatch(dashboardSource, /maximum_backlogs:\s*parseInt\(/);
});
