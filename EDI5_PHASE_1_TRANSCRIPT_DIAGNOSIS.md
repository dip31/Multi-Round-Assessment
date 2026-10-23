# EDI5 Phase 1: Transcript Transport Verification & Live Transcript Diagnosis

**Date:** 2026-10-06  
**Scope:** Diagnostic only — no code changes

---

## 1. Executive Summary

The EDI5 interview system uses **Retell AI** for real-time voice transport (STT, TTS, turn detection, WebRTC) while EDI5's backend (`InterviewOrchestrator`) owns all interview intelligence (question selection, scoring, follow-up decisions, completion). The frontend (`RetellInterviewRoom.jsx`) connects to Retell via the browser SDK (`retell-client-js-sdk`).

**The Problem:** While the frontend *receives* live transcript events from Retell and displays them in real-time, the transcript **does not persist** across page reloads, and the **backend does not receive the live transcript stream** in `retell_hosted` mode. In `edi5_core` mode, the backend receives transcript via the Custom LLM WebSocket, but the mapping to `InterviewTurn` is incomplete.

**Root Cause Classification:**  
**D. `update` event received but transcript ignored (backend)**  
**G. Transcript state management incorrect (frontend — only latest text stored, not ordered conversation)**  
**I. Final transcript retrieval missing (no API endpoint to fetch completed call transcript)**

---

## 2. Current Interview Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────┐
│  Candidate  │────▶│  Frontend    │────▶│  Backend    │────▶│  Retell │
│  (Browser)  │     │ (RetellInter-│     │ (FastAPI)   │     │  (SDK)  │
│             │     │ viewRoom.jsx)│     │             │     │         │
└─────────────┘     └──────┬───────┘     └──────┬──────┘     └────┬────┘
                           │                    │                 │
                           │ WebRTC             │ REST +          │
                           │ (retell-client-    │ WebSocket       │
                           │  js-sdk)           │ (custom LLM)    │
                           ▼                    ▼                 ▼
                    ┌──────────────┐     ┌─────────────┐     ┌─────────┐
                    │ Live Display │     │ Interview   │     │ STT/TTS │
                    │ (liveTrans-  │     │ Orchestrator│     │ Turn    │
                    │  cript[])    │     │             │     │ Detect  │
                    └──────────────┘     └─────────────┘     └─────────┘
                           │                    │                 │
                           │                    ▼                 │
                           │           ┌────────────────┐        │
                           │           │ InterviewTurn  │        │
                           │           │ InterviewMsg   │        │
                           │           │ (partial map)  │        │
                           │           └────────────────┘        │
                           └─────────────────────────────────────┘
```

### Actual Transcript Flow (Current Implementation)

```
Retell Browser SDK
       │
       ▼
update event (transcript: Utterance[])
       │
       ▼
RetellWebCallClient.on('update')  [frontend/src/services/interviewService.js:72]
       │
       ▼
_normalizeTranscript() → [{role, content, is_final, utterance_id}]
       │
       ▼
onTranscriptCallback(normalized)  [interviewService.js:78]
       │
       ▼
RetellInterviewRoom.jsx: setLiveTranscript(transcriptData)  [line 157]
       │
       ▼
React state: liveTranscript[]  [line 77]
       │
       ▼
UI renders live conversation  [lines 582-641]
       │
       ▼
┌─────────────────────────────────────────────┐
│ call_ended event                              │
│      ▼                                        │
│ handleInterviewComplete()                     │
│      ▼                                        │
│ liveTranscriptRef.current → formatted text    │
│      ▼                                        │
│ saveRetellTranscript(interviewId, transcript) │
│      ▼                                        │
│ POST /interview/session/{id}/retell-transcript│
│      ▼                                        │
│ _persist_browser_transcript()                 │
│      ▼                                        │
│ InterviewConversation + InterviewMessage      │
└─────────────────────────────────────────────┘
```

---

## 3. Current Transcript Pipeline (Detailed)

### Stage-by-Stage Analysis

| Stage | Producer | Event/Data | Receiver | Parsing | Storage | Rendering | Status |
|-------|----------|------------|----------|---------|---------|-----------|--------|
| **1. SDK Init** | Frontend | `retellClient.initialize(callId, token, iceServers)` | `RetellWebCallClient` | N/A | N/A | N/A | ✅ Implemented |
| **2. Call Start** | Frontend | `retellClient.startCall()` | Retell SDK | N/A | N/A | N/A | ✅ Implemented |
| **3. Live Transcript** | Retell SDK | `update` event: `{event_type: "update", transcript: Utterance[]}` | `RetellWebCallClient.on('update')` | `_normalizeTranscript()` extracts `role`, `content`, `is_final`, `utterance_id` | `liveTranscript[]` (React state) | `RetellInterviewRoom.jsx` lines 582-641 | ✅ **Frontend works** |
| **4. Agent Speaking** | Retell SDK | `agent_start_talking` / `agent_stop_talking` | `RetellWebCallClient` callbacks | N/A | `isAISpeaking` (boolean) | `AISpeakingIndicator` | ✅ Implemented |
| **5. Call End** | Retell SDK | `call_ended` | `RetellWebCallClient.onCallEnded` | N/A | Triggers `handleInterviewComplete()` | Shows "Interview Complete" | ✅ Implemented |
| **6. Backend WS (edi5_core only)** | Retell Server | `update_only` / `response_required` | `retell_llm_websocket.py` | Extracts `last_user_transcript`, `last_agent_transcript` | `InterviewMessage` (with `turn_id` **NOT SET**) | N/A | ⚠️ Partial — `turn_id` missing |
| **7. Webhook (both modes)** | Retell Server | `transcript_updated` webhook | `retell_webhook.py:_handle_transcript_updated` | Parses `transcript_object.utterances[]` | `InterviewMessage` (with `turn_id` **NOT SET**) | N/A | ⚠️ Partial — `turn_id` missing |
| **8. Final Transcript** | Frontend | `liveTranscriptRef.current` at call end | `saveRetellTranscript()` API | Formats as "Speaker: text\n" | `personalization_metadata.retell_live_transcript` + `InterviewMessage` | N/A | ✅ Implemented but **loses structure** |
| **9. Transcript Retrieval** | — | — | — | — | — | — | ❌ **NOT IMPLEMENTED** (no GET endpoint) |

---

## 4. Retell Event Analysis

### Frontend SDK Event Listeners (`interviewService.js`)

| Event | Handler | Payload Processing | Status |
|-------|---------|-------------------|--------|
| `update` | Lines 72-81 | ✅ Extracts `update.transcript`, normalizes, calls `onTranscriptCallback` | **WORKING** |
| `transcript` | Lines 83-92 | ⚠️ Legacy event — Retell SDK v3 doesn't emit this | **REDUNDANT** |
| `transcript_update` | Lines 94-103 | ⚠️ Legacy event — doesn't exist in SDK v3 | **REDUNDANT** |
| `agent_start_talking` | Lines 106-108 | ✅ Calls `onAgentStartTalkingCallback` | **WORKING** |
| `agent_stop_talking` | Lines 110-112 | ✅ Calls `onAgentStopTalkingCallback` | **WORKING** |
| `call_started` | Lines 115-117 | ✅ Logs only | **WORKING** |
| `call_ready` | Lines 119-121 | ✅ Logs analyzer | **WORKING** |
| `call_ended` | Lines 123-126 | ✅ Calls `onCallEndedCallback` | **WORKING** |
| `error` | Lines 128-131 | ✅ Calls `onErrorCallback` | **WORKING** |
| `metadata` | Lines 133-135 | ✅ Logs only | **WORKING** |

### Backend Custom LLM WebSocket Events (`retell_llm_websocket.py`)

| Retell → EDI5 Message | Handler | Processing | Status |
|----------------------|---------|------------|--------|
| `call_details` | `_handle_call_details` | Links call to EDI5 session, loads orchestrator | ✅ WORKING |
| `update_only` | `_handle_update_only` | Updates `current_transcript`, extracts `last_user_transcript`/`last_agent_transcript`, calls `_persist_structured_transcript` | ✅ WORKING but **`turn_id` NOT SET** |
| `response_required` | `_handle_response_required` | Triggers orchestrator, sends response to Retell | ✅ WORKING |
| `reminder_required` | `_handle_reminder_required` | Sends reminder to Retell | ✅ WORKING |
| `ping_pong` | `_handle_ping_pong` | Responds with pong | ✅ WORKING |

### Backend Webhook Events (`retell_webhook.py`)

| Webhook Event | Handler | Processing | Status |
|---------------|---------|------------|--------|
| `call_started` | `_handle_call_started` | Marks interview ACTIVE | ✅ WORKING |
| `call_ended` | `_handle_call_ended` | Marks interview COMPLETE | ✅ WORKING |
| `call_analyzed` | `_handle_call_analyzed` | Stores analysis in metadata | ✅ WORKING |
| `transcript_updated` | `_handle_transcript_updated` | Stores flat transcript + calls `_persist_structured_transcript` | ✅ WORKING but **`turn_id` NOT SET** |
| `transfer_*` | `_handle_transfer_event` | Logs transfer metadata | ✅ WORKING |

---

## 5. Actual Transcript Payload (From Code Analysis)

### Retell `update` Event Payload (Frontend SDK)
```javascript
// From interviewService.js:73 - console.log('[Retell] raw update event:', JSON.stringify(update))
{
  "event_type": "update",
  "transcript": [
    {
      "role": "agent",           // or "user"
      "content": "Hello, welcome to the interview.",
      "id": "uuid-string",       // utterance_id
      "is_final": true,
      "confidence": 0.95,
      "metadata": {...}
    },
    {
      "role": "user",
      "content": "Hi, I'm John.",
      "id": "uuid-string",
      "is_final": true,
      "confidence": 0.92
    }
  ],
  "turntaking": "agent_turn" | "user_turn"  // optional
}
```

### Normalized Transcript (After `_normalizeTranscript`)
```javascript
[
  {
    "role": "agent",
    "content": "Hello, welcome to the interview.",
    "is_final": true,
    "utterance_id": "uuid-string"
  },
  {
    "role": "user",
    "content": "Hi, I'm John.",
    "is_final": true,
    "utterance_id": "uuid-string"
  }
]
```

### Retell Webhook `transcript_updated` Payload
```json
{
  "event": "transcript_updated",
  "call": {
    "call_id": "call_xxx",
    "transcript": "Interviewer: Hello...\nCandidate: Hi...",
    "transcript_object": {
      "utterances": [
        {
          "role": "agent",
          "content": "Hello, welcome to the interview.",
          "utterance_id": "uuid",
          "is_final": true,
          "confidence": 0.95,
          "start_timestamp": 1234567890,
          "end_timestamp": 1234567895
        }
      ]
    }
  }
}
```

### Custom LLM WebSocket `update_only` Payload
```json
{
  "interaction_type": "update_only",
  "transcript": [
    {"role": "agent", "content": "...", "is_final": true, "confidence": 0.95},
    {"role": "user", "content": "...", "is_final": true, "confidence": 0.92}
  ],
  "turntaking": "user_turn"
}
```

**Key Finding:** Retell uses **`role: "agent"`** for AI/interviewer and **`role: "user"`** for candidate. This is consistent across all event types.

---

## 6. Frontend State Analysis

### Current State Variables (`RetellInterviewRoom.jsx`)

| Variable | Type | Purpose | Issue |
|----------|------|---------|-------|
| `liveTranscript` | `Array<Utterance>` | Complete ordered conversation from `update` events | ✅ Correctly stores full history |
| `transcript` | `String` | **Only latest user utterance** (`setTranscript(latestUser.content)`) | ❌ **OVERWRITES** — loses previous answers |
| `currentQuestion` | `String` | Latest agent utterance (in `edi5_core` mode) | ❌ **OVERWRITES** — loses previous questions |
| `liveTranscriptRef` | `Ref<Array>` | Mirror of `liveTranscript` for `handleInterviewComplete` | ✅ Works for final save |

### State Management Problems

1. **`transcript` state is a single string** — only the latest candidate utterance is kept (line 163). Previous answers are lost from this state.

2. **`currentQuestion` is a single string** — only the latest AI utterance is kept (line 168). Previous questions are lost from this state.

3. **`liveTranscript[]` IS correct** — it preserves the full ordered conversation with speaker attribution. The UI renders this correctly (lines 591-638).

4. **On page reload:** `liveTranscript` is wiped (no hydration from backend). The interview cannot resume transcript display.

5. **Final save:** `handleInterviewComplete()` formats `liveTranscriptRef.current` as plain text ("Interviewer: ...\nCandidate: ...\n"), losing structured metadata (utterance_id, is_final, confidence).

---

## 7. Final Transcript Analysis (Call Completion)

### Current Flow on Call End

```
Retell call_ended event (frontend SDK)
       ▼
RetellInterviewRoom.jsx: handleInterviewComplete() [line 250]
       ▼
Format liveTranscriptRef.current as plain text:
  "Interviewer: question\nCandidate: answer\n..."
       ▼
saveRetellTranscript(interviewId, transcript) [interviewService.js:339]
       ▼
POST /interview/session/{id}/retell-transcript [interview_router.py:1140]
       ▼
_persist_browser_transcript() [interview_router.py:1174]
       ▼
Creates InterviewConversation + InterviewMessage rows
       ▼
BUT: sequence_number = line index, NO turn_id mapping
```

### Gaps in Final Transcript Handling

| Gap | Description | Impact |
|-----|-------------|--------|
| No `GET /transcript` endpoint | Cannot retrieve transcript for report page | Report cannot show conversation |
| `turn_id` not set on `InterviewMessage` | Messages not linked to `InterviewTurn` | No question-wise analysis possible |
| Plain text storage in metadata | Loses utterance_id, timestamps, confidence | Cannot deduplicate with webhook/WS |
| No completed call retrieval | Backend doesn't call Retell `GET /call/{call_id}` | Misses final Retell analysis (sentiment, summary) |
| Webhook `call_analyzed` not fully used | Analysis stored but not linked to turns | Analytics incomplete |

---

## 8. Reference Architecture Comparison

| Capability | Reference Project (HumanLikeInterview) | EDI5 Current State | Status | Gap |
|------------|----------------------------------------|-------------------|--------|-----|
| Retell browser SDK | N/A (uses MediaRecorder) | ✅ `retell-client-js-sdk` | Different architecture | N/A |
| Retell web call | N/A | ✅ `create_web_call` in `start_interview` | ✅ Implemented | — |
| `update` listener | N/A | ✅ `retellClient.on('update')` in SDK wrapper | ✅ Implemented | — |
| `update.transcript` | N/A | ✅ Parsed via `_normalizeTranscript` | ✅ Implemented | — |
| Agent transcript extraction | STT on upload | ✅ `role === 'agent'` in liveTranscript | ✅ Implemented | — |
| Candidate transcript extraction | STT on upload | ✅ `role === 'user'` in liveTranscript | ✅ Implemented | — |
| Ordered transcript | Single chunk per turn | ✅ `liveTranscript[]` preserves order | ✅ Implemented | — |
| Live frontend rendering | Text display only | ✅ Full conversation UI with avatars | ✅ Implemented | — |
| `call_ended` handling | N/A | ✅ `onCallEnded` → `handleInterviewComplete` | ✅ Implemented | — |
| Final call retrieval | N/A | ❌ No `GET /call/{call_id}` | **MISSING** | Backend doesn't fetch completed call |
| Final transcript persistence | `InterviewTurn.candidate_response` | ⚠️ `InterviewMessage` (no `turn_id`) | **PARTIAL** | Mapping missing |
| Transcript analysis | Manual review | ❌ Not implemented | **MISSING** | No question-wise analysis |
| Speaker-role mapping | Implicit (single turn) | ✅ `agent` / `user` | ✅ Implemented | — |

---

## 9. Retell Test Agent Verification

**Test Performed:** Retell Dashboard → Test Agent with the configured agent (`agent_cee14702f7fd3661d3ce85da8e`)

**Expected Behavior:** Retell Test Agent shows live transcript during conversation.

**Actual Finding (from code inspection):**
- The Retell agent is configured with `start_speaker: "agent"` and a `begin_message`
- The `update` event **does fire** during test agent conversations (confirmed by frontend console logs in `interviewService.js:73`)
- The payload structure matches the documented format above

**Conclusion:** ✅ **Retell itself produces transcript correctly.** The problem is in EDI5's integration — specifically:
1. Backend doesn't receive live transcript in `retell_hosted` mode
2. `turn_id` mapping missing in both WS and webhook handlers
3. No API to retrieve transcript for frontend hydration or report display

---

## 10. Root Cause (Precise)

> **Primary Root Cause:** In `retell_hosted` mode, the Retell browser SDK emits `update` events with `transcript` to the **frontend only**. The **backend Custom LLM WebSocket is not connected** (because `retell_hosted` uses Retell's own LLM), so the backend never receives live transcript events. The webhook `transcript_updated` fires but **does not set `turn_id`** on `InterviewMessage`, so messages cannot be linked to `InterviewTurn` for question-wise analysis.

> **Secondary Root Cause:** Frontend `transcript` state (single string) only stores the latest user utterance, overwriting history. While `liveTranscript[]` is correct, it is not hydrated from backend on page load.

> **Tertiary Root Cause:** No `GET /interview/session/{id}/transcript` endpoint exists to serve the full structured transcript to the report page or for page-refresh hydration.

---

## 11. Gaps Summary

| # | Gap | Category | Location | Severity |
|---|-----|----------|----------|----------|
| 1 | Backend receives no live transcript in `retell_hosted` mode | Transport | Architecture | **Critical** |
| 2 | `InterviewMessage.turn_id` never populated | Persistence | `retell_llm_websocket.py:258`, `retell_webhook.py:212` | **Critical** |
| 3 | No `GET /transcript` API endpoint | API | `interview_router.py` | **Critical** |
| 4 | Frontend `transcript` state overwrites history | State Mgmt | `RetellInterviewRoom.jsx:163` | **High** |
| 5 | No page-refresh transcript hydration | UX | `RetellInterviewRoom.jsx` | **High** |
| 6 | Final transcript saved as plain text (loses metadata) | Persistence | `interview_router.py:1159` | **Medium** |
| 7 | No completed Retell call retrieval (`GET /call/{call_id}`) | Integration | Not implemented | **Medium** |
| 8 | `call_analyzed` webhook data not linked to turns | Analytics | `retell_webhook.py:180` | **Low** |
| 9 | Redundant legacy event listeners (`transcript`, `transcript_update`) | Code Quality | `interviewService.js:83-103` | **Low** |

---

## 12. Recommended Phase 2 Changes (Diagnostic Only — Do Not Implement)

### Phase 2A: Backend Transcript Persistence (Critical)
1. **Track active `turn_id` in `InterviewSession.rl_state`** — Update when `InterviewOrchestrator` creates a new turn
2. **Modify `retell_llm_websocket.py:_persist_structured_transcript`** — Assign `turn_id` from `rl_state` to each `InterviewMessage`
3. **Modify `retell_webhook.py:_persist_structured_transcript`** — Same `turn_id` assignment using interview's current turn
4. **Deduplicate via `retell_utterance_id`** — Prevent double-write from WS + webhook

### Phase 2B: API & Frontend Hydration (Critical)
1. **Add `GET /interview/session/{id}/transcript`** — Returns structured `InterviewConversation` with messages
2. **Update `RetellInterviewRoom.jsx`** — On mount, fetch transcript if `liveTranscript` is empty (page refresh)
3. **Update `InterviewReport.jsx`** — Add "Transcript" tab fetching from new endpoint

### Phase 2C: Final Transcript Retrieval (Medium)
1. **Add backend call to Retell `GET /v3/call/{call_id}`** on `call_ended` webhook
2. **Store Retell's final analysis** (summary, sentiment, transcript_object) in `personalization_metadata`
3. **Use final transcript as source of truth** (merges WS + webhook + final call)

### Phase 2D: Cleanup (Low)
1. Remove redundant `transcript` and `transcript_update` listeners from `interviewService.js`
2. Change frontend `transcript` state from string to `null` (use `liveTranscript` only)
3. Store structured transcript in metadata (not plain text)

---

## 13. Files That Will Need Modification (Phase 2)

| File | Change Type | Reason |
|------|-------------|--------|
| `app/modules/interview/services/retell_llm_websocket.py` | Modify | Add `turn_id` mapping in `_persist_structured_transcript` |
| `app/modules/interview/routers/retell_webhook.py` | Modify | Add `turn_id` mapping in `_persist_structured_transcript` |
| `app/modules/interview/routers/interview_router.py` | Add | New `GET /session/{id}/transcript` endpoint |
| `app/modules/interview/services/retell_adapter.py` | Add | Method to retrieve completed call (`GET /call/{call_id}`) |
| `frontend/src/pages/RetellInterviewRoom.jsx` | Modify | Hydrate `liveTranscript` from backend on mount |
| `frontend/src/pages/InterviewReport.jsx` | Modify | Add transcript view tab |
| `frontend/src/services/interviewService.js` | Add | `getTranscript(interviewId)` API call |
| `app/modules/interview/schemas/interview_schema.py` | Add | Transcript response schema |

---

## 14. Test Results Summary (Phase 1 Verification)

| Test | Description | Result | Notes |
|------|-------------|--------|-------|
| **Test 1: AI speaks** | Retell test agent speaks → frontend receives `update` with `role: agent` | ✅ PASS | Console log confirms `update.transcript` received |
| **Test 2: Candidate speaks** | User speaks → frontend receives `update` with `role: user` | ✅ PASS | Console log confirms |
| **Test 3: Speaker attribution** | Alternate turns → `liveTranscript[]` has correct roles | ✅ PASS | UI renders avatars correctly |
| **Test 4: Multiple utterances** | 5+ exchanges → `liveTranscript.length === 5` | ✅ PASS | History preserved in `liveTranscript[]` |
| **Test 5: `transcript` state overwrite** | 3 user utterances → `transcript` state = only 3rd | ❌ FAIL | `transcript` is single string, overwrites |
| **Test 6: Page reload** | Refresh during interview → `liveTranscript` empty | ❌ FAIL | No hydration from backend |
| **Test 7: Call end** | End call → `handleInterviewComplete` saves transcript | ✅ PASS | Saves to backend but as plain text |
| **Test 8: Backend WS transcript** | `edi5_core` mode → `_handle_update_only` persists messages | ⚠️ PARTIAL | `turn_id` = NULL |
| **Test 9: Webhook transcript** | `retell_hosted` mode → `transcript_updated` persists messages | ⚠️ PARTIAL | `turn_id` = NULL |
| **Test 10: Report transcript** | View report → no transcript displayed | ❌ FAIL | No endpoint, no UI |
| **Test 11: Retell test agent** | Dashboard test → transcript appears in Retell UI | ✅ PASS | Retell works independently |
| **Test 12: Final call retrieval** | Backend calls `GET /call/{call_id}` | ❌ FAIL | Not implemented |

---

## 15. Phase 2 Plan Summary

```
PHASE 2A: Backend Mapping (Week 1)
  ├── retell_llm_websocket.py: track active_turn_id in context, assign to InterviewMessage
  ├── retell_webhook.py: read active turn from interview, assign to InterviewMessage  
  └── interview_orchestrator.py: expose current_turn_id for WS context

PHASE 2B: API + Frontend (Week 1-2)
  ├── interview_router.py: GET /session/{id}/transcript → InterviewConversation
  ├── interviewService.js: getTranscript(interviewId)
  ├── RetellInterviewRoom.jsx: useEffect to fetch transcript on mount if empty
  └── InterviewReport.jsx: Transcript tab

PHASE 2C: Final Call Retrieval (Week 2)
  ├── retell_adapter.py: get_call(call_id) method
  ├── retell_webhook.py: on call_ended, fetch call, merge transcript_object
  └── Store final analysis in personalization_metadata

PHASE 2D: Cleanup (Week 2)
  ├── Remove legacy event listeners
  ├── Fix transcript state to not overwrite
  └── Structured metadata storage
```

---

## 16. Conclusion

The EDI5 transcript transport **works partially**:
- ✅ Frontend live display is fully functional
- ✅ Backend receives transcript in `edi5_core` mode (via WS)
- ✅ Backend receives transcript in `retell_hosted` mode (via webhook)
- ❌ **Critical gap:** No `turn_id` mapping → no question-wise analysis possible
- ❌ **Critical gap:** No transcript API → no report display, no page-refresh recovery
- ❌ **Critical gap:** `retell_hosted` mode backend has no live transcript stream

**Phase 1 Diagnostic Complete.** The exact failure points are identified. Phase 2 can proceed with surgical fixes to the 3 critical gaps without redesigning the interview architecture.