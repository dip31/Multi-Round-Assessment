# Project Problems Detailed Report

Date: 2026-05-13
Project: Multi-Round-Assesment

## 1) Scope and Method

This report was generated from direct project checks:

- Workspace diagnostics (IDE error scan)
- Backend health script execution
- Frontend lint run (`npm run lint`)
- Frontend production build (`npm run build`)
- Frontend dependency audit (`npm audit --json`)
- Python dependency consistency check (`pip check`)
- Python source compile check (`python -m compileall`)

## 2) Executive Summary

- Backend status: Mostly healthy, but one critical security misconfiguration detected.
- Frontend status: Build succeeds, but lint fails heavily and includes correctness/hook-order issues that can cause runtime defects.
- Dependency security: Frontend dependencies include known high/moderate vulnerabilities.
- Testability: Backend and frontend test command configuration is inconsistent with current environment/scripts.

Overall risk level: HIGH

## 3) Detailed Findings

### A. Security Findings (High Priority)

1. Default SECRET_KEY in backend configuration
- Evidence: backend health check fails with message: "SECRET_KEY using default value (security risk)"
- Source check logic: `backend_health_check.py` checks if `settings.SECRET_KEY == "change-me-in-production"`.
- Impact:
  - Token/signature forgery risk if default key is publicly known or guessable.
  - Session/auth compromise potential.
- Status: OPEN
- Recommended fix:
  - Set a strong random SECRET_KEY in environment configuration.
  - Ensure no default production key fallback in deployment.

2. Frontend npm vulnerabilities found by audit (7 total)
- Summary:
  - High: 4
  - Moderate: 3
  - Total: 7
- Affected packages and risk highlights:
  - axios (direct): multiple advisories including SSRF/prototype-pollution related chains.
  - vite (direct): high severity dev-server file read / fs deny bypass / path traversal advisories in affected range.
  - flatted (transitive): prototype pollution advisory.
  - picomatch (transitive): ReDoS/method-injection advisories.
  - postcss (transitive): XSS-related output escaping advisory.
  - follow-redirects (transitive): header leakage advisory.
  - brace-expansion (transitive): process hang/memory exhaustion advisory.
- Status: OPEN
- Recommended fix:
  - Run `npm audit fix` and then explicit upgrades for direct deps (`axios`, `vite`) to patched versions.
  - Re-run audit and verify vulnerability count is zero (or documented exceptions).

### B. Frontend Code Quality and Correctness Findings (High/Medium Priority)

#### B1. ESLint Overall

- Command: `npm run lint`
- Result: FAILED
- Totals:
  - 56 errors
  - 18 warnings
  - 74 total problems

#### B2. Critical Hook/Execution-Order Issues

These are stronger signals than style warnings because they can cause stale values, runtime bugs, or inconsistent behavior:

1. Access before declaration (`react-hooks/immutability` / closure ordering)
- `frontend/src/hooks/useBasicAdvancedProctoring.js`
  - `logProctoringEvent` used before declaration.
  - `updateRiskScore` used before declaration.
- `frontend/src/hooks/useProctoring.js`
  - `handleIdleActivity` used before declaration.
- `frontend/src/pages/InterviewRoom.jsx`
  - `fetchNextQuestion` accessed before declaration.

2. Ref access misuse (`react-hooks/refs`)
- `frontend/src/pages/HumanLikeInterview.jsx`
  - Ref usage flagged with "Cannot access refs during render" warning at the `video` ref binding site.

3. setState directly in effect body (`react-hooks/set-state-in-effect`)
- `frontend/src/components/AdvancedProctoringMonitor.jsx`
  - `setRecentViolations([])` called synchronously within effect body.

4. Hook dependency integrity (`react-hooks/exhaustive-deps`)
- Multiple missing dependency warnings across:
  - `frontend/src/hooks/useAdvancedProctoring.js`
  - `frontend/src/hooks/useBasicAdvancedProctoring.js`
  - `frontend/src/hooks/useProctoring.js`
  - `frontend/src/pages/AptitudeTest.jsx`
  - `frontend/src/pages/AdminProctoringDashboard.jsx`
  - `frontend/src/pages/HumanLikeInterview.jsx`
  - `frontend/src/pages/InterviewRoom.jsx`
  - `frontend/src/pages/Profile.jsx`

#### B3. Unused Variables and Empty Blocks (Maintainability/Defect Risk)

Recurring lint failures include:
- `no-unused-vars` (many files, often unused `e`, `error`, `err`, refs/state values)
- `no-empty` (empty catch/blocks in interview page)
- `no-undef` in frontend test file due CommonJS `require` in ESM lint context

Implication:
- Increases bug surface and masks real defects.
- Reduces confidence in proctoring/interview flow correctness.

### C. Build and Performance Findings (Medium Priority)

1. Frontend production build succeeds but warns about large chunk size
- Build succeeded with output JS chunk around ~1 MB minified.
- Vite warning recommends code-splitting/manualChunks/threshold tuning.
- Impact:
  - Slower initial load on low bandwidth or low-end devices.
- Status: OPEN (optimization)

### D. Testing and Tooling Gaps (Medium Priority)

1. Backend tests cannot run in current venv
- Attempted: `.venv\Scripts\python.exe -m pytest -q`
- Result: `No module named pytest`
- Observed mismatch:
  - README references pytest commands.
  - `requirements.txt` does not include pytest.
- Impact:
  - Cannot validate backend behavior regressions in current setup.

2. Frontend README test commands mismatch scripts
- README references `npm test` and `npm run test:e2e`.
- `frontend/package.json` scripts only include: `dev`, `build`, `lint`, `preview`.
- Impact:
  - Test instructions not executable as documented.
  - CI/test readiness ambiguity.

### E. Backend Structural/Runtime Sanity Checks (Informational)

These checks passed and indicate baseline backend wiring is mostly intact:
- Imports: PASS
- Database connection: PASS
- API routes registration: PASS (41 routes)
- Critical endpoint presence: PASS
- DB model loading: PASS

Python compile check results:
- `python -m compileall app tests *.py` compiled project modules without syntax failures.
- Note: terminal displayed `Can't list '*.py'` for literal wildcard listing step, but core app/tests compilation succeeded.

## 4) Full Frontend Lint File Coverage (Where Problems Exist)

Problems were reported in the following files:

- `frontend/src/components/AdminRoute.jsx`
- `frontend/src/components/AdvancedProctoringMonitor.jsx`
- `frontend/src/components/ProctoringVideoDisplay.jsx`
- `frontend/src/hooks/useAdvancedProctoring.js`
- `frontend/src/hooks/useBasicAdvancedProctoring.js`
- `frontend/src/hooks/useProctoring.js`
- `frontend/src/pages/AdminLogin.jsx`
- `frontend/src/pages/AdminProctoringDashboard.jsx`
- `frontend/src/pages/AptitudeTest.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/pages/HumanLikeInterview.jsx`
- `frontend/src/pages/Instructions.jsx`
- `frontend/src/pages/InterviewReport.jsx`
- `frontend/src/pages/InterviewRoom.jsx`
- `frontend/src/pages/LandingPage.jsx`
- `frontend/src/pages/Login.jsx`
- `frontend/src/pages/Profile.jsx`
- `frontend/src/pages/ResumeUpload.jsx`
- `frontend/tests/test_crash.js`

## 5) Risk-Prioritized Remediation Plan

### Priority 0 (Immediate)
1. Replace production SECRET_KEY default with secure secret injection.
2. Upgrade direct vulnerable deps: `axios`, `vite`.
3. Re-run `npm audit --json` and confirm vulnerability reduction.

### Priority 1
1. Fix hook-order/access-before-declaration issues in:
   - `useBasicAdvancedProctoring.js`
   - `useProctoring.js`
   - `InterviewRoom.jsx`
2. Resolve ref/setState effect anti-patterns in:
   - `HumanLikeInterview.jsx`
   - `AdvancedProctoringMonitor.jsx`

### Priority 2
1. Remove/resolve unused variables and empty blocks across flagged files.
2. Align README test commands with real scripts and install test dependencies (`pytest`, frontend test tooling if required).

### Priority 3
1. Optimize frontend bundle with lazy loading and chunk strategy.
2. Add CI gates for lint, audit, and test to prevent regression.

## 6) Reproduction Commands

Run from project root unless stated otherwise:

- Backend health check:
  - `.\.venv\Scripts\python.exe backend_health_check.py`
- Python compile sanity:
  - `.\.venv\Scripts\python.exe -m compileall app tests *.py`
- Python dependency consistency:
  - `.\.venv\Scripts\python.exe -m pip check`
- Frontend lint:
  - `cd frontend && npm run lint`
- Frontend build:
  - `cd frontend && npm run build`
- Frontend audit:
  - `cd frontend && npm audit --json`

## 7) Conclusion

The project is close to runnable (backend checks mostly pass, frontend build passes), but it is not production-ready due to:
- active secret-key security misconfiguration,
- known vulnerable frontend dependencies,
- significant frontend lint/correctness debt,
- incomplete test tooling setup.

Addressing Priority 0 and Priority 1 items should be treated as release blockers.
