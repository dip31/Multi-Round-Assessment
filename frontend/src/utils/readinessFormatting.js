// Pure formatting/derivation helpers for the TPO Readiness Analytics page.
// Every function operates only on data returned by the backend readiness
// overview endpoint — nothing here invents values.

// Section 2 subtitle: describes where values come from without repeating the
// old long "persisted assessment records" paragraph in every state.
export const READINESS_SECTION2_SUBTITLE =
    'Readiness metrics are calculated from eligible assessment evidence in the selected period and scope.';

// Concise copy for a KPI's unavailable state. The average-readiness card is
// intentionally blank: the single section notice already carries the full
// readiness reason, so the card must not repeat it. Threshold/placement keep
// one short line because their unavailability is specific to that metric and
// no section-wide notice explains it.
export const UNAVAILABLE_KPI_META = {
    average: '',
    improvement: 'Requires 2+ eligible scored attempts for a candidate.',
    threshold: 'No authoritative threshold in system data or business rules',
    placement: 'No persisted placement or offer records',
};

export function unavailableKpiMeta(metric) {
    return UNAVAILABLE_KPI_META[metric] ?? '';
}

// One-line "because …" clause for the single readiness-unavailable notice.
// It mirrors the backend's average_readiness reason branches
// (report_router.py: completed → pinned snapshot → configured competencies →
// evidence mappings → usable score) and is derived from the SAME live
// `coverage` counters the notice displays, so the copy can never contradict
// the returned data. Counts are rendered once, on their own compact line.
export function readinessNoticeReason(coverage) {
    const completed = coverage?.completed_contexts ?? 0;
    const snapshots = coverage?.contexts_with_snapshot ?? 0;
    const configured = coverage?.contexts_with_configured_competencies ?? 0;
    const mapped = coverage?.contexts_with_evidence_mappings ?? 0;
    if (!completed) return 'because no completed attempts exist in the selected period and scope.';
    if (!snapshots) return 'because no completed attempt carries a pinned blueprint snapshot.';
    if (!configured) return 'because no configured competencies have mapped assessment evidence.';
    if (!mapped) return 'because configured competencies have no mapped assessment evidence.';
    return 'because no completed attempt produced a usable competency readiness score.';
}

export function formatScore(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    return Number(value).toFixed(1);
}

export function formatDelta(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    const n = Number(value);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(1)}`;
}

export function formatPercent(count, total) {
    if (!total || total <= 0) return '—';
    return `${((count / total) * 100).toFixed(1)}%`;
}

export function kpiDisplay(kpi) {
    if (!kpi || kpi.available !== true) {
        return {
            display: '—',
            meta: kpi?.reason || 'Unavailable',
            available: false,
        };
    }
    if (kpi.value !== undefined && kpi.value !== null) {
        return {
            display: formatScore(kpi.value),
            meta: kpi.definition || '',
            available: true,
        };
    }
    return {
        display: formatDelta(kpi.mean_delta),
        meta: kpi.definition || '',
        available: true,
    };
}

export function readinessBuckets(distribution) {
    return distribution?.buckets || [];
}

export function overTimePoints(series) {
    return series || [];
}

export function skillGapRows(skillGaps) {
    return skillGaps?.competencies || [];
}

export function unassessedSkillRows(skillGaps) {
    return skillGaps?.unassessed || [];
}

export function insightList(payload) {
    return payload?.insights || [];
}

export function hasScoredAttempts(coverage) {
    return (coverage?.scored_attempts || 0) > 0;
}

export function eligibleSummary(coverage) {
    if (!coverage) return 'No coverage data.';
    return `${coverage.scored_attempts ?? 0} scored attempt(s) across ${coverage.unique_scored_candidates ?? 0} candidate(s)`;
}

// ── Section 2 KPI derivations (Section 2 cards 2–4) ──────────────────
// Each derivation returns { display, meta, available } and reads only the
// backend payload. A metric that the backend cannot answer is shown as an
// em-dash ("—") with an honest reason — never a fabricated number and never
// a zero standing in for missing data.

const NO_SCOPE = {
    display: '—',
    meta: 'No completed assessment rounds in scope.',
    available: false,
};

// Card 2 — Assessment Coverage: completed rounds with a usable scored
// result over all completed rounds in scope. The percentage comes from the
// backend evidence-coverage summary; the numerator/denominator are shown so
// the figure is auditable.
export function assessmentCoverageKpi(evidenceSummary) {
    const denominator = evidenceSummary?.denominator || 0;
    const numerator = evidenceSummary?.numerator || 0;
    if (denominator <= 0) return { ...NO_SCOPE };
    const pct = evidenceSummary?.value != null
        ? evidenceSummary.value
        : Math.round((numerator / denominator) * 1000) / 10;
    return {
        display: `${formatScore(pct)}%`,
        meta: `${numerator} of ${denominator} completed rounds validly scored`,
        available: true,
    };
}

// Card 3 — Candidates Needing Assessment: distinct candidates who completed
// assessment activity but produced no usable scored attempt. The backend
// counts distinct candidates; the page never re-counts attempts as people.
export function candidatesNeedingAssessmentKpi(coverage, assessment) {
    if ((coverage?.completed_contexts ?? 0) <= 0) return { ...NO_SCOPE };
    const explicit = coverage?.candidates_with_completed_no_usable_score;
    let value = null;
    if (explicit != null) {
        value = explicit;
    } else if (coverage?.students_with_contexts != null && coverage?.unique_scored_candidates != null) {
        value = Math.max(0, coverage.students_with_contexts - coverage.unique_scored_candidates);
    } else {
        const block = assessment?.summary?.candidates_assessed;
        if (block && block.available) {
            value = Math.max(0, (block.denominator || 0) - (block.value || 0));
        }
    }
    if (value == null) {
        return {
            display: '—',
            meta: 'Candidate-level scoring coverage is unavailable for this scope.',
            available: false,
        };
    }
    return {
        display: String(value),
        meta: 'Distinct candidates with completed activity but no usable scored attempt in scope.',
        available: true,
    };
}

// Card 4 — Scoring Follow-up: completed assessment rounds that did not
// produce a usable readiness score. These are attempts (rounds), never
// candidates, and each attempt carries exactly one reason.
export function scoringFollowupKpi(coverage, evidenceSummary) {
    if ((coverage?.completed_contexts ?? 0) <= 0) return { ...NO_SCOPE };
    const explicit = coverage?.rounds_needing_followup;
    if (explicit != null) {
        return {
            display: String(explicit),
            meta: 'Completed assessment rounds requiring scoring follow-up in scope.',
            available: true,
        };
    }
    const denominator = evidenceSummary?.denominator || 0;
    const numerator = evidenceSummary?.numerator || 0;
    if (denominator <= 0) return { ...NO_SCOPE };
    return {
        display: String(Math.max(0, denominator - numerator)),
        meta: 'Completed rounds without a usable scored result in scope.',
        available: true,
    };
}

// ── Recommended Actions ───────────────────────────────────────────────
// Every action is derived from a real counter: either a per-assessment
// scoring gap from `assessment_performance.components` or a follow-up reason
// from `coverage.followup_breakdown`. Nothing is hardcoded and no action is
// suggested when the data shows no gap. `tone` drives the icon colour in the
// page; `text` carries the counts so the action is auditable.
export function recommendedActions(coverage, evidenceSummary, assessment) {
    const actions = [];
    const fb = coverage?.followup_breakdown || {};
    const denominator = evidenceSummary?.denominator || 0;
    const numerator = evidenceSummary?.numerator || 0;
    const totalMissing = denominator > 0 ? Math.max(0, denominator - numerator) : 0;

    // Per-assessment completion/scoring gaps (rounds, not candidates).
    const components = assessment?.components;
    if (components) {
        Object.values(components).forEach((comp) => {
            if (!comp) return;
            if (comp.completed_rounds > 0 && comp.rounds_with_valid_scores === 0 && comp.rounds_with_results === 0) {
                actions.push({
                    key: `no-results-${comp.key}`,
                    tone: 'info',
                    text: `${comp.label}: ${comp.completed_rounds} completed round(s) have no persisted result — check the assessment completion/scoring pipeline.`,
                });
            } else if (comp.rounds_with_results > 0 && comp.rounds_with_valid_scores === 0) {
                actions.push({
                    key: `results-not-usable-${comp.key}`,
                    tone: 'warning',
                    text: `${comp.label}: results exist but none is usable — review scoring failures for this assessment type.`,
                });
            }
        });
    }

    // Competency-config / mapping / scoring follow-ups for completed attempts.
    if ((fb.missing_pinned_snapshot || 0) > 0) {
        actions.push({
            key: 'missing-snapshot',
            tone: 'warning',
            text: `${fb.missing_pinned_snapshot} completed attempt(s) have no pinned blueprint snapshot — no competency readiness can be computed for them.`,
        });
    }
    if ((fb.no_configured_competencies || 0) > 0) {
        actions.push({
            key: 'no-competencies-config',
            tone: 'info',
            text: `${fb.no_configured_competencies} completed attempt(s) have a pinned snapshot with no configured competencies — configure competencies on blueprints used for future drives (historical snapshots are never changed).`,
        });
    }
    if ((fb.no_mapped_evidence || 0) > 0) {
        actions.push({
            key: 'no-mappings',
            tone: 'warning',
            text: `${fb.no_mapped_evidence} completed attempt(s) have configured competencies but no mapped evidence — investigate competency evidence mapping for those sessions.`,
        });
    }
    if ((fb.no_usable_score || 0) > 0) {
        actions.push({
            key: 'no-usable-score',
            tone: 'warning',
            text: `${fb.no_usable_score} completed attempt(s) have mapped evidence but no usable score — review scoring failures.`,
        });
    }
    if ((fb.scoring_error || 0) > 0) {
        actions.push({
            key: 'scoring-error',
            tone: 'danger',
            text: `${fb.scoring_error} completed attempt(s) hit a scoring error during aggregation — investigate the scoring service for those sessions.`,
        });
    }

    // Fallback when no breakdown is available but completed rounds lack
    // usable scores.
    if (actions.length === 0 && totalMissing > 0) {
        actions.push({
            key: 'missing-scores',
            tone: 'warning',
            text: `${totalMissing} completed assessment round(s) have no usable scored result — review results or scoring configuration.`,
        });
    }
    return actions;
}
