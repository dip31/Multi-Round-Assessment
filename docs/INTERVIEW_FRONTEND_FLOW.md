# IntelliHire — Interview Frontend Flow

Frontend runs on port 5173 (React 18 + Vite). Base API proxy to backend `/api/v1/interview`.

## Screen Flow (every page/state with transitions)
- Landing → Start Screen:
  - Action: Click "Start Interview" → POST /start → enter `PERMISSION_CHECK`.
- Permission Check:
  - Requests webcam + mic; shows toggles; fallback options for text-only.
  - Transitions: success → READY; failure → show guidance and allow `text` mode.
- Ready Screen:
  - Displays role, time remaining, question preview button; click "Begin" → GET /next-question → `QUESTION_ASKED`.
- Interview Screen:
  - Shows question text, TTS play button, timer, answer input (text box or record button).
  - States: `QUESTION_ASKED` → on record start `RECORDING` → stop → `PROCESSING`.
- Processing → EVALUATING:
  - Spinner while STT + LLM evaluate.
- Next Question:
  - Shows short feedback and "Next" auto-triggered; transitions back to `QUESTION_ASKED` or to `COMPLETED`.
- Results Screen:
  - Summarizes scores and provides downloadable transcript and feedback.

## Permission Check Flow (webcam + mic + fallbacks)
1. Request `navigator.mediaDevices.getUserMedia({video:true, audio:true})`.
2. If denied for video:
   - Log `webcam_permission_denied` → set `answer_mode` to `text` or `voice` if audio available.
3. If denied for audio:
   - Force `text` mode, show banner "Mic not available — switching to text mode".
4. If both denied:
   - Allow text-only flow; log event to backend.

## Interview Screen Layout (component breakdown)
- `InterviewLayout`
  - `Header` (timer, question count)
  - `QuestionPanel` (question_text, category tag, difficulty badge)
  - `TtsPlayer` (play/pause, tts_audio_url)
  - `AnswerPanel`
     - `VoiceRecorder` (record, stop, waveform)
     - `TextInput` (fallback)
     - `SubmitButton` (disabled until recording processed or text provided)
  - `ProctoringOverlay` (warning banner, screenshot preview)
  - `Footer` (skip, end session)
- Each component connected to central `InterviewContext` for state sync.

## Timer Behavior (session-level, warning colors)
- Session-level countdown from start_time to max 30 minutes in header.
- Per-question timer from `time_limit` (default 120s):
  - >50% time remaining: green
  - 20–50%: amber
  - <20%: red + audible soft beep (if audio enabled)
- When no answer within 2 minutes → auto-skip (POST /skip-question) and show toast.

## Voice Recording Flow (start → capture → STT → display)
1. User presses `Record` → UI sets `RECORDING`.
2. Stop → upload to pre-signed storage, send `answer_audio_url` in POST /submit-answer.
3. Backend calls /stt; frontend displays "Transcribing..." and shows partial waveform and transcript when available.
4. If STT returns in <10s: show transcript for confirmation; user can edit before final submit.
5. If STT times out (>10s): fallback to text input with message "Transcription timed out — please type your answer".

## Answer Submission Flow (validation, loading, response)
- Validation:
  - Ensure `answer_text` length > 0 OR `answer_audio_url` present.
  - Prevent copy/paste in text answer (monitored; triggers proctoring event if detected).
- Submit:
  - POST /submit-answer with `client_request_id` for idempotency.
  - Show spinner; on 200 display scores and `ai_feedback`.
- Idempotency:
  - `client_request_id` used so duplicate clicks return stored result (409 returns same response).
- Error handling:
  - On 503 (LLM rate limit), UI shows "Queued for evaluation" and polls for result.

## Proctoring Overlay Behavior
- Always-on monitoring HUD minimized during recording.
- On first warning: yellow banner with message and counter.
- On second warning: orange banner, semi-opaque overlay, suggest corrective action.
- On third warning: red full-screen modal before termination with "Session terminating" and auto POST /end.

## Warning Banner Display Rules
- Banner displays event_type and `warning_number`.
- Each banner persists for 10 seconds unless higher-severity event triggers new banner.
- Overlay displays thumbnail screenshot if available.

## Results Screen Layout
- Top: Final score and grade (see INTERVIEW_SCORING_SYSTEM.md).
- Middle: Per-dimension bars (technical, communication, confidence, problem_solving) with numeric values.
- Bottom: Detailed per-question feedback with timestamps, transcripts, and audio playback links.
- Download: `Download detailed report` (JSON + CSV export).

## Mobile Responsiveness Rules
- UI adapts to single-column layout; question and answer panels stacked.
- Recording uses device audio API; on mobile, default to `voice` if available but allow text fallback.
- Ensure TTS playback works with mobile autoplay restrictions — user must tap to enable audio.

## Accessibility Requirements (WCAG 2.1 AA)
- All interactive elements keyboard-accessible.
- Provide visible focus indicators.
- All images and TTS audio have text alternatives (transcripts).
- Color contrast minimum 4.5:1.
- Provide ARIA labels for recording controls and timers.
- Keyboard shortcuts: Start/Stop recording (Space), Submit (Ctrl+Enter), Skip (S).
- Ensure screen reader compatibility for feedback and results.
