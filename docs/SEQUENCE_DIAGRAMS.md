# Sequence Diagrams

These diagrams are intentionally detailed because agents use them to understand the actual control flow.

## Aptitude Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant A as API
    participant R as RL Engine
    participant D as DB

    F->>A: GET next question
    A->>D: load session + attempt history
    D-->>A: session state
    A->>R: request next difficulty
    R-->>A: selected question / difficulty
    A->>D: persist rl session state
    A-->>F: question payload
```

## Coding Submit Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant A as API
    participant J as Judge0
    participant E as Evaluator
    participant D as DB

    F->>A: POST submit code
    A->>D: validate session + assigned problem
    D-->>A: session and test cases
    A->>E: evaluate_submission(code, cases)
    loop each test case
        E->>J: submit source (wait=true)
        J-->>E: stdout / verdict / stats
    end
    E-->>A: verdict + score + metrics
    A->>D: store coding_submissions row
    A-->>F: synchronous submission response
```

## Interview Flow

```mermaid
sequenceDiagram
    participant C as Candidate
    participant F as Frontend
    participant A as API
    participant S as STT
    participant R as RAG
    participant L as LLM
    participant E as Evaluation
    participant RL as RL Engine

    C->>F: speak response
    F->>S: transcribe audio
    S-->>F: transcript
    F->>A: submit response + transcript
    A->>R: retrieve context
    R-->>A: retrieved context
    A->>L: generate next question
    L-->>A: question text
    A->>E: score response
    E-->>A: evaluation
    A->>RL: update adaptive policy
    RL-->>A: next question strategy
    A-->>F: next question
```

## Session Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API
    participant D as DB

    U->>F: login
    F->>A: register/login
    A->>D: create or verify user
    A-->>F: JWT
    F->>A: start assessment session
    A->>D: create assessment session + rounds
    A-->>F: session payload
```
