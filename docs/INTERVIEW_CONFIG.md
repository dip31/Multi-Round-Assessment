# IntelliHire — Interview Configuration Reference

List of configurable parameters. Defaults reflect safe production settings.

## Session Config
- VARIABLE: `INTELLIHIRE_MAX_QUESTIONS`
  - Default: `10`
  - Allowed: integer >=1 and <=100
  - What breaks: UI and RL loops assume max 10; setting <1 disables interview; >100 may cause long sessions.
- VARIABLE: `INTELLIHIRE_MAX_DURATION_SECONDS`
  - Default: `1800` (30 minutes)
  - Allowed: integer >=60 and <=10800
  - What breaks: shorter than 60s undermines session; longer may prevent auto-termination logic.

## RL Engine Config
- VARIABLE: `RL_ALPHA`
  - Default: `0.1`
  - Allowed: float between 0.0 and 1.0
  - What breaks: 0 disables learning; >1 unstable updates.
- VARIABLE: `RL_GAMMA`
  - Default: `0.9`
  - Allowed: float 0.0–1.0
  - What breaks: out-of-range yields incorrect discounting.
- VARIABLE: `RL_EPSILON_START`
  - Default: `0.30`
  - Allowed: float 0.0–1.0
  - What breaks: 0 disables exploration.
- VARIABLE: `RL_EPSILON_MIN`
  - Default: `0.05`
  - Allowed: float 0.0–1.0
  - What breaks: <0 or >1 invalid.
- VARIABLE: `RL_EPSILON_DECAY`
  - Default: `0.995`
  - Allowed: 0.0 < float <1.0
  - What breaks: >=1 will not decay.
- VARIABLE: `RL_OPTIMISTIC_INIT`
  - Default: `0.1`
  - Allowed: float
  - What breaks: very large values bias policy.

## AI Model Config
- VARIABLE: `GROQ_MODEL`
  - Default: `llama-3.1-70b-versatile`
  - Allowed: provider-supported model strings
  - What breaks: unsupported model causes provider errors.
- VARIABLE: `GROQ_TEMP_EVAL`
  - Default: `0.2`
  - Allowed: 0.0–1.0
  - What breaks: high values produce inconsistent evals.
- VARIABLE: `GROQ_TEMP_GEN`
  - Default: `0.7`
  - Allowed: 0.0–1.0
- VARIABLE: `GROQ_MAX_TOKENS_EVAL`
  - Default: `512`
  - Allowed: integer > 0
- VARIABLE: `GROQ_RATE_LIMIT_RETRIES`
  - Default: `5`
  - Allowed: integer >=0
  - What breaks: 0 disables retrying on 429.

## Proctoring Config
- VARIABLE: `PROCTORING_MAX_WARNINGS`
  - Default: `3`
  - Allowed: integer >=1
  - What breaks: lower values may false-terminate; higher values weaken enforcement.
- VARIABLE: `PROCTORING_WEBCAM_MISSING_THRESHOLD_SECONDS`
  - Default: `10`
  - Allowed: integer >=1
  - What breaks: too small triggers false positives.
- VARIABLE: `PROCTORING_FACE_CHECK_INTERVAL_SECONDS`
  - Default: `5`
  - Allowed: integer >=1
  - What breaks: <1 increases CPU/energy on client devices.

## Scoring Config
- VARIABLE: `SCORE_WEIGHT_TECHNICAL`
  - Default: `0.4` (40%)
  - Allowed: float 0.0–1.0; sum of weights must equal 1.0 across dimensions.
  - What breaks: weights that do not sum to 1.0 break normalization.
- VARIABLE: `SCORE_WEIGHT_COMMUNICATION`
  - Default: `0.2`
- VARIABLE: `SCORE_WEIGHT_CONFIDENCE`
  - Default: `0.2`
- VARIABLE: `SCORE_WEIGHT_PROBLEM_SOLVING`
  - Default: `0.2`
- VARIABLE: `PENALTY_PER_WARNING`
  - Default: `2` (points)
  - Allowed: integer >=0

## Database Config
- VARIABLE: `DATABASE_URL`
  - Default: `postgresql+asyncpg://<user>:<pass>@<host>:5432/intellihire`
  - Allowed: valid SQLAlchemy connection URLs
  - What breaks: incorrect dialect or missing driver causes DB connectivity errors.
- VARIABLE: `SQLALCHEMY_ECHO`
  - Default: `false`
  - Allowed: boolean
- VARIABLE: `RL_QTABLE_PERSIST_EPSILON`
  - Default: `false` (known limitation: epsilon in-memory)
  - Allowed: boolean
  - What breaks: true requires schema migration to add epsilon column.

## API Keys
- VARIABLE: `GROQ_API_KEY`
  - Default: `""` (must be set)
  - Allowed: provider API key string
  - What breaks: unset key causes LLM failures.
- VARIABLE: `SARVAM_TTS_KEY`
  - Default: `""` (must be set)
- VARIABLE: `S3_BUCKET_URL`
  - Default: `""` (must be set for audio storage)

## Frontend Config
- VARIABLE: `FRONTEND_PORT`
  - Default: `5173`
  - Allowed: integer > 1024
  - What breaks: port conflicts with other services.
- VARIABLE: `API_BASE_PATH`
  - Default: `/api/v1/interview`
  - Allowed: string path starting with `/`
  - What breaks: mismatch with backend routing breaks communication.
- VARIABLE: `STRICT_MODE_REACT_GUARD`
  - Default: `true` (front-end must guard duplicate GET /next-question)
  - Allowed: boolean
  - What breaks: false may lead to double fetches in React StrictMode.
