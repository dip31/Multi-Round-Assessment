# IntelliHire — Edge Cases & Handling

For each scenario: Scenario, Detection, Frontend behavior, Backend behavior, Data impact, Recovery path.

1) Browser refresh mid-session → resume from last question
- Scenario: Candidate refreshes browser during interview.
- Detection: Frontend calls GET /session/{session_id}/status on load.
- Frontend behavior: Show "Resuming interview..." then call GET /next-question.
- Backend behavior: Validate `session_token`/JWT; return `current_question_index` and next question.
- Data impact: No data loss; session persisted; `last_activity_at` updated.
- Recovery: Resume; if `interview_sessions` missing → 404 and redirect to login.

2) STT timeout (>10s) → fallback to text input mode
- Scenario: Groq Whisper does not return in 10s.
- Detection: STT returns 504 or backend timeout callback at 10s.
- Frontend: Show "Transcription timed out — please type your answer", enable text input.
- Backend: Mark transcription log `stt_timeout=true`; do not evaluate automatic LLM evaluation; await text submission or mark skip if none.
- Data impact: No transcript saved; may incur `is_skipped` if no response.
- Recovery: Candidate types answer and submits; evaluation proceeds.

3) TTS failure → show text question, continue silently
- Scenario: Sarvam Bulbul TTS fails (503 or network error).
- Detection: POST /tts returns 5xx or timeout.
- Frontend: Display question text prominently with visual highlighting and continue.
- Backend: Log `tts_failure` in telemetry and provide `audio_url=null`.
- Data impact: No audio generated; question flow unaffected.
- Recovery: Candidate proceeds in text or voice without audio.

4) Groq API rate limit → queue request, show loading state
- Scenario: Groq returns 429.
- Detection: 429 response with `retry_after`.
- Frontend: Show "Queued for generation..." and poll GET /next-question/status.
- Backend: Enqueue generation, return 202 with `retry_after`. When done, deliver via GET /next-question.
- Data impact: Delay in question; no data loss.
- Recovery: Retry via queue; fallback bank used if retries exceed threshold.

5) Empty answer submitted → treat as skip, log is_skipped=true
- Scenario: Candidate submits empty text or audio with silence.
- Detection: answer_text empty or STT result empty.
- Frontend: Show "Empty answer treated as skip" toast.
- Backend: Create `interview_answers` with `is_skipped=true`, apply skip penalty −1.
- Data impact: Increases skip count.
- Recovery: Continue to next question.

6) Duplicate submit (double-click) → idempotent, return same result
- Scenario: User double-clicks Submit.
- Detection: `client_request_id` idempotency key used to deduplicate.
- Frontend: Disable submit button after first click; if network issues, use retry logic.
- Backend: If duplicate `client_request_id`, return existing record with 409 or 200 as configured.
- Data impact: No duplicate evaluations; visit_count unaffected.
- Recovery: Frontend shows stored result.

7) Network drop during submit → retry once after 3s, then show error
- Scenario: Loss of connectivity while submitting answer.
- Detection: frontend network error.
- Frontend: Retry once after 3s; if still failing, show "Network error — try again" and allow resume.
- Backend: If request arrives twice, idempotency used.
- Data impact: Potential delay; no data loss if retry succeeds.
- Recovery: Candidate resubmits or resumes after reconnection.

8) Session expired (>30min) → auto-terminate, save partial score
- Scenario: Session duration exceeds 30 minutes.
- Detection: compare now() - start_time > 1800s on any action.
- Frontend: Show "Session expired" and redirect to result page.
- Backend: POST /end called automatically; persist `interview_evaluation` with available answers.
- Data impact: Partial evaluation persisted.
- Recovery: Candidate must reapply or request new session.

9) Webcam permission denied → proceed in text-only + audio-only mode
- Scenario: User denies webcam.
- Detection: getUserMedia error.
- Frontend: Offer `text` mode or proceed in `voice` only (audio) if mic available; log event.
- Backend: Persist `answer_mode` change.
- Data impact: Proctoring reduced; note in audit logs.
- Recovery: Candidate continues; admin review may be required.

10) Mic permission denied → force text mode, log in session
- Scenario: User denies mic.
- Detection: getUserMedia permission error for audio.
- Frontend: Switch to text mode, inform user.
- Backend: Update `interview_sessions.answer_mode='text'`.
- Data impact: STT not used.
- Recovery: Candidate continues in text-only.

11) All 10 questions answered early → end session, trigger evaluation
- Scenario: Candidate finishes before time; `current_question_index` reaches 10.
- Detection: After last submit, backend checks index >=10.
- Frontend: Show "Interview completed — generating results..."
- Backend: Aggregate scores and write `interview_evaluation`.
- Data impact: Full evaluation persisted.
- Recovery: None needed.

12) warning_count reaches 3 mid-answer → save answer then terminate
- Scenario: Third warning occurs while answering.
- Detection: proctoring_event logged with warning_number==3.
- Frontend: Immediately POST /end after saving current state.
- Backend: Save current `interview_answers` (partial if necessary), then mark `TERMINATED`, persist `interview_evaluation`.
- Data impact: Partial answer saved; final_score computed on available answers.
- Recovery: Admin may review for appeal.

13) AI returns empty evaluation → use default rubric scores (5/10 each)
- Scenario: LLM response empty or unparsable.
- Detection: JSON parse failure or missing keys.
- Backend: Use default rubric (5/10 each), log error with stacktrace, continue RL update with default reward mapping.
- Data impact: Default scores persisted.
- Recovery: Operator investigates LLM logs; fallback enforced.

14) Question generation fails → pull from fallback question bank
- Scenario: LLM generation errors out or returns nonsense.
- Detection: LLM 5xx or invalid JSON.
- Backend: Select next question from local fallback bank, label `source='fallback'`, and continue.
- Data impact: `interview_questions` persisted with `question_text` from fallback.
- Recovery: Queue a background job to regenerate and reconcile if needed.

15) interview_sessions row missing on resume → return 404, redirect login
- Scenario: DB row deleted or inconsistent.
- Detection: GET /status returns no row.
- Frontend: Redirect to login and show message "Session not found. Please sign in."
- Backend: Return 404 and log incident for support.
