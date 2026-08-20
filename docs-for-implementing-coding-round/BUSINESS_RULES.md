# Business Rules

This file prevents the platform from drifting into inconsistent or imaginary behavior.

## Assessment Rules

- Candidate cannot skip rounds.
- Candidate cannot return to a previous round.
- Round timer cannot pause.
- Submission after timeout is rejected.
- Only authenticated users can start or resume an assessment session.
- One active assessment session per user is allowed.

## Aptitude Rules

- Questions are selected adaptively.
- Reinforcement learning controls the next difficulty.
- Each question attempt is recorded with attempt number, response time, and reward.
- Aptitude completion unlocks coding only if the configured score threshold is reached.

## Coding Rules

- Best submission counts for final score.
- Hidden test cases affect final score.
- Run Code does not persist a submission.
- Submit Code persists the submission.
- Only problems assigned to the session can be viewed or submitted.
- Mark-for-review is session-scoped.

## Interview Rules

- Max 10 questions.
- Max response time = 3 minutes per question.
- Difficulty adapts every 2 questions.
- Response transcripts must be stored for evaluation.
- Final interview report is generated only after the round completes.

## Proctoring Rules

- Browser tab switches are logged.
- Fullscreen exit is logged.
- Webcam state changes are logged.
- Violation severity affects escalation.
- High-severity repeated violations can terminate the session.

## Reporting Rules

- Final result must aggregate all completed rounds.
- Analytics must show both round scores and round status.
- Session reports should include proctoring metadata when available.
