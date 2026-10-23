# Coding Round Finish and Results Fix

## Reported problem

Candidates could not reliably finish a coding round. Clicking **Finish Round** could display a face-detection warning or fail to navigate to results. When proctoring terminated a test, the round could remain unfinished and its result page had no completed result to display.

## Root causes

1. **Proctoring stop endpoint returned HTTP 500.** The stop-event service passed a Python dictionary to `ProctoringEvent.event_metadata`, which maps to a text column. PostgreSQL could not adapt the dictionary (`can't adapt type 'dict'`).
2. **Finish flow stopped when proctoring stop failed.** The frontend awaited the stop request before calling the coding-round finish endpoint. The 500 therefore prevented round finalization.
3. **Proctoring termination did not reliably finalize the round.** The termination UI returned candidates to the dashboard instead of using the normal round-completion and result flow.
4. **Coding completion did not always persist a completion timestamp.** The round could be marked completed without setting `completed_at`.
5. **Warnings could cover the finish control.** The warning overlay occupied the same area as the coding header controls.

## Changes made

- Serialize proctoring metadata using the model's `metadata_dict` property before persistence.
- Return decoded JSON metadata from the proctoring-events endpoint.
- Make the coding finish handler stop monitoring, finalize the round, and then navigate to its round-specific result page.
- Route automatic proctoring termination and timer expiry through the same finish handler.
- Show a retryable error if finalization fails rather than silently leaving the candidate without results.
- Set `completed_at` when finalizing coding rounds, including rounds with no assigned problems.
- Keep warning overlays from intercepting clicks on the finish control.
- Add regression tests for proctoring metadata serialization and idempotent stop-event persistence.

## Result behavior

When a coding round finishes or is terminated:

1. Proctoring monitoring stops in the browser.
2. The backend marks the coding round completed and persists its score and completion time.
3. The frontend navigates to `/result/{sessionId}/{roundId}` when both identifiers are available. The legacy `/coding/result` route remains as a fallback.
4. If finalization fails, the page displays an error and allows the candidate to retry.

Scores reflect persisted submissions. A problem with no submission contributes zero to the round score.

## Files changed

- `app/services/proctoring_service.py`
- `app/modules/proctoring/routers/proctoring_router.py`
- `app/modules/coding/services/coding_service.py`
- `frontend/src/pages/CodingRoundV2.jsx`
- `frontend/src/components/coding/CodingHeader.jsx`
- `tests/test_proctoring_stop_service.py`

## Validation

- Frontend production build: passed.
- `git diff --check`: passed.
- The regression test file was added, but the available test runner did not discover or execute it in this environment; backend test execution remains unverified.

## Manual verification

1. Start a coding round and submit at least one solution.
2. Click **Finish Round**. Confirm the browser navigates to the round-specific result page and displays the persisted score.
3. Repeat with a proctoring termination. Confirm the round is finalized and results are shown.
4. Check backend logs to confirm the proctoring stop request no longer returns a 500 error.
