# Historical Assessment Configuration — Phase 1 Fix

Implements the durable, single-source-of-truth round configuration described in
`HISTORICAL_ASSESSMENT_CONFIGURATION_AUDIT.md`. No migration was required: the
configuration lives inside the existing `CompanyPattern.pattern_data` JSONB.

## Persisted shape (inside `pattern_data`)

- `assessment_rounds` — the **effective** round order consumed by blueprint
  generation (evidence rounds minus explicit deselections, plus TPO-added
  rounds, TPO-added appended last in TPO order).
- `evidence_rounds` — the **pure historical evidence** round list, recorded
  before any TPO add/deselect. Never mutated by TPO choices; lets consumers tell
  evidence apart from TPO decisions. Source records are never deleted.
- `round_patterns` — per-round effective configuration, keyed by effective round.
- `tpo_configuration` — the durable TPO decision ledger:

  ```json
  {
    "version": 1,
    "updated_at": "<ISO-8601>",
    "rounds": [
      {
        "round_type": "coding",
        "enabled": true,
        "round_origin": "evidence" | "tpo_added",
        "question_count": 40,
        "duration_minutes": 90,
        "difficulty_distribution": {"easy": 0, "medium": 1, "hard": 0},
        "focus_areas": ["Arrays"]
      }
    ]
  }
  ```

## Precedence and merge rules

1. **Evidence first.** A fresh pattern is always re-derived from the historical
   sources (`_extract_pattern_from_sources`). Historical evidence is the base
   layer and is never synthesized.
2. **Restore durable TPO decisions.** A previously persisted `tpo_configuration`
   is re-applied (`_restore_tpo_configuration`): enabled `tpo_added` rounds are
   re-appended, and enabled per-round overrides (count/duration/difficulty/topics)
   are written over the evidence values. This is what makes recalculation stop
   erasing TPO settings.
3. **Request overrides win.** Explicit `round_configuration`, `added_rounds` and
   `deselected_rounds` in the request are applied after the restore. Request
   values beat restored values for the same round.
4. **Three-state semantics** (`_resolve_tpo_configuration`):
   - `enabled: true` — the TPO explicitly selected/added the round.
   - `enabled: false` — the TPO explicitly deselected the round (removed from
     the effective view, values retained, evidence preserved).
   - **no entry** — *unspecified*: the evidence default stands. Absence is never
     treated as deselection.
5. **Deselection durability.** A prior deselection persists across recalculation
   unless the same round is explicitly re-selected (`round_configuration` or
   `added_rounds`) in a later request. A request deselection always wins.
6. **No position/label/UI dependence.** Entries are keyed by normalized
   `round_type`; merging is keyed, so order, display labels and UI-only state
   never affect the result. Repeated recalculation is idempotent (no duplicate
   rounds or topics; topics de-duplicated).
7. **Evidence rounds are never downgraded.** Adding a round already present in
   evidence is a no-op and keeps `round_origin: "evidence"`.

## Attribution

- Evidence rounds carry `round_origin: "evidence"`; TPO-added rounds carry
  `round_origin: "tpo_added"`. Badges are derived from the persisted origin and
  the effective/evidence split rather than any display-only fabrication.
- `evidence_rounds` exposes the pure evidence set for honest provenance.

## TPO-added rounds without evidence topics (EDI5 follow-up)

A TPO-added round has no historical topic evidence to select from. Previously a
round added via `added_rounds` with complete numeric settings but no
`focus_areas` stayed flagged `requires_tpo_configuration`, and blueprint
generation then failed with 422 (`... requires TPO configuration for topic
selection ...`) even though the TPO had fully configured the round.

Rule now: a round counts as **fully configured** when its numeric settings
(`question_count`, `duration_minutes`, `difficulty_distribution`) are present
**and** either it has selected topics **or** it is `round_origin: "tpo_added"`.
For a TPO-added round the blueprint derives the canonical default topics for
that round type (marked `is_default: true`) instead of blocking. Evidence rounds
still require an explicit topic selection, and an incomplete TPO-added round
(missing numerics) still 422s with an actionable message. This lives in
`_round_is_fully_configured` / `_apply_round_configuration`
(`app/services/company_data_service.py`) so the pattern-level flag, the durable
`tpo_configuration` ledger, recalculation and blueprint generation all agree.

## Files changed

- `app/schemas/company_data.py` — added `GeneratePatternRequest.deselected_rounds`
  (+ validator).
- `app/services/company_data_service.py` — added `_restore_tpo_configuration`,
  `_resolve_tpo_configuration`, `_apply_deselected_rounds`, `_refresh_round_config_flag`;
  `generate_pattern` now fetches the existing pattern up front, records
  `evidence_rounds`, restores the durable config, applies request overrides, then
  persists the merged `tpo_configuration`. `_round_is_fully_configured` treats a
  fully-numeric-configured `tpo_added` round as complete (blueprint uses default
  topics) while evidence rounds still require topic selection. Existing helper
  behavior and the 422 contracts are otherwise unchanged.
- `app/api/v1/company_data.py` — threads `deselected_rounds` through
  `POST /pattern/generate`.
- `frontend/src/utils/historicalRoundConfig.js` (+ `.test.js`) — pure
  derive/payload helpers (single effective source; explicit deselection).
- `frontend/src/components/CompanyPatternModal.jsx` — panel state is derived from
  persisted pattern data; save sends `round_configuration` + `added_rounds` +
  `deselected_rounds`; API errors (string / `{message}` / validation list) are
  surfaced; the save button tracks dirty state and reflects a successful save.

## Tests added

- `tests/test_historical_tpo_configuration_persistence.py` (5 tests): TPO-added
  round survives recalc; edited values survive recalc; explicit deselection is
  durable and distinguishable from absence; absent round is not deselected;
  legacy pattern without `tpo_configuration` loads compatibly.
- `tests/test_historical_blueprint_route.py` —
  `test_evidence_round_plus_tpo_added_round_saves_reloads_and_generates`: the
  reported EDI5 chain (evidence Coding only → TPO adds Aptitude → save → reload →
  approve → blueprint generate) succeeds, with the TPO-added round using default
  topics and the blueprint 404ing before generation.
- `frontend/src/utils/historicalRoundConfig.test.js` (5 tests): derive/payload
  semantics for prefill, deselection vs absence, and TPO-added rounds.

## Merge rules — source-of-truth matrix

| Concern | Authoritative field | Rule |
| --- | --- | --- |
| Which rounds exist | `assessment_rounds` | evidence − deselected + tpo_added |
| What evidence existed | `evidence_rounds` | immutable snapshot per generation |
| Per-round values | `round_patterns` | TPO override > evidence value |
| TPO intent | `tpo_configuration` | keyed ledger; enabled/disabled/absent |
