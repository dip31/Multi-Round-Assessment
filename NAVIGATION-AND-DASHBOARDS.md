# Navigation and Dashboard Connections

## React mounting

The application starts from [`frontend/index.html`](frontend/index.html). This file is only the Vite/React mounting shell:

```html
<div id="root"></div>
<script type="module" src="/src/main.jsx"></script>
```

React then loads [`frontend/src/main.jsx`](frontend/src/main.jsx), which renders [`frontend/src/App.jsx`](frontend/src/App.jsx).

The actual landing page is the React component [`LandingPage.jsx`](frontend/src/pages/LandingPage.jsx), not raw HTML in `index.html`.

## Main navigation flow

```text
Landing page (/)
    ├── Sign in ──────────────> Login page (/login)
    ├── Create account ───────> Registration page (/register)
    └── Page sections
          ├── Rounds
          ├── Who signs in
          └── Integrity

Login page (/login)
    └── Successful login ─────> Role dashboard

Registration page (/register)
    └── Successful registration -> /login
```

The landing-page sign-in and registration buttons use React Router `<Link>` components, so navigation happens without a full browser reload.

## Student assessment flow

The active student dashboard is [`StudentDashboard.jsx`](frontend/src/pages/StudentDashboard.jsx), routed at `/student/dashboard`.

```text
/student/dashboard
    ├── Start aptitude ───────> /aptitude
    ├── Start coding ─────────> /coding
    ├── Start interview ──────> /resume-upload
    ├── Profile ──────────────> /profile
    └── Analytics ────────────> /analytics

/aptitude
    └── Completed test ───────> /result

/coding
    └── Completed round ──────> /coding/result

/coding/result
    ├── Back to dashboard ────> /student/dashboard
    └── Continue interview ───> /interview

/resume-upload
    └── Resume processed ─────> /interview

/interview
    └── Interview completed ──> /interview/report/:interviewId

/interview/report/:interviewId
    └── Back to dashboard ────> /student/dashboard

/analytics
    └── Back to dashboard ────> /student/dashboard

/profile
    └── Back to dashboard ────> /student/dashboard
```

## Student routes

| Page | Route | Component |
|---|---|---|
| Landing page | `/` | [`LandingPage.jsx`](frontend/src/pages/LandingPage.jsx) |
| Login | `/login` | [`Login.jsx`](frontend/src/pages/Login.jsx) |
| Registration | `/register` | [`Register.jsx`](frontend/src/pages/Register.jsx) |
| Legacy assessment dashboard | `/dashboard` (redirects) | [`Dashboard.jsx`](frontend/src/pages/Dashboard.jsx) |
| Profile | `/profile` | [`Profile.jsx`](frontend/src/pages/Profile.jsx) |
| Analytics | `/analytics` | [`Analytics.jsx`](frontend/src/pages/Analytics.jsx) |
| Instructions | `/instructions` | [`Instructions.jsx`](frontend/src/pages/Instructions.jsx) |
| Aptitude test | `/aptitude` | [`AptitudeTest.jsx`](frontend/src/pages/AptitudeTest.jsx) |
| Coding round | `/coding` | [`CodingRound.jsx`](frontend/src/pages/CodingRound.jsx) |
| Coding result | `/coding/result` | [`CodingResultPage.jsx`](frontend/src/pages/CodingResultPage.jsx) |
| Assessment result | `/result` | [`ResultPage.jsx`](frontend/src/pages/ResultPage.jsx) |
| Resume upload | `/resume-upload` | [`ResumeUpload.jsx`](frontend/src/pages/ResumeUpload.jsx) |
| Human-like interview | `/interview` | [`HumanLikeInterview.jsx`](frontend/src/pages/HumanLikeInterview.jsx) |
| Interview report | `/interview/report/:interviewId` | [`InterviewReport.jsx`](frontend/src/pages/InterviewReport.jsx) |
| Role-based student dashboard | `/student/dashboard` | [`StudentDashboard.jsx`](frontend/src/pages/StudentDashboard.jsx) |
| Role-based faculty dashboard | `/faculty/dashboard` | [`FacultyDashboard.jsx`](frontend/src/pages/FacultyDashboard.jsx) |
| Role-based TPO dashboard | `/tpo/dashboard` | [`TPODashboard.jsx`](frontend/src/pages/TPODashboard.jsx) |

## Route protection

Student and assessment pages are wrapped by [`PrivateRoute.jsx`](frontend/src/components/PrivateRoute.jsx).

It checks for:

```js
localStorage.getItem('access_token')
```

If no access token exists, the user is redirected to `/login`.

This means a user can only open the student dashboard and assessment pages after authentication.

## Admin navigation flow

Administrators use a separate login route:

```text
/admin/login
    └── Successful admin login ─> /admin/dashboard
```

The admin routes are:

| Admin page | Route | Component |
|---|---|---|
| Analytics overview | `/admin/dashboard` | [`AdminAnalyticsDashboard.jsx`](frontend/src/pages/AdminAnalyticsDashboard.jsx) |
| Candidate reports | `/admin/analytics` | [`AdminCandidateReports.jsx`](frontend/src/pages/AdminCandidateReports.jsx) |
| Question review | `/admin/review` | [`AdminReview.jsx`](frontend/src/pages/AdminReview.jsx) |
| Pools | `/admin/pools` | [`AdminPools.jsx`](frontend/src/pages/AdminPools.jsx) |
| Proctoring monitor | `/admin/proctoring` | [`AdminProctoringDashboard.jsx`](frontend/src/pages/AdminProctoringDashboard.jsx) |

The admin sidebar is provided by [`AdminLayout.jsx`](frontend/src/components/AdminLayout.jsx). It lets an administrator navigate between:

- Analytics Overview
- Candidate Reports
- Question Review
- Proctoring Monitor
- Sign out

## Admin route protection

Admin pages are wrapped by [`AdminRoute.jsx`](frontend/src/components/AdminRoute.jsx).

The guard:

1. Redirects unauthenticated users to `/admin/login`.
2. Decodes the JWT access token.
3. Checks the `is_admin` claim.
4. Redirects authenticated non-admin users to `/student/dashboard`.

## Role-based dashboard routing

[`roleService.js`](frontend/src/services/roleService.js) defines the intended dashboard for each role:

```js
student: '/student/dashboard',
faculty: '/faculty/dashboard',
tpo: '/tpo/dashboard',
```

The supported role names are:

- `student`
- `faculty`
- `tpo`

The service also normalizes aliases such as:

- `candidate` -> `student`
- `teacher`, `professor`, `staff` -> `faculty`
- `placement_officer`, `placement`, `tpo_officer` -> `tpo`

The role destinations are implemented as routes in [`App.jsx`](frontend/src/App.jsx):

```text
/faculty/dashboard
/tpo/dashboard
```

The current [`Login.jsx`](frontend/src/pages/Login.jsx) now resolves the authenticated backend role through [`roleService.js`](frontend/src/services/roleService.js) and redirects to:

```js
homeForRole(role)
```

Therefore, successful student, faculty, and TPO logins are sent to their role-specific dashboard. If login was triggered by a protected route, the original route is preserved and the role guard decides whether it is allowed.

## Registration and backend data

Registration sends `name`, `email`, `password`, and a validated role (`student`,
`faculty`, or `tpo`) to `POST /api/v1/auth/register`. The role is persisted on the
existing `users.role` column; no duplicate profile tables were introduced because
the current schema has one user profile model.

Dashboard pages load live data from:

```text
GET /api/v1/dashboard/student
GET /api/v1/dashboard/faculty
GET /api/v1/dashboard/tpo
```

Each endpoint requires a bearer token and rejects requests where the URL role does
not match the authenticated user's role. Student history and scores are aggregated
from that user's `assessment_sessions` and `assessment_rounds`. A new account
receives empty collections and null metrics rather than sample identity, scores,
recommendations, or completed rounds. Faculty and TPO currently receive the same
explicit empty-state contract until scoped cohort and placement relationships are
added to the database, so the UI does not present fabricated institutional data.

## Dashboard count

There are currently **6 dashboard pages/components**:

1. Legacy student assessment dashboard component: `Dashboard.jsx` (kept for rollback, no longer active)
2. Active student dashboard: `/student/dashboard`
3. Active faculty dashboard: `/faculty/dashboard`
4. Active TPO dashboard: `/tpo/dashboard`
5. Admin analytics dashboard: `/admin/dashboard`
6. Admin proctoring dashboard: `/admin/proctoring`

There are also two additional admin/analytics destinations:

- `/admin/analytics` — candidate reports
- `/analytics` — student analytics

These are analytics/report pages, not separate dashboard components.

## Fallback route

Any unknown route matches the catch-all route in [`App.jsx`](frontend/src/App.jsx):

```jsx
<Route path="*" element={<Navigate to="/login" replace />} />
```

As a result, an unrecognized URL sends the user to `/login`.
