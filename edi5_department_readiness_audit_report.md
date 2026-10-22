# EDI5 Deep Audit — Department Readiness Single-Bar Investigation

**Scope:** Determine why the TPO Readiness page's "Department Readiness" chart renders only one bar (`Electronics & Communication — 29.0`), audit the full data pipeline end to end, fix genuine defects only, add regression tests, verify end to end, and record per-record exclusion evidence.
**Status:** Complete. **No defect found in the chart or the readiness pipeline.** The single bar is the correct, evidence-derived output of the current data. The behavior is now locked by regression tests.
**Data policy:** No blueprints were configured for historical/future cohorts, no snapshots were mutated or backfilled, and no readiness scores were inserted or recomputed. All statements are backed by read-only inspection of repository source and the local development database.

---

## 1. Executive summary

The Department Readiness chart shows a single bar because **exactly one completed mock-drive context has both a pinned blueprint snapshot that contains configured competencies and mapped evidence**, and that context belongs to a student whose profile department is `Electronics & Communication`.

Root cause, stated precisely:

- Readiness is **competency-derived**, never participation- or raw-aptitude-derived. A completed context is scorable only if its **pinned** `blueprint_snapshot` carries configured competencies and evidence has been mapped to them.
- Of **43 completed mock-drive contexts**, **13** have a pinned snapshot at all, and of those **13 only one (ctx 783)** has any configured competencies. Every other snapshotted context returns the identical `scoring_error = "no_configured_competencies"` and scores `None` (fail-closed, never zero).
- The one scorable context (ctx 783, student 135, dept `Electronics & Communication`, drive 116, blueprint #44) yields the authoritative `overall_score = 29.0` (`final`, 4/4 competencies assessed, coverage 1.0).
- Departments present among completed contexts: `Computer Science` (23 students / 37 contexts, **0 with competencies**) and `Electronics & Communication` (1 student / 6 contexts, 1 with competencies). `Information Technology` has 13 profiles but **0 completed contexts**.

Therefore the chart is **correct**: only one department can legitimately produce a bar. The `by_department` aggregation (`report_router.py:2080-2106`) and the frontend `toDepartmentBars` transform are both correct and were verified against a live multi-department API response and unit fixtures.

The genuine, non-defect limitation: historical CS contexts **cannot** produce authoritative scores without mutating pinned snapshots (forbidden), because configuring a blueprint now does not retroactively change a pinned snapshot (`assessment_blueprint_service.py:97-103` returns the pinned copy, never the live blueprint). This is documented as a limitation, not fixed by invention.

---

## 2. What was and was not changed

### Changed
- `tests/test_readiness_overview.py` — **7 new regression tests** plus a `_seed_attempt` extension (`snapshot_competencies`, `drive_id`, `company`) and a `_set_department` helper. No production code was changed.

### Not changed (verified correct as-is)
- `app/modules/report/routers/report_router.py` — `by_department` aggregation and eligibility/reason branches.
- `app/services/competency_mapping_service.py` — exact topic matching, aptitude/coding-only mapping, fail-closed on ambiguity.
- `app/services/competency_scoring_service.py` — weight fail-closed, `_countable_score`, `overall_score` derivation.
- `app/services/assessment_blueprint_service.py` — pinned-snapshot semantics.
- `frontend/src/pages/TPOReadinessPage.jsx`, `frontend/src/utils/readinessCharts.js` — Department Readiness wiring and `toDepartmentBars`.

No blueprint, drive, context, session, round, attempt, or snapshot was created or modified by this audit.

---

## 3. Pipeline audit (record-by-record)

### 3.1 Snapshot pinning is definitive
`get_session_blueprint_snapshot` (`app/services/assessment_blueprint_service.py:84`) returns the **context's pinned** `blueprint_snapshot` when present (lines 97-103, `deepcopy`), and only falls back to the drive/blueprint if the context has no snapshot. It never re-reads the live blueprint. Consequently, configuring competencies on a blueprint today cannot retroactively enable scoring for a context whose snapshot was pinned before the configuration.

### 3.2 Scoring fails closed
`competency_scoring_service.py`: `overall_score = None` when no competencies are configured; weights must sum to 100 ±0.1 else fail closed; missing evidence is never redistributed; a missing answer is never counted as zero. A completed context with no configured competencies is therefore **completed but unscored**, and is excluded from readiness rather than shown as 0.

### 3.3 Live DB evidence (completed contexts with a snapshot)
Read-only query of completed `AssessmentContext` rows carrying a `blueprint_snapshot`:

| Context | Department | Configured competencies in pinned snapshot | Snapshot md5 (12) |
|---|---|---|---|
| 630 | Computer Science | 0 | 52e0ed396581 |
| 698 | Computer Science | 0 | 5c09db000ac4 |
| 702 | Computer Science | 0 | 14a0a80f7ad6 |
| 769 | Computer Science | 0 | 14100e033f11 |
| 771 | Computer Science | 0 | 3965a6081c0c |
| 773 | Electronics & Communication | 0 | 3965a6081c0c |
| 774 | Electronics & Communication | 0 | 14a0a80f7ad6 |
| 777 | Computer Science | 0 | 13d4bdbd4dbb |
| 779 | Computer Science | 0 | 97a787434f41 |
| 781 | Computer Science | 0 | 62d117e03077 |
| 782 | Computer Science | 0 | 3cfba323cb67 |
| **783** | **Electronics & Communication** | **4** | **56e8696e48b7** |
| 770 | Electronics & Communication | 0 | 13d4bdbd4dbb |

Only ctx 783 has competencies → only ctx 783 yields an authoritative readiness score. All other 12 snapshotted contexts return `scoring_error = "no_configured_competencies"`.

### 3.4 Department distribution of completed contexts
| Department | Students | Completed contexts | Contexts with configured competencies | Scorable |
|---|---|---|---|---|
| Computer Science | 23 | 37 | 0 | 0 |
| Electronics & Communication | 1 | 6 | 1 | 1 |
| Information Technology | 13 profiles | 0 | 0 | 0 |

No completed-context student is missing a profile row, and no profile has a NULL/blank department (column is `NOT NULL`, default `Computer Science`).

### 3.5 Live API confirmation (post-audit, `period=all`)
```
by_department: [ { department: "Electronics & Communication", candidates: 1, attempts: 1, avg_readiness: 29.0 } ]
coverage: { completed_contexts: 43, contexts_with_snapshot: 13,
            contexts_with_configured_competencies: 1,
            contexts_with_evidence_mappings: 1, scored_attempts: 1,
            unique_scored_candidates: 1, skipped_scoring_errors: 0 }
kpis.average_readiness: { available: true, value: 29.0, eligible_candidates: 1, final_attempts: 1 }
```

---

## 4. Why the CS blueprints cannot be "just configured"

Blueprints 39/42/43/47/48/49/51/52 are `approved` and use aptitude topics overlapping #44's competency topics, but each CS context's snapshot is **pinned without competencies**. Two constraints forbid the tempting shortcut:

1. **Mutating pinned snapshots is forbidden** (it would rewrite the historical assessment configuration actually administered).
2. **`reprocess_competency_mapping` cannot help** — it consumes the **pinned** snapshot and never changes or backfills scores; scoring remains fail-closed.

Configuring those blueprints now would only affect **future** contexts, not the already-pinned historical ones. Turning raw aptitude accuracy into readiness would violate the directive that readiness must be competency-derived, not a raw-aptitude proxy.

---

## 5. Regression tests added

Added to `tests/test_readiness_overview.py` (suite now **49 passed**; was 42):

| Test | Locks |
|---|---|
| `test_readiness_department_chart_renders_multiple_departments_as_separate_bars` | ≥2 departments render as separate rows; stable name order |
| `test_readiness_department_average_weights_multiple_candidates_in_a_department` | multiple candidates in one department average (not overwrite) |
| `test_readiness_department_excludes_completed_but_unscored_contexts` | completed-but-unscored context produces no bar and no fabricated 0 |
| `test_readiness_department_reports_blank_department_as_unspecified` | blank (NOT NULL → `""`) department maps to `Unspecified`, retained |
| `test_readiness_department_contexts_are_attempts_not_candidates` | repeated attempts → 1 candidate / N attempts |
| `test_readiness_department_filtered_scope_updates_every_row` | chart is filter-responsive; company filter narrows the department set |
| `test_readiness_unscored_context_does_not_mutate_pinned_snapshot` | overview reads never rewrite/backfill a pinned snapshot |

Frontend contract already covered in `frontend/src/utils/readinessCharts.test.js` (`toDepartmentBars`: multiple departments, whitespace/casing grouping, blanks→`Unspecified`, excludes unscored, keeps legitimate zero) and the removed-graphs regression in the same file.

---

## 6. Verification results

| Check | Result |
|---|---|
| `pytest tests/test_readiness_overview.py` | **49 passed** |
| `pytest tests/{readiness_overview,competency_mapping,competency_scoring,report_router,mock_drive_roster}` | **143 passed, 1 pre-existing fail** (roster) |
| Full backend suite (`--ignore=test_phone_detection_properties.py`) | 525 passed, 1 skipped, **24 pre-existing env failures** (portfolio/proctoring/phase2/phase3 — `RuntimeError`/async-fixture, unrelated to readiness/competency) |
| `npm test` (frontend) | **84 passed / 0 fail** |
| Scoped `eslint` (readiness page + utils + tests) | **0 errors, 2 pre-existing warnings** |
| Live API re-probe (`period=all`) | single correct department row; coverage funnel matches audit |
| Live DB snapshot audit | exactly 13 snapshotted completed contexts; only ctx 783 has competencies |

**Pre-existing, unrelated items (reported, not fixed):**
- `tests/test_mock_drive_roster.py::test_roster_derives_participants_and_counts_from_contexts` — 1 failure.
- `tests/test_phone_detection_properties.py` — collection error: `ModuleNotFoundError: No module named 'hypothesis'`.
- 24 backend failures in portfolio/proctoring/phase2/phase3 suites (environment/async-fixture), unrelated to this change.

---

## 7. Conclusion and recommendation

- **No code defect.** The Department Readiness chart correctly shows one bar because only one completed context is competency-scorable. The aggregation and rendering paths were verified correct against both unit fixtures and a live API response.
- **Genuine limitation:** historical Computer Science contexts are completed but their **pinned** snapshots lack configured competencies, and readiness cannot be produced without mutating those snapshots (forbidden) or proxying raw aptitude (forbidden). This is documented, not "fixed" by invention.
- **Recommendation (out of scope for this data-only task):** for *future* cohorts only, configure competencies on the blueprint(s) used by the relevant drives **before** sessions are created, so new contexts pin snapshots that are scorable. This changes no historical record and requires explicit approval.
