# Frontend Implementation

## Phase 1 — Scaffold
- [x] Create Vite + React project
- [x] Install dependencies (axios, react-router-dom, tailwindcss)
- [x] Configure TailwindCSS with dark theme
- [x] Create [index.css](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/index.css) with theme tokens

## Phase 2 — Services & Hooks
- [x] [api.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/services/api.js) — Axios instance + interceptors
- [x] [authService.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/services/authService.js) — register, login
- [x] [sessionService.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/services/sessionService.js) — start, status
- [x] [aptitudeService.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/services/aptitudeService.js) — next question, submit, result
- [x] [useAuth.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/hooks/useAuth.js) hook
- [x] [useSession.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/hooks/useSession.js) hook

## Phase 3 — Components
- [x] [PrivateRoute.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/components/PrivateRoute.jsx)
- [x] [Navbar.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/components/Navbar.jsx)
- [x] [QuestionCard.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/components/QuestionCard.jsx)
- [x] [Timer.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/components/Timer.jsx)

## Phase 4 — Pages
- [x] [Login.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Login.jsx)
- [x] [Register.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Register.jsx)
- [x] [Dashboard.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Dashboard.jsx)
- [x] [AptitudeTest.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/AptitudeTest.jsx)
- [x] [Result.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Result.jsx)

## Phase 5 — App Wiring & Verification
- [x] [App.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/App.jsx) with routes
- [x] [main.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/main.jsx) entry point
- [x] Build check — ✅ zero errors
- [x] Inter font added to index.html

## Phase 6 — RL Demonstration UI/UX
- [x] Add `average_response_time`, `longest_correct_streak`, `difficulty_progression`, `rl_report` to basic `/result` backend API
- [x] Implement Question Navigator component (Grid of states: Active, Answered, Unanswered)
- [x] Implement Submit Test Confirmation Modal
- [x] Update [Result.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Result.jsx) with Difficulty Progression visualization
- [x] Update `Result.js  - [x] Integrate learning metrics into `/result` endpoint
- [x] **Frontend Dashboard Update (Phase 5)**
  - [x] Configure standard React routing for aptitude round
  - [x] Replace dashboard entry point with new API integration
- [x] **Frontend Architecture Update (Phase 6)**
  - [x] Implement adaptive question UI state and interactions
  - [x] Build Test Progress Sidebar indicating answered/skipped questions
  - [x] Build Detailed Results Page parsing RL stats into UX metrics
- [x] **Frontend Theme Consistency (Phase 7)**
  - [x] Refactor dark theme tokens in [index.css](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/index.css) to Light Theme layout (`#F4F3FF` base, `#FFFFFF` cards, `#0A0F1E` navbar).
  - [x] Apply Primary Accent `#6C63FF` to interactive elements (Next/Submit Buttons, progress circles).
  - [x] Enforce `Syne` and `JetBrains Mono` fonts for Header and metrics typography.
  - [x] Unify Login, Register, Dashboard, Assessment, and Result component architectures.
  - [x] Run local visual verification tests across the entire testing funnel. and Deep Navy muted themes applied

## Phase 8 — Critical Bug Fixes
- [x] Fixed React Strict Mode double API invocation pushing initial state to Question 2
- [x] Fixed naive time UTC-to-Local conversion resolving in timer jumping to 360 hours
- [x] Fixed UI Unmounting of Timer widget during API loading requests

## Phase 9 — Demonstration Prep & Network Hardening
  - [x] Reduce `MAX_QUESTIONS` sequence limit from 20 to exactly 10 for rapid demonstrations.
  - [x] Enforce hard network halt with a "Connection Lost" modal if the backend is shut down mid-test, explicitly blocking further arbitrary UX continuity.
  - [x] Fixed stale-closure issue in [AptitudeTest.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/AptitudeTest.jsx) preventing Proctoring APIs (`log-event`) from correctly receiving `session_id`, connecting the frontend tracking correctly to the backend router.
  - [x] Restarted local FastAPI backend process resolving silent `ERR_CONNECTION_REFUSED` crash loops preventing session starts.
  - [x] Built the [Instructions](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/pages/Instructions.jsx#6-149) UI intercept page and wired it dynamically between the Dashboard and the Aptitude test to ensure rules and proctoring constraints are understood before the clock runs.
  - [x] Refactored [useProctoring.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment/frontend/src/hooks/useProctoring.js) initialization to explicitly attach `visibilitychange` and `fullscreenchange` DOM listeners asynchronously, preventing the Camera device prompt from blocking violation tracking.
  - [x] Hardened Tab-Switch tracking by intercepting `window.onblur` to catch system popups and loss of focus, triggering auto-submit lockout on 3 strikes.
  - [x] Implemented continuous live `<video>` preview for the camera feed, mitigating React Strict Mode unmount tearing by binding the active `MediaStream` to a persistent cleanup `useRef`.
  - [x] Corrected `document` fullscreen API constraints by calculating `window.innerHeight` vs `screen.height` natively via `resize` events to reliably identify keyboard F11 triggers.
