# System Boundaries

This file is the anti-hallucination guardrail for agents.

## Coding Round Does Not

- Perform plagiarism detection.
- Perform AST analysis.
- Perform AI code review.
- Auto-fix submissions.
- Execute hidden static analysis beyond Judge0 execution results.

## Interview Does Not

- Perform real emotion detection.
- Perform real psychological analysis.
- Infer personality traits from raw voice alone.
- Make hiring decisions without the documented scoring logic.

## Aptitude Does Not

- Use free-form generative question creation as the default.
- Change session state outside the documented round lifecycle.
- Skip RL logging when adaptive mode is enabled.

## Proctoring Does Not

- Claim certainty about cheating from a single browser event.
- Replace human review for critical escalations.
- Store biometric data unless explicitly added to the system design.

## Platform Does Not

- Allow skipping ahead to later rounds.
- Allow previous-round re-entry after progression.
- Treat frontend navigation as the source of truth.
