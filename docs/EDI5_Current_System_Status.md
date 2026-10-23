# EDI5 Current System Status Report

This is a comprehensive and honest audit of the EDI5 codebase as of the current state. The rule applied is strict: a feature is marked as **EXISTS** only if it is wired end-to-end with real database data. Hardcoded UI shells are marked as **PARTIAL**, and disconnected/dead code is marked as **MISSING**.

---

## SECTION 1 — Project Structure

**Frontend (`frontend/src`)**
- `/components`: Shared UI elements (Navbar, Toast, PageSkeleton, VideoProctoring, etc.)
- `/hooks`: Custom React hooks (useBasicProctoring, useAdvancedProctoring, etc.)
- `/pages`: Route views (Dashboard, FacultyDashboard, TPODashboard, Admin dashboards, InterviewRoom, etc.)
- `/services`: API client integrations (api.js, authService, profileService, sessionService, etc.)
- `App.jsx`, `main.jsx`: Application entry and routing (React Router)

**Backend (`app/`)**
- `/api/v1`: Core router registry (router.py, profile.py)
- `/config`: Configuration and environment parsing
- `/core`: Core utilities (security, auth middleware)
- `/database`: Database connection and session management
- `/models`: SQLAlchemy ORM models (user, profile, assessment, coding, proctoring, etc.)
- `/modules`: Domain-specific logic (auth, session, coding, interview, report) containing their own routers and services
- `/schemas`: Pydantic validation schemas
- `/services`: Global/shared business logic (session_service, profile_service)

---

## SECTION 2 — Authentication & Roles

- **User registration endpoint:** EXISTS (Implemented via `auth_router.py` creating user and profile tables)
- **Role selection during signup (Student / Faculty / TPO):** EXISTS (Handled in `Register.jsx` frontend and creates appropriate profile records backend)
- **Student-specific registration form + fields:** EXISTS (Captures roll number, department, target role, graduation year)
- **Faculty-specific registration form + fields:** EXISTS (Captures department, faculty ID, designation)
- **TPO-specific registration form:** EXISTS (Captures institution, contact info)

---

## SECTION 3 — Database Schema

- **User / Accounts Table:** EXISTS (Defined in `app/models/user.py`)
- **Student Profile Table:** EXISTS (Defined in `app/models/profile.py` linked to User)
- **Faculty Profile Table:** EXISTS (Defined in `app/models/profile.py` linked to User)
- **TPO Profile Table:** EXISTS (Defined in `app/models/profile.py` linked to User)
- **Assessment Session Table:** EXISTS (Defined in `app/models/assessment.py`)
- **Assessment Round Table:** EXISTS (Defined in `app/models/assessment.py`)
- **Assessment Mode Field:** MISSING (There is no explicit `mode` field for PRACTICE/OFFICIAL in the assessment session/round models)

---

## SECTION 4 — Student Dashboard

- **Displays correct user info from DB:** EXISTS (Fetches via `/profile/me` and falls back to user object if missing)
- **Displays actual assessment history (not hardcoded):** EXISTS (Fetches via `/session/status` and `/session/results`)
- **"Start New Assessment" button triggers DB session:** EXISTS (Calls `/session/fresh` or `/session/start` to create real session records)
- **Profile completion calculation based on DB fields:** EXISTS (Calculated dynamically in `Dashboard.jsx` based on loaded profile completeness)

---

## SECTION 5 — Faculty Dashboard

- **Faculty Dashboard route exists:** EXISTS (`/faculty/dashboard` implemented in `FacultyDashboard.jsx`)
- **Displays real cohort data:** EXISTS (Fetches department students via `/profile/cohort/students?department=...`)
- **Displays real average scores:** EXISTS (Calculated dynamically from the cohort's assessment results)
- **Student scorecard view:** EXISTS (Modal displays real student profile, academic stats, and assessment scores)

---

## SECTION 6 — TPO Dashboard

- **TPO Dashboard route exists:** EXISTS (`/tpo/dashboard` implemented in `TPODashboard.jsx`)
- **Displays real placement eligibility:** EXISTS (Calculates eligibility dynamically based on CGPA >= 7.0 and 0 backlogs from DB data)
- **Filters by department and eligibility:** EXISTS (Frontend filtering applies to the real student dataset loaded via API)
- **Active placement drives tracking:** PARTIAL (The UI cards for Google, Amazon, TCS are hardcoded, but the eligible candidate counts within them are calculated dynamically from real DB data)

---

## SECTION 7 — Administrator Panel

- **System overview metrics (active sessions, total users):** EXISTS (Available in `AdminAnalyticsDashboard.jsx` pulling from `/report/admin/...`)
- **Manage question banks (CRUD for aptitude/coding problems):** MISSING (No frontend screens exist for CRUD operations on question banks)
- **View proctoring red flags:** EXISTS (`AdminProctoringDashboard.jsx` displays flagged events)
- **Export reports (CSV/PDF):** PARTIAL (CSV export exists for proctoring logs; PDF print support exists for Interview Reports; no global system-wide data export)

---

## SECTION 8 — Assessment Engine

- **AssessmentSession model / table:** EXISTS (Tracks overall session status and total score)
- **AssessmentRound model / table:** EXISTS (Tracks individual round status and score)
- **Session creation endpoint:** EXISTS (`/session/start` creates a new `in_progress` session)
- **State machine transitions:** PARTIAL (Rounds transition from `active` -> `completed` and sessions from `not_started` -> `in_progress` -> `completed` / `expired`. Exact requested states like `ASSIGNED`, `AVAILABLE`, `ROUND_TRANSITION` do not explicitly exist)
- **Exception states (EXPIRED / TERMINATED / CANCELLED / FAILED):** PARTIAL (Only `expired` state is explicitly handled in the auto-timeout logic of `session_service.py`)

---

## SECTION 9 — Existing Assessment Rounds

- **Aptitude round:** EXISTS (Logic and endpoints implemented)
- **Coding round:** EXISTS (Full integration with problems, test cases, and submissions)
- **Judge0 integration:** EXISTS (External execution via `evaluate_submission` function to remote server)
- **Coding result storage and display:** EXISTS (`CodingSubmission` model persists data, viewed on `CodingResultPage.jsx`)
- **Technical interview round:** EXISTS (AI-driven via Sarvam/Groq APIs on `HumanLikeInterview.jsx`)
- **Interview report generation:** EXISTS (`InterviewReport.jsx` fetches aggregated scores and feedback)
- **HR interview round:** MISSING (No separate HR round flow exists)
- **Resume upload:** EXISTS (`ResumeUpload.jsx` processes PDFs via `/profile/resumes` endpoint)

---

## SECTION 10 — Proctoring & Security

- **Basic proctoring (Tab switch, copy/paste):** EXISTS (Managed via `useBasicProctoring.js`)
- **Advanced proctoring (Camera, face detection):** EXISTS (Managed via `useAdvancedProctoring.js` and `ProctoringVideoDisplay.jsx`)
- **Proctoring data written to the database:** EXISTS (Saved to `proctoring_events` and `advanced_proctoring_events` tables)
- **Kill-switch / toggle to disable proctoring for demo:** MISSING (No explicit environment variable or toggle exists to globally bypass proctoring during demos)

---

## Final Honest Assessment

The EDI5 platform is in an advanced state of development. The core architecture—including user registration, role-based profiles (Student, Faculty, TPO), and the complete assessment pipeline (Aptitude -> Coding with Judge0 -> AI Interview)—is fully functional and wired end-to-end to PostgreSQL. Dashboard metrics for Faculty and TPOs successfully fetch and calculate real data from these assessments. 

**However, significant gaps remain:**
1. **Mock Data:** Placement drive details in the TPO dashboard are hardcoded shells.
2. **Missing Admin Features:** There is no CRUD interface for managing assessment questions or global system configurations.
3. **Assessment Modes:** There is no distinction between "Practice" and "Official" assessment modes.
4. **Dev Experience:** The lack of a proctoring bypass toggle makes local testing and demonstrations cumbersome.
