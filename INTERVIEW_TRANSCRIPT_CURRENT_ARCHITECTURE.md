# EDI5 Interview Transcript — Current Architecture Analysis

## 1. Executive Summary

This report provides a detailed analysis of the current interview architecture in the EDI5 project, specifically focusing on how conversation data (audio and transcripts) flows through the system. The analysis confirms that a significant portion of the transcript infrastructure already exists, primarily driven by the Retell integration. However, critical gaps remain in correctly associating transcript utterances with specific interview turns and utilizing this structured data for comprehensive evaluation.

## 2. Current Interview Architecture

The interview architecture is a hybrid system where EDI5 acts as the "brain" (Interview Intelligence) and Retell acts as the "mouth/ears" (Voice Transport).

Key components:
*   **Frontend**: React-based UI (`RetellInterviewRoom.jsx`) that handles the user interface and WebRTC connection to Retell.
*   **Backend Orchestrator**: `InterviewOrchestrator` (`app/modules/interview/services/interview_orchestrator.py`) makes decisions (next question, follow-up, evaluate answer).
*   **Voice Integration**: Retell handles STT, TTS, and turn detection. It communicates with the backend via two channels:
    *   **Custom LLM WebSocket** (`app/modules/interview/services/retell_llm_websocket.py`): Real-time control loop where Retell asks EDI5 what to say next.
    *   **Webhooks** (`app/modules/interview/routers/retell_webhook.py`): Asynchronous event notifications (e.g., `transcript_updated`, `call_ended`).

## 3. End-to-End Interview Flow

1.  **Interview creation**: The frontend calls `startInterview` (`/interview/session/start`), which creates an `InterviewSession` and initiates a Retell Web Call.
2.  **Interviewer/agent configuration**: Retell is configured to use a "Custom LLM" pointing to the EDI5 WebSocket endpoint.
3.  **Interview session start**: The frontend (`RetellInterviewRoom.jsx`) connects to Retell using the `retell-client-js-sdk` WebRTC transport. Retell's backend simultaneously connects to EDI5's Custom LLM WebSocket (`wss://.../retell/llm/{call_id}`).
4.  **Frontend ↔ backend communication**: The frontend communicates with Retell directly for audio. Retell communicates with the backend WebSocket for logic and transcripts.
5.  **AI speaks**: The backend WebSocket sends a `response` event to Retell containing the text to speak. Retell synthesizes the audio and streams it to the frontend via WebRTC.
6.  **Candidate speaks**: Candidate audio is captured by the browser, sent via WebRTC to Retell.
7.  **Question generation / follow-up**: Retell performs STT, detects when the user finishes speaking, and sends a `response_required` event to the backend WebSocket with the current transcript. The backend's `InterviewOrchestrator` evaluates the answer, selects the next action (e.g., `ASK_QUESTION`, `FOLLOW_UP`), and sends the next text response back to Retell.

## 4. Audio Flow

The audio flow heavily relies on the Retell infrastructure and WebRTC:

### Candidate → AI
*   **Microphone capture**: Browser MediaStream API.
*   **Transport**: WebRTC managed by `retell-client-js-sdk` in `RetellInterviewRoom.jsx`.
*   **STT**: Handled by Retell's internal systems. The resulting text is sent to the backend via the Custom LLM WebSocket and Webhooks, and to the frontend via SDK events.

### AI → Candidate
*   **Audio streaming**: Retell generates audio (TTS) based on text provided by the EDI5 backend.
*   **Transport**: Audio is streamed back to the frontend via the established WebRTC connection and played through the browser.

## 5. Retell Integration

The Retell implementation is mature and handles the heavy lifting of voice interaction:
*   **SDK Usage**: Frontend uses `retell-client-js-sdk` (legacy `RetellWebClient`). Backend uses REST API for call creation and WebSocket for Custom LLM control.
*   **Call Creation**: `RetellAdapter.create_web_call` (`retell_adapter.py`) initializes the call.
*   **Webhooks**: Configured and active in `retell_webhook.py`. Handles `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, etc.
*   **Live Transcripts**: Yes, Retell provides live, partial, and final transcripts via both the WebSocket (`update_only` events) and Webhooks (`transcript_updated`).
*   **Persistence**: `call_id` is stored in the `InterviewSession` table (`retell_call_id`).

## 6. Frontend Architecture

The exact frontend implementation is in `frontend/src/pages/RetellInterviewRoom.jsx` and `frontend/src/services/interviewService.js`.

*   **State Management**: Manages states like `CONNECTING`, `READY`, `LISTENING`, `PROCESSING`.
*   **Transcript Rendering**: **Yes, live transcript rendering currently exists!** The frontend receives `transcript` and `update` events directly from the `retellClient` and renders them in a styled container labeled "Live Conversation".
*   **Missing Features**: The frontend only displays transcripts from the active WebRTC connection. It does not fetch past conversation history from the backend if the page is refreshed.

## 7. Backend Architecture

During the interview, the frontend **does not** communicate directly with the backend REST API for conversational turns.

The actual architecture is:
```text
Frontend (Browser)  <-- WebRTC -->  Retell Servers  <-- WebSocket -->  EDI5 Backend
```
Retell acts as the man-in-the-middle for all real-time communication. The frontend receives transcript events directly from Retell's WebRTC data channel, while the backend receives them via the Custom LLM WebSocket connection from Retell.

## 8. Current Transcript Capability

Transcript data is abundant in the current system:

1.  **Frontend Live Events**: The `retell-client-js-sdk` emits `transcript` events directly to the browser. *Used for live UI.*
2.  **Backend WebSocket**: `retell_llm_websocket.py` receives `update_only` and `response_required` events containing the full transcript array. *Used for orchestrator logic and persistence.*
3.  **Backend Webhook**: `retell_webhook.py` receives `transcript_updated` events. *Used as a fallback persistence mechanism.*

The backend actively attempts to persist these transcripts into the `InterviewConversation` and `InterviewMessage` tables using `_persist_structured_transcript` functions in both the WebSocket and Webhook handlers.

## 9. Database Architecture

The schema currently **partially supports** transcript storage.

Relevant Models (`app/models/interview.py`):
*   `InterviewConversation`: Represents the entire chat sequence for a session.
*   `InterviewMessage`: Represents individual utterances (`speaker`, `text`, `sequence_number`, `turn_id`, `parent_message_id`).
*   `InterviewTurn`: Represents the evaluated question/answer pair.

**Current Limitations**: While the tables exist and transcripts are being saved to `InterviewMessage`, the critical `turn_id` foreign key is **never populated**. The `_persist_structured_transcript` logic maps utterances to the conversation but fails to link them to the active `InterviewTurn`.

## 10. Current Interview Evaluation

Current flow:
1.  Candidate speaks -> Retell detects end of turn -> sends `response_required` to WebSocket.
2.  WebSocket handler (`_process_user_answer`) extracts ONLY the `last_user_transcript` (the most recent utterance).
3.  It constructs a mock `SubmitResponseRequest` with this single utterance.
4.  `InterviewOrchestrator` calls `AnswerUnderstanding` to classify this single utterance.
5.  Score and feedback are generated based ONLY on this latest utterance, completely ignoring previous context or multi-part answers.

The current evaluation system **lacks the complete conversational context**. It cannot properly evaluate an answer that spans multiple back-and-forth clarifications.

## 11. Question-Answer Mapping

**This mapping does not currently exist.**

Although the schema has a `turn_id` on the `InterviewMessage` table, the code that persists Retell transcripts (`_persist_structured_transcript` in both `retell_llm_websocket.py` and `retell_webhook.py`) completely ignores it.

When an AI utterance (Question) or a Candidate utterance (Answer) is saved, the system does not know which `InterviewTurn` it belongs to.

## 12. Transcript Architecture Options

### Option A — Frontend speech-to-text
*Not applicable/Redundant.* Retell already provides highly accurate STT.

### Option B — Retell transcript/events (Current Implementation)
*   **Live UI**: Frontend uses Retell SDK WebRTC events. (Latency: Ultra-low)
*   **Backend Storage**: Backend uses Retell Custom LLM WebSocket events. (Latency: Low)
*   **Compatibility**: High. This is exactly how the system is currently wired.

### Option C — Retell post-call transcript
*   Retrieve transcript only after the call.
*   **Pros**: Simplifies backend logic.
*   **Cons**: Prevents real-time question-wise evaluation and dynamic follow-up logic based on the full conversational context.

## 13. Recommended Architecture

The system should stick to the **existing architecture (Option B)** but fix the missing links.

The frontend is already receiving and displaying live transcripts perfectly via the Retell SDK. No architectural changes are needed there.

The backend is already receiving live transcripts via WebSocket. The only required change is fixing the persistence logic to accurately map utterances to `turn_id` and updating the `InterviewOrchestrator` to evaluate the *entire* turn transcript rather than just the final utterance.

## 14. Proposed Data Flow

1.  Retell sends WebSocket `update_only` event with transcript array.
2.  Backend `_persist_structured_transcript` identifies new utterances.
3.  Backend looks up the *active* `InterviewTurn` ID.
4.  Backend saves `InterviewMessage` with the correct `turn_id`.
5.  When `response_required` arrives, the orchestrator queries all `InterviewMessage` records for the current `turn_id` to evaluate the complete answer context.

## 15. Files That Would Need Modification

### Backend
*   `app/modules/interview/services/retell_llm_websocket.py`
    *   *Reason*: Modify `_persist_structured_transcript` to track the current active `turn_id` and assign it to new `InterviewMessage` records. Modify `_process_user_answer` to pass the full turn context to the orchestrator instead of just `last_user_transcript`.
*   `app/modules/interview/routers/retell_webhook.py`
    *   *Reason*: Ensure webhook persistence logic matches the WebSocket logic, or rely solely on WebSocket for primary persistence to avoid race conditions.
*   `app/modules/interview/services/interview_orchestrator.py`
    *   *Reason*: Update `handle_response` to accept and utilize a full transcript context rather than a single string.

### Frontend
*   `frontend/src/pages/RetellInterviewRoom.jsx`
    *   *Reason*: Minor updates. Currently, it loses the transcript on page refresh. Needs a `useEffect` to fetch past `InterviewMessages` from the backend API to hydrate the `liveTranscript` state on load.

## 16. Missing Components

| Requirement                | Exists? | Current Location | Missing Piece |
| -------------------------- | ------- | ---------------- | ------------- |
| Live AI transcript         | Yes     | Frontend/Retell  | None |
| Live candidate transcript  | Yes     | Frontend/Retell  | None |
| Transcript persistence     | Yes     | DB / WS Handler  | Association with `turn_id` |
| Call transcript retrieval  | No      | API              | Needs a REST endpoint to fetch `InterviewConversation` |
| Question-answer mapping    | No      | DB Schema only   | Logic in `_persist_structured_transcript` to link `turn_id` |
| Final transcript           | Yes     | DB               | None |
| Question-wise evaluation   | Partial | Orchestrator     | Orchestrator only sees the final sentence, not the full context |

## 17. Risks and Edge Cases

*   **Duplicate Persistence**: Both `retell_llm_websocket.py` and `retell_webhook.py` attempt to persist the transcript. This could lead to race conditions or duplicate entries if `utterance_id` deduplication fails.
*   **Turn Mapping Complexity**: Accurately mapping an utterance to a turn is difficult because Retell's transcript is a flat array, while EDI5's logic is turn-based. If the AI asks a follow-up, does that start a new turn or continue the existing one?
*   **Evaluation Context Limit**: Sending an entire conversation history to the LLM for every evaluation could hit token limits or increase latency significantly.
*   **Interruptions**: If a candidate interrupts the AI, Retell handles the audio gracefully, but accurately mapping the interrupted AI utterance and the candidate's interjection to the correct `turn_id` requires careful logic.

## 18. Implementation Phases

1.  **Phase 1: Fix Persistence & Mapping**: Update WebSocket handlers to accurately assign `turn_id` to incoming `InterviewMessage` records.
2.  **Phase 2: Contextual Evaluation**: Modify the `InterviewOrchestrator` to evaluate the aggregated candidate utterances for a given turn, rather than just the final string.
3.  **Phase 3: Frontend Hydration**: Add an API endpoint to fetch the conversation history and update the React component to load this history on mount.

## 19. What Already Works

*   Real-time voice communication (WebRTC).
*   Live transcript delivery to the frontend UI.
*   Live transcript delivery to the backend WebSocket.
*   Basic persistence of utterances to the database (without relations).
*   End-of-turn detection via Retell `response_required`.

## 20. What Does Not Exist Yet

*   Relational mapping between utterances (`InterviewMessage`) and the interview logic (`InterviewTurn`).
*   Evaluation logic that understands multi-utterance answers or conversational back-and-forth within a single turn.
*   Retrieval of historical transcripts for a session via REST API.

## 21. Final Architecture Diagram

```text
                 ┌─────────────────────┐
                 │     Candidate       │
                 │      Browser        │
                 └──────────┬──────────┘
                            │
              WebRTC (Audio + Live Transcript Data)
                            │
                            ▼
                 ┌─────────────────────┐
                 │    Retell Servers   │
                 │     (STT / TTS)     │
                 └───────┬─────┬───────┘
                         │     │
            WebSocket: update_only / response_required
                         │     │
                         ▼     ▼
                 ┌─────────────────────┐
                 │ EDI5 WebSocket API  │
                 │(retell_llm_websocket)│
                 └──────────┬──────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
        Database Storage        InterviewOrchestrator
      (InterviewMessage)               │
                 │                     ▼
                 │            AnswerUnderstanding
                 │                     │
                 │                     ▼
                 │               QuestionPlanner
                 │                     │
                 └─────────────────────┘
```
