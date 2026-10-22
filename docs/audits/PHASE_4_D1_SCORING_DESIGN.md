# Phase 4 D1 — Competency Scoring: Audit Findings & Implementation Design

Date: 2026-10-12
Status: design recorded before implementation
Related: `docs/audits/PHASE_4_RECONCILED_GAP_REPORT.md` (G5–G7 blocked on D1)

## 1. Audit findings (what already exists)

### Blueprint competency configuration (reusable — do not reinvent)
- `CompanyBlueprint.blueprint_data` JSONB carries an **optional** `competencies` list
  (`app/models/company_data.py:149-238`). Each entry: `{id?, name, weight_pct, topics: [str]}`.
- Validated by `BlueprintCompetency` / `validate_competency_configuration`
  (`app/schemas/company_data.py:342-420`): names/ids unique, topics unique per set,
  each `weight_pct` finite, `>0` and `<=100`, and the set **sums to 100.0 ± 0.1**.
- Preserved across blueprint recalculation and edits; **pinned** into a snapshot.

### Pinned snapshot (reproducibility)
- `snapshot_company_blueprint()` → `{blueprint_id, blueprint_version, status, company_name,
  target_role, blueprint_data}` (`app/services/assessment_blueprint_service.py:15-23`).
- Stored on `AssessmentContext.blueprint_snapshot` / `MockDrive.blueprint_snapshot`.
- Runtime read: `get_session_blueprint_snapshot(db, session)` (`:84-103`), which validates
  `status == "approved"`. Historical assessments keep their pinned config.

### Persisted evidence (the only scoring input)
- Model `CompetencyEvidenceMapping` (`app/models/competency.py:29-87`), table
  `competency_evidence_mappings`, unique `(evidence_type, evidence_id, competency_id)`.
  Columns: `candidate_id, context_id, session_id, round_id, evidence_type, evidence_id,
  competency_id, competency_name, source, blueprint_version, raw_metric (JSONB)`.
- Populated by `competency_mapping_service` at Mock Drive finalization
  (`_finalize_mock_drive` → `finalize_session_competency_mapping`, `mock_drive_service.py:1531-1573`).
- Evidence coverage today: **`aptitude_attempt`** and **`coding_submission`** only.
  Interview rounds are intentionally **unmapped** (no persisted topic on `InterviewTurn`).
- `raw_metric` (untouched originals):
  - aptitude: `{topic, is_correct: bool, response_time, difficulty, reward, attempt_number}`
  - coding: `{topic, status, score, language, execution_time, memory_used}`
- **No competency score is persisted anywhere.** `competency_evidence_mappings` currently has
  **no reader/consumer** — this service will be its first.

### Evidence metric scales (for normalization)
- Aptitude is a deterministic attempt: `is_correct` → 0/100 (unambiguous).
- Coding `CodingSubmission.score` is a **0..1 fraction** (`evaluate_submission`:
  `score = passed/total`, `code_evaluator.py:444`; `finalize_coding_round` docstring
  "Returns the computed round score (0..1)", `coding_service.py:378-403`).
- Coding statuses `VALID_CODING_STATUSES` (`code_evaluator.py:12-21`); `internal_error` is an
  infrastructure failure (Judge0), and `running` is non-final — neither is candidate performance.

### Result aggregation (extend, do not fork)
- `get_mock_drive_result()` (`app/services/mock_drive_service.py:1579-1760`) → `MockDriveResultResponse`
  (`app/schemas/mock_drive.py:222-239`); served by `GET /mock-drives/{id}/result` and the
  staff-only `GET /tpo/mock-drives/{id}/candidates/{student_id}/result`.
- `get_mock_drive_roster()` (`:1812-1881`) → `MockDriveRosterResponse`.
- Existing `overall_score` is a **plain per-round average**, unrelated to blueprint weights.

### Timeout/finalization (evidence preservation)
- `_finalize_expired_round` (`:1464-1528`) marks rounds `expired` and finalizes the drive; it
  does **not** fabricate scores. `_finalize_mock_drive` then runs competency mapping.
- Therefore a timed-out round's **already-persisted** attempts/submissions are mapped and can be
  scored; missing evidence stays missing.

### Gaps confirmed (no product policy exists)
- No `required` flag, no `min_evidence`, no scoring/normalization logic anywhere in `app/`.
- No reader of `competency_evidence_mappings`.

## 2. Intended implementation (decisions)

Everything below is a **read-time derivation** from persisted mappings + pinned snapshot.
**No new table, column, or migration** (avoids destructive change; keeps evidence auditable).

### D1a — Normalization to 0–100 (reuse persisted evidence)
`aptitude_attempt` → `100.0 if raw_metric["is_correct"] else 0.0`.
`coding_submission` → `clamp(float(raw_metric["score"]), 0, 1) * 100`; statuses
`internal_error` / `running` are **not countable** (excluded, never a candidate zero).
Values are clamped to `[0, 100]`.

### D1b — Evidence requirement (documented gap → conservative rule)
The blueprint defines **no** minimum-evidence field. Conservative explicit rule for this
milestone: a competency is **`assessed`** iff it has **≥ 1 countable mapping**; otherwise
`not_assessed` with `normalized_score = None`. A competency with only zero-valued evidence is
still `assessed` with score `0.0` (a legitimate zero). Coverage = assessed / required.
Multiple attempts of the same question are distinct persisted evidence rows (the model
explicitly stores `attempt_number`); within a competency a given `evidence_id` cannot repeat
(DB unique constraint).

### D1c — Weighting (percentages, fail closed)
Weights are blueprint `competency.weight_pct` (**percentages**, validated to sum 100 ± 0.1).
Scoring validation: each finite and `>= 0`, at least one positive, sum within `0.1` of 100.
If invalid → **fail closed**: overall `unavailable` + explicit `scoring_error`; never invent
equal weights and never redistribute.

### D1c — Overall score & status (the three required states)
- Required = all configured competencies (no `required` flag exists → all are required;
  documented).
- `assessed == 0` → **`unavailable`** (`overall_score = null`).
- `missing == 0` → **`final`**: `Σ (weight_pct/100) * normalized_score`.
- `0 < assessed < required` → **`provisional`**: `Σ over assessed only`; missing contribute `0`
  and weights are **not** redistributed. Informational only; not comparable/rankable.
- No configured competencies → `unavailable` (reason `no_configured_competencies`).
- Invalid weights → `unavailable` (explicit `scoring_error`).

### D1c — Determinism
Pure function; repeated retrieval is identical. Result exposes `blueprint_id`,
`blueprint_version`, and a `scoring_policy_version` constant for reproducibility.

### D1e — Results API (additive, backward compatible)
Add an optional nested `competency_scoring` object to `MockDriveResultResponse` and summary
fields to `MockDriveRosterEntry`. Existing fields and candidate behavior are untouched.

### D1f — Timeout / infra failure
Scoring reads only persisted evidence, so timed-out rounds keep valid evidence; no invented
zeros. `internal_error`/`running` coding evidence is excluded, so an infrastructure failure
never becomes a candidate score of zero.

## 3. Files to change
- add `app/services/competency_scoring_service.py`
- edit `app/services/mock_drive_service.py` (`get_mock_drive_result`, `get_mock_drive_roster`)
- edit `app/schemas/mock_drive.py` (additive schemas)
- edit `frontend/src/pages/TPOMockDrivesPage.jsx`, `frontend/src/utils/mockDriveRoster.js`
- add `tests/test_competency_scoring.py`
- update `docs/audits/PHASE_4_RECONCILED_GAP_REPORT.md`
