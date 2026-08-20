# API Contracts

This is the strict route contract reference for the platform. Agents should not invent routes outside of these documented contracts.

## Auth

### Register

`POST /api/v1/auth/register`

Request

```json
{
  "name": "Alice Smith",
  "email": "alice@example.com",
  "password": "secret1234"
}
```

Response

```json
{
  "id": 1,
  "name": "Alice Smith",
  "email": "alice@example.com",
  "role": "student",
  "is_active": true,
  "is_verified": false,
  "created_at": "2026-05-21T10:00:00Z"
}
```

### Login

`POST /api/v1/auth/login`

Request

```json
{
  "email": "alice@example.com",
  "password": "secret1234"
}
```

Response

```json
{
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

### Refresh

`POST /api/v1/auth/refresh`

Request

```json
{
  "token": "existing-jwt-token"
}
```

Response

```json
{
  "access_token": "new-jwt-token",
  "token_type": "bearer"
}
```

## Assessment Session

### Start Session

`POST /api/v1/session/start`

Response: `SessionResponse`

### Get Active Session

`GET /api/v1/session/status`

Response: `SessionResponse`

### Restart Session

`POST /api/v1/session/restart`

Response: `SessionResponse`

## Aptitude

The aptitude router is currently a stub in the backend. These are the contracts the system should expose once implemented.

### Next Question

`GET /api/v1/aptitude/questions/next`

Request

```json
{
  "round_id": 1
}
```

Response

```json
{
  "question_id": 12,
  "question_text": "...",
  "options": {
    "A": "...",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "difficulty": "medium",
  "attempt_number": 3
}
```

### Submit Answer

`POST /api/v1/aptitude/attempts`

Request

```json
{
  "round_id": 1,
  "question_id": 12,
  "selected_option": "B",
  "response_time": 8.3
}
```

### Aptitude Results

`GET /api/v1/aptitude/results/{round_id}`

## Coding

### Start Round

`POST /api/v1/coding/start-round`

Request

```json
{}
```

Response

```json
{
  "round_id": 21,
  "status": "active",
  "time_limit_minutes": 90,
  "end_time": "2026-05-21T12:30:00Z",
  "problems": []
}
```

### Restart Round

`POST /api/v1/coding/restart-round`

### Session Status

`GET /api/v1/coding/session/{round_id}`

Response

```json
{
  "round_id": 21,
  "status": "active",
  "time_limit_minutes": 90,
  "end_time": "2026-05-21T12:30:00Z",
  "time_remaining_seconds": 4500,
  "problems": [],
  "all_problems_solved": false
}
```

### End Round

`POST /api/v1/coding/session/{round_id}/end`

### Round Result

`GET /api/v1/coding/session/{round_id}/result`

### Problems List

`GET /api/v1/coding/problems/{round_id}`

### Problem Detail

`GET /api/v1/coding/problem/{round_id}/{problem_id}`

### Run Code

`POST /api/v1/coding/run`

Request

```json
{
  "round_id": 21,
  "problem_id": 3,
  "code": "print('hello')",
  "language": "python"
}
```

Response

```json
{
  "results": []
}
```

### Submit Code

`POST /api/v1/coding/submit`

Request

```json
{
  "round_id": 21,
  "problem_id": 3,
  "code": "print('hello')",
  "language": "python"
}
```

Response

```json
{
  "submission_id": 100,
  "verdict": "accepted",
  "score": 100.0,
  "passed_cases": 4,
  "total_cases": 4,
  "execution_time": 0.02,
  "memory_used": 12000
}
```

### Submission History

`GET /api/v1/coding/submissions/{round_id}/{problem_id}`

### Mark For Review

`POST /api/v1/coding/problem/{round_id}/{problem_id}/mark-review`

## Interview

These contracts are part of the target system design. The current repository does not yet include a full interview module implementation.

### Next Question

`GET /api/v1/interview/next-question`

### Submit Response

`POST /api/v1/interview/response`

### Generate Report

`POST /api/v1/interview/report`

## Proctoring

### Log Event

`POST /api/v1/proctoring/events`

### Get Violations

`GET /api/v1/proctoring/events/{round_id}`
