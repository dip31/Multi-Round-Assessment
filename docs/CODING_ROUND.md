# Coding Round

This document explains how the coding round is implemented in the current backend.

## Core Flow

1. Candidate starts or restarts the coding round.
2. Backend finds the active assessment session and the coding `AssessmentRound`.
3. Random problems are assigned to the session.
4. Candidate requests assigned problems and problem details.
5. Candidate runs code on visible test cases.
6. Candidate submits code on all test cases.
7. Backend evaluates the submission synchronously through Judge0.
8. Submission is stored in `coding_submissions`.
9. Final round result is calculated from best submissions per problem.

## Implementation Surface

- Router: [app/modules/coding/routers/coding_router.py](../app/modules/coding/routers/coding_router.py)
- Session logic: [app/modules/coding/services/session_service.py](../app/modules/coding/services/session_service.py)
- Coding logic: [app/modules/coding/services/coding_service.py](../app/modules/coding/services/coding_service.py)
- Evaluator: [app/modules/coding/utils/code_evaluator.py](../app/modules/coding/utils/code_evaluator.py)
- Judge0 client: [app/modules/coding/utils/judge0_client.py](../app/modules/coding/utils/judge0_client.py)

## Problem Assignment

- `start_coding_round` randomly selects `CODING_ROUND_PROBLEMS_COUNT` rows from `coding_problems`.
- Assigned problems are stored in `session_problems`.
- Each assignment includes `problem_order` and `marked_for_review`.

## Run Code Behavior

- Evaluates visible test cases only.
- Does not persist a submission.
- Returns per-test output comparison results.

## Submit Code Behavior

- Evaluates both visible and hidden test cases.
- Creates a `coding_submissions` row.
- Returns synchronous verdict, score, pass counts, and resource metrics.

## Scoring

- Per-submission score is a test-case pass ratio.
- Final round score uses the best submission score for each assigned problem.
- Hidden test cases matter for the final verdict and score.

## Timer Behavior

- Round duration is controlled by `CODING_ROUND_TIME_LIMIT_MINUTES`.
- The round auto-expires when the current time passes `end_time`.
- Submission after expiry is rejected.
