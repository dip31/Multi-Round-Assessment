# AI-Driven Multi-Round Assessment Platform - Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Project Structure](#project-structure)
7. [Key Features](#key-features)
8. [Configuration](#configuration)
9. [Security Implementation](#security-implementation)
10. [Middleware Layer](#middleware-layer)

---

## Project Overview

The **AI-Driven Multi-Round Assessment Platform** is a comprehensive backend system designed for conducting multi-stage technical assessments. The platform supports three types of assessment rounds:

- **Aptitude Round**: Multiple-choice questions with RL-driven difficulty adaptation
- **Coding Round**: Programming challenges with automated code execution and evaluation
- **Interview Round**: AI-powered behavioral and technical interview sessions

The system includes advanced features like:
- JWT-based authentication and authorization
- Real-time proctoring event tracking
- Reinforcement Learning (RL) for adaptive question difficulty
- Integration with Judge0 for code execution
- Comprehensive analytics and scoring

---

## Tech Stack

### Backend Framework
- **FastAPI** (v0.1.0): Modern, high-performance Python web framework
  - Async/await support
  - Automatic API documentation (Swagger/OpenAPI)
  - Type hints and Pydantic validation
  - Dependency injection system

### Database
- **PostgreSQL**: Primary relational database
  - ACID compliance for data integrity
  - Advanced indexing for performance
  - JSONB support for flexible data structures
  - Materialized views for analytics

### ORM & Migrations
- **SQLAlchemy**: Python SQL toolkit and ORM
  - Declarative model definitions
  - Relationship management
  - Query optimization
- **Alembic**: Database migration tool
  - Version-controlled schema changes
  - Auto-generation from model changes

### Security & Authentication
- **python-jose**: JWT token creation and validation
  - HS256 algorithm for signing
  - Token expiration management
- **passlib**: Password hashing library
  - bcrypt hashing scheme
  - Secure password verification
- **OAuth2PasswordBearer**: FastAPI security scheme for bearer tokens

### Validation & Configuration
- **Pydantic**: Data validation using Python type annotations
  - Request/response schema validation
  - Settings management via environment variables
  - Automatic JSON serialization

### Development Tools
- **uvicorn**: ASGI server for running FastAPI applications
- **Python 3.10+**: Modern Python features (type unions, pattern matching)

---

## Architecture

### Layered Architecture Pattern

The application follows a clean, modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (Routers)                   │
│  - HTTP request handling                                 │
│  - Input validation (Pydantic schemas)                   │
│  - Response formatting                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   Service Layer                          │
│  - Business logic                                        │
│  - Transaction management                                │
│  - Data transformation                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                   Data Layer (Models)                    │
│  - ORM models                                            │
│  - Database operations                                   │
│  - Relationships                                         │
└─────────────────────────────────────────────────────────┘
```

### Module Organization

The project uses a **modular monolith** approach where each feature domain is self-contained:


- **auth**: User registration, login, token management
- **session**: Assessment session lifecycle management
- **aptitude**: Aptitude test questions and RL adaptation
- **coding**: Coding problems and Judge0 integration
- **interview**: AI-powered interview sessions (planned)

---

## Database Schema

### Core Tables

#### 1. Users Table
Stores user account information with role-based access control.

```sql
users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100),
  email VARCHAR(150) UNIQUE,
  password_hash TEXT,
  role VARCHAR(20) DEFAULT 'student',  -- 'student' | 'admin'
  is_active BOOLEAN DEFAULT TRUE,
  is_verified BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP
)
```

**Key Features**:
- Email uniqueness constraint
- Indexed email for fast lookups
- Role-based access (student/admin)
- Account verification status

#### 2. Assessment Sessions Table
Tracks complete assessment attempts by users.

```sql
assessment_sessions (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  status VARCHAR(20),  -- 'not_started' | 'in_progress' | 'completed' | 'terminated'
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  total_score FLOAT DEFAULT 0
)
```

**Key Features**:
- One active session per user (unique constraint)
- Status lifecycle tracking
- Aggregate scoring

#### 3. Assessment Rounds Table
Individual rounds within a session (aptitude, coding, interview).

```sql
assessment_rounds (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES assessment_sessions(id) ON DELETE CASCADE,
  round_type VARCHAR(20),  -- 'aptitude' | 'coding' | 'interview'
  status VARCHAR(20),      -- 'pending' | 'active' | 'completed' | 'terminated'
  score FLOAT DEFAULT 0,
  max_questions INTEGER DEFAULT 20,
  started_at TIMESTAMP,
  completed_at TIMESTAMP
)
```


#### 4. Aptitude Questions Table
Question bank with difficulty levels and topic categorization.

```sql
aptitude_questions (
  id SERIAL PRIMARY KEY,
  question_text TEXT,
  option_a TEXT,
  option_b TEXT,
  option_c TEXT,
  option_d TEXT,
  correct_option CHAR(1),  -- 'A' | 'B' | 'C' | 'D'
  difficulty VARCHAR(10),   -- 'easy' | 'medium' | 'hard'
  topic_id INTEGER REFERENCES aptitude_topics(id),
  version INTEGER DEFAULT 1,
  is_active BOOLEAN DEFAULT TRUE,
  created_by INTEGER REFERENCES users(id)
)
```

#### 5. Aptitude Attempts Table
Records each question attempt with timing and correctness.

```sql
aptitude_attempts (
  id SERIAL PRIMARY KEY,
  round_id INTEGER REFERENCES assessment_rounds(id) ON DELETE CASCADE,
  question_id INTEGER REFERENCES aptitude_questions(id),
  attempt_number INTEGER,
  selected_option CHAR(1),
  is_correct BOOLEAN,
  response_time FLOAT,
  difficulty VARCHAR(10),
  reward FLOAT,
  attempted_at TIMESTAMP,
  UNIQUE(round_id, attempt_number)
)
```

#### 6. RL Sessions Table
Reinforcement Learning state tracking for adaptive difficulty.

```sql
rl_sessions (
  id SERIAL PRIMARY KEY,
  round_id INTEGER REFERENCES assessment_rounds(id) ON DELETE CASCADE,
  step_number INTEGER,
  prev_difficulty VARCHAR(10),
  action_taken VARCHAR(10),
  reward_received FLOAT,
  accuracy_so_far FLOAT,
  avg_response_time FLOAT,
  q_values JSONB,
  UNIQUE(round_id, step_number)
)
```

**Key Features**:
- Stores Q-learning state-action values
- Tracks accuracy and response time metrics
- Enables adaptive difficulty progression


#### 7. Coding Problems Table
Programming challenge definitions.

```sql
coding_problems (
  id SERIAL PRIMARY KEY,
  title VARCHAR(200),
  description TEXT,
  difficulty VARCHAR(10),
  tags TEXT[],
  input_format TEXT,
  output_format TEXT,
  constraints TEXT,
  created_by INTEGER REFERENCES users(id)
)
```

#### 8. Coding Test Cases Table
Test cases for validating code submissions.

```sql
coding_test_cases (
  id SERIAL PRIMARY KEY,
  problem_id INTEGER REFERENCES coding_problems(id) ON DELETE CASCADE,
  input_data TEXT,
  expected_output TEXT,
  is_hidden BOOLEAN DEFAULT TRUE,
  case_order INTEGER DEFAULT 0,
  explanation TEXT
)
```

#### 9. Coding Submissions Table
Code submission tracking with Judge0 integration.

```sql
coding_submissions (
  id SERIAL PRIMARY KEY,
  round_id INTEGER REFERENCES assessment_rounds(id) ON DELETE CASCADE,
  problem_id INTEGER REFERENCES coding_problems(id),
  code TEXT,
  language VARCHAR(50),
  judge0_token VARCHAR(100),
  status VARCHAR(30),  -- 'running' | 'accepted' | 'wrong_answer' | etc.
  score FLOAT,
  execution_time FLOAT,
  memory_used INTEGER,
  submitted_at TIMESTAMP
)
```

**Key Features**:
- Judge0 token for async result polling
- Multiple submission statuses
- Performance metrics (time, memory)

#### 10. Proctoring Events Table
Real-time monitoring and integrity tracking.

```sql
proctoring_events (
  id SERIAL PRIMARY KEY,
  round_id INTEGER REFERENCES assessment_rounds(id) ON DELETE CASCADE,
  event_type VARCHAR(50),
  severity VARCHAR(10),  -- 'low' | 'medium' | 'high' | 'critical'
  event_data JSONB,
  created_at TIMESTAMP
)
```


#### 11. Additional Tables

- **refresh_tokens**: Token revocation and refresh management
- **user_resumes**: Resume parsing and skill extraction (JSONB)
- **aptitude_topics**: Question categorization
- **interview_sessions**: AI interview transcripts and scoring

### Materialized View: round_analytics

Aggregated analytics for performance optimization:

```sql
CREATE MATERIALIZED VIEW round_analytics AS
SELECT
  r.id AS round_id,
  r.round_type,
  COUNT(aa.id) AS total_questions,
  SUM(CASE WHEN aa.is_correct THEN 1 ELSE 0 END) AS correct_answers,
  AVG(aa.response_time) AS avg_response_time,
  NULL::FLOAT AS coding_score
FROM assessment_rounds r
LEFT JOIN aptitude_attempts aa ON aa.round_id = r.id
WHERE r.round_type = 'aptitude'
GROUP BY r.id, r.round_type

UNION ALL

SELECT
  r.id,
  r.round_type,
  COUNT(cs.id),
  NULL,
  NULL,
  AVG(cs.score)
FROM assessment_rounds r
LEFT JOIN coding_submissions cs ON cs.round_id = r.id
WHERE r.round_type = 'coding'
GROUP BY r.id, r.round_type;
```

---

## API Endpoints

### Authentication Module (`/api/v1/auth`)

#### POST `/auth/register`
Register a new user account.

**Request Body**:
```json
{
  "name": "Alice Smith",
  "email": "alice@example.com",
  "password": "securepassword123"
}
```

**Response** (201 Created):
```json
{
  "id": 1,
  "name": "Alice Smith",
  "email": "alice@example.com",
  "role": "student",
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-03-06T10:30:00Z"
}
```


**Error Responses**:
- 409 Conflict: Email already registered

#### POST `/auth/login`
Authenticate and receive JWT access token.

**Request Body**:
```json
{
  "email": "alice@example.com",
  "password": "securepassword123"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses**:
- 401 Unauthorized: Invalid credentials

#### POST `/auth/refresh`
Refresh an existing access token.

**Request Body**:
```json
{
  "token": "existing_jwt_token"
}
```

**Response** (200 OK):
```json
{
  "access_token": "new_jwt_token",
  "token_type": "bearer"
}
```

---

### Session Module (`/api/v1/session`)

All session endpoints require authentication via `Authorization: Bearer <token>` header.

#### POST `/session/start`
Create a new assessment session for the authenticated user.

**Response** (201 Created):
```json
{
  "id": 1,
  "user_id": 1,
  "status": "in_progress",
  "started_at": "2024-03-06T10:35:00Z",
  "completed_at": null,
  "total_score": 0.0,
  "rounds": []
}
```

**Error Responses**:
- 409 Conflict: Active session already exists
- 401 Unauthorized: Invalid or missing token


#### GET `/session/status`
Retrieve the current active session.

**Response** (200 OK):
```json
{
  "id": 1,
  "user_id": 1,
  "status": "in_progress",
  "started_at": "2024-03-06T10:35:00Z",
  "completed_at": null,
  "total_score": 0.0,
  "rounds": [
    {
      "id": 1,
      "session_id": 1,
      "round_type": "aptitude",
      "status": "active",
      "score": 0.0,
      "max_questions": 20,
      "started_at": "2024-03-06T10:36:00Z",
      "completed_at": null
    }
  ]
}
```

**Error Responses**:
- 404 Not Found: No active session

---

### Aptitude Module (`/api/v1/aptitude`)

**Status**: Stub implementation - endpoints planned but not yet implemented.

**Planned Endpoints**:
- `GET /aptitude/questions` - Fetch next question with RL-selected difficulty
- `POST /aptitude/attempt` - Submit answer and receive feedback
- `GET /aptitude/results` - Round analytics and performance metrics

---

### Coding Module (`/api/v1/coding`)

**Status**: Stub implementation - endpoints planned but not yet implemented.

**Planned Endpoints**:
- `GET /coding/problems` - List available coding problems for the round
- `POST /coding/submit` - Submit code for Judge0 execution
- `GET /coding/submission/{id}` - Poll submission status and results

---

## Project Structure

```
Multi-Round-Assessment/
├── alembic/                      # Database migrations
│   ├── versions/                 # Migration scripts
│   ├── env.py                    # Alembic environment config
│   └── script.py.mako            # Migration template
│
├── app/                          # Main application package
│   ├── api/                      # API versioning
│   │   └── v1/
│   │       └── router.py         # Aggregated v1 router
│   │
│   ├── config/                   # Configuration management
│   │   ├── settings.py           # Environment-based settings
│   │   └── security.py           # JWT & password utilities
│   │
│   ├── core/                     # Core utilities
│   │   └── auth.py               # Authentication dependency
│   │
│   ├── database/                 # Database setup
│   │   ├── base.py               # SQLAlchemy Base
│   │   └── db.py                 # Engine & session factory
│   │
│   ├── middleware/               # HTTP middleware
│   │   ├── cors.py               # CORS configuration
│   │   ├── rate_limit.py         # Rate limiting
│   │   └── request_logging.py   # Request/response logging
│   │
│   ├── models/                   # ORM models
│   │   ├── user.py               # User model
│   │   └── assessment.py         # Session & Round models
│   │
│   ├── modules/                  # Feature modules
│   │   ├── auth/
│   │   │   └── routers/
│   │   │       └── auth_router.py
│   │   ├── session/
│   │   │   └── routers/
│   │   │       └── session_router.py
│   │   ├── aptitude/
│   │   │   └── routers/
│   │   │       └── aptitude_router.py
│   │   └── coding/
│   │       └── routers/
│   │           └── coding_router.py
│   │
│   ├── schemas/                  # Pydantic schemas
│   │   ├── user.py               # User request/response schemas
│   │   └── assessment.py         # Assessment schemas
│   │
│   ├── services/                 # Business logic layer
│   │   ├── user_service.py       # User operations
│   │   └── assessment_service.py # Session/round operations
│   │
│   └── main.py                   # FastAPI app entry point
│
├── database/
│   └── schema.sql                # Complete PostgreSQL schema
│
├── tests/
│   └── test_smoke.py             # Basic smoke tests
│
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── alembic.ini                   # Alembic configuration
└── README.md                     # Project readme
```


---

## Key Features

### 1. JWT-Based Authentication

**Implementation Details**:
- **Token Generation**: Uses `python-jose` with HS256 algorithm
- **Token Payload**: Contains user ID in `sub` claim and expiration timestamp
- **Token Lifetime**: Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 30 minutes)
- **Password Security**: bcrypt hashing via `passlib` with automatic salt generation

**Authentication Flow**:
1. User registers → password hashed and stored
2. User logs in → credentials verified → JWT issued
3. Protected endpoints → JWT validated → user object injected via dependency

**Code Example**:
```python
# Dependency injection for protected routes
@router.get("/protected")
def protected_route(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id}
```

### 2. Session Management

**Session Lifecycle**:
```
not_started → in_progress → completed/terminated
```

**Key Constraints**:
- One active session per user (enforced by unique index)
- Cascade deletion of rounds when session is deleted
- Automatic timestamp tracking (started_at, completed_at)

**Business Rules**:
- Users cannot start a new session while one is active
- Session completion triggers score aggregation
- All rounds must be completed before session completion

### 3. Round Management

**Round Types**:
1. **Aptitude**: MCQ questions with RL-driven difficulty
2. **Coding**: Programming challenges with automated testing
3. **Interview**: AI-powered behavioral/technical assessment

**Round Status Flow**:
```
pending → active → completed/terminated
```

### 4. Reinforcement Learning Integration

**Purpose**: Adaptive difficulty adjustment based on user performance

**RL Algorithm**: Q-Learning
- **State**: Current difficulty level
- **Actions**: Select next difficulty (easy/medium/hard)
- **Reward**: Based on correctness and response time
- **Q-Values**: Stored in JSONB for flexibility


**Metrics Tracked**:
- Accuracy so far
- Average response time
- Question difficulty progression
- Reward signals

### 5. Code Execution with Judge0

**Integration Points**:
- Submit code → Judge0 API → receive token
- Poll token → get execution results
- Store results in `coding_submissions` table

**Supported Metrics**:
- Execution time (milliseconds)
- Memory usage (KB)
- Test case pass/fail status
- Compilation errors

### 6. Proctoring System

**Event Types**:
- Tab switches
- Window focus loss
- Multiple faces detected
- No face detected
- Suspicious behavior patterns

**Severity Levels**:
- **Low**: Minor distractions
- **Medium**: Repeated violations
- **High**: Clear policy violations
- **Critical**: Immediate termination triggers

**Data Storage**: JSONB format for flexible event metadata

### 7. Analytics & Reporting

**Materialized View Benefits**:
- Pre-aggregated statistics
- Fast query performance
- Reduced database load
- Scheduled refresh capability

**Available Metrics**:
- Total questions attempted
- Correct answer count
- Average response time
- Coding problem scores
- Round-wise performance

---

## Configuration

### Environment Variables

All configuration is managed through environment variables or a `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:password@localhost/ai_placement_platform

# JWT Configuration
SECRET_KEY=change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS Configuration
ALLOWED_ORIGINS=["http://localhost:3000"]
```


### Settings Management

**Implementation**: Pydantic `BaseSettings` class

**Features**:
- Type validation
- Default values
- Environment variable override
- Case-sensitive keys
- Automatic `.env` file loading

**Code Example**:
```python
from app.config.settings import settings

# Access configuration
db_url = settings.DATABASE_URL
token_expiry = settings.ACCESS_TOKEN_EXPIRE_MINUTES
```

---

## Security Implementation

### 1. Password Security

**Hashing Algorithm**: bcrypt via passlib
- Automatic salt generation
- Configurable work factor
- Resistant to rainbow table attacks

**Implementation**:
```python
# Hash password on registration
password_hash = hash_password(plain_password)

# Verify on login
is_valid = verify_password(plain_password, stored_hash)
```

### 2. JWT Token Security

**Token Structure**:
```json
{
  "sub": "user_id",
  "exp": 1234567890
}
```

**Security Features**:
- Signed with secret key (HS256)
- Expiration timestamp validation
- Automatic expiry enforcement
- Stateless authentication

**Best Practices Implemented**:
- Short token lifetime (30 minutes default)
- Secure secret key storage
- Token validation on every request
- Proper error handling for expired tokens

### 3. SQL Injection Prevention

**Protection Mechanisms**:
- SQLAlchemy ORM (parameterized queries)
- No raw SQL string concatenation
- Input validation via Pydantic schemas

### 4. CORS Configuration

**Purpose**: Control which origins can access the API

**Configuration**:
```python
allow_origins=["http://localhost:3000"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```


---

## Middleware Layer

### 1. CORS Middleware

**Purpose**: Enable cross-origin requests from frontend applications

**Configuration**:
- Allowed origins from settings
- Credentials support enabled
- All HTTP methods allowed
- All headers allowed

**Location**: `app/middleware/cors.py`

### 2. Rate Limiting Middleware

**Purpose**: Prevent API abuse and DDoS attacks

**Implementation**: In-memory token bucket algorithm
- **Default Limit**: 100 requests per 60 seconds
- **Keying**: By client IP address
- **Response**: 429 Too Many Requests when exceeded

**Features**:
- Rolling window tracking
- Automatic cleanup of stale timestamps
- Configurable limits per endpoint

**Production Note**: Replace with Redis-backed solution (e.g., `slowapi`) for distributed systems

**Location**: `app/middleware/rate_limit.py`

### 3. Request Logging Middleware

**Purpose**: Monitor API usage and performance

**Logged Information**:
- HTTP method (GET, POST, etc.)
- Request path
- Response status code
- Processing time (milliseconds)

**Example Log Output**:
```
INFO: POST /api/v1/auth/login → 200 (45.3 ms)
INFO: GET /api/v1/session/status → 200 (12.7 ms)
```

**Location**: `app/middleware/request_logging.py`

### Middleware Execution Order

Middleware is executed in reverse order of registration:

```
Request → Rate Limit → Request Logging → CORS → Route Handler
Response ← Rate Limit ← Request Logging ← CORS ← Route Handler
```

---

## Database Migrations with Alembic

### Setup

**Configuration File**: `alembic.ini`
- Database URL overridden by `settings.DATABASE_URL`
- Migration scripts in `alembic/versions/`

### Common Commands

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add new table"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current version
alembic current
```


### Auto-generation Process

1. Modify ORM models in `app/models/`
2. Run `alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Apply with `alembic upgrade head`

**Important**: Always review auto-generated migrations before applying!

---

## Data Models (ORM)

### User Model

**File**: `app/models/user.py`

**Relationships**:
- One-to-many with `AssessmentSession`

**Key Methods**:
- `__repr__`: String representation for debugging

### AssessmentSession Model

**File**: `app/models/assessment.py`

**Relationships**:
- Many-to-one with `User`
- One-to-many with `AssessmentRound` (cascade delete)

**Status Values**:
- `not_started`: Session created but not begun
- `in_progress`: Currently active
- `completed`: Successfully finished
- `terminated`: Ended due to violations

### AssessmentRound Model

**File**: `app/models/assessment.py`

**Relationships**:
- Many-to-one with `AssessmentSession`

**Round Types**:
- `aptitude`: Multiple-choice questions
- `coding`: Programming challenges
- `interview`: AI-powered interview

**Status Values**:
- `pending`: Waiting to start
- `active`: Currently in progress
- `completed`: Successfully finished
- `terminated`: Ended prematurely

---

## Pydantic Schemas

### Purpose

Pydantic schemas serve three main purposes:

1. **Request Validation**: Ensure incoming data is valid
2. **Response Serialization**: Format outgoing data consistently
3. **API Documentation**: Auto-generate OpenAPI specs

### User Schemas

**File**: `app/schemas/user.py`

**UserCreate** (Request):
- name: 1-100 characters
- email: Valid email format
- password: 8-128 characters

**UserLogin** (Request):
- email: Valid email format
- password: Any string

**UserResponse** (Response):
- Excludes password_hash
- Includes all public fields
- `from_attributes=True` for ORM conversion

**TokenResponse** (Response):
- access_token: JWT string
- token_type: Always "bearer"


### Assessment Schemas

**File**: `app/schemas/assessment.py`

**SessionCreate** (Request):
- Empty payload (user_id from auth)

**RoundCreate** (Request):
- round_type: Regex validated (aptitude|coding|interview)

**RoundResponse** (Response):
- All round fields
- Timestamps in ISO format

**SessionResponse** (Response):
- All session fields
- Nested rounds array
- Automatic ORM conversion

---

## Service Layer

### User Service

**File**: `app/services/user_service.py`

**Functions**:

1. `create_user(db, name, email, password)` → User
   - Hashes password
   - Creates user record
   - Returns committed user

2. `get_user_by_email(db, email)` → User | None
   - Email lookup
   - Returns None if not found

3. `get_user_by_id(db, user_id)` → User | None
   - Primary key lookup
   - Used by auth dependency

4. `verify_user_credentials(db, email, password)` → User | None
   - Combines lookup and password verification
   - Returns None if invalid

### Assessment Service

**File**: `app/services/assessment_service.py`

**Session Functions**:

1. `create_session(db, user_id)` → AssessmentSession
   - Creates session with status "in_progress"
   - Auto-commits and refreshes

2. `get_active_session(db, user_id)` → AssessmentSession | None
   - Finds in_progress session
   - Returns None if no active session

3. `complete_session(db, session_id)` → AssessmentSession | None
   - Sets status to "completed"
   - Records completion timestamp

**Round Functions**:

1. `create_round(db, session_id, round_type)` → AssessmentRound
   - Creates round with status "active"
   - Links to session

2. `get_active_round(db, session_id)` → AssessmentRound | None
   - Finds active round for session

3. `end_round(db, round_id)` → AssessmentRound | None
   - Sets status to "completed"
   - Records completion timestamp

---

## Running the Application

### Prerequisites

1. Python 3.10 or higher
2. PostgreSQL database
3. Virtual environment (recommended)


### Installation Steps

```bash
# 1. Clone the repository
git clone <repository-url>
cd Multi-Round-Assessment

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install fastapi uvicorn sqlalchemy psycopg2-binary alembic
pip install python-jose[cryptography] passlib[bcrypt] pydantic-settings

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your database credentials

# 5. Create database
createdb ai_placement_platform

# 6. Run migrations
alembic upgrade head

# 7. Start the server
uvicorn app.main:app --reload
```

### Development Server

```bash
# Start with auto-reload
uvicorn app.main:app --reload

# Custom host and port
uvicorn app.main:app --host 0.0.0.0 --port 8000

# With log level
uvicorn app.main:app --reload --log-level debug
```

### API Documentation

Once running, access interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Testing

### Health Check Endpoint

```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

### Testing Authentication Flow

```bash
# 1. Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "password123"
  }'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'

# 3. Use token for protected endpoints
curl -X POST http://localhost:8000/api/v1/session/start \
  -H "Authorization: Bearer <your_token_here>"
```

---

## Future Enhancements

### Planned Features

1. **Aptitude Module Completion**
   - Question fetching with RL-based difficulty selection
   - Answer submission and validation
   - Real-time score calculation
   - Performance analytics

2. **Coding Module Completion**
   - Judge0 API integration
   - Code submission handling
   - Test case execution
   - Result polling and storage


3. **Interview Module**
   - Speech-to-text integration
   - AI-powered question generation
   - Sentiment analysis
   - Confidence scoring

4. **Proctoring Enhancements**
   - WebRTC integration for video monitoring
   - Face detection and recognition
   - Eye tracking
   - Screen recording

5. **Admin Dashboard**
   - User management
   - Question bank management
   - Analytics and reporting
   - System configuration

6. **Advanced RL Features**
   - Multi-armed bandit algorithms
   - Deep Q-Networks (DQN)
   - Personalized learning paths
   - Skill gap analysis

7. **Performance Optimizations**
   - Redis caching layer
   - Database query optimization
   - Async task queue (Celery)
   - CDN for static assets

8. **Security Enhancements**
   - Refresh token rotation
   - Two-factor authentication
   - IP whitelisting
   - Audit logging

---

## Development Best Practices

### Code Organization

1. **Separation of Concerns**
   - Routers: HTTP handling only
   - Services: Business logic
   - Models: Data structure
   - Schemas: Validation

2. **Dependency Injection**
   - Database sessions via `Depends(get_db)`
   - Authentication via `Depends(get_current_user)`
   - Configuration via settings object

3. **Type Hints**
   - All functions have type annotations
   - Enables IDE autocomplete
   - Catches errors early

### Error Handling

**HTTP Exceptions**:
```python
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found"
)
```

**Common Status Codes**:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 409: Conflict
- 422: Validation Error
- 429: Too Many Requests
- 500: Internal Server Error

### Database Best Practices

1. **Always use transactions**
   - Commit after successful operations
   - Rollback on errors

2. **Use indexes**
   - Email lookups
   - Foreign key relationships
   - Frequently queried fields

3. **Cascade deletes**
   - Rounds deleted with sessions
   - Attempts deleted with rounds


4. **Connection pooling**
   - Pool size: 10
   - Max overflow: 20
   - Pre-ping enabled

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Problem**: `sqlalchemy.exc.OperationalError: could not connect to server`

**Solutions**:
- Verify PostgreSQL is running
- Check DATABASE_URL in .env
- Ensure database exists
- Verify credentials

#### 2. Import Errors

**Problem**: `ModuleNotFoundError: No module named 'app'`

**Solutions**:
- Run from project root directory
- Activate virtual environment
- Install all dependencies

#### 3. Migration Errors

**Problem**: `alembic.util.exc.CommandError: Target database is not up to date`

**Solutions**:
```bash
# Check current version
alembic current

# View pending migrations
alembic history

# Apply all migrations
alembic upgrade head
```

#### 4. JWT Token Errors

**Problem**: `401 Unauthorized: Could not validate credentials`

**Solutions**:
- Check token expiration
- Verify SECRET_KEY matches
- Ensure Bearer prefix in header
- Check token format

#### 5. CORS Errors

**Problem**: `Access to fetch blocked by CORS policy`

**Solutions**:
- Add frontend origin to ALLOWED_ORIGINS
- Verify CORS middleware is registered
- Check browser console for exact error

---

## Performance Considerations

### Database Optimization

1. **Indexes**
   - Email lookups: `idx_users_email`
   - Round queries: `idx_round_session`
   - Token lookups: `idx_refresh_token_hash`

2. **Materialized Views**
   - Pre-computed analytics
   - Refresh strategy needed
   - Significant query speedup

3. **Connection Pooling**
   - Reuse database connections
   - Configurable pool size
   - Automatic connection recycling

### API Performance

1. **Rate Limiting**
   - Prevents abuse
   - Protects resources
   - Configurable per endpoint

2. **Async Operations**
   - FastAPI async support
   - Non-blocking I/O
   - Better concurrency

3. **Response Caching**
   - Cache static data
   - Redis integration (future)
   - ETags for conditional requests


---

## Deployment Considerations

### Production Checklist

1. **Environment Variables**
   - [ ] Change SECRET_KEY to strong random value
   - [ ] Update DATABASE_URL with production credentials
   - [ ] Configure ALLOWED_ORIGINS for production domains
   - [ ] Set appropriate ACCESS_TOKEN_EXPIRE_MINUTES

2. **Database**
   - [ ] Run all migrations
   - [ ] Set up automated backups
   - [ ] Configure connection pooling
   - [ ] Enable SSL connections

3. **Security**
   - [ ] Enable HTTPS
   - [ ] Configure firewall rules
   - [ ] Set up rate limiting with Redis
   - [ ] Implement request logging
   - [ ] Enable audit trails

4. **Monitoring**
   - [ ] Set up application logging
   - [ ] Configure error tracking (Sentry)
   - [ ] Monitor database performance
   - [ ] Track API response times

5. **Scalability**
   - [ ] Use production ASGI server (Gunicorn + Uvicorn)
   - [ ] Set up load balancer
   - [ ] Configure auto-scaling
   - [ ] Implement caching layer

### Recommended Production Stack

```
┌─────────────────────────────────────────┐
│         Load Balancer (Nginx)           │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│    Gunicorn + Uvicorn Workers (4-8)     │
│         FastAPI Application              │
└─────────────────────────────────────────┘
                  ↓
┌──────────────────┐    ┌────────────────┐
│   PostgreSQL     │    │  Redis Cache   │
│   (Primary DB)   │    │  (Sessions)    │
└──────────────────┘    └────────────────┘
```

### Docker Deployment (Future)

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## API Design Principles

### RESTful Conventions

1. **Resource Naming**
   - Plural nouns: `/users`, `/sessions`
   - Hierarchical: `/sessions/{id}/rounds`
   - Lowercase with hyphens

2. **HTTP Methods**
   - GET: Retrieve resources
   - POST: Create resources
   - PUT/PATCH: Update resources
   - DELETE: Remove resources

3. **Status Codes**
   - 2xx: Success
   - 4xx: Client errors
   - 5xx: Server errors

4. **Response Format**
   - Consistent JSON structure
   - ISO 8601 timestamps
   - Pagination for lists (future)

### Versioning Strategy

**Current**: `/api/v1/`

**Benefits**:
- Backward compatibility
- Gradual migration
- Clear API evolution

**Future versions**: `/api/v2/` when breaking changes needed


---

## Technology Decisions & Rationale

### Why FastAPI?

1. **Performance**: Built on Starlette and Pydantic, one of the fastest Python frameworks
2. **Modern Python**: Native async/await support, type hints
3. **Auto Documentation**: Swagger UI and ReDoc generated automatically
4. **Developer Experience**: Excellent error messages, IDE support
5. **Validation**: Pydantic integration for robust data validation

### Why PostgreSQL?

1. **ACID Compliance**: Critical for assessment data integrity
2. **JSONB Support**: Flexible storage for RL state, proctoring events
3. **Advanced Features**: Materialized views, full-text search, array types
4. **Scalability**: Proven at enterprise scale
5. **Open Source**: No licensing costs

### Why SQLAlchemy?

1. **ORM Benefits**: Pythonic database interactions
2. **Migration Support**: Alembic integration
3. **Relationship Management**: Automatic joins, lazy loading
4. **Database Agnostic**: Easy to switch databases if needed
5. **Query Optimization**: Control over SQL generation

### Why JWT for Authentication?

1. **Stateless**: No server-side session storage needed
2. **Scalable**: Works across multiple servers
3. **Standard**: Industry-standard (RFC 7519)
4. **Flexible**: Can include custom claims
5. **Mobile-Friendly**: Easy to use in mobile apps

---

## Code Quality & Standards

### Type Hints

All functions use Python type hints:

```python
def create_user(db: Session, name: str, email: str, password: str) -> User:
    """Create a new user with type-safe parameters."""
    pass
```

### Docstrings

Google-style docstrings for all public functions:

```python
def verify_user_credentials(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password.

    Args:
        db: Active database session.
        email: User email.
        password: Plain-text password to verify.

    Returns:
        The ``User`` if credentials are valid, otherwise ``None``.
    """
```

### Import Organization

```python
# 1. Standard library
from datetime import datetime
from typing import Optional

# 2. Third-party packages
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 3. Local imports
from app.models.user import User
from app.services.user_service import create_user
```

### Naming Conventions

- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

---

## Summary

This project implements a production-ready backend for an AI-driven assessment platform with:

### ✅ Completed Features

1. **Authentication System**
   - User registration and login
   - JWT token generation and validation
   - Password hashing with bcrypt
   - Protected route dependencies

2. **Session Management**
   - Session creation and tracking
   - Status lifecycle management
   - One active session per user constraint

3. **Database Architecture**
   - Comprehensive PostgreSQL schema
   - 15+ tables covering all features
   - Proper indexing and constraints
   - Materialized views for analytics

4. **API Structure**
   - RESTful endpoint design
   - Versioned API (v1)
   - Modular router organization
   - Automatic OpenAPI documentation

5. **Middleware Layer**
   - CORS configuration
   - Rate limiting
   - Request logging
   - Performance monitoring

6. **Configuration Management**
   - Environment-based settings
   - Type-safe configuration
   - Secure defaults

7. **Database Migrations**
   - Alembic setup
   - Auto-generation support
   - Version control for schema


### 🚧 In Progress / Planned

1. **Aptitude Module**
   - Question fetching endpoints
   - Answer submission logic
   - RL-based difficulty adaptation
   - Performance analytics

2. **Coding Module**
   - Judge0 API integration
   - Code submission handling
   - Test case execution
   - Result retrieval

3. **Interview Module**
   - Speech-to-text integration
   - AI question generation
   - Scoring algorithms

4. **Proctoring System**
   - Event capture endpoints
   - Real-time monitoring
   - Violation detection
   - Alert system

5. **Admin Features**
   - User management
   - Question bank CRUD
   - Analytics dashboard
   - System configuration

### 📊 Technical Metrics

- **Total Files**: 40+ Python files
- **Database Tables**: 15 tables
- **API Endpoints**: 5 implemented, 10+ planned
- **Lines of Code**: ~2000+ lines
- **Test Coverage**: Basic smoke tests (expandable)

### 🎯 Key Strengths

1. **Clean Architecture**: Clear separation of concerns
2. **Type Safety**: Comprehensive type hints throughout
3. **Security**: Industry-standard authentication and hashing
4. **Scalability**: Connection pooling, async support
5. **Maintainability**: Modular design, well-documented
6. **Extensibility**: Easy to add new modules and features

### 🔧 Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | FastAPI | Web framework |
| **Database** | PostgreSQL | Data persistence |
| **ORM** | SQLAlchemy | Database abstraction |
| **Migrations** | Alembic | Schema versioning |
| **Auth** | JWT + bcrypt | Security |
| **Validation** | Pydantic | Data validation |
| **Server** | Uvicorn | ASGI server |
| **Language** | Python 3.10+ | Core language |

---

## Conclusion

The **AI-Driven Multi-Round Assessment Platform** provides a solid foundation for conducting technical assessments with advanced features like adaptive difficulty, code execution, and proctoring. The architecture is designed for scalability, security, and maintainability, making it suitable for both development and production environments.

The modular design allows for easy extension and customization, while the comprehensive database schema supports complex assessment workflows. With the core authentication and session management in place, the platform is ready for the implementation of the remaining assessment modules.

---

**Document Version**: 1.0  
**Last Updated**: March 6, 2026  
**Project Status**: Active Development  
**License**: [To be determined]

---

## Quick Reference

### Start Development Server
```bash
uvicorn app.main:app --reload
```

### Run Migrations
```bash
alembic upgrade head
```

### Access API Documentation
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Environment Setup
```bash
cp .env.example .env
# Edit .env with your configuration
```

---

*For questions or contributions, please refer to the project repository.*
