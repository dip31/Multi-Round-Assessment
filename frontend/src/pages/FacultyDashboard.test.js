import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const dashboardSource = readFileSync(new URL('./FacultyDashboard.jsx', import.meta.url), 'utf8');

test('imports the Recharts Legend rendered by the dashboard chart', () => {
    assert.match(dashboardSource, /import\s*\{[^}]*\bLegend\b[^}]*\}\s*from\s*['"]recharts['"]/s);
    assert.match(dashboardSource, /<Legend\s*\/>/);
});
