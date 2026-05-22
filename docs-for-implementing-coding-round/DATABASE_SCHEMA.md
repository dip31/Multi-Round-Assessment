# Database Schema

This document is the canonical schema reference for agents. It lists the tables, relationships, enums, and constraints that the assessment system uses or expects.

## Core Tables

### `users`

- `id` SERIAL PRIMARY KEY
- `name` VARCHAR(100) NOT NULL
- `email` VARCHAR(150) UNIQUE NOT NULL
- `password_hash` TEXT NOT NULL
- `role` VARCHAR(20) NOT NULL DEFAULT `student`
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `is_verified` BOOLEAN NOT NULL DEFAULT FALSE
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `role IN ('student','admin')`

### `refresh_tokens`

- `id` SERIAL PRIMARY KEY
- `user_id` INTEGER NOT NULL REFERENCES `users(id)` ON DELETE CASCADE
- `token_hash` TEXT NOT NULL
- `expires_at` TIMESTAMP NOT NULL
- `is_revoked` BOOLEAN DEFAULT FALSE
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `user_resumes`

- `id` SERIAL PRIMARY KEY
- `user_id` INTEGER NOT NULL REFERENCES `users(id)` ON DELETE CASCADE
- `resume_text` TEXT NOT NULL
- `parsed_skills` JSONB
- `parsed_projects` JSONB
- `uploaded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `assessment_sessions`

- `id` SERIAL PRIMARY KEY
- `user_id` INTEGER NOT NULL REFERENCES `users(id)`
- `status` VARCHAR(20) NOT NULL
- `started_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `completed_at` TIMESTAMP
- `total_score` FLOAT DEFAULT 0

Constraints:
- `status IN ('not_started','in_progress','completed','terminated')`
- Unique partial index: one active session per user where `status = 'in_progress'`

### `assessment_rounds`

- `id` SERIAL PRIMARY KEY
- `session_id` INTEGER NOT NULL REFERENCES `assessment_sessions(id)` ON DELETE CASCADE
- `round_type` VARCHAR(20) NOT NULL
- `status` VARCHAR(20) NOT NULL
- `score` FLOAT DEFAULT 0
- `max_questions` INTEGER NOT NULL DEFAULT 20
- `started_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- `completed_at` TIMESTAMP

Constraints:
- `round_type IN ('aptitude','coding','interview')`
- `status IN ('pending','active','completed','terminated')`

### `aptitude_topics`

- `id` SERIAL PRIMARY KEY
- `name` VARCHAR(100) UNIQUE NOT NULL

### `aptitude_questions`

- `id` SERIAL PRIMARY KEY
- `question_text` TEXT NOT NULL
- `option_a` TEXT NOT NULL
- `option_b` TEXT NOT NULL
- `option_c` TEXT NOT NULL
- `option_d` TEXT NOT NULL
- `correct_option` CHAR(1) NOT NULL
- `difficulty` VARCHAR(10) NOT NULL
- `topic_id` INTEGER REFERENCES `aptitude_topics(id)`
- `version` INTEGER NOT NULL DEFAULT 1
- `is_active` BOOLEAN NOT NULL DEFAULT TRUE
- `created_by` INTEGER REFERENCES `users(id)`
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `correct_option IN ('A','B','C','D')`
- `difficulty IN ('easy','medium','hard')`

### `aptitude_attempts`

- `id` SERIAL PRIMARY KEY
- `round_id` INTEGER NOT NULL REFERENCES `assessment_rounds(id)` ON DELETE CASCADE
- `question_id` INTEGER NOT NULL REFERENCES `aptitude_questions(id)`
- `attempt_number` INTEGER NOT NULL
- `selected_option` CHAR(1)
- `is_correct` BOOLEAN
- `response_time` FLOAT
- `difficulty` VARCHAR(10)
- `reward` FLOAT
- `attempted_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- Unique `(round_id, attempt_number)`

### `rl_sessions`

- `id` SERIAL PRIMARY KEY
- `round_id` INTEGER NOT NULL REFERENCES `assessment_rounds(id)` ON DELETE CASCADE
- `step_number` INTEGER NOT NULL
- `prev_difficulty` VARCHAR(10)
- `action_taken` VARCHAR(10) NOT NULL
- `reward_received` FLOAT
- `accuracy_so_far` FLOAT
- `avg_response_time` FLOAT
- `q_values` JSONB
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `prev_difficulty IN ('easy','medium','hard')`
- `action_taken IN ('easy','medium','hard')`
- Unique `(round_id, step_number)`

### `coding_problems`

- `id` SERIAL PRIMARY KEY
- `title` VARCHAR(200) NOT NULL
- `description` TEXT NOT NULL
- `difficulty` VARCHAR(10)
- `tags` TEXT[]
- `input_format` TEXT
- `output_format` TEXT
- `constraints` TEXT
- `created_by` INTEGER REFERENCES `users(id)`
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `difficulty IN ('easy','medium','hard')`

### `coding_test_cases`

- `id` SERIAL PRIMARY KEY
- `problem_id` INTEGER NOT NULL REFERENCES `coding_problems(id)` ON DELETE CASCADE
- `input_data` TEXT NOT NULL
- `expected_output` TEXT NOT NULL
- `is_hidden` BOOLEAN DEFAULT TRUE
- `case_order` INTEGER NOT NULL DEFAULT 0
- `explanation` TEXT

### `coding_submissions`

- `id` SERIAL PRIMARY KEY
- `round_id` INTEGER NOT NULL REFERENCES `assessment_rounds(id)` ON DELETE CASCADE
- `problem_id` INTEGER NOT NULL REFERENCES `coding_problems(id)`
- `code` TEXT NOT NULL
- `language` VARCHAR(50)
- `judge0_token` VARCHAR(100)
- `status` VARCHAR(30)
- `score` FLOAT
- `execution_time` FLOAT
- `memory_used` INTEGER
- `submitted_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `status IN ('running','accepted','wrong_answer','runtime_error','time_limit_exceeded','compilation_error')`

### `proctoring_events`

- `id` SERIAL PRIMARY KEY
- `round_id` INTEGER NOT NULL REFERENCES `assessment_rounds(id)` ON DELETE CASCADE
- `event_type` VARCHAR(50) NOT NULL
- `severity` VARCHAR(10) NOT NULL DEFAULT `low`
- `event_data` JSONB
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Constraints:
- `severity IN ('low','medium','high','critical')`

### `interview_sessions`

- `id` SERIAL PRIMARY KEY
- `round_id` INTEGER NOT NULL REFERENCES `assessment_rounds(id)` ON DELETE CASCADE
- `transcript` TEXT
- `behavioral_score` FLOAT
- `confidence_score` FLOAT
- `technical_score` FLOAT
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### `round_analytics` materialized view

- Aggregates aptitude and coding round performance for dashboard use.
- Includes counts, correctness, response times, and coding scores.

## Relationships

- `User` → `AssessmentSession`
- `AssessmentSession` → `AssessmentRound`
- `AssessmentRound` → round-specific data tables
- `CodingProblem` → `CodingTestCase`
- `CodingProblem` → `CodingSubmission`
- `AssessmentRound` → `SessionProblem` via coding assignment table

## Important Missing or Recommended Tables

These are not present in the current schema but are useful for a fuller system design.

### `coding_round_sessions`

Recommended columns:
- `round_id`
- `start_time`
- `end_time`
- `active_problem_id`
- `current_score`

### `session_problem_map`

Recommended columns:
- `round_id`
- `problem_id`
- `assigned_order`
- `review_flag`

### `interview_turns`

Recommended columns:
- `question`
- `response`
- `evaluation`
- `timestamps`

### `rl_state`

Recommended columns:
- `q_table`
- `epsilon`
- `state_history`
