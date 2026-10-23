# EDI5 — Full Transcript Architecture Audit

## 1. Executive Summary

This architecture audit analyzes the current state of transcript capability within the EDI5 interview system. The EDI5 implementation currently utilizes Retell for audio processing and real-time interaction (WebRTC, STT, TTS), while the EDI5 backend handles core interview logic via `InterviewOrchestrator` and `retell_llm_websocket.py`.

The primary issue is that while the frontend receives and displays real-time transcript events via Retell's SDK, and the backend captures transcripts in a generalized `InterviewMessage` table, the system lacks the structural mapping to associate conversation utterances with specific `InterviewTurn` (Question/Answer pairs). Consequently, the final question-wise analysis cannot reliably map expected answers, candidate responses, and missing concepts. The transcript data flow is incomplete between real-time processing and persistent structured analysis.

## 2. Current Interview Architecture

**Components & Roles:**
*   **Frontend (`RetellInterviewRoom.jsx`)**: Connects to Retell via WebRTC using `retell-client-js-sdk` and renders realtime speech updates.
*   **Backend Websocket (`retell_llm_websocket.py`)**: Intercepts LLM WebSocket connections from Retell, receiving `update_only` (transcript) and `response_required` (turn completion) events.
*   **Backend Logic (`interview_orchestrator.py`)**: Manages the flow of questions. Evaluates `last_user_transcript` using a mock `SubmitResponseRequest` to determine next steps.
*   **Database (`models/interview.py`)**: Defines `InterviewSession`, `InterviewTurn`, `InterviewConversation`, and `InterviewMessage`.

**Mismatch:** Retell controls the conversational turn boundaries, but EDI5 orchestrates the logical question boundaries. The current state connects them loosely, but fails to capture complete, mapped transcripts for analysis.

## 3. End-to-End Transcript Flow

```text
Candidate starts interview
        ↓
Interview session created (/interview/session/start)
        ↓
AI interviewer initialized (Retell Web Call created)
        ↓
AI generates question (via Orchestrator)
        ↓
AI speaks question (Retell TTS via websocket response)
        ↓
Candidate hears question (WebRTC)
        ↓
Candidate speaks answer (WebRTC)
        ↓
Candidate audio reaches backend/provider (Retell)
        ↓
Speech-to-text/transcription occurs (Retell STT)
        ↓
Candidate transcript generated (Retell event)
        ↓
Transcript sent/stored somewhere (Sent to Frontend via WebRTC, sent to Backend WS as `update_only`)
        ↓
AI analyzes candidate response (Orchestrator evaluates `last_user_transcript`)
        ↓
Follow-up question generated (Orchestrator decides `FOLLOWUP`)
        ↓
AI speaks follow-up
        ↓
...
        ↓
Interview ends (Orchestrator returns `COMPLETE`)
        ↓
Final transcript assembled
        ↓ MISSING (Current DB captures messages without turn association)
Conversation analyzed
        ↓ MISSING (Analysis logic operates on fragments or is incomplete)
Question-wise analysis generated
        ↓ MISSING
Interview result stored
        ↓ PARTIAL (Scores stored, but mapped transcripts are missing)
Frontend retrieves/display results
        ↓ PARTIAL (UI shows result, but transcript view is lacking)
```

## 4. AI Speech Flow

*   **Generation:** `InterviewOrchestrator` generates the text based on current state (via `groq_service.rephrase_question`).
*   **Audio Generation/Streaming:** The backend sends a JSON response to Retell's LLM WebSocket. Retell generates TTS and streams it to the frontend via WebRTC.
*   **Events/Storage:** Retell streams back `update_only` events for the AI's speech. The backend (`_persist_structured_transcript` logic) attempts to save this to `InterviewMessage`, but without associating it strongly with the current question (`turn_id` is missing).

## 5. Candidate Speech Flow

*   **Capture/Stream:** Frontend microphone audio is streamed directly to Retell via WebRTC.
*   **STT:** Handled entirely by Retell.
*   **Transcript Generation:** Retell fires `update_only` WebSocket events to the backend, and `update` events to the frontend SDK.
*   **Storage:** Backend WS handler captures the `last_user_transcript` string for immediate orchestrator use, and saves utterances to `InterviewMessage`. It does *not* link them to a specific `turn_id` or aggregate them safely.

## 6. Retell Integration

The integration primarily uses the **Custom LLM WebSocket** approach.

| Event | Received? | Where? | Stored? | Sent to frontend? |
|---|---|---|---|---|
| AI speaking | Yes | WS `update_only` | Yes (`InterviewMessage` - unmapped) | Yes (WebRTC `update` event) |
| AI transcript | Yes | WS `update_only` | Yes (`InterviewMessage` - unmapped) | Yes (WebRTC `update` event) |
| Candidate speaking | Yes | WS `update_only` | Yes (`InterviewMessage` - unmapped) | Yes (WebRTC `update` event) |
| Candidate transcript | Yes | WS `update_only` | Yes (`InterviewMessage` - unmapped) | Yes (WebRTC `update` event) |
| Final transcript | Yes | Webhook `call_analyzed` | No (Webhook logic incomplete/unmapped) | No |
| Call ended | Yes | Webhook `call_analyzed` / WS | Yes (Status updated) | Yes (WebRTC close) |

## 7. WebSocket / Real-Time Flow

```text
Frontend (Retell SDK)
   ↓ (WebRTC - Audio)
Retell Server
   ↓ (WebSocket - JSON Events)
Backend (`retell_llm_websocket.py`)
   ↓
Orchestrator
```

*   **Frontend ↔ Retell:** Real-time STT/TTS. Frontend receives `update` events and renders `liveTranscript`.
*   **Retell ↔ Backend:** Backend receives `update_only` (transcript) and `response_required` (turn boundary).
*   **Synchronization Issues:** The frontend `liveTranscript` is ephemeral React state. It is lost on refresh. The backend transcript storage (`InterviewMessage`) is disconnected from the logical interview state, leading to data fragmentation.

## 8. Database Persistence

*   **Table/model:** `InterviewSession` (Tracks session state)
*   **Table/model:** `InterviewTurn` (Evaluated turn: Question + Score)
*   **Table/model:** `InterviewMessage` (Utterances)
    *   **Purpose:** Store transcript utterances.
    *   **Primary key:** `id`
    *   **Interview/session relationship:** `conversation_id` -> `InterviewConversation`
    *   **Question relationship:** `turn_id` (Exists in schema, but **NEVER POPULATED**).
    *   **Speaker information:** `speaker` column.
    *   **Message/transcript storage:** `text` column.
    *   **Timestamp:** Yes.

The database stores individual conversation turns, but because `turn_id` is missing from `InterviewMessage`, they cannot be reliably grouped back into a complete Answer for a specific Question.

## 9. Frontend Transcript Flow

```text
Backend transcript event -> MISSING (No direct backend-to-frontend event for transcript)
        ↓
API/WebSocket
        ↓
Frontend event handler -> (Frontend listens to Retell SDK `update` directly)
        ↓
React state -> `liveTranscript`
        ↓
Transcript component -> Rendered in `RetellInterviewRoom.jsx`
```

*   The frontend transcript is live, but ephemeral. If the user refreshes, it vanishes because there is no API endpoint to re-hydrate the transcript from the backend.

## 10. Interview Completion Flow

```text
Candidate clicks End (or AI determines End)
        ↓
Frontend disconnects / Backend sends `action="COMPLETE"`
        ↓
Retell call termination
        ↓
Webhook/event -> (`call_analyzed` webhook fires asynchronously)
        ↓
Transcript retrieval -> MISSING (Relies on WS events, but final webhook data is not merged)
        ↓
Transcript persistence -> PARTIAL (Unmapped messages)
        ↓
Analysis -> MISSING / INCOMPLETE (Orchestrator handles some scoring mid-flight, but no final comprehensive gap analysis)
        ↓
Result generation
        ↓
Frontend result page
```

*   The result generation races with the asynchronous Webhook, and cannot produce a proper transcript review.

## 11. Question → Answer Mapping

Currently:
```text
One large conversation transcript (unmapped InterviewMessages)
```

The system **does not** reliably know which candidate answer maps to which question because `turn_id` is missing in `InterviewMessage`. `InterviewOrchestrator` uses `last_user_transcript` directly, losing the aggregated context of a multi-utterance candidate response.

## 12. Current Analysis Pipeline

Currently, the orchestrator evaluates the `last_user_transcript` using a mock `SubmitResponseRequest`. It attempts to determine if the candidate answered the question to proceed or ask a follow-up.
It does **NOT** produce a final, comprehensive:
```text
Question | Expected Answer | Candidate Answer | Gap | Score | Reason
```
It currently produces a mid-flight action (`NEXT`, `FOLLOWUP`, `RETRY`), and scores the immediate turn.

## 13. Failure Points

1.  **Problem: Transcript is persisted but incorrectly associated with interview**
    *   **Evidence:** `InterviewMessage.turn_id` is not populated.
    *   **File:** `app/modules/interview/services/retell_llm_websocket.py`
    *   **Current behavior:** Utterances are saved to DB without knowing the active question.
    *   **Impact:** Cannot reconstruct Question-Answer pairs. Severity: Critical.

2.  **Problem: Partial transcripts are treated poorly / context lost**
    *   **Evidence:** Orchestrator only receives `self.context.last_user_transcript` instead of an aggregated answer.
    *   **File:** `retell_llm_websocket.py` -> `_process_user_answer`
    *   **Current behavior:** Only the last thing the candidate said before a pause is analyzed.
    *   **Impact:** If a candidate pauses, the orchestrator evaluates an incomplete answer. Severity: High.

3.  **Problem: Frontend state management problem (Ephemeral Transcript)**
    *   **Evidence:** `RetellInterviewRoom.jsx` relies entirely on Retell SDK events.
    *   **File:** `frontend/src/pages/RetellInterviewRoom.jsx`
    *   **Current behavior:** Refreshing wipes the transcript.
    *   **Impact:** Poor user experience. Severity: Medium.

## 14. Root Cause

**Confirmed root cause:** The backend LLM WebSocket handler (`retell_llm_websocket.py`) fails to track the `active_turn_id` from the `InterviewOrchestrator`'s state. When it persists `update_only` events into `InterviewMessage`, the relation to the current `InterviewTurn` is lost. Subsequently, all downstream analysis fails because the foundational data structure (a mapped Q&A pair) cannot be reliably reconstructed.

## 15. Proposed Correct Architecture

```text
AI speaks
   ↓
Backend tracks current `active_turn_id`. Stores AI utterance to `InterviewMessage` linked to `active_turn_id`.

Candidate speaks
   ↓
Retell STT -> Backend WS. Backend stores User utterance to `InterviewMessage` linked to `active_turn_id`.

Turn Ends (`response_required`)
   ↓
Backend aggregates all `InterviewMessages` for `active_turn_id` into a complete `candidate_response`.
Orchestrator evaluates complete response.
Advances `active_turn_id`.

Interview ends
   ↓
Background Task: Final Transcript Assembly
   ↓
Question-answer pairs reconstructed from `InterviewTurn` + `InterviewMessage`
   ↓
Question-wise Analysis (LLM identifies Missing Concepts against Expected Answer)
   ↓
Final interview report available to Frontend.
```

## 16. Required Changes

### Backend
1.  Update `retell_llm_websocket.py` to maintain the `active_turn_id`.
2.  Modify the persistence logic to save `active_turn_id` onto `InterviewMessage`.
3.  Update `_process_user_answer` to query and aggregate all candidate messages for the current turn, rather than using just `last_user_transcript`.
4.  Implement `GET /interview/session/{id}/transcript` to serve the full mapped transcript.

### Frontend
1.  Update `RetellInterviewRoom.jsx` to fetch the transcript from `GET /interview/session/{id}/transcript` on mount to hydrate state.
2.  Update result page to display the structured Q&A pairs.

### Database
1.  Ensure `InterviewTurn` stores `expected_answer` (rubric) from the `ApprovedQuestionPool`.

### Analysis
1.  Implement a post-call background job that performs formal gap analysis (comparing the aggregated candidate answer against the expected answer).

## 17. Implementation Phases

*   **Phase 0 — Architecture audit** (Complete)
*   **Phase 1 — Reliable transcript event capture:** Update `retell_llm_websocket.py` to track and populate `turn_id` on `InterviewMessage`.
*   **Phase 2 — Contextual Turn Evaluation:** Update the Orchestrator call to use the aggregated transcript for the turn.
*   **Phase 3 — Live frontend transcript hydration:** Implement transcript API and update Frontend.
*   **Phase 4 — Question-answer reconstruction & Analysis:** Implement the post-call LLM analysis pipeline to identify Gaps.
*   **Phase 5 — Final interview report UI:** Display the gaps and structured transcript in the frontend.
