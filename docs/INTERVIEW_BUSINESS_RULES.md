# IntelliHire — Interview Business Rules (Round 3)

## Session Rules (duration, max questions, idempotency)
- Max questions per session: 10.
- Max duration: 30 minutes (1800 seconds) from `interview_sessions.start_time` to `end_time`.
- Sessions are resumable and idempotent: `session_token` saved in `interview_sessions`. A browser refresh resumes at `current_question_index`.
- Session status values: `IDLE`, `INITIALIZING`, `PERMISSION_CHECK`, `READY`, `QUESTION_ASKED`, `RECORDING`, `PROCESSING`, `EVALUATING`, `NEXT_QUESTION`, `COMPLETED`, `TERMINATED`.
- Session expiration (>30 minutes) triggers auto-termination and partial scoring persisted in `interview_evaluation` with `status='COMPLETED'` and `final_score` computed on available answers.

## Answer Mode Rules (voice vs text, switching rules)
- Candidate selects answer mode at start (`answer_mode` in `interview_sessions`): `voice` or `text`.
- Mode can be switched only under these conditions:
  - During permission check or BEFORE first question: free switch.
  - After the first question, switching from `voice`→`text` allowed if mic permission denied or STT timed out.
  - Switching from `text`→`voice` allowed only if mic permission granted and STT available.
- Any forced switch (mic denied, webcam denied) is logged to `interview_sessions` (field `answer_mode` updated and event stored).
- If voice is chosen but STT fails (>10s), fallback to text mode and log `is_skipped` or `fallback_to_text` in answer record.

## Adaptive Difficulty Rules (exact RL thresholds)
- RL State: 5-tuple string format "difficulty|correct_streak|wrong_streak|response_time_bin|topic_accuracy_bin".
- Actions: `increase`, `same`, `decrease`.
- Epsilon: start 0.30, min 0.05, decay 0.995 (stored in-memory; known limitation).
- Alpha = 0.1; Gamma = 0.9.
- Bellman update: Q(s,a) ← Q(s,a) + 0.1 * (r + 0.9 * maxQ(s′,a′) − Q(s,a)).
- Reward clamp: clamp reward to [-3.0, +3.0] before Q update.
- Difficulty multipliers applied when computing reward: easy×0.5, medium×1.0, hard×1.5.
- Time bonus modifier:
  - ratio < 0.4 → +0.5
  - ratio 0.4–0.7 → +0.2
  - ratio > 0.9 → −0.3
- Streak modifier:
  - correct_streak ≥ 3 → +0.3
  - wrong_streak ≥ 3 → −0.3
- Policy guard:
  - If wrong_streak ≥ 4 → force `decrease` action (override policy).
  - If correct_streak ≥ 5 → force `increase` action (override policy).
  - No "easy"→"hard" jump allowed (only via sequential increases through `medium`).
- Q-table default optimistic init: Q-value default = 0.1.
- Persistence: `rl_q_table` stores `user_id`, `state`, `action`, `q_value`, `visit_count`, `updated_at`. Epsilon is currently stored in-memory and may reset on server restart.

## Scoring Rules (weights, penalties, normalization)
- Weights:
  - Technical Accuracy: 40%
  - Communication: 20%
  - Confidence: 20%
  - Problem Solving: 20%
- Per-question LLM scores returned on scale 0–10. If LLM returns empty evaluation → default rubric scores 5/10 for each dimension.
- Per-question total = sum(dimension_score × dimension_weight).
- Session aggregate:
  - Average per-dimension across answered questions, then weighted sum.
  - Normalize final score to 0–100 scale (see INTERVIEW_SCORING_SYSTEM.md).
- Penalties:
  - Proctoring violation: −2 points per warning from final score (applied after normalization).
  - Auto-skipped question: −1 point per skip (applied after normalization).
- Duplicate submissions: idempotent — repeated submits for the same `question_id` return the same stored evaluation and scores.

## Proctoring Rules (warning triggers, termination)
- Warning triggers (each adds +1 to `warning_count` and logged into `proctoring_violations`):
  - Tab switch detected (Visibility API) → warning.
  - Webcam unavailable > 10 seconds → warning.
  - Multiple faces detected → warning.
  - Copy/paste attempt (Clipboard API write attempt during answer text focus) → warning.
- On reaching `warning_count` == 3 → immediate termination (save current answer, persist evaluation, set `status='TERMINATED'`).
- Proctoring events persisted to `proctoring_violations` with `warning_number` sequential per session.

## Termination Conditions (all cases that end a session)
- Normal completion: All 10 questions answered or `end` invoked by candidate → `COMPLETED`.
- Time limit exceeded (>30 minutes) → auto-terminate and mark as `COMPLETED` (partial).
- Proctoring warnings >=3 → `TERMINATED`.
- Session expired token or missing `interview_sessions` row during resume → return 404 and instruct redirect to login.
- Manual admin termination via internal endpoint (not public) → `TERMINATED`.
- Browser refresh with missing session token or corrupted `interview_sessions` row → return 404 and instruct re-authentication.

## Retry and Resume Rules
- Resume from last `current_question_index` with `session_token` or JWT-based session authentication.
- Duplicate GET /next-question requests are allowed (frontend React StrictMode guard recommended).
- On network drop during submit, backend will allow one retry after 3s; second failure returns 503 to frontend.
- Epsilon stored in memory resets on restart — recommended to persist in `rl_q_table` as `epsilon` column (documented known bug).

## Question Skip Rules
- Auto-skip triggered when no answer within 2 minutes → `is_skipped=true`, penalty −1 point.
- Candidate may manually invoke skip via POST /skip-question; counts as skip and applies penalty.
- Skips increment `current_question_index`, do not change `answer_mode`.

## AI Behavior Rules (what AI must and must not do)
Must:
- Produce JSON outputs strictly matching expected schemas (see INTERVIEW_API_CONTRACTS.md).
- Provide clear scoring breakdown and short human-readable feedback.
- Avoid hallucinated claims about candidate identity or external systems.
- Respect policy guards (no easy→hard jump).
- Use optimistic Q init and clamp reward per RL config.
Must not:
- Use PII without explicit consent.
- Attempt to infer non-assessed behavioral attributes (e.g., mental health).
- Expose system internals in candidate-facing feedback (no Q-values, RL internals).
- Change difficulty outside RL action set {increase, same, decrease}.
- Return unparsable text — any malformed LLM output triggers fallback to default rubric.
