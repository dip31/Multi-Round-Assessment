# EDI5 Current System Audit

## 1. Executive Summary
Overall Project Status: 4/10

Frontend: Implemented but contains duplicate components and disconnected pages.
Backend: Complex architecture with modular routers, but many AI features are either mocked or partially implemented.
Database: Relational schema using SQLAlchemy. Core tables exist but seed data might be causing issues.
Authentication: Implemented using JWT and role-based access.
Role System: Exists in DB (student, faculty, tpo, admin) but registration UI might lack role selection.
Dashboards: Fragmented. Old and new dashboards exist side-by-side.
Assessment: Core engine exists (session -> round), but flow state logic is brittle.
Proctoring: Basic and Advanced proctoring implemented (MediaPipe, YOLOv8).
Portfolio: Mostly planned/mocked, minimal implementation.
Mock Drive: Not implemented / planned only.
Integration: API endpoints exist, but frontend-backend binding is inconsistent.

## 2. Current Technology Stack
### Frontend
- Framework: React 19.2.0
- Build System: Vite 7.3.1
- Routing: React Router v7
- CSS: Tailwind CSS 4.2
- Editor: Monaco Editor (`@monaco-editor/react`)
- External: MediaPipe for proctoring, Recharts for analytics, Axios for HTTP

### Backend
- Framework: FastAPI
- Database ORM: SQLAlchemy + Alembic
- Driver: psycopg2 (PostgreSQL)
- Background Jobs: Celery + Redis
- AI Services: LlamaIndex, Groq, SarvamAI, HuggingFace Sentence Transformers, YOLOv8 (ultralytics)

## 3. Repository Structure
```text
Root
├── frontend
│   ├── src
│   │   ├── components
│   │   ├── hooks
│   │   ├── pages
│   │   └── services
├── app (Backend)
│   ├── api
│   ├── config
│   ├── core
│   ├── database
│   ├── middleware
│   ├── models
│   ├── modules
│   ├── schemas
│   ├── services
│   └── worker
├── database (SQL scripts, sqlite fallback)
├── alembic (Migrations)
├── scripts (Seeding, testing)
├── docs
└── requirements.txt, package.json
```

## 4. Frontend Architecture
The frontend uses Vite+React. Routing is defined in `App.jsx` using `react-router-dom`. State management is mostly local (React State) and API calls are handled via `axios` instances.

## 5. Backend Architecture
FastAPI application with a modular structure under `app/modules/`. It uses a router-service-repository pattern (or directly queries DB via SQLAlchemy session). Features include RAG pipelines and asynchronous Celery workers.

## 6. Database Architecture
SQLAlchemy ORM models defining a relational Postgres schema. 
Migrations managed by Alembic.

## 7. Database Tables
- `users`: Core identity table (id, name, email, password_hash, role)
- `assessment_sessions`: Tracks a user's full attempt (user_id, status, started_at)
- `assessment_rounds`: Tracks individual rounds within a session (session_id, round_type, status, score)
- `proctoring_events`: Basic proctoring logs.
- `advanced_proctoring_events`: AI-based proctoring logs.

## 8. Database Relationships
```text
users
  │
  └────────── assessment_sessions
                  │
                  ├────────── assessment_rounds
                  │
                  ├────────── proctoring_events
                  │
                  └────────── advanced_proctoring_events
```

## 9. Authentication
JWT based. Handled via `app/core/auth.py` and `app/modules/auth`. Token stored in localStorage on frontend.

## 10. Registration
Uses `Register.jsx` -> POST `/api/v1/auth/register`. Role selection is likely missing or hardcoded to 'student' by default on the backend (`server_default=text("'student'")`).

## 11. Role System
Roles: `student`, `faculty`, `tpo`, `admin`.
Stored in: `users.role` in DB.
Validated by: `RoleRoute.jsx` on frontend and `Depends(get_current_user)` on backend.

## 12. Route Map
| Route | Component | Role | Purpose |
| ----- | --------- | ---- | ------- |
| `/login` | `Login` | Public | Auth |
| `/register` | `Register` | Public | Signup |
| `/student/dashboard` | `StudentDashboard`| Student | Main hub |
| `/faculty/dashboard` | `FacultyDashboard`| Faculty | Faculty hub |
| `/tpo/dashboard` | `TPODashboard` | TPO | TPO hub |
| `/admin/*` | `Admin*` | Admin | Admin pages |
| `/dashboard` | Navigate | Any | Redirects to /student/dashboard |
| `/aptitude` | `AptitudeTest` | Auth | Assessment |
| `/coding` | `CodingRound` | Auth | Coding |

## 13. Dashboard Architecture
Frontend uses role-specific dashboards (`StudentDashboard.jsx`, etc.) that fetch from `/api/v1/dashboard/{role}` using the `useDashboardData` hook. 

## 14. Duplicate Dashboard Analysis
- `Dashboard.jsx`: OLD. Still exists in the codebase but is NOT referenced in `App.jsx`. It fetches from `/session/status`.
- `StudentDashboard.jsx`: NEW. Fetches from `/dashboard/student`. 
- `App.jsx` redirects `/dashboard` to `/student/dashboard`.

## 15. API Inventory
- `GET /api/v1/dashboard/{role}`: Fetches aggregated dashboard stats.
- `POST /api/v1/session/start`: Starts/resumes an assessment session.
- `GET /api/v1/session/status`: Legacy session status endpoint.

## 16. API → Frontend Mapping
`StudentDashboard.jsx` -> `useDashboardData('student')` -> `GET /api/v1/dashboard/student` -> `dashboard_router.py`

## 17. API → Backend Service Mapping
Router: `app/modules/dashboard/routers/dashboard_router.py` -> directly queries `AssessmentSession` via SQLAlchemy, no intermediate service layer.

## 18. API → Database Mapping
`GET /dashboard/student`
Reads: `users`, `assessment_sessions`, `assessment_rounds`

## 19. External Service Integrations
- LlamaIndex / FAISS / Groq / SarvamAI for Interview and RAG.
- YOLOv8 (local model) for Phone Detection.
- MediaPipe (frontend) for face mesh tracking.

## 20. Assessment Engine
Sessions are created, which automatically spawn rounds (Aptitude, Coding, Interview). 

## 21. Assessment Sessions
Created via `POST /session/start`. Status lifecycle: `not_started` -> `in_progress` -> `completed`.

## 22. Assessment Rounds
Round lifecycle: `pending` -> `active` -> `completed`.

## 23-30. Various Modules (Aptitude, Coding, Interview, Proctoring)
Aptitude: Implemented.
Coding: Implemented (Monaco Editor).
Interview: Implemented (Voice-based).
Proctoring: Implemented (MediaPipe + YOLOv8).

## 31-33. Dashboard Data Audit
`StudentDashboard`: Uses real API (`/dashboard/student`).
Data is mapped from database `assessment_sessions` and `assessment_rounds`.

## 34-36. Hardcoded, Mock, and Seed Data
- DB might contain seeded `completed` rounds, which cause the "All rounds completed" issue on the dashboard.
- The default role in backend DB is 'student'.

## 37. Authorization
APIs check `current_user.role` (e.g. dashboard router enforces the user matches the requested role dashboard).

## 38-39. Security Gaps and Known Bugs
- Role registration is not dynamic.
- Old files (like `Dashboard.jsx`) clutter the project.
- "All rounds completed" bug stems from database seeding or logic marking rounds completed prematurely.

## 40. Assessment Round State Investigation
Lifecycle: `pending` -> `active` -> `completed`.
If seed scripts insert `completed` rounds, the dashboard calculates 100% progress instantly.

## 41-43. Portfolio & Mock Drive
Planned / Partially Implemented. No deep database footprint found.

## 44. Admin
Separate login (`/admin/login`), separate routes (`/admin/dashboard`, etc.). Uses `AdminRoute.jsx`.

## 45-48. Architecture vs Implementation Gap
Many features outlined in architecture (Competency, Mock Drive) are not fully realized in backend logic. Core assessment flow is present.

## 49. Critical Problems
1. Duplicate/Legacy Frontend Files (`Dashboard.jsx`).
2. Hardcoded/Seed Data causing 100% completion bug.
3. Registration missing role selection mapping.

## 50. Recommended Implementation Order
1. Clean up unused frontend files (`Dashboard.jsx`).
2. Fix seed data scripts to initialize `pending` rounds.
3. Update Registration UI to handle roles properly.

## 51-52. Future Improvements
Remove dead code, decouple dashboard logic into services.

## 53. Final System Status
WHAT WE HAVE: A working skeleton of an AI assessment platform.
WHAT IS WORKING: Routing, Auth, Basic Dashboard, Proctoring.
WHAT MUST BE FIXED FIRST: The duplicate dashboard code and the faulty round state seeding.
