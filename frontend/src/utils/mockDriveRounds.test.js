import assert from 'node:assert/strict';
import test from 'node:test';
import { getConfiguredMockDriveRounds } from './mockDriveRounds.js';
import { createEmptyMockDriveForm, loadMockDriveForm } from './mockDriveForm.js';

test('persisted selections determine draft rounds while retaining blueprint order', () => {
    const drive = {
        selected_rounds: { aptitude: true, coding: true, technical_interview: true },
        rounds: ['coding'],
    };

    assert.deepEqual(getConfiguredMockDriveRounds(drive), [
        'coding',
        'aptitude',
        'technical_interview',
    ]);
});

test('legacy drives fall back to the rounds projection', () => {
    assert.deepEqual(
        getConfiguredMockDriveRounds({ selected_rounds: {}, rounds: ['aptitude', 'coding'] }),
        ['aptitude', 'coding'],
    );
});

test('a new Mock Drive gets independent empty defaults', () => {
    const first = createEmptyMockDriveForm();
    first.eligible_branches.push('Computer Science');
    first.selected_rounds.coding = true;

    const second = createEmptyMockDriveForm();
    assert.equal(second.company_name, '');
    assert.equal(second.target_role, '');
    assert.equal(second.minimum_cgpa, 6.0);
    assert.deepEqual(second.eligible_branches, []);
    assert.deepEqual(second.selected_rounds, {});
    assert.equal(second.blueprint_id, null);
});

test('explicitly opening an existing drive loads only that drive data', () => {
    const drive = {
        id: 42,
        company_name: 'Citi Test 2',
        target_role: 'Software Engineer',
        description: 'Saved drive',
        minimum_cgpa: 8.2,
        maximum_backlogs: 1,
        eligible_branches: ['Computer Science'],
        blueprint_id: 17,
    };
    const loaded = loadMockDriveForm(drive, { coding: true });

    assert.equal(loaded.company_name, 'Citi Test 2');
    assert.equal(loaded.description, 'Saved drive');
    assert.equal(loaded.minimum_cgpa, 8.2);
    assert.deepEqual(loaded.eligible_branches, ['Computer Science']);
    assert.deepEqual(loaded.selected_rounds, { coding: true });
    assert.equal(loaded.blueprint_id, 17);
});
