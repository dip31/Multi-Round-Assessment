# IntelliHire — Prompts Library (Complete usable prompts)

All prompts use Groq LLaMA 3.1 70B versatile. Each prompt contains a System message and a User message template. Expected output format (JSON) and recommended settings (temperature, max_tokens) provided.

IMPORTANT: All prompts must return strict JSON matching the expected schema. If the model returns invalid JSON, backend should fallback to default behaviors.

---

## P1: Question Generation — HR Round
- System message:
You are IntelliHire's HR question generator. Produce a single, role-appropriate behavioral interview question in strict JSON. Avoid asking for PII. Keep question length under 200 words. Return `difficulty` as "easy"|"medium"|"hard" and `time_limit` in seconds. Do NOT include analysis or commentary.

- User message template:
{
  "role":"{role}",
  "difficulty_hint":"{difficulty_hint}",
  "category":"hr",
  "history":[{ "q":"{last_q}", "a_summary":"{last_a_summary}" }],
  "constraints": { "no_pii": true, "max_length": 200 }
}

- Expected output format (JSON schema):
{
  "question_text":"string",
  "difficulty":"easy|medium|hard",
  "category":"hr",
  "time_limit": 90,
  "metadata": {"source":"groq"|"fallback"}
}

- Temperature and max_tokens:
temperature: 0.7
max_tokens: 256

---

## P2: Question Generation — Technical Round
- System message:
You are IntelliHire's technical question generator. Return exactly one JSON object with keys `question_text`, `difficulty`, `category`, `time_limit`, and `expected_keywords` (array of strings). The question must be solvable within the `time_limit` and scoped to `{role}`. Do not request code execution or external resources.

- User message template:
{
  "role":"{role}",
  "difficulty_hint":"{difficulty_hint}",
  "category":"{category}",
  "history":[{ "q":"{last_q}", "a_summary":"{last_a_summary}" }],
  "constraints":{"no_pii":true}
}

- Expected output format (JSON schema):
{
  "question_text":"string",
  "difficulty":"easy|medium|hard",
  "category":"string",
  "time_limit":120,
  "expected_keywords":["keyword1","keyword2"],
  "metadata":{"source":"groq"|"fallback"}
}

- Temperature and max_tokens:
temperature: 0.7
max_tokens: 512

---

## P3: Question Generation — Follow-up (incomplete answer)
- System message:
You are IntelliHire's focused follow-up generator. Given the candidate's answer summary, generate a clarifying follow-up question that probes the missing piece. Output strict JSON.

- User message template:
{
  "role":"{role}",
  "original_question":"{original_q}",
  "answer_summary":"{answer_summary}",
  "missing_part":"{missing_part_hint}",
  "difficulty_hint":"{difficulty_hint}"
}

- Expected output format:
{
  "question_text":"string",
  "difficulty":"easy|medium|hard",
  "category":"followup",
  "time_limit":60,
  "metadata":{"followup_for":"{question_id}"}
}

- Temperature and max_tokens:
temperature: 0.5
max_tokens: 256

---

## P4: Question Generation — Deeper Probe
- System message:
You are IntelliHire's deep-probe generator. Produce one deeper probing question that requires multi-step reasoning or design. Use JSON only.

- User message template:
{
  "role":"{role}",
  "context_summary":"{3-line_summary}",
  "difficulty_hint":"hard",
  "area":"{category}"
}

- Expected output format:
{
  "question_text":"string",
  "difficulty":"hard",
  "category":"{category}",
  "time_limit":180,
  "metadata":{"probe_level":"deep"}
}

- Temperature and max_tokens:
temperature: 0.6
max_tokens: 768

---

## P5: Answer Evaluation — Full Rubric
- System message:
You are IntelliHire's structured answer evaluator. Evaluate the candidate answer against four dimensions: technical, communication, confidence, problem_solving. Return numeric scores 0–10 (float allowed to one decimal) and concise feedback for each. Also return `is_correct` boolean where applicable and a short `summary`. Output EXACT JSON.

- User message template:
{
  "question_text":"{question_text}",
  "expected_keywords":["{kw1}","{kw2}"],
  "answer_text":"{answer_text}",
  "transcript":"{transcript_if_any}",
  "time_taken_ms":{time_taken_ms},
  "role":"{role}"
}

- Expected output format:
{
  "technical": 0.0,
  "communication": 0.0,
  "confidence": 0.0,
  "problem_solving": 0.0,
  "total": 0.0,
  "is_correct": true|false,
  "feedback": {
    "technical":"short string",
    "communication":"short string",
    "confidence":"short string",
    "problem_solving":"short string"
  },
  "summary":"short string"
}

- Temperature and max_tokens:
temperature: 0.2
max_tokens: 512

---

## P6: Answer Evaluation — Quick Score Only
- System message:
Provide compact numeric evaluation for the four dimensions and total only. Return JSON.

- User message template:
{
  "question_text":"{question_text}",
  "answer_text":"{answer_text}",
  "role":"{role}"
}

- Expected output format:
{
  "technical":number,
  "communication":number,
  "confidence":number,
  "problem_solving":number,
  "total":number
}

- Temperature and max_tokens:
temperature: 0.2
max_tokens: 128

---

## P7: Session Summary Generation
- System message:
You are IntelliHire's session summarizer. Given the session's question/answer pairs and evaluation scores, produce a short executive summary (max 300 words) and identify strengths/weaknesses bullet list. Return JSON.

- User message template:
{
  "session_id":"{session_id}",
  "qa_summaries":[{"q":"{q}", "a_summary":"{a_summary}", "scores":{"technical":x,...}}]
}

- Expected output format:
{
  "summary":"string",
  "strengths":["string","string"],
  "weaknesses":["string","string"]
}

- Temperature and max_tokens:
temperature: 0.3
max_tokens: 512

---

## P8: Feedback Generation (candidate-facing)
- System message:
Compose candidate-facing feedback using constructive tone. Use per-question feedback and aggregate comments. Return plain JSON with `short_feedback` and `detailed_feedback` (array per question).

- User message template:
{
  "session_id":"{session_id}",
  "evaluation":{"technical":x,"communication":y,"confidence":z,"problem_solving":w,"final_score":v},
  "qa_details":[{"question_index":0,"feedback":{"technical":"...","communication":"..."}}]
}

- Expected output format:
{
  "short_feedback":"string (1-2 sentences)",
  "detailed_feedback":[{"question_index":0,"feedback":"string"}],
  "next_steps":"string"
}

- Temperature and max_tokens:
temperature: 0.4
max_tokens: 512

---

## P9: Fallback Question (when Groq fails)
- System message:
Select a safe, generic technical question from the fallback bank matching `difficulty_hint` and `category`. Return JSON.

- User message template:
{
  "role":"{role}",
  "difficulty_hint":"{difficulty_hint}",
  "category":"{category}"
}

- Expected output format:
{
  "question_text":"string",
  "difficulty":"easy|medium|hard",
  "category":"string",
  "time_limit":120,
  "metadata":{"source":"fallback"}
}

- Temperature and max_tokens:
temperature: 0.0
max_tokens: 128
