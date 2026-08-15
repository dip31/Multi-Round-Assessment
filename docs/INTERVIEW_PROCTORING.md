# IntelliHire — Proctoring Guide (Round 3)

## Monitored Events (types with detection method)
- `tab_switch`: detected via Page Visibility API (`visibilitychange` event).
- `webcam_unavailable` / `webcam_missing`: monitor video track availability via `MediaStreamTrack.readyState` and `oninactive` events. If unavailable >10s, log event.
- `multiple_faces`: detected by running face-detection model client-side (lightweight) and sending `face_count>1`.
- `copy_paste`: monitor `onpaste` and `copy` events in answer text area; clipboard `write` attempts also trigger.
- `webcam_permission_denied`: navigator.mediaDevices error handling.
- `microphone_permission_denied`: similar handling.
- All events are POSTed to `/api/v1/interview/session/{session_id}/proctoring-event`.

## Warning Escalation Rules
- Each event increments `warning_count` by 1 and logs a `proctoring_violations` row with `warning_number`.
- UI escalation:
  - 1 warning: yellow banner (informational).
  - 2 warnings: orange overlay (serious).
  - 3 warnings: red modal and immediate termination.
- On 3rd warning backend transitions `interview_sessions.status` to `TERMINATED` and returns termination response.

## Termination Trigger
- If `warning_number` for a session reaches 3:
  - Backend persists `TERMINATED` status and writes `interview_evaluation` with partial aggregates.
  - Save `interview_answers` up to last submission.
  - Return termination notice to frontend and stop question flow.

## Browser APIs Used
- Visibility API (`document.visibilityState`) — tab switches.
- Fullscreen API — optionally used to reduce distraction; failure doesn't cause warning.
- MediaDevices (`getUserMedia`) — webcam/mic availability and permission status.
- Clipboard API — detect unwanted clipboard writes/reads during answer entry.
- Page focus/blur — additional heuristics for suspicious behavior.

## Face Detection Approach
- Client-side lightweight model (e.g., MediaPipe or small TF.js cascade) runs periodically (every 5s) only when webcam enabled.
- If more than one face detected persistently >3 consecutive checks, POST `multiple_faces` with base64 thumbnail to backend.
- Avoid sending raw frames — only thumbnails for evidence; thumbnails stored in S3 with `screenshot_url` saved.

## Data Logged per Event (fields in proctoring_violations)
- `id`, `session_id`, `event_type`, `timestamp`, `screenshot_url` (nullable), `warning_number`.
- Backend enriches log with `user_agent`, `page_url`, and optional `video_segment_url` if recorded for audit.

## Frontend Behavior on Warning
- 1st warning:
  - Show yellow banner: "Attention: suspicious activity detected. This is warning 1 of 3."
- 2nd warning:
  - Show orange semi-opaque overlay, pause recording (if in RECORDING state), ask candidate to correct behavior.
- 3rd warning:
  - Red full-screen modal: "Session terminating due to repeated proctoring violations." Automatically POST /end and navigate to results/terminated screen.

## Admin View of Proctoring Report
- Admin UI (separate tool) shows:
  - Session timeline with proctoring events, thumbnails, and timestamps.
  - Warnings and final termination flags.
  - Exportable CSV (`session_id, event_type, timestamp, warning_number, screenshot_url`).
- Admin can mark false positives; UI allows toggle to override termination (admin action writes audit record).
