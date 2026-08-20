# Frontend Flow

This document describes the intended page flow and component behavior so frontend agents do not invent new navigation patterns.

## Exact Page Flow

```text
/dashboard
  -> /assessment/aptitude
  -> /assessment/coding
  -> /assessment/interview
  -> /results
```

## Current App Routes

- `/` landing page
- `/login`
- `/register`
- `/dashboard`
- `/round/aptitude`
- `/round/aptitude/active`
- `/round/aptitude/result`
- `/round/coding`
- `/round/coding/active`
- `/round/coding/result`
- `/results`

## Navigation Rules

- Dashboard should start or resume the active assessment session.
- Aptitude must complete before coding unlocks.
- Coding must complete before interview unlocks.
- Results page should only be reachable after the final round or after an explicit end-state.
- No page should expose direct links to future rounds before their progression rule is satisfied.

## Component Behavior

### Dashboard

- Shows session state, current round, and next actionable step.
- Button states must reflect current round availability.
- Start, resume, and continue actions must be functional.

### Aptitude Round

- Load the next question automatically after an answer is submitted.
- Persist round state after each answer.
- Show immediate feedback and difficulty progression cues.
- Do not allow skipping questions or returning to already answered questions unless the product explicitly enables review.

### Coding Round

- Load assigned problems and highlight current selection.
- Run Code should execute visible cases only and keep the editor state.
- Submit Code should persist the submission and update the problem status.
- When timer ends:
  - disable the editor
  - auto-submit the latest code state if the product policy requires it
  - redirect to the result page or round summary page
- Mark-for-review state should be visible in the UI.

### Interview Round

- After each response, save transcript and evaluate the response.
- Generate the next question based on the current adaptive policy.
- Keep response timing visible to the candidate if product policy allows it.

### Results Page

- Display round-by-round scores.
- Show pass/fail outcome for each stage.
- Offer analytics summaries and a clear completion state.

## State Synchronization

- Frontend must poll session status while a timed round is active.
- Backend session state is the source of truth for timers and progression.
- UI must gracefully handle expired rounds and server-side validation failures.
