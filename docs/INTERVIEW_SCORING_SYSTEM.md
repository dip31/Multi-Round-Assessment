# IntelliHire — Interview Scoring System

## Score Dimensions (weights + what each measures)
- Technical Accuracy — 40%: correctness, depth, code, design tradeoffs.
- Communication — 20%: clarity, structure, conciseness.
- Confidence — 20%: tone, decisiveness, pacing.
- Problem Solving — 20%: approach, decomposition, edge case handling.

## Per-Question Scoring (LLM rubric for each dimension)
LLM returns numeric 0–10 and short feedback.
- Technical:
  - 9–10: Correct, efficient solution and edge cases handled.
  - 7–8: Mostly correct, minor gaps.
  - 4–6: Partial correctness or missing major cases.
  - 0–3: Incorrect or irrelevant.
- Communication:
  - 9–10: Structured, succinct, uses examples.
  - 7–8: Clear with minor filler.
  - 4–6: Rambling or unclear.
  - 0–3: Not communicative.
- Confidence:
  - 9–10: Firm, concise statements, appropriate hedging.
  - 7–8: Minor hesitation.
  - 4–6: Frequent uncertainty.
  - 0–3: Very unsure or contradicts self.
- Problem Solving:
  - 9–10: Breaks down problem, gives algorithmic rationale.
  - 7–8: Good approach with minor misses.
  - 4–6: Partial decomposition.
  - 0–3: No coherent approach.

If LLM returns empty evaluation: default each dimension = 5/10.

## Session Score Aggregation (average, weighted, normalized)
1. For each question compute weighted per-question total:
   per_question_total = technical*0.4 + communication*0.2 + confidence*0.2 + problem_solving*0.2  (score range 0–10)
2. Compute per-dimension averages across answered questions.
3. Compute aggregate_total = weighted sum of averaged dimensions (0–10).
4. Normalize to 0–100: final_raw_score = aggregate_total * 10.
5. Apply penalties: final_score = final_raw_score − penalty_points − skip_penalties.
6. Clamp final_score to [0,100].

## Penalty System (proctoring, skips — exact deductions)
- Each proctoring violation warning (logged in `proctoring_violations`) = +1 warning_count and −2 points from final_score.
- Each auto-skipped question (no answer in 2 minutes or explicit skip) = −1 point from final_score.
- Penalty_points field in `interview_evaluation` is sum of penalty deductions applied.

## Final Score Calculation Formula (step by step)
1. For N answered questions, compute avg_technical = mean(technical_i), etc.
2. aggregate_total = avg_technical*0.4 + avg_communication*0.2 + avg_confidence*0.2 + avg_problem_solving*0.2  (0–10)
3. final_raw_score = aggregate_total × 10  (0–100)
4. penalty_points = (warnings × 2) + (skips × 1)
5. final_score = final_raw_score − penalty_points
6. If final_score < 0 → final_score = 0; if >100 → final_score = 100
7. Persist into `interview_evaluation.final_score`.

Example:
- avg_technical=8.3, avg_comm=7.8, avg_conf=8.0, avg_ps=8.6
- aggregate_total = 8.3*0.4 + 7.8*0.2 + 8.0*0.2 + 8.6*0.2 = 8.18
- final_raw_score = 81.8
- warnings=1, skips=2 → penalty_points = 2 + 2 = 4
- final_score = 77.8

## Score → Grade Mapping (A/B/C/D/F bands)
- A: 90–100
- B: 80–89.99
- C: 70–79.99
- D: 60–69.99
- F: 0–59.99

## RL Reward Derivation from LLM Score
- Given per-question weighted total (0–10):
  reward_base = (per_question_total / 10) × difficulty_multiplier
  Apply time bonus (ratio defined by response_time_bin) and streak modifier (correct/wrong streak).
  Final reward = clamp(reward_base + time_bonus + streak_modifier, -3.0, +3.0)
- Example: per_question_total=8.0, difficulty=medium → reward_base=0.8; time_bonus=+0.2 → 1.0; clamp → 1.0.

## Score Normalization (0–100 scale)
- Aggregate_total (0–10) × 10 = 0–100
- After penalties and clamping, final_score stored in `interview_evaluation.final_score`.

See INTERVIEW_DATABASE_SCHEMA.md §Table Definitions for how scores are persisted in `interview_answers.scores` and `interview_evaluation`.
