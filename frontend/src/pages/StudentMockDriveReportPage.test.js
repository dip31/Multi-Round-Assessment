import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const page = readFileSync(fileURLToPath(new URL('./StudentMockDriveReportPage.jsx', import.meta.url)), 'utf8');
const app = readFileSync(fileURLToPath(new URL('../App.jsx', import.meta.url)), 'utf8');
const overview = readFileSync(fileURLToPath(new URL('./MockDriveOverview.jsx', import.meta.url)), 'utf8');

test('live report route uses the drive id and does not import preview fixtures', () => {
  assert.match(app, /\/student\/mock-drives\/:mockDriveId\/report/);
  assert.match(page, /useParams\(\)/);
  assert.match(page, /`\/mock-drives\/\$\{encodeURIComponent\(mockDriveId\)\}\/result`/);
  assert.doesNotMatch(page, /studentMockDriveReportPreview|REPORT_SCENARIOS/);
});

test('report UI keeps unavailable scores distinct and links completed history by drive id', () => {
  assert.match(page, /round\.score == null/);
  assert.match(page, /evaluation_status/);
  assert.match(overview, /\/student\/mock-drives\/\$\{drive\.mock_drive_id\}\/report/);
  assert.match(overview, /View Performance Report/);
});

test('live report presents persisted summary, evidence and print action without preview fixtures', () => {
  for (const text of ['Performance Summary', 'Key Insights', 'Round-by-round performance', 'Improvement Plan', 'Print / Save Report']) {
    assert.ok(page.includes(text), `Expected live report section: ${text}`);
  }
  assert.match(page, /evaluation_status === 'evaluated'/);
  assert.match(page, /total_questions \?\? 'Unavailable'/);
  assert.doesNotMatch(page, /studentMockDriveReportPreview|REPORT_SCENARIOS|overall_score\s*=/);
});

test('Results route shows all authenticated drive history states and a retryable error state', () => {
  assert.match(overview, /pathname === '\/mock-drive\/results'/);
  assert.match(overview, /historyError/);
  assert.match(overview, /driveHistory\.map\(\(drive\)/);
  assert.match(overview, /\/student\/mock-drives\/\$\{drive\.mock_drive_id\}\/report/);
  assert.doesNotMatch(overview, /Completed mock drives/);
});
