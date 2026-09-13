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
    └── Successful login ─────> /dashboard

Registration page (/register)
    └── Successful registration -> /login
```

The landing-page sign-in and registration buttons use React Router `<Link>` components, so navigation happens without a full browser reload.

## Student assessment flow

The standard student dashboard is [`Dashboard.jsx`](frontend/src/pages/Dashboard.jsx), routed at `/dashboard`.

```text
/dashboard
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
    ├── Back to dashboard ────> /dashboard
    └── Continue interview ───> /interview

/resume-upload
    └── Resume processed ─────> /interview

/interview
    └── Interview completed ──> /interview/report/:interviewId

/interview/report/:interviewId
    └── Back to dashboard ────> /dashboard

/analytics
    └── Back to dashboard ────> /dashboard

/profile
    └── Back to dashboard ────> /dashboard
```

## Student routes

| Page | Route | Component |
|---|---|---|
| Landing page | `/` | [`LandingPage.jsx`](frontend/src/pages/LandingPage.jsx) |
| Login | `/login` | [`Login.jsx`](frontend/src/pages/Login.jsx) |
| Registration | `/register` | [`Register.jsx`](frontend/src/pages/Register.jsx) |
| Main assessment dashboard | `/dashboard` | [`Dashboard.jsx`](frontend/src/pages/Dashboard.jsx) |
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
4. Redirects authenticated non-admin users to `/dashboard`.

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

## Current role-routing limitation

Only the student role dashboard currently exists:

```text
/student/dashboard
```

These destinations are referenced by [`roleService.js`](frontend/src/services/roleService.js), but are not currently implemented as routes in [`App.jsx`](frontend/src/App.jsx):

```text
/faculty/dashboard
/tpo/dashboard
```

Also, the current [`Login.jsx`](frontend/src/pages/Login.jsx) redirects every successful login to:

```js
navigate('/dashboard')
```

Therefore, the role-based dashboard service is present, but the login flow is not yet using it to send users to `/student/dashboard`, `/faculty/dashboard`, or `/tpo/dashboard`.

## Dashboard count

There are currently **4 implemented dashboard pages**:

1. Main student assessment dashboard: `/dashboard`
2. Role-based student dashboard: `/student/dashboard`
3. Admin analytics dashboard: `/admin/dashboard`
4. Admin proctoring dashboard: `/admin/proctoring`

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
