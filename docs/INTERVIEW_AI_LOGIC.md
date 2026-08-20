# IntelliHire — Interview AI Logic (Round 3)

## Question Generation Pipeline
- Primary path: Backend constructs a Groq generation prompt and calls Groq using LLaMA 3.1 70B versatile to generate question text, difficulty, category, and optional TTS text.
- Prompt construction:
  - System role: "You are IntelliHire's structured interview question generator. Respond only in JSON."
  - User prompt includes structured fields:
    - role: `{role}` (from `interview_sessions.role`)
    - difficulty_hint: current RL-decided difficulty (`easy|medium|hard`)
    - category: optional category seed (e.g., `algorithms`)
    - history: last 3 Q/A summaries (short) to avoid repetition
    - constraints: time_limit (seconds), no open-ended legal/PII asks.
  - Example user prompt payload:
    {
      "role":"backend_engineer",
      "difficulty_hint":"medium",
      "category":"systems",
      "history":[{"q":"...","a_summary":"..."}]
    }
- How previous answers influence next question:
  - Candidate topic_accuracy_bin and correct/wrong streaks part of state.
  - If topic_accuracy_bin == "low", generator is instructed to probe same topic or generate simpler follow-up.
  - If correct_streak high, generator may produce deeper probe or broaden scope.
- Fallback question bank trigger:
  - If Groq API returns error, empty payload, or rate-limited: pull pre-seeded fallback bank (local JSON file) and mark `source: 'fallback'` in `interview_questions`.

## Answer Evaluation Pipeline
- Multi-dimensional scoring:
  - For each answer evaluate: `technical`, `communication`, `confidence`, `problem_solving` (each 0–10).
  - LLM prompt asks for numeric scores and short textual feedback for each dimension and an overall `is_correct` boolean where applicable.
- Mapping scores to RL reward:
  - Compute per-question weighted total using weights: technical 0.4, communication 0.2, confidence 0.2, problem_solving 0.2.
  - Convert per-question total (0–10 weighted average) to reward: reward_base = (total / 10) * difficulty_multiplier (easy×0.5, medium×1.0, hard×1.5).
  - Apply time bonus and streak modifier, then clamp to [-3.0, 3.0].
  - Example: total=8.0 on `medium` → reward_base=8.0/10*1.0=0.8; time bonus +0.2 → 1.0; clamp → 1.0.
- LLM output parsing and validation:
  - Expect strict JSON. If missing keys or parsing fails, use default rubric (5/10 each) and log parsing error.
  - Validation steps:
    - Ensure numeric fields within 0–10.
    - `is_correct` as boolean.
    - `feedback` string <= 2000 chars.
    - If `topic` key missing (known bug), check `topic is None` before filtering to avoid incorrect `topic_accuracy_bin`.

## Follow-up Question Logic
- When to generate follow-up:
  - If `is_correct` == false AND technical score >= 4 → generate a focused follow-up (probe depth surface→probe).
  - If `is_correct` true but `problem_solving` < 6 → generate a deeper probe.
  - Do not generate follow-up if question was marked `is_skipped`.
- Depth levels:
  - Surface: Clarifying question, <30s expected.
  - Probe: Requires brief code explanation or design sketch, 30–90s.
  - Deep: Multi-step design or algorithm, 90–180s.
- Follow-ups are treated as new `question_index` entries with a `category` of `followup` and difficulty adjusted by RL action.

## Context Memory Strategy
- What is kept in LLM context window:
  - Last 3 question/answer summaries (each ≤ 120 tokens).
  - Session role and current difficulty.
  - Last RL decision summary (state_before, action_taken).
- Transcript summarization:
  - Full raw transcripts stored in DB; before each Groq call we compress transcripts to bullet summaries using a summarization prompt to prevent token overflow.
  - Summaries trimmed to ensure total token usage <= configured max_tokens per call.

## Groq API Usage
- Model: `llama-3.1-70b-versatile`.
- Default settings (per call):
  - Temperature: 0.2 for evaluation tasks, 0.7 for creative/question-generation tasks.
  - max_tokens:
    - Evaluation: 512
    - Generation: 1024
    - Summarization: 256
- Rate limit handling:
  - If provider returns 429, backend enqueues request, returns `202 Accepted` to frontend with `retry_after`.
  - Queue worker retries with exponential backoff; frontend shows loading spinner and message "Generating question...".
  - If retry limit exceeded, use fallback question bank.

## STT Pipeline (Groq Whisper)
- Audio format requirements:
  - WAV, PCM 16-bit, 16kHz, mono.
  - Max file size: 8 MB.
- REST call format:
  - POST to /stt provider endpoint with `audio_url` and `format=wav`.
- Timeout and fallback:
  - STT timeout set to 10 seconds; if duration >10s or provider 504, fallback to text input mode and log `stt_timeout=true`.
  - If confidence < 0.5, mark transcription as low-confidence and request text confirmation from candidate (frontend).

## TTS Pipeline (Sarvam Bulbul v3)
- REST call format:
  - POST JSON: {"text":"...", "voice":"default", "format":"wav", "sample_rate":16000}
  - Backend stores returned audio blob to object storage and returns `audio_url`.
- Audio buffering strategy:
  - Generate and buffer pre-fetch TTS for the next question after current evaluation completes.
  - Keep TTS files for session TTL (30 minutes) and delete via background cleanup job.
- Failure fallback:
  - If TTS fails or provider 503, frontend shows question text with visual emphasis and continues silently; log `tts_failure` in analytics.
