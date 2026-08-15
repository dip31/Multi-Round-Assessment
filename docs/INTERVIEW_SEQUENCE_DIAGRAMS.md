# IntelliHire — Interview Sequence Diagrams (Mermaid)

## 1. Start Interview
```mermaid
sequenceDiagram
  participant FE as Frontend (5173)
  participant API as FastAPI /api/v1/interview
  participant DB as PostgreSQL
  FE->>API: POST /api/v1/interview/start {role, answer_mode}
  API->>DB: INSERT interview_sessions(...)
  DB-->>API: session_id
  API-->>FE: 201 {session_id, session_token, status: INITIALIZING}
```

## 2. Get Next Question (with RL engine flow)
```mermaid
sequenceDiagram
  participant FE as Frontend
  participant API as FastAPI
  participant RL as RL Engine
  participant LLM as Groq LLaMA
  participant DB as PostgreSQL
  FE->>API: GET /session/{id}/next-question
  API->>DB: SELECT interview_sessions WHERE id
  API->>RL: compute state string "medium|2|0|fast|high"
  RL->>DB: SELECT rl_q_table WHERE user_id & state
  alt policy guard (wrong_streak>=4)
    RL-->>API: action=decrease
  else
    RL-->>API: action sampled (epsilon-greedy)
  end
  API->>LLM: generate question (with prompt)
  LLM-->>API: JSON {question_text, difficulty}
  API->>DB: INSERT interview_questions(...)
  API-->>FE: 200 {question_id, question_text, difficulty}
```

## 3. Submit Voice Answer (STT → evaluate → RL update)
```mermaid
sequenceDiagram
  participant FE as Frontend
  participant API as FastAPI
  participant STT as Groq Whisper
  participant LLM as Groq LLaMA
  participant RL as RL Engine
  participant DB as PostgreSQL
  FE->>API: POST /session/{id}/submit-answer {answer_audio_url, response_time_ms, client_request_id}
  API->>STT: POST /stt {audio_url, format=wav}
  STT-->>API: {transcript, confidence}
  API->>LLM: POST evaluation prompt {question, transcript}
  LLM-->>API: {scores, feedback, is_correct}
  API->>RL: compute reward (weights + multipliers + time + streaks)
  RL->>DB: UPDATE rl_q_table (Bellman update), INSERT rl_attempt_log
  API->>DB: INSERT interview_answers (scores, ai_feedback)
  API-->>FE: 200 {answer_id, scores, ai_feedback, rl:{state_before,action_taken,reward,state_after}}
```

## 4. Submit Text Answer (evaluate → RL update)
```mermaid
sequenceDiagram
  FE->>API: POST /session/{id}/submit-answer {answer_text,...}
  API->>LLM: POST evaluation prompt {question, answer_text}
  LLM-->>API: {scores, feedback}
  API->>RL: derive reward
  RL->>DB: UPDATE rl_q_table, INSERT rl_attempt_log
  API->>DB: INSERT interview_answers
  API-->>FE: 200 {scores, ai_feedback, rl:...}
```

## 5. Proctoring Event
```mermaid
sequenceDiagram
  FE->>API: POST /session/{id}/proctoring-event {event_type, screenshot_url}
  API->>DB: INSERT proctoring_violations
  DB-->>API: new violation_id
  API-->>FE: 201 {violation_id, warning_number}
  alt warning_number >=3
    API->>DB: UPDATE interview_sessions status=TERMINATED
    API-->>FE: 200 {status: TERMINATED}
  end
```

## 6. Browser Refresh / Session Resume
```mermaid
sequenceDiagram
  FE(reload)->>API: GET /session/{id}/status
  API->>DB: SELECT interview_sessions
  alt session exists
    API-->>FE: 200 {status, current_question_index, answer_mode, session_token}
    FE->>API: GET /next-question (resume)
  else
    API-->>FE: 404 {error:"session_not_found"}
  end
```

## 7. End Interview + Trigger Evaluation
```mermaid
sequenceDiagram
  FE->>API: POST /session/{id}/end {reason}
  API->>DB: SELECT interview_answers WHERE session_id
  API->>LLM: optionally request summary (session transcript)
  API->>DB: INSERT interview_evaluation (aggregate scores, penalties)
  API-->>FE: 200 {evaluation_id, final_score}
```

## 8. TTS Playback Flow
```mermaid
sequenceDiagram
  FE->>API: POST /tts {text, format:wav}
  API->>TTS: Sarvam Bulbul v3 {text,voice}
  TTS-->>API: audio_blob
  API->>Storage: upload audio_blob
  Storage-->>API: audio_url
  API-->>FE: 200 {audio_url}
```
