# EDI5 Retell Hosted Live Transcript — Diagnosis

**Date:** 2026-10-13  
**SDK Version:** `retell-client-js-sdk@3.0.2` (legacy `RetellWebClient`)

---

## 1. Current Architecture

### 1.1 Frontend SDK (`frontend/src/services/interviewService.js`)
- Uses legacy `RetellWebClient` from `retell-client-js-sdk@3.0.2`
- Listens for events: `update`, `transcript`, `transcript_update`, `data`, `agent_start_talking`, `agent_stop_talking`, `call_ended`, `call_ready`, `error`, `metadata`
- **Problem**: Only `update` event actually exists on the legacy client. Events `transcript`, `transcript_update`, `data` **do not exist**.

### 1.2 Backend Webhook (`app/modules/interview/routers/retell_webhook.py`)
- Receives Retell webhooks: `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, `transfer_*`
- On `transcript_updated`: extracts utterances, normalizes, broadcasts to frontend via WebSocket
- **Problem**: Duplicates frontend SDK live transcript

### 1.3 Frontend WebSocket (`app/modules/interview/routers/transcript_websocket.py`)
- Broadcasts canonical transcript events to frontend
- Frontend (`RetellInterviewRoom.jsx`) connects to `WS /api/v1/interview/session/{id}/transcript`
- Receives `transcript`, `transcript_final`, `transcript_clear` messages

### 1.4 Frontend Component (`RetellInterviewRoom.jsx`)
- Maintains `liveTranscript` state array
- `handleTranscriptUpdate` merges by `turn_id` (fallback to timestamp)
- Renders transcript with speaker avatars, interim/final indicators

---

## 2. Retell SDK Event Reality (Verified from Source)

### 2.1 Legacy `RetellWebClient` Events (Actual)
| Event | Payload | Carries Transcript? |
|-------|---------|---------------------|
| `call_started` | none | No |
| `call_ready` | `{ analyzer }` | No |
| `call_ended` | none | No |
| `error` | `string` | No |
| `update` | `{ event_type: "update", transcript: Utterance[], turntaking?: "agent_turn" \| "user_turn" }` | **YES** |
| `metadata` | `{ event_type: "metadata", metadata: ... }` | No |
| `agent_start_talking` | none | No |
| `agent_stop_talking` | none | No |
| `node_transition` | `{ event_type: "node_transition", ... }` | No |
| `audio` | `Float32Array` | No |

**Events that DO NOT EXIST**: `transcript`, `transcript_update`, `data`, `disconnected`

### 2.2 `UpdateEvent` Payload Structure
```typescript
interface UpdateEvent {
    event_type: "update";
    transcript: Utterance[];  // FULL cumulative snapshot each time
    turntaking?: "agent_turn" | "user_turn";
}

interface Utterance {
    role: "agent" | "user" | "transfer_target";
    content: string;
    metadata?: {
        is_backchannel?: boolean;
        response_id?: number;
        interrupt_id?: number;
    };
}
```

**Critical Observations:**
- **No `is_final` field** on base `Utterance`
- **No `id`/`utterance_id`** on base `Utterance` (only on `LiveCallUtterance` which adds `id: string`, `time_sec: number`)
- SDK sends **complete transcript array** on every `update` (cumulative snapshot)
- Interim vs final determination: NOT available from SDK directly

---

## 3. Root Cause Analysis

### 3.1 Duplicate Transcript Sources
Two independent paths push transcript to the same `liveTranscript` state:

| Path | Source | Trigger | Broadcasts To |
|------|--------|---------|---------------|
| A | Frontend SDK `update` event | Every partial STT result | `liveTranscript` via `onTranscriptCallback` |
| B | Backend webhook `transcript_updated` | Retell server webhook | Frontend WS → `liveTranscript` |

**Result**: Each utterance appears twice (once from SDK, once from webhook→WS)

### 3.2 Incorrect Normalization
`interviewService.js:_normalizeTranscript` assumes fields that don't exist:
```javascript
is_final: u.is_final !== false,      // Utterance has NO is_final
utterance_id: u.id || u.utterance_id || idx  // Utterance has NO id/utterance_id
```

### 3.3 No Deduplication of Cumulative Snapshots
SDK sends **full transcript array** on every `update`. Current code treats each event as incremental, causing:
- Same utterances appended repeatedly
- `handleTranscriptUpdate` deduplicates by `turn_id` but SDK provides no stable ID
- Fallback to `idx` breaks when array grows (same utterance gets new index each event)

### 3.4 Backend Webhook Unnecessary for Live UI
For `retell_hosted`, the webhook `transcript_updated` fires concurrently with frontend SDK `update` events. Backend persistence is valuable, but **live UI should use SDK as authoritative source** to avoid round-trip latency and duplicates.

---

## 4. Proposed Fix (Minimal, Hosted-Only)

### 4.1 Frontend SDK Layer (`interviewService.js`)
1. **Remove non-existent event listeners**: `transcript`, `transcript_update`, `data`
2. **Fix normalization**: Map only existing fields (`role`, `content`, `metadata`)
3. **Add cumulative snapshot deduplication**: Track last seen transcript length/fingerprint
4. **Expose normalized callback**: `onTranscript(utterances[])` with stable shape

### 4.2 Frontend Component (`RetellInterviewRoom.jsx`)
1. **For `retell_hosted` mode ONLY**: Use SDK callback as **sole live transcript source**
2. **Disable backend WS transcript handling** when `voiceMode === 'retell_hosted'`
3. **Reconcile cumulative snapshots**: Replace entire `liveTranscript` with normalized SDK array
4. **Preserve `edi5_core` behavior**: Keep WS + existing logic unchanged

### 4.3 Backend Webhook (`retell_webhook.py`)
1. **Keep persistence**: Continue saving `transcript_updated` to DB for finalization
2. **Stop broadcasting to WS** for `retell_hosted` interviews (or make it conditional)
3. **Keep `call_ended`/`call_analyzed` handling** for finalization

### 4.4 Reconciliation Strategy
Since SDK provides no stable IDs or finality flags:
- **Snapshot reconciliation**: Each `update` event replaces entire transcript array
- **Visual interim indication**: Use `turntaking` field (`user_turn` = candidate speaking = likely interim)
- **Finalization**: Rely on backend final call retrieval (`call.retrieve()`) for authoritative final transcript

---

## 5. Files to Modify

| File | Change |
|------|--------|
| `frontend/src/services/interviewService.js` | Fix normalization, remove ghost listeners, add snapshot dedup |
| `frontend/src/pages/RetellInterviewRoom.jsx` | Hosted-mode SDK-only transcript path; disable WS transcript for hosted |
| `app/modules/interview/routers/retell_webhook.py` | Conditional broadcast (skip for hosted mode) |

---

## 6. Verification Plan

1. **Unit test**: Mock SDK `update` events → verify normalized output shape
2. **Integration test**: Simulate cumulative snapshots → verify no duplicates in `liveTranscript`
3. **Mode isolation**: Verify `edi5_core` still uses WS + existing logic
4. **Live test**: Run `retell_hosted` interview → confirm live transcript appears, no duplicates, interim updates visible