# Aptitude Round

This file documents the intended aptitude round behavior and the current backend hook points.

## Current Backend State

- The aptitude router currently exists as a stub.
- The core session and schema groundwork already exists.
- `aptitude_questions`, `aptitude_attempts`, `rl_sessions`, and `aptitude_topics` are present in the database schema.

## Intended Flow

1. Session starts.
2. Aptitude round becomes active.
3. Frontend requests the next adaptive question.
4. Candidate submits an answer.
5. The system evaluates correctness and reward.
6. RL state is updated.
7. The next question difficulty is chosen.
8. Round completes when the maximum question count or completion rule is reached.

## RL Expectations

- State: difficulty, accuracy, response time, attempt history.
- Action: next difficulty selection.
- Reward: correctness and response speed.
- History: persist every attempt and RL step.

## Data Contract

- `aptitude_attempts` stores question-level results.
- `rl_sessions` stores adaptive decision history.
- `assessment_rounds.score` stores the round score.
