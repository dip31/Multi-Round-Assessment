import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const pageSource = await readFile(
    new URL('../pages/TPOReadinessPage.jsx', import.meta.url),
    'utf8',
);
const cardStart = pageSource.indexOf('data-testid="assessment-insights"');
const cardEnd = pageSource.indexOf('data-testid="evidence-gaps"', cardStart);
const assessmentCard = pageSource.slice(cardStart, cardEnd);

test('Assessment Insights renders as one parent card with three ordered subsections', () => {
    assert.ok(cardStart >= 0);
    assert.ok(cardEnd > cardStart);
    assert.match(assessmentCard, /<h[1-6][^>]*>Assessment Insights<\/h[1-6]>/);
    assert.equal((assessmentCard.match(/glass-card rounded-2xl p-5/g) || []).length, 1);

    const aptitudeIndex = assessmentCard.indexOf('data-testid="aptitude-assessment-insights"');
    const codingInterviewIndex = assessmentCard.indexOf('data-testid="assessment-type-status"');
    assert.ok(aptitudeIndex >= 0 && codingInterviewIndex > aptitudeIndex);
    assert.match(assessmentCard.slice(codingInterviewIndex), /statusRows\.map[\s\S]*Coding Assessment Insights[\s\S]*Interview Assessment Insights/);
});

test('the old standalone aptitude and coding/interview cards are gone', () => {
    assert.doesNotMatch(assessmentCard, /<section className="glass-card rounded-2xl p-5" data-testid="aptitude-assessment-insights"/);
    assert.doesNotMatch(assessmentCard, /<section className="glass-card rounded-2xl p-5" data-testid="assessment-type-status"/);
});

test('assessment metrics, availability badges, and summaries remain in the card', () => {
    for (const label of [
        'Completed Eligible Assessments',
        'Assessments With Results',
        'Assessments With Valid Scores',
        'Completed Eligible Rounds',
        'Rounds With Results',
        'Rounds With Valid Scores',
        'Score Coverage',
        'Distinct Candidates With Valid Scores',
        'Available',
        'Needs Review',
        'Unavailable',
    ]) {
        assert.ok(assessmentCard.includes(label), `Missing assessment insight content: ${label}`);
    }
    assert.match(assessmentCard, /aptComp\?\.reason/);
    assert.match(assessmentCard, /row\.reason/);
    assert.match(assessmentCard, /No usable aptitude scores available/);
    assert.match(assessmentCard, /scores are available for \{valid\} of \{completed\}/);
});
