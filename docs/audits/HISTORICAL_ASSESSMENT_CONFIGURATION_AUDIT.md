# Historical Data, Assessment Blueprint and Mock Drive Configuration — Read-Only Audit (EDI5)

**Scope:** Read-only investigation of the historical-data / assessment-blueprint / mock-drive
configuration flow. Focused on reported Issues A–E. **No code, data, or configuration was
modified.** All findings are grounded in source references; runtime-only hypotheses are labelled.

**Audit date:** 2026-10-10
**Component under audit:** `frontend/src/components/CompanyPatternModal.jsx` and its backend
pipeline (`app/api/v1/company_data.py`, `app/services/company_data_service.py`,
`app/services/company_blueprint_service.py`, `app/services/mock_drive_service.py`).

---

## A. Executive Summary

The TPO "company assessment blueprint & historical foundation" flow has **two independent notions
of "the rounds"** that the UI presents side-by-side as if they were the same thing:

1. **Evidence-derived rounds** — a deterministic **union** of the rounds mentioned by *every*
   historical source for the company+role (manual entries, uploaded docs, pre-seeded benchmarks).
   Persisted in `company_patterns.pattern_data.assessment_rounds` / `round_patterns`.
2. **A local, editable checkbox panel** ("Assessment Rounds", backed by React state
   `historicalConfig`) that the TPO can toggle, which is **never persisted on its own** and is
   **merged into, never pruned from**, across loads.

"Standard Assessment Progression" renders **only** source (1). The checkbox panel renders source
(2). Because the two are not reconciled, they routinely disagree (Issue A/D). Round configuration
is not stored in a dedicated table — it is folded into `pattern_data.round_patterns` only when a
`POST /pattern/generate` request carries it, so **any recalculation that omits it silently discards
it** (Issues B/C). Checking a round that has no evidence fails server-side with HTTP 422, and
unchecking an evidence round is a no-op, so the panel's checkboxes give a false impression of
add/remove capability (Issues A/B/C/D). Finally, a round's provenance ("From evidence" vs "Added by
TPO") is a **per-round union flag**, not per-source attribution, and legacy provenance shown in the
UI is synthetic/display-only — so the badges cannot be trusted for source attribution (Issue E).

**Confirmed root causes: 5** (all five issues traced to concrete code paths; see §C).
**Shared causes across issues: 3** (see §C.6).
**Issues requiring runtime reproduction to fully confirm the exact user-recorded state:** the precise
per-source round contents and the exact `historicalConfig` staleness for `citi test manually` /
`data engineer` (no DB mutation was performed). Mechanism is confirmed in code; the specific
record state is inferred.

---

## B. Architecture and Data Flow

```
                          ┌──────────────────────────────────────────────────────────┐
                          │ CompanyPatternModal.jsx  (single TPO surface)             │
                          │                                                            │
  POST /historical ──────▶│ Tab "Log Past Drive"  (handleSaveManualRecord :590)       │
  POST /historical/upload▶│ Tab "Upload File"     (handleUploadFile :644)             │
  DELETE /historical/{id}▶│ Tab "Evidence Sources"(handleDeleteSource :684)           │
                          │                                                            │
                          │ Tab "Structured Pattern"                                  │
                          │   • Standard Assessment Progression  ← pattern.assessment_rounds (server)
                          │   • "Assessment Rounds" panel        ← historicalConfig (LOCAL state)
                          │   • Save Round Configuration (:972)  → handleConfigureHistoricalRounds (:334)
                          │   • Recalculate Pattern (:1098)      → handleGeneratePattern (:302)
                          │                                                            │
                          │ Tab "Assessment Blueprint" → /blueprint/*                  │
                          └───────────────┬──────────────────────────────────────────┘
                                          │
   POST /tpo/company-data/pattern/generate│        POST /tpo/company-data/blueprint/generate
                                          ▼                                          ▼
        ┌──────────────────────────────────────────┐        ┌─────────────────────────────────────┐
        │ company_data_service.generate_pattern     │        │ company_blueprint_service           │
        │  (:884)                                    │        │  .generate_blueprint_from_pattern   │
        │  1. _extract_pattern_from_sources (:1011)  │        │  (:124) requires pattern approved   │
        │       → UNION of all sources' rounds       │        │  _compute_blueprint_rounds (:384)   │
        │  2. _apply_added_rounds (:842)             │        │   rejects requires_tpo_config      │
        │  3. _apply_round_configuration (:731)      │        │   (422) if still unconfigured       │
        │  4. UPSERT CompanyPattern.pattern_data     │        └──────────────┬──────────────────────┘
        │     (REPLACES pattern_data wholesale)      │                       │
        └───────────────┬────────────────────────────┘                       ▼
                        │                                   company_blueprints.blueprint_data.rounds
                        ▼
        company_patterns.pattern_data                      POST /blueprint/{c}/{r}/approve
        { assessment_rounds, round_patterns, ... }                        │
                        │                                                  ▼
                        │                                   MockDrive attach (snapshot pinned)
                        │                                   mock_drives.blueprint_snapshot  (deep copy)
                        │                                   mock_drives.round_configurations (derived)
                        │                                   mock_drives.selected_rounds
                        ▼
        GET /pattern/{c}/{r}  →  TPO Mock Drives page / CompanyPatternModal
```

**Key data objects**

| Object | Where stored | Role |
|---|---|---|
| Raw historical source | `company_historical_data` (`raw_data.rounds`, `topics`, `round_patterns`, `difficulty`, ...) | Input evidence (append-only per source; delete removes one) |
| Derived pattern | `company_patterns.pattern_data` | UNION aggregation of all sources + applied TPO config |
| Blueprint | `company_blueprints.blueprint_data.rounds` | Approved, editable assessment spec |
| Mock drive snapshot | `mock_drives.blueprint_snapshot` | Pinned deep copy of the blueprint at attach time |

---

## C. Issue-by-Issue Findings

### C.1 Issue A — "Assessment Rounds" disagrees with "Standard Assessment Progression"

**Observed (reported):** Aptitude (20 Q / 23 min / Medium) and Technical (10 Q / 30 min / Hard)
checked; Coding unchecked. "Standard Assessment Progression" shows **only Coding**.

**Code locations**
- Progression reads the **server** pattern:
  `CompanyPatternModal.jsx:720` `patternRounds = patternData.assessment_rounds || []`;
  `:724` `progressionRounds = patternRounds.length > 0 ? patternRounds : driveRounds`;
  rendered `:1231-1274` from `patternData.round_patterns?.[rnd]`.
- Checkbox panel reads **local** state:
  `historicalConfig` (`:65`), prefill effect `:148-176`, rendered `:847-980`.
- Prefill **merges and never prunes** (`:154-175`): `next = { ...prev }` then only adds/updates
  entries for the current `assessmentRounds`. Rounds removed from the server pattern are **not**
  deleted from the panel.
- Save handler sends only *enabled* rounds: `:339-351`.
- Backend rejects configured rounds absent from evidence:
  `company_data_service.py:761-768` (`if rtype not in assessment_rounds: raise 422`).
- Nothing removes an evidence round from `assessment_rounds` short of deleting its source
  (`handleDeleteSource :684-693`); `_extract_pattern_from_sources` re-derives the union every time.

**Data flow / confirmed root cause**
Two structurally different data sources feed two adjacent UI regions. The paintable mismatch is
produced by a combination of:
1. **Stale local panel state** — the merge-without-prune prefill leaves rounds visible that are no
   longer in the evidence-derived `assessment_rounds`.
2. **422 on save** — configuring such a round (Aptitude/Technical not in evidence) fails; server
   unchanged, progression still shows only the evidence round (Coding).
3. **No removal path** — unchecking an evidence round changes nothing server-side.

**Evidence:** `:148-176`, `:720-724`, `:1231-1274`, `:339-351`, `company_data_service.py:731-768`,
`:1153-1157`.

**Uncertainty:** The exact stale set for the reported company/role depends on the recorded
`historicalConfig` at that moment (no runtime repro performed). The *mechanism* is confirmed.

**Recommended minimal fix (NOT implemented):** Reconcile the panel to the server pattern on every
load — replace `setHistoricalConfig(prev => ...)` with a prune that drops keys not in
`assessment_rounds` (or key the panel strictly off `assessment_rounds`). Separately, make the
save path surface 422 clearly and either auto-send unchosen-but-evidence rounds or route
non-evidence rounds through `added_rounds`.

---

### C.2 Issue B — "Save Round Configuration" does not persist

**Observed (reported):** Pressing **Save Round Configuration** appears to have no effect.

**Code locations**
- Handler: `CompanyPatternModal.jsx:334-397` → `POST /tpo/company-data/pattern/generate` with
  `added_rounds` + `round_configuration` (`:364-369`).
- Endpoint: `app/api/v1/company_data.py:174-206`.
- Service: `company_data_service.generate_pattern:884`; apply order
  `_extract_pattern_from_sources` → `_apply_added_rounds` (`:939-940`) → `_apply_round_configuration`
  (`:941-942`); then **wholesale replace** `existing.pattern_data = pattern_data` (`:991`).
- Validation that can 422: `_apply_round_configuration:761-768` (round not in evidence),
  `:770-783` (missing `question_count` / `duration_minutes` / `difficulty_distribution`),
  `:817-826` (topic not evidence-backed for the round).
- Screens that can silently wipe config: **"Recalculate Pattern"** button `:1097-1105` →
  `handleGeneratePattern:302-332` sends **no** `round_configuration` and **no** `added_rounds`.

**Data flow / confirmed root cause**
Round configuration has **no dedicated storage**. It only exists inside
`company_patterns.pattern_data.round_patterns`, and only if it is passed in the same
`/pattern/generate` call. Consequences:
1. Any configured round that is not in the evidence union (or `added_rounds`) → **HTTP 422**, the
   whole save is rejected, nothing persists.
2. Any later "Recalculate Pattern" (no config args) rebuilds `pattern_data` from evidence and
   **overwrites** the saved configuration.
3. The panel's checkbox state is not the persisted source of truth, so "save" reforms a value the
   server may reject or later overwrite.

**Evidence:** `:334-397`, `:302-332`, `:1097-1105`, `company_data_service.py:731-783`, `:938-942`,
`:983-1008`, `schemas/company_data.py:48-129`.

**Uncertainty:** Whether the user's specific save failed with 422 (round not in evidence) vs. was
later overwritten by a recalculation — both paths exist and are confirmed; the exact trigger for
the reported event needs the record's history.

**Recommended minimal fix (NOT implemented):** Persist TPO round configuration independently of the
pattern (e.g. a `round_configuration` set on `CompanyPattern`/`CompanyBlueprint`), and make
`generate_pattern` **preserve** existing TPO configuration/added rounds when no explicit config is
supplied instead of dropping them. Surface the 422 detail to the user.

---

### C.3 Issue C — TPO-added rounds do not update progression/config

**Observed (reported):** Rounds the TPO adds do not appear in (or survive in) the pattern/progression.

**Code locations**
- Add UI: `handleAddAssessmentRound:820-840` (`addedRounds`, `historicalConfig[key].round_origin='tpo_added'`),
  button `:946-970`.
- `addedRounds` re-derived only from `round_origin === 'tpo_added'` on each pattern load (`:151-153`).
- Save blocks unless **every** enabled round is fully configured: `:352-361`.
- Backend apply: `_apply_added_rounds:842-881` (append to `assessment_rounds`, tag `tpo_added`,
  mark `requires_tpo_configuration`); applied **before** `_apply_round_configuration` (`:939-942`).
- Recalculate omits `added_rounds`: `handleGeneratePattern:309-313`.
- Blueprint generation rejects still-unconfigured rounds:
  `company_blueprint_service.py:425` + `:436-491`.

**Data flow / confirmed root cause**
An added round only persists inside `pattern_data` when it is submitted **in the same request**
that adds it (`added_rounds`) and is also fully configured. Because:
- the frontend blocks the save entirely until the new round has count/duration/difficulty (`:352-361`), and
- a subsequent "Recalculate Pattern" (`:1097-1105`) rebuilds the union **without** `added_rounds`,
the added round is dropped server-side; the panel then also drops it (its `addedRounds` re-derives
from `round_origin`, now absent). Any added round that survives but remains
`requires_tpo_configuration` also blocks blueprint generation.

**Evidence:** `:820-840`, `:946-970`, `:151-153`, `:352-361`, `:1097-1105`,
`company_data_service.py:842-881`, `company_blueprint_service.py:384-514`.

**Uncertainty:** None material — the drop-on-recalculate path is deterministic in code.

**Recommended minimal fix (NOT implemented):** Persist `added_rounds`/`round_origin` independently
so recalculation does not erase them, or make `generate_pattern` carry forward existing
`tpo_added` rounds. Allow adding a round without forcing immediate full configuration, while still
blocking only *blueprint generation*.

---

### C.4 Issue D — Manual historical-drive selections are inconsistent / overwritten

**Observed (reported):** Company `citi test manually`, role `data engineer`. Manual drive selected
Aptitude + Coding (Technical/HR unselected). A historical document indicated Coding; Aptitude was
selected later by the TPO. Result: "Assessment Rounds" shows **Aptitude selected, Coding
unselected, Technical added by TPO**.

**Code locations**
- Manual form default `rounds: ['aptitude','coding']` (`:87`); manual save
  `handleSaveManualRecord:590-641` → `POST /historical` then `loadCompanyData` (no regeneration).
- `add_manual_historical_data` (`company_data_service.py:217-246`) always **inserts** a new source;
  it never replaces or supersedes other sources.
- Aggregation is a **union**: `_extract_pattern_from_sources:1033-1059` accumulates
  `round_sources_map`; `:1153-1157` `ordered_rounds = [r for r in round_order if len(round_sources_map[r])>0]`.
  A later source can **add** a round but can never **remove** one contributed by another source.
- Panel "selected" state is `historicalConfig[rnd].enabled` (`:867-868`), independent of evidence
  and not persisted; the prefill sets `enabled: true` for every round in `assessment_rounds`
  (`:163`).
- TPO-added Technical persists only through the same-request `added_rounds` path (see C.3).

**Data flow / confirmed root cause**
Historical rounds are an **additive union**, not an override. Saving a manual drive does **not**
regenerate the pattern (it only inserts a source and reloads), so an existing document's rounds
stay until a recalculation merges them in. What the user reads as "Aptitude selected / Coding
unselected" is the **local panel flag**, which is decoupled from the evidence union (Issue A
mechanism) and from persistence. Therefore:
- The manual drive's Aptitude+Coding and the document's Coding **merge** to `{aptitude, coding}`
  (both would be present once recalculated).
- Any apparent "Coding unselected" is a local checkbox state, not a server removal.
- "Technical added by TPO" is the separate `added_rounds` mechanism.

**Evidence:** `:87`, `:590-641`, `company_data_service.py:217-246`, `:1033-1059`, `:1153-1157`,
`:867-868`, `:163`.

**Uncertainty:** The exact saved `raw_data.rounds` for each of the reported user's sources (manual
vs document vs benchmark) is inferred from the report; it was not read from the DB (read-only, no
mutation).

**Recommended minimal fix (NOT implemented):** Decide and document the product rule for
"later manual selection vs earlier document": the code currently implements **union**; if the
intent is override, a precedence model must be added. Independently, decouple the panel checkboxes
from round membership (see A/B) so "selected" reflects real persisted state.

---

### C.5 Issue E — Source attribution is unclear / badges cannot be trusted

**Observed (reported):** Cannot tell whether a round came from evidence or was TPO-added; badges
such as "From evidence" / "Added by TPO" should not be trusted.

**Code locations**
- Badge in panel: `:871-873` `isEvidenceRound = cfg.round_origin === 'evidence'` → `'From evidence'`
  else `'Added by TPO'`.
- Badge in progression: `:1238`, `:1254-1256` same `round_origin` logic.
- `round_origin` is set during extraction for **every** round seen in **any** source:
  `company_data_service.py:1255` `rp["round_origin"] = "evidence"` (per union round); added rounds
  set `tpo_added` only if not already evidence: `:876-877` (`if rp.get("round_origin") != "evidence"`).
- Legacy provenance shown in the UI is **synthetic and display-only**:
  `addDisplayOnlyLegacyProvenance:20-43` builds a `source_provenance` object only when the record
  lacks one, marks it `legacy_display_only: true` (`:39`), and is applied **only in the React
  component** (`:217-222`, `:232-237`) — it is never persisted.
- Per-source round data **does exist** in `sources_summary[].rounds_found`
  (`:1142-1150`, `:1148`) but is not used for attribution in the panel or progression.

**Data flow / confirmed root cause**
`round_origin` is a **per-round union flag**, not per-source attribution: a round present in *any*
source (manual, uploaded, or pre-seeded benchmark) is labelled "evidence" and the specific
contributing source is not surfaced. Added rounds are only "TPO-added" while no source evidences
them; once any source mentions the round, it silently flips to "evidence". Legacy display-only
provenance is fabricated client-side and must not be treated as authoritative.

**Evidence:** `:871-873`, `:1238-1256`, `:20-43`, `:217-222`, `:232-237`,
`company_data_service.py:1142-1150`, `:1255`, `:876-877`.

**Uncertainty:** None material.

**Recommended minimal fix (NOT implemented):** Surface per-source attribution from the existing
`sources_summary[].rounds_found` (and the raw evidence) instead of inferring from `round_origin`.
Persist any provenance that the UI claims, and clearly mark legacy/derived provenance as
non-authoritative.

---

### C.6 Shared causes (cross-issue)

1. **No independent persistence for TPO configuration / added rounds.** They live only inside
   `pattern_data`, which is wholly rebuilt on every `generate_pattern`. → Issues B, C (and D via
   recalculation).
2. **Two unsynchronized round sources in the UI** (server `assessment_rounds` vs local
   `historicalConfig`; merge-without-prune prefill; checkboxes that neither add nor remove). →
   Issues A, B, D, E.
3. **Union-only aggregation with no precedence/override rule.** Historical rounds can only be
   added, never removed/overridden by a later source. → Issues A, D (and the surprising
   "selected but not shown" behaviour).

---

## D. Source-of-Truth Matrix

| Value | Original source | Persisted location | API / read path | UI consumer | Can be overwritten by recalculation? |
|---|---|---|---|---|---|
| Raw rounds per source | TPO manual entry / file extraction / EDI5 seed | `company_historical_data.raw_data.rounds` | `GET /tpo/company-data/historical` | Evidence Sources tab (`:1828-1832`) | No (append-only; only explicit delete removes one) |
| Derived rounds (union) | Computed from all sources' `raw_data.rounds` | `company_patterns.pattern_data.assessment_rounds` | `GET /pattern/{c}/{r}` | Standard Assessment Progression (`:724`, `:1232`) | **Yes** — rebuilt every `generate_pattern` |
| Per-round evidence aggregates | Computed extraction averages/focus | `pattern_data.round_patterns[round].{avg_question_count,avg_duration_minutes,focus_areas,difficulty_distribution,sources_count}` | `GET /pattern/{c}/{r}` | Progression cards; panel prefill | **Yes** — rebuilt every `generate_pattern` |
| Round origin (`evidence`/`tpo_added`) | Extraction / `_apply_added_rounds` | `pattern_data.round_patterns[round].round_origin` | `GET /pattern/{c}/{r}` | "From evidence"/"Added by TPO" badges (`:872`, `:1255`) | **Yes** — recomputed each generation |
| TPO round configuration (counts/duration/difficulty/topics) | TPO panel → `round_configuration` on `POST /pattern/generate` | **Only** `pattern_data.round_patterns[round].{question_count,duration_minutes,difficulty_distribution,focus_areas}` (no dedicated column) | `GET /pattern/{c}/{r}` | Panel + progression | **Yes** — lost unless resubmitted with the same request |
| TPO-added rounds | `added_rounds` on `POST /pattern/generate` | `pattern_data.assessment_rounds` + `round_patterns[round].round_origin='tpo_added'` | `GET /pattern/{c}/{r}` | Panel + progression | **Yes** — lost unless resubmitted |
| Panel checkbox/value state | Local React state `historicalConfig` | **Not persisted** | n/a | "Assessment Rounds" panel | Re-merged each load; never pruned (stale retained) |
| Pattern review status | TPO approve/flag | `pattern_data.review_status` (+ `reviewed_by`, `reviewed_at`) | `GET /pattern/{c}/{r}` | TPO Verification Status (`:1352-1381`) | Preserved on regen **only** if already `approved` and not fallback (`:986-989`) |
| Blueprint rounds | `generate_blueprint_from_pattern` from approved pattern | `company_blueprints.blueprint_data.rounds` | `GET /blueprint/{c}/{r}` | Blueprint tab; TPO Mock Drives page | Recalculated separately; existing replaced (competencies preserved), status reset to `draft` (`:284-298`) |
| Blueprint snapshot | Deep copy at drive attach | `mock_drives.blueprint_snapshot` | `create_mock_drive` / `get_drive_blueprint_snapshot` | Runtime assessment | **No** — pinned; live blueprint changes do not alter existing drives (re-snapshot only on `update_mock_drive` blueprint/identity change) |
| Drive round config cache | Derived from pinned snapshot | `mock_drives.round_configurations` | `_round_configurations_from_snapshot:111-153` | Runtime | No (derived, server-side; client input ignored when blueprint attached) |
| Drive enabled rounds | Drive payload / blueprint rounds | `mock_drives.selected_rounds` | `_enabled_rounds_in_order:461-503` | Runtime progression | No |
| Legacy provenance (display) | Fabricated client-side | **Not persisted** (`legacy_display_only`) | n/a | Badges/labels | n/a (recomputed in render) |

---

## E. Save Operation Trace

| UI action | Handler (file:line) | HTTP | Service | Persists to | Regenerates pattern? |
|---|---|---|---|---|---|
| Log Past Drive → **Save Historical Drive** | `CompanyPatternModal.jsx:590` | `POST /historical` | `add_manual_historical_data` (`company_data_service.py:217`) | `company_historical_data` (insert) | **No** (only reloads) |
| Upload File → **Upload & Extract** | `:644` | `POST /historical/upload` | `add_file_historical_data` (`:249`) + `_extract_from_file` (`:304`) | `company_historical_data` (insert) | **No** |
| Evidence Sources → **Delete** | `:684` | `DELETE /historical/{id}` | `delete_historical_data` (`:702`) | removes one source | **No** |
| **Save Round Configuration** | `:334` | `POST /pattern/generate` (`added_rounds` + `round_configuration`) | `generate_pattern` (`:884`) → `_extract_pattern_from_sources` → `_apply_added_rounds` → `_apply_round_configuration` | upserts `company_patterns.pattern_data` (**replaces**) | **Yes** |
| **Recalculate Pattern** (top-right) | `:302` | `POST /pattern/generate` (**no** config args) | `generate_pattern` | upserts `company_patterns.pattern_data` (**replaces, wiping config/added**) | **Yes** |
| **Generate/Recalculate Blueprint** | `:464` | `POST /blueprint/generate` | `generate_blueprint_from_pattern` (`company_blueprint_service.py:124`) | `company_blueprints` | n/a (recomputes blueprint) |
| **Approve Blueprint** | `:534` | `POST /blueprint/{c}/{r}/approve` | `approve_blueprint` (`:715`) | `company_blueprints.status` | n/a |

Note the asymmetry: **ingest** actions (`/historical`, upload, delete) never regenerate the pattern;
only the explicit `/pattern/generate` calls do — and one of those (Recalculate) discards TPO config.

---

## F. Recalculation / Overwrite Analysis

- **`generate_pattern` always rebuilds `pattern_data` from scratch** via
  `_extract_pattern_from_sources` (`company_data_service.py:938`), then optionally re-applies
  `added_rounds` (`:939-940`) and `round_configuration` (`:941-942`), then **replaces**
  `existing.pattern_data` (`:991`). Anything not passed in *that* request is lost.
- **Only two fields survive** a regenerate: `review_status` (when already `approved` and not a
  fallback — `:986-989`). No round configuration or added rounds survive.
- **Ingest does not auto-regenerate**, so progression can lag behind newly saved evidence until a
  manual recalculation — and that recalculation is the very action that drops prior TPO config.
- **Blueprint recalculation** (`company_blueprint_service.py:289-298`) replaces `rounds` and resets
  status to `draft`, preserving only TPO-authored `competencies` (`:284-287`).
- **Mock drives are protected**: `blueprint_snapshot` is pinned (`assessment_blueprint_service.py:15-23`,
  `mock_drive_service.py:190/213`) and `get_drive_blueprint_snapshot:26-68` refuses to substitute a
  newer live blueprint. Existing drives therefore do **not** change when the live blueprint changes.

---

## G. Minimal Remediation Plan (dependency order — NOT implemented)

1. **Introduce durable storage for TPO round configuration and added rounds** (independent of
   `pattern_data`), or make `generate_pattern` preserve existing `round_patterns`/
   TPO-added rounds when no explicit config is supplied. *(Unblocks B, C; reduces D.)*
2. **Reconcile the UI panel to the server pattern** (prune stale `historicalConfig` keys; drive
   checkboxes strictly from persisted state). *(Fixes A, D display; clarifies E.)*
3. **Define and document the precedence rule** for "later manual selection vs earlier document"
   (union today). Implement it explicitly if override is intended. *(Fixes D semantics.)*
4. **Surface real per-source attribution** from `sources_summary[].rounds_found` / raw evidence and
   stop presenting synthetic legacy provenance as authoritative. *(Fixes E.)*
5. **Harden UX for 422s** from `_apply_round_configuration` (clear message; route non-evidence
   rounds through `added_rounds`). *(Reduces A/B confusion.)*

Dependencies: 1 should precede 2–3 (persistence defines what the UI can show). 4 and 5 are
independent.

---

## H. Verification Plan (post-fix, when authorized)

- **Unit/API (backend):**
  - `generate_pattern` **without** `round_configuration`/`added_rounds` preserves prior TPO config
    and TPO-added rounds (regression tests).
  - Configuring a round absent from evidence remains rejected (422) and the message is surfaced.
  - `added_rounds` survives a subsequent recalculation.
- **Frontend (component):**
  - Load a pattern whose evidence rounds changed between fetches → panel prunes stale rounds and
    matches "Standard Assessment Progression".
  - Check/uncheck behaviour produces persisted state consistent with the server response.
- **End-to-end (read-only repro first, then fix verification):**
  - Reproduce `citi test manually` / `data engineer`: capture each source's `raw_data.rounds`, the
    resulting `assessment_rounds`, and the panel state; confirm the union + staleness mechanisms.
  - Confirm mock-drive snapshots remain unchanged when the live blueprint is regenerated (existing
    Phase 4C tests: `tests/test_mock_drive_blueprint_integration.py`,
    `tests/test_mock_drive_security_isolation.py`).
- **Guardrails:** existing suites for company data, blueprint generation, and mock drives must stay
  green; no competency/scoring changes in scope.

---

## Appendix — Primary Code References

- `frontend/src/components/CompanyPatternModal.jsx` — panel state `:65-70`; prefill `:148-176`;
  load `:193-259`; save config `:334-397`; recalculate `:302-332`; manual `:590-641`; upload
  `:644-681`; delete `:684-693`; progression `:720-724`, `:1231-1274`; panel `:811-980`;
  manual/upload forms `:1858-2068`; provenance shim `:20-43`.
- `app/services/company_data_service.py` — `add_manual_historical_data:217`; `add_file_historical_data:249`;
  `_apply_round_configuration:731`; `_apply_added_rounds:842`; `generate_pattern:884`;
  `_extract_pattern_from_sources:1011`; `review_pattern:1334`.
- `app/api/v1/company_data.py` — `POST /historical:78`; `POST /historical/upload:97`;
  `POST /pattern/generate:174`; `POST /blueprint/generate:299`; approve `:384`.
- `app/services/company_blueprint_service.py` — `generate_blueprint_from_pattern:124`;
  `_compute_blueprint_rounds:384`; `update_blueprint:649`; `approve_blueprint:715`.
- `app/services/assessment_blueprint_service.py` — snapshot + round-config readers `:15-214`.
- `app/services/mock_drive_service.py` — attach/snapshot `:66-219`; derived configs `:111-153`;
  `_enabled_rounds_in_order:461-503`.
- `app/schemas/company_data.py` — `TpoRoundConfiguration:48`; `GeneratePatternRequest:107`.
- `app/models/company_data.py` — `CompanyHistoricalData:27`; `CompanyPattern:100`; `CompanyBlueprint:149`.
