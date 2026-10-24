import test from 'node:test';
import assert from 'node:assert/strict';
import {
    CODING_SKILL_GAP_DEMO_ROWS,
    codingSkillGapPresentation,
} from './competencyGapDemoData.js';

const realSkillGaps = {
    competencies: [{ competency_id: 'all-api-row' }],
    summary: { competencies_assessed: 1 },
    assessment_types: ['aptitude', 'coding'],
    by_assessment_type: {
        aptitude: { competencies: [{ competency_id: 'aptitude-api-row' }] },
        coding: {
            competencies: [],
            unassessed: [{ competency_id: 'coding-api-row' }],
            summary: { competencies_assessed: 0, competencies_unassessed: 4 },
        },
    },
};

test('Coding demo view uses the supplied presentation KPIs and competencies', () => {
    const view = codingSkillGapPresentation(realSkillGaps, 'coding', true);

    assert.equal(view.summary.competencies_assessed, 4);
    assert.equal(view.summary.competencies_unassessed, 1);
    assert.equal(view.summary.average_competency_score, 64.5);
    assert.equal(view.summary.largest_competency_gap, 40.0);
    assert.deepEqual(view.competencies, CODING_SKILL_GAP_DEMO_ROWS);
    assert.deepEqual(
        view.competencies.map((row) => ({
            name: row.competency_name,
            score: row.avg_score,
            gap: row.gap_to_100,
            attempts: `${row.assessed_attempts} / ${row.eligible_attempts}`,
            coverage: `${row.assessed_attempts} / ${row.eligible_attempts} · ${row.coverage_percent}%`,
            evidence: row.evidence_items,
            sources: row.evidence_sources,
        })),
        [
            { name: 'Problem-solving and algorithmic thinking', score: 60.0, gap: 40.0, attempts: '2 / 3', coverage: '2 / 3 · 66.7%', evidence: 12, sources: ['coding'] },
            { name: 'Data structures and algorithms', score: 63.0, gap: 37.0, attempts: '2 / 3', coverage: '2 / 3 · 66.7%', evidence: 10, sources: ['coding'] },
            { name: 'Code correctness and testing', score: 67.0, gap: 33.0, attempts: '2 / 3', coverage: '2 / 3 · 66.7%', evidence: 9, sources: ['coding'] },
            { name: 'Code quality and maintainability', score: 68.0, gap: 32.0, attempts: '1 / 1', coverage: '1 / 1 · 100%', evidence: 5, sources: ['coding'] },
        ],
    );
    assert.ok(view.competencies.every((row) => row.gap_to_100 === 100 - row.avg_score));
    assert.equal(
        view.competencies.reduce((total, row) => total + row.avg_score, 0) / view.competencies.length,
        64.5,
    );
});

test('Aptitude, combined scope, and disabled Coding demo preserve the API data', () => {
    assert.equal(codingSkillGapPresentation(realSkillGaps, 'aptitude', true), realSkillGaps.by_assessment_type.aptitude);
    assert.equal(codingSkillGapPresentation(realSkillGaps, 'all', true), realSkillGaps);
    assert.equal(codingSkillGapPresentation(realSkillGaps, 'coding', false), realSkillGaps.by_assessment_type.coding);
});
