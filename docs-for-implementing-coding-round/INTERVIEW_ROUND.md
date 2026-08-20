# Interview Round

This document defines the intended interview round contract.

## Current Status

- The assessment session and round model already include `round_type = interview`.
- The backend does not yet expose a dedicated interview router implementation.
- Database support exists for `interview_sessions`.

## Intended Flow

1. Candidate reaches the interview round after coding passes the configured threshold.
2. The system generates the first interview question.
3. Candidate responds verbally or through the UI.
4. Transcript is stored.
5. Response is evaluated.
6. The next question is generated adaptively.
7. The round ends after the maximum question count or completion rule.
8. Final interview report is generated.

## Evaluation Dimensions

- Technical depth
- Communication clarity
- Problem solving
- Confidence and structure

## Data Contract

- `interview_sessions.transcript`
- `interview_sessions.behavioral_score`
- `interview_sessions.confidence_score`
- `interview_sessions.technical_score`
