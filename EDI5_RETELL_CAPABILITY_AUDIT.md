# EDI5 Retell Capability Audit

**Date**: 2026-09-30  
**Retell API Version**: 2026-09-14-b240eb0  
**Purpose**: Document verified Retell capabilities for EDI5 integration

---

## Verified Capabilities

### 1. Web Call Creation (`POST /v3/create-web-call`)
- **Mechanism**: REST API endpoint
- **EDI5 Usage**: Create real-time voice session when candidate starts interview
- **Input**: `agent_id`, optional `agent_override`, `metadata`, `retell_llm_dynamic_variables`
- **Output**: `call_id`, `access_token`, `transport` (gateway), `ice_servers` (STUN/TURN), `expires_at`
- **Latency**: ~200-500ms API call
- **Limitations**: Requires pre-created agent; access token expires (need refresh for long sessions)

### 2. Custom LLM WebSocket (`wss://{your-server}/{call_id}`)
- **Mechanism**: Bidirectional WebSocket protocol
- **EDI5 Usage**: Primary integration path - EDI5 acts as custom LLM server
- **Retell → EDI5 Events**:
  - `call_details` - Initial call metadata (if enabled in config)
  - `update_only` - Live transcript updates, turntaking (`agent_turn`/`user_turn`)
  - `response_required` - Ask EDI5 for response content
  - `reminder_required` - User silent, need reminder
  - `ping_pong` - Keepalive (if `auto_reconnect=true`)
- **EDI5 → Retell Events**:
  - `config` - Configure auto_reconnect, call_details, transcript_with_tool_calls
  - `response` - Stream response content with `response_id`, `content_complete`
  - `agent_interrupt` - Immediate interruption with `interrupt_id`
  - `update_agent` - Modify responsiveness, interruption_sensitivity mid-call
  - `tool_call_invocation` / `tool_call_result` - Bookkeep function calls
  - `metadata` - Forward data to frontend (avatar emotion, etc.)
- **Latency**: Sub-100ms for WebSocket round-trip; streaming responses reduce perceived latency
- **Limitations**: 
  - Must respond to `response_required` within Retell's timeout
  - Connection management (reconnection) is manual
  - No built-in STT - Retell handles STT, sends transcript

### 3. Agent Override (`agent_override` in create-web-call)
- **Mechanism**: Per-call agent configuration override
- **EDI5 Usage**: Map EDI5 interviewer profiles to Retell voice/persona per session
- **Overridable Fields**:
  - `agent.voice_id`, `agent.voice_model`, `agent.voice_speed`, `agent.voice_emotion`
  - `agent.enable_expressive_mode`, `agent.expressive_emotion_tags`
  - `agent.responsiveness`, `agent.interruption_sensitivity`
  - `agent.enable_backchannel`, `agent.backchannel_frequency`
  - `retell_llm.model`, `retell_llm.model_temperature`, `retell_llm.begin_message`
  - `conversation_flow` settings (if using flow)
- **Latency**: Applied at call creation, no runtime overhead
- **Limitations**: Cannot change voice mid-call (requires new call)

### 4. Webhooks (`webhook_url` per agent or account-level)
- **Mechanism**: HTTP POST to EDI5 endpoint
- **EDI5 Usage**: Session lifecycle tracking, audit trail, async processing
- **Events**: `call_started`, `call_ended`, `call_analyzed`, `transcript_updated`, transfer events
- **Payload**: Full call object including transcript, metadata, recording URLs
- **Security**: `x-retell-signature` header for verification
- **Idempotency**: Retell retries up to 3x with 10s timeout; must deduplicate by `event` + `call_id`
- **Latency**: Async, not in critical path
- **Limitations**: 
  - `transcript_updated` fires many times - not for deduplication
  - Webhook endpoint must be publicly accessible (no localhost)

### 5. Custom LLM Response Engine (`type: "custom-llm"`)
- **Mechanism**: Agent configuration with `llm_websocket_url`
- **EDI5 Usage**: Deploy EDI5 WebSocket server as custom LLM endpoint
- **Configuration**: `llm_websocket_url` (e.g., `wss://edi5.example.com/retell/llm/{call_id}`)
- **Latency**: Adds one network hop (Retell → EDI5 WebSocket)
- **Limitations**: 
  - EDI5 must host WebSocket server accessible to Retell
  - No built-in load balancing - single URL per agent

### 6. Dynamic Variables (`retell_llm_dynamic_variables`)
- **Mechanism**: Key-value strings injected into agent prompt at call creation
- **EDI5 Usage**: Pass candidate name, interview type, interviewer persona
- **Format**: `{"candidate_name": "John", "interview_type": "technical", "interviewer": "Arjun"}`
- **Latency**: Resolved at call creation
- **Limitations**: String values only; no complex objects

### 7. Function Calling (Custom Functions)
- **Mechanism**: LLM decides to call function → EDI5 executes → returns result
- **EDI5 Usage**: Could implement `end_interview`, `get_candidate_context` tools
- **Types**: Custom functions (HTTP), Code Tool (JS sandbox), Integration tools
- **Latency**: Additional round-trip for function execution
- **Limitations**: Function execution is synchronous from LLM perspective

### 8. Voice Providers & Models
- **Providers**: ElevenLabs, Cartesia, Minimax, OpenAI (gpt-4o-mini-tts), PlayHT, Inworld, etc.
- **Models**: `eleven_flash_v2`, `eleven_multilingual_v2`, `sonic-3`, `speech-02-turbo`, etc.
- **EDI5 Usage**: Map interviewer profiles to specific voice_ids
- **Voices Available**: 
  - `retell-Cimo`, `retell-Jessica`, `retell-Eric`, etc. (Retell platform voices)
  - ElevenLabs: `eleven-Cimo`, `eleven-Jessica`, etc.
  - Cartesia: `cartesia-Cimo`, etc.
  - Minimax: `minimax-Cimo`, etc.
- **Limitations**: Voice selection per agent; fallback_voice_ids for provider outages

### 9. Expressive Mode & Emotion Tags
- **Mechanism**: `enable_expressive_mode=true` + `expressive_emotion_tags`
- **EDI5 Usage**: Natural conversational delivery per interviewer persona
- **Tags**: `empathetic`, `excited`, `happy`, `curious`, `surprised`, `sigh`, `clear throat`, `pause`, `long pause`, `emphasis`
- **Latency**: No additional latency
- **Limitations**: Only for platform voices (Retell, Cartesia, Minimax)

### 10. Interruption & Barge-in
- **Mechanism**: `interruption_sensitivity` (0-1), `agent_interrupt` event
- **EDI5 Usage**: Natural conversation flow; EDI5 can interrupt via `agent_interrupt`
- **Latency**: Handled by Retell's audio pipeline
- **Limitations**: `interruption_sensitivity=0` disables interruption entirely

### 11. Backchanneling
- **Mechanism**: `enable_backchannel`, `backchannel_frequency`, `backchannel_words`
- **EDI5 Usage**: Natural "yeah", "uh-huh" during candidate responses
- **Limitations**: Only works with certain voices

### 12. Metadata Event (Frontend Communication)
- **Mechanism**: EDI5 sends `metadata` event → Retell forwards to frontend via Audio WebSocket
- **EDI5 Usage**: Send interviewer avatar emotion, turn indicators to frontend
- **Latency**: Sub-100ms via WebSocket

---

## Missing / Limited Capabilities

| Capability | Status | Workaround |
|------------|--------|------------|
| Mid-call voice change | ❌ Not supported | Create new call with different agent_override |
| Real-time STT streaming to EDI5 | ⚠️ Partial | `update_only` events include transcript |
| EDI5-controlled turn-taking | ⚠️ Partial | `response_required` triggered by Retell's VAD |
| Persistent WebSocket across calls | ❌ No | New WebSocket per call_id |
| WebRTC stats / quality metrics | ⚠️ Via webhook | Post-call analysis |
| Agent state persistence | ❌ No | EDI5 must maintain state externally |

---

## Architecture Decision: Custom LLM WebSocket vs Agent Override

### Option A: Custom LLM WebSocket (Recommended)
- EDI5 hosts WebSocket server at `wss://edi5.example.com/retell/llm/{call_id}`
- Agent configured with `response_engine: {type: "custom-llm", llm_websocket_url: "wss://..."}`
- Full control: EDI5 receives transcript, decides response, streams back
- Supports `agent_interrupt`, `update_agent`, `metadata` events
- **Best for**: EDI5 as authoritative interview brain

### Option B: Retell LLM + Agent Override + Functions
- Use `retell-llm` response engine with detailed prompt
- Override `begin_message`, `model_temperature`, `dynamic_variables` per call
- Use custom functions for EDI5 decisions
- **Best for**: Simpler deployments, but less control

**Recommendation**: **Option A (Custom LLM WebSocket)** - Keeps EDI5 as single source of truth for interview intelligence.

---

## EDI5 Integration Mapping

| EDI5 Component | Retell Mechanism |
|----------------|------------------|
| InterviewSession creation | `create-web-call` + metadata |
| Interviewer selection | `agent_override.voice_id` + dynamic variables |
| Candidate transcript | `update_only` / `response_required` events |
| Answer understanding | EDI5 processes transcript |
| Follow-up decision | EDI5 decides → streams `response` |
| Next question | EDI5 decides → streams `response` |
| Interviewer persona wording | EDI5 generates → Retell delivers via TTS |
| Voice/TTS | `agent_override.voice_id` + expressive mode |
| Session end | `response` with `end_call: true` |
| State persistence | EDI5 database (InterviewSession, InterviewTurn) |
| Audit/analytics | Webhooks (`call_ended`, `call_analyzed`) |

---

## Latency Implications

| Stage | Current (Groq STT + Sarvam TTS) | Retell (Custom LLM WS) | Notes |
|-------|--------------------------------|------------------------|-------|
| Speech end → Transcript | ~400-800ms (Groq Whisper) | ~200-400ms (Retell STT) | Retell uses fast STT mode |
| Transcript → EDI5 | HTTP POST ~50-100ms | WS ~20-50ms | WebSocket lower overhead |
| Answer Understanding | ~300ms (Groq LLM) | ~300ms (same) | Same LLM call |
| Question Planning | ~10ms | ~10ms | Same |
| Decision → Speech | ~500-1000ms (Sarvam TTS) | ~200-400ms (Retell TTS) | Retell streams audio |
| **Total Perceived** | **~1200-2200ms** | **~700-1200ms** | ~40-50% improvement |

---

## Security Considerations

1. **API Keys**: Store `RETELL_API_KEY` in backend only (settings)
2. **Webhook Verification**: Use `retell.verify(raw_body, api_key, signature)`
3. **WebSocket Auth**: `call_id` in path validates session
4. **Metadata**: Pass `edi5_interview_session_id`, `candidate_id` in call metadata
5. **Frontend Token**: `access_token` from create-web-call is short-lived (JWT)

---

## Next Steps

1. **Phase 0**: ✅ Capability audit complete
2. **Phase 1**: Create `retell_adapter.py` - isolated integration layer
3. **Phase 2**: Session mapping (EDI5 InterviewSession ↔ Retell call_id)
4. **Phase 3**: Custom LLM WebSocket server in EDI5
5. **Phase 4**: Transcript → EDI5 pipeline
6. **Phase 5**: EDI5 decision → Retell response streaming
7. **Phase 6**: Interviewer profile → Retell voice mapping
8. **Phase 7**: Frontend Web Call SDK integration
9. **Phase 8**: Feature flag (legacy vs retell voice provider)
10. **Phase 9**: Performance testing & latency measurement