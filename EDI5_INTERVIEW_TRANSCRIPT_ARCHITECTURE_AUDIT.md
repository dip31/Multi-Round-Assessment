# Phase 0 — EDI5 Interview Transcript Architecture Audit

## 1. Executive Summary

This architecture audit analyzes the current state of transcript capability within the EDI5 interview system. The EDI5 implementation relies on Retell for audio processing and transport (STT, TTS, turn detection), while the backend handles interview logic (`InterviewOrchestrator`). While the backend properly receives realtime WebRTC/WebSocket events and basic transcript data, this data is not structurally mapped to our core unit of analysis: the `InterviewTurn`. 

This report contrasts the current EDI5 architecture with the reference `HumanLikeInterview` implementation, outlines the precise gaps, and defines a phased implementation plan to build a persistent, question-mapped transcript architecture that feeds into the Student Competency Profile.

## 2. Current EDI5 Architecture

The current architecture is a hybrid where Retell drives the conversational voice channel, and EDI5 acts as the logic engine.

**Runtime Flow:**
1. **Candidate → Frontend:** Candidate connects via `RetellInterviewRoom.jsx` and clicks Start.
2. **Frontend → Backend:** Frontend calls `/interview/session/start`.
3. **Backend → Retell:** Backend calls Retell API to create a Web Call (`create_web_call`), linking it to the Custom LLM WebSocket endpoint (`retell_llm_websocket.py`).
4. **Interview Session:** Frontend connects to Retell via WebRTC. Retell connects to Backend via WebSocket.
5. **Questions/Follow-ups:** Retell streams STT events. When the candidate stops speaking, Retell sends `response_required` to the Backend WebSocket.
6. **Backend Logic:** `retell_llm_websocket.py` extracts the `last_user_transcript` and constructs a mock `SubmitResponseRequest`. It calls `InterviewOrchestrator.handle_response()` to run `AnswerUnderstanding`, score the answer, and plan the next question.
7. **Call Completion:** The orchestrator eventually returns `action="COMPLETE"`. The session is finalized, and proctoring stops.
8. **Result Storage:** Scores are stored on `InterviewTurn`, and session metadata is updated. (Transcripts are saved to `InterviewMessage` but without relational mapping to the turns).

## 3. Current Retell Integration

**Agent Configuration:**
* Agents are dynamically configured via `RetellAdapter` (`retell_adapter.py`). 
* A Web Call is created per session, mapping the `llm_websocket_url` to EDI5.

**During Call Capabilities:**
* **AI Transcript:** Yes (via `update_only` events).
* **Candidate Transcript:** Yes (via `update_only` and WebRTC events).
* **Speaker Identity:** Yes (`role`: "agent" | "user").
* **Timestamps:** NOT CONFIRMED — Retell payload contains utterances but explicit accurate timestamps may require mapping from the Webhook.
* **Turn boundaries:** Yes (`response_required` signals turn end).

**After Call Capabilities:**
* **Complete Transcript:** Yes (via `call_analyzed` Webhook).
* **Finalized Speaker Turns:** Yes.
* **Call Metadata:** Yes (via Webhook).

## 4. Current Frontend Architecture

**Interview Page:** `frontend/src/pages/RetellInterviewRoom.jsx`

**State and Transcripts:**
* The frontend uses `retell-client-js-sdk` to establish the WebRTC connection.
* **Live Transcript Event:** The frontend *already* receives live transcripts via the `retellClient.on('update', ...)` event.
* **Display:** It maintains a `liveTranscript` state array and renders it in real-time.
* **Persistence:** The frontend does *not* persist this. If the page reloads, the `liveTranscript` state is wiped.

## 5. Current Database Architecture

**Relevant Tables (`app/models/interview.py`):**
* `InterviewSession`: Tracks the session.
* `InterviewTurn`: Tracks the evaluated turn (Question + Answer + Score).
* `InterviewConversation` / `InterviewMessage`: These exist for transcript storage.

**Schema Analysis:**
* **Existing and Reusable:** `InterviewSession`, `InterviewTurn`, `InterviewConversation`, `InterviewMessage`.
* **Existing but Insufficient:** `InterviewMessage` has a `turn_id` column, but it is *never populated* by the WebSocket/Webhook handlers.
* **Completely Missing:** A structured mechanism to map multiple `InterviewMessage` utterances to a single `InterviewTurn`.

## 6. Reference Implementation Architecture

The reference implementation is `frontend/src/pages/HumanLikeInterview.jsx` backed by `interview_router.py` (`POST /respond`).

**Key Differences:**
* **Transport:** It uses native browser `MediaRecorder`, uploads the audio chunk to the backend, and awaits a JSON response.
* **Turn Lifecycle:** It strictly enforces a 1:1 ratio between candidate audio chunks and `InterviewTurn` evaluation.
* **Transcripts:** STT is performed directly on the audio chunk using Groq/Whisper, so the transcript is deterministically mapped to the turn before `InterviewOrchestrator` is even called.
* **Persistence:** The `InterviewOrchestrator` saves the single chunk's transcript into `InterviewTurn.candidate_response`. 

*Note: The reference implementation forces a strict turn-based system, whereas Retell allows a fluid, overlapping conversation. Copying the reference blindly would break Retell's natural conversational flow.*

## 7. EDI5 vs Reference Comparison

| Capability                 | EDI5 Current | Reference | Gap | Recommended EDI5 Approach |
| -------------------------- | ------------ | --------- | --- | ------------------------- |
| Live AI transcript         | Yes (Retell) | No        | None| Keep Retell SDK events    |
| Live candidate transcript  | Yes (Retell) | No        | None| Keep Retell SDK events    |
| Speaker identification     | Yes (Retell) | Implicit  | None| Rely on Retell `role`     |
| Active speaker             | Yes          | Implicit  | None| Keep Retell events        |
| Transcript persistence     | Partial (DB) | Yes       | Missing `turn_id` | Fix WS/Webhook DB logic |
| Final transcript retrieval | No           | No        | Needs API | Build API endpoint |
| Question mapping           | No           | Yes       | Mapping logic | Sync WS events to current turn |
| Follow-up mapping          | No           | Yes       | Mapping logic | Associate with parent turn |
| Expected answer            | Implicit     | Implicit  | Needs Rubric | Explicit rubric mapping |
| Candidate answer           | Yes (Latest) | Yes (Full)| Loses context | Aggregate messages per turn |
| Question-wise analysis     | Partial      | Partial   | No Gap extraction | Post-call LLM analysis pipeline |
| Gap analysis               | No           | No        | Completely missing | Implement Gap Extractor |
| Competency evaluation      | No           | No        | Completely missing | Map Gaps to Competencies |
| Student profile update     | No           | No        | Completely missing | Integrate with `AssessmentSession` |

## 8. Target Architecture

We must preserve Retell's conversational fluidity while overlaying a structured analysis pipeline.

**Conceptual Flow:**
1. **Live Transcript:** Retell WebRTC → Frontend (Display) + Retell WS → Backend (Persistence).
2. **Transcript Service:** Saves every utterance to `InterviewMessage`, explicitly tracking the *active* `InterviewTurn`.
3. **Question/Answer Mapping:** At `response_required`, aggregate all `InterviewMessage`s for the current `turn_id` and evaluate them holistically.
4. **Question-wise Analysis:** (Post-Call) Analyze the aggregated answers against the question's rubric to extract correct concepts and *Missing Concepts* (Gaps).
5. **Competency Evaluation:** Map the identified Gaps to specific skills in the Student Competency Profile.

## 9. Transcript Data Model Proposal

The existing schema is mostly sufficient, but we need to strictly enforce the relationships.

**Transcript (`InterviewMessage`)**
* `conversation_id`: Ties to `InterviewSession`.
* `retell_utterance_id`: For deduplication between WS and Webhook events.
* `speaker`: 'agent' | 'user'
* `text`: The transcribed text.
* `timestamp`: Required for chronological rendering.
* `turn_id`: **CRITICAL**. Maps the utterance to the `InterviewTurn`.

**QuestionAnswer (`InterviewTurn` extension/usage)**
* `id`: Turn ID.
* `question_text`: The AI's prompt.
* `candidate_response`: We should change this from a single string to an aggregated text of all candidate utterances for this turn, or rely on `InterviewMessage` relations.
* `expected_answer`: *New requirement*. Needs to be fetched from `ApprovedQuestionPool`.
* `parent_turn_id`: Links follow-ups to main questions.

## 10. Question Mapping Strategy

**Deterministic Mapping (Recommended):**
Because the backend controls the interview logic via `InterviewOrchestrator`, it inherently knows the "active state".

1. **AI Question Turn:** The orchestrator sets the active question.
2. **Candidate Answer Turns:** As Retell streams `update_only` events, the backend persists them to `InterviewMessage`, stamping them with the *currently active* `turn_id`.
3. **Question Completion:** When Retell sends `response_required`, the orchestrator evaluates the turn. If it decides to ask a `FOLLOWUP`, a new `InterviewTurn` is created, and it becomes the active `turn_id`.
4. **Fallback:** Deduplication logic in the Webhook uses `retell_utterance_id` to ensure no lost messages.

## 11. Question-wise Analysis Strategy

Rather than asking an LLM for a blind score, we use an Evidence-Based Pipeline.

**Pipeline (Post-Interview):**
1. **Input Generation:** For each main `InterviewTurn`, gather the main question, the expected answer rubric (from the pool), the main candidate answer, and all associated follow-up questions and answers.
2. **Concept Extraction:** Ask the LLM to list the core concepts required by the rubric.
3. **Coverage Mapping:** Ask the LLM to map candidate statements directly to the required concepts.
4. **Gap Identification:** Any required concept without candidate evidence is flagged as a "Missing Concept".
5. **Scoring:** Score is calculated deterministically based on `% of concepts covered`, modified by follow-up penalties.

## 12. Competency Integration Strategy

The interview evidence must flow into the Competency Engine.

**Data Produced:**
* For every identified "Missing Concept", the system emits a `SkillGap` event.
* For every covered concept, the system emits a `SkillDemonstrated` event.

**Integration:**
When the interview is marked `COMPLETE`, a background task will aggregate these events, normalize the skill names using the `ApprovedQuestionPool.extracted_skills`, and push them to the `AssessmentSession` results, which eventually merge into the Student Competency Profile.

## 13. File-Level Implementation Map

### Frontend Files
* `frontend/src/pages/RetellInterviewRoom.jsx`
  * *Responsibility:* Handle page refreshes.
  * *Change:* Add `useEffect` to fetch historical `InterviewMessage`s from the backend on load to hydrate `liveTranscript`.
* `frontend/src/pages/InterviewReport.jsx`
  * *Responsibility:* Show the results.
  * *Change:* Add a "Transcript View" tab that fetches and renders the `InterviewConversation`.

### Backend Files
* `app/modules/interview/services/retell_llm_websocket.py`
  * *Responsibility:* Live WS transcript persistence.
  * *Change:* Track `active_turn_id` in `InterviewSession.rl_state`. Assign this ID to all incoming `InterviewMessage` records in `_persist_structured_transcript`.
* `app/modules/interview/services/interview_orchestrator.py`
  * *Responsibility:* Turn evaluation.
  * *Change:* Instead of using just `last_user_transcript`, query all `InterviewMessage`s for the active `turn_id` and concatenate them for `AnswerUnderstanding`.
* `app/modules/interview/routers/interview_router.py`
  * *Responsibility:* API Endpoints.
  * *Change:* Add `GET /interview/session/{id}/transcript` to serve the full transcript to the frontend.

### Database / Schema Files (Future Phase)
* `app/models/interview.py`
  * *Change:* Eventually add `expected_answer_rubric` to `InterviewTurn`. (No changes in Phase 0).

## 14. Risks and Mitigations

* **Risk:** Retell Event Ordering. Webhooks may arrive after WS events.
  * **Mitigation:** Use `upsert` logic based on `retell_utterance_id`.
* **Risk:** Question Boundary Ambiguity. A candidate interrupts the AI.
  * **Mitigation:** Retell handles interruption gracefully; the backend should map the interrupted AI utterance to the *previous* turn, and the candidate's new speech to the *current* turn.
* **Risk:** LLM Latency during analysis.
  * **Mitigation:** Perform the Question-wise analysis and Gap Identification asynchronously in a background task after `action="COMPLETE"`.
* **Risk:** State mutations failing to persist.
  * **Mitigation:** Strictly adhere to the JSONB assignment rule documented in `interview_orchestrator.py`.

## 15. Implementation Phases

* **Phase 1 — Transcript Persistence:** Fix `retell_llm_websocket.py` to accurately map `InterviewMessage` to `turn_id`.
* **Phase 2 — Contextual Evaluation:** Modify `InterviewOrchestrator` to evaluate the aggregated candidate utterances for a given turn.
* **Phase 3 — API & Frontend Hydration:** Add `GET /transcript` endpoint and update `RetellInterviewRoom.jsx` to load history on mount.
* **Phase 4 — Question-wise Analysis:** Implement the post-call LLM analysis pipeline (Concept Coverage & Gap Detection) as a background task.
* **Phase 5 — Report UI:** Update `InterviewReport.jsx` to display the transcript and the identified gaps.
* **Phase 6 — Competency Evaluation:** Map gaps to the Student Competency Profile.

## 16. Recommended Next Step

**Implement Phase 1 (Transcript Persistence).**

*Why:* Without accurate `turn_id` mapping in the database, no downstream analysis (Question-wise Analysis, Gap Detection) is possible. The frontend already handles live display, so fixing the backend data structure is the critical blocker. This requires modifying `retell_llm_websocket.py` to track and apply the active `turn_id` to incoming utterances.
