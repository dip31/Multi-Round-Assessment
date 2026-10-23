# EDI5 Retell Transcript Finalization Fix Report

**Date:** 2026-10-13  
**Retell SDK Version:** 6.0.1  
**Issue:** `AttributeError: 'TranscriptObject' object has no attribute 'get'` during transcript finalization

---

## Root Cause

The Retell Python SDK v6.0.1 returns **Pydantic models** (`TranscriptObject`, `TranscriptObjectWord`) for the final call transcript, not plain dictionaries. The EDI5 codebase assumed the transcript was a list of dictionaries and called `.get()` on each utterance, which fails on Pydantic models with `AttributeError: 'TranscriptObject' object has no attribute 'get'`.

### Confirmed SDK Schema (v6.0.1)

```python
# retell.types.web_call_response.TranscriptObject
class TranscriptObject(BaseModel):
    content: str
    role: Literal["agent", "user", "transfer_target"]
    words: List[TranscriptObjectWord]

class TranscriptObjectWord(BaseModel):
    end: Optional[float]
    start: Optional[float]
    word: Optional[str]
```

**Key differences from assumed schema:**
- No `utterance_id`, `is_final`, `confidence`, `start_timestamp` fields
- `words` array contains word-level timing data
- Returned as Pydantic models, not plain dicts

---

## Fix Summary

### Files Modified

| File | Changes |
|------|---------|
| `app/modules/interview/services/transcript_normalizer.py` | Added `_to_dict()` helper, updated all normalization functions to handle Pydantic models |
| `tests/test_transcript_object_normalization.py` | New test suite for Pydantic model handling |
| `tests/test_webhook_pydantic_transcript.py` | New integration test for webhook handling |
| `tests/test_actual_retell_sdk.py` | Validation tests for actual SDK types |

### Core Fix: `_to_dict()` Helper

Added a reusable `_to_dict()` function in `transcript_normalizer.py` that safely converts any object to a dictionary:

```python
def _to_dict(obj: Any) -> Dict[str, Any]:
    """Safely convert an object to a dictionary.
    
    Handles:
    - Pydantic models (via model_dump() / dict())
    - Objects with __dict__ (fallback)
    - Dictionaries (pass through)
    - None (returns empty dict)
    """
```

All normalization functions now use `_to_dict()` before accessing fields:
- `extract_utterances()`
- `normalize_retell_utterance()`
- `normalize_retell_transcript()`
- `normalize_call_transcript_object()`

---

## Verification

### Test Results (43 tests passing)

| Test Suite | Tests | Status |
|------------|-------|--------|
| `test_transcript_object_normalization.py` | 9 | ✅ |
| `test_transcript_finalization.py` | 17 | ✅ |
| `test_webhook_pydantic_transcript.py` | 2 | ✅ |
| `test_actual_retell_sdk.py` | 5 | ✅ |
| `test_interview_voice_modes.py` | 3 | ✅ |
| `test_assessment_lifecycle.py` | 5 | ✅ |
| `test_proctoring_stop_service.py` | 2 | ✅ |
| **Total** | **43** | ✅ **All Pass** |

### Key Test Coverage

1. **Pydantic model handling** - All normalization functions work with Pydantic models
2. **Backward compatibility** - Plain dicts still work (webhook payloads, fixtures)
3. **Edge cases** - Empty lists, None input, transfer_target role
4. **Webhook integration** - Full pipeline from webhook → extract → normalize → persist
5. **Actual SDK types** - Verified against real `retell.types.web_call_response` models
6. **SDK compatibility** - Works with both Pydantic v1 (`dict()`) and v2 (`model_dump()`)

### Frontend Build

```
✓ built in 31.25s
```

---

## Finalization Workflow (Verified)

1. **Call retrieval** - `RetellFinalizationService._retrieve_call()` calls `client.call.retrieve()`
2. **Ownership validation** - Validates `edi5_interview_session_id` in call metadata
3. **Transcript extraction** - `extract_utterances()` handles Pydantic models via `_to_dict()`
4. **Normalization** - `normalize_call_transcript_object()` produces canonical events
5. **Reconciliation** - Matches final transcript to live messages by sequence number
6. **Persistence** - Updates/inserts `InterviewMessage` records
7. **Status update** - Marks `transcript_status = "completed"`
8. **Analysis trigger** - Background task runs `analyze_interview()` after successful finalization

### Idempotency & Retry

- ✅ Finalization is idempotent (checks `transcript_status == "completed"`)
- ✅ Failed finalization can be retried (force=True or webhook retry)
- ✅ Analysis only runs after successful finalization
- ✅ No duplicate messages (reconciliation by sequence number)
- ✅ No duplicate competency evidence (checked by `source_id` + `skill`)

---

## Live Transcript (Separate Issue)

**Note:** The backend finalization crash fix does **not** automatically fix the missing live transcript in `retell_hosted` mode. The live transcript issue is separate:

- **Live transcript source:** Browser SDK `update` events → `RetellWebCallClient` → `onTranscriptCallback` → React state
- **Current status:** Requires separate diagnosis (SDK `update` event structure, listener registration, React rendering)

The finalization fix ensures that **after the call ends**, the authoritative transcript is correctly retrieved, normalized, and persisted for analysis/reporting.

---

## Files Changed

```
M app/modules/interview/services/transcript_normalizer.py
A tests/test_transcript_object_normalization.py
A tests/test_webhook_pydantic_transcript.py
A tests/test_actual_retell_sdk.py
```

No database migrations required. No API contract changes. No `edi5_core` behavior changes.