# EDI5 — Read-Only Audit: Global Glass Background and Sidebar Styling Not Visible

- **Date:** 2026-10-18
- **Mode:** Strict read-only verification (no application files modified; this report is the only file created)
- **Audit scope:** Why the implemented global atmospheric background and glass sidebar styling are reported as "not visible" after running the application

---

## 1. Executive Summary

**The implemented styling is present, compiled, served, and actively applied by the running application.** Browser-level probes (headless Chrome + raw DevTools Protocol) against the live dev server confirmed every mechanism:

- `body` computes to `rgb(246, 247, 252)` **with the full 5-layer atmospheric gradient** and `background-attachment: fixed`.
- Every page-root inspected computes `background-color: rgba(0, 0, 0, 0)` — the scoped `#root > .bg-slate-50` / `#root > .bg-background` neutralization matches the real DOM and works.
- All four audited sidebars compute `rgba(255, 255, 255, 0.78)` + `backdrop-filter: blur(16px)` + the intended edge shadow from `.sidebar-glass`.
- Programmatic pixel sampling of screenshots proves all four gradient tints render (soft blue top-left, lavender top-right, pink bottom-right, blue bottom-left).

**The reason the changes are "not visible" is perceptual, not mechanical:**

1. **The effects are intentionally restrained and mathematically tiny.** The glass sidebar sits over a near-white backdrop, so 78 % white + blur composites to within **≤ 7 RGB units** of the previous solid white — and `backdrop-filter: blur()` cannot be perceived when there is no high-contrast content behind the sidebar (only a flat pastel gradient).
2. **The gradient is masked where users look.** The strongest corner tints (~19–30 RGB units) occur at the extreme top corners, which are covered by the Navbar (`bg-white/90`), and everywhere else by content cards/sections. It is clearly visible only in empty page margins/gutters (measured e.g. `(10,70) = rgb(229,239,254)` on the login page left margin vs. the old flat `rgb(248,250,252)`).
3. **The TPO rail is a small auto-height element** (~64 px wide × ~280 px tall when collapsed) — below it the column is raw page background, so the glass surface occupies a small fraction of that sidebar column.

No broken code was found. `docs/` exists, so this report was created at the required path without creating directories.

---

## 2. Working-Tree State (recorded before and after inspection)

| Check | Result |
|---|---|
| `git status --short` | **128 changed paths** (all pre-existing: backend files, frontend files from earlier tasks, untracked tests) — identical before and after the audit |
| `git diff --cached` | **Empty** — nothing staged; audit staged nothing |
| Reset / revert / stash / clean / commit / push | **Not performed** |
| Files modified by this audit | **Only** `docs/GLOBAL_GLASS_STYLING_VERIFICATION_AUDIT.md` |
| Five implementation files (diffstat vs HEAD) | `index.css +27/-…`, `StudentSidebar.jsx 14`, `StudentModeSidebar.jsx 18`, `AdminLayout.jsx 18`, `TPODashboard.jsx 422` (422 includes earlier tasks' uncommitted roster/analytics removal work) — unchanged during audit |

Scratch artifacts (screenshots, DOM dumps, CDP scripts) were written **outside the repository** to `C:\Users\Akshada\AppData\Local\Temp\opencode\audit\`.

### Implementation file mtimes vs. running dev server

| Event | Time |
|---|---|
| Vite dev server (PID 11684) started | 2026-10-17 **21:30:04** |
| Uvicorn backend (PID 21768) started | 2026-10-17 21:29:57 |
| `index.css` / sidebars / `TPODashboard.jsx` last written | 2026-10-18 **00:16:58 – 00:18:22** (≈ 2 h 47 m *after* server start) |
| `frontend/dist/assets/index-E9V6L5xr.css` built | 2026-10-18 00:23:30 (audit-relevant only if a static build were served — it is not; see §5) |

---

## 3. Files Inspected

**Implementation (all five):** `frontend/src/index.css`, `frontend/src/components/StudentSidebar.jsx`, `frontend/src/components/StudentModeSidebar.jsx`, `frontend/src/components/AdminLayout.jsx`, `frontend/src/pages/TPODashboard.jsx`

**Entry/build:** `frontend/index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/vite.config.js`, `frontend/dist/assets/index-E9V6L5xr.css` (production build output)

**Route wrappers:** `PrivateRoute.jsx`, `RoleRoute.jsx`, `AdminRoute.jsx`, `ErrorBoundary.jsx`

**Layouts:** `StudentLayout.jsx`, `StudentModeLayout.jsx`, `AdminLayout.jsx`, `Navbar.jsx`

**Runtime/service:** `app/main.py` (static mounts), `app/api/v1/router.py`, `app/modules/auth/routers/auth_router.py` (login endpoint), process command lines (PID 11684, 21768), listening ports

**Runtime artifacts (browser):** DOM dump of `/login`, computed-style probes of `/`, `/home`, `/tpo/dashboard`, `/tpo/analytics`, `/admin/dashboard`; screenshots desktop + mobile; pixel samples via `System.Drawing`

**Read-only data:** `.env` `DATABASE_URL` (credentials redacted in this report), `users` table (emails/roles only)

---

## 4. Background CSS Trace and Actual Wrapper Hierarchy

### 4.1 Is the gradient in the source and the bundle?

- **Source:** `index.css` `@layer base body` contains `background-color: #F6F7FC`, four `radial-gradient` layers (blue TL `rgba(191,219,254,.55)`, lavender TR `rgba(221,214,254,.45)`, pink BR `rgba(252,231,243,.5)`, blue BL `rgba(219,234,254,.5)`), a base `linear-gradient(#F8FAFF → #F5F6FC)`, `background-attachment: fixed`.
- **Compiled bundle (`dist/assets/index-E9V6L5xr.css`, 124 794 bytes):** confirmed present (Lightning CSS minified to hex alpha: `radial-gradient(1100px 560px at 6% -8%,#bfdbfe8c,#0000 62%),...;background-attachment:fixed`).

### 4.2 Is the stylesheet imported by the real entry point?

**Confirmed.** `index.html → /src/main.jsx → import './index.css'`. A repo-wide scan found **exactly one** CSS import in `frontend/src` (main.jsx:3). `App.css` is referenced nowhere. `index.html` has no inline styles, no `html/body` background styles.

### 4.3 Does anything override the body background?

Compiled-CSS scan: `body{...background...}` rules = **1** (the gradient). `html{...background...}` rules = **0**. `#root{...}` background rules = **0**. No second stylesheet exists.

### 4.4 Actual hierarchy from `#root` to content

Route wrappers are transparent to the DOM:

| Layer | Renders extra DOM? |
|---|---|
| `BrowserRouter` / `Routes` / `Route` | No |
| `PrivateRoute`, `RoleRoute`, `AdminRoute` | No (return `children` or `<Navigate>`) |
| `ErrorBoundary` | No (returns `children` unless erroring) |
| Layouts (`StudentModeLayout`, `AdminLayout`) | **Yes** — their root `<div>` is the direct child of `#root` |
| Page components with own root (TPO*, Login, Dashboard…) | Their root `<div>` is the direct child of `#root` |

**Browser-confirmed root children (CDP `getComputedStyle` on the running app):**

| URL | `#root` first element class | Computed `background-color` |
|---|---|---|
| `/login` | `min-h-screen bg-slate-50 … flex flex-col` | **`rgba(0, 0, 0, 0)`** |
| `/home` | `flex min-h-screen bg-slate-50` (StudentModeLayout) | **`rgba(0, 0, 0, 0)`** |
| `/tpo/dashboard` | `min-h-screen bg-slate-50 …` | **`rgba(0, 0, 0, 0)`** |
| `/tpo/analytics` | `min-h-screen bg-slate-50 …` | **`rgba(0, 0, 0, 0)`** |
| `/admin/dashboard` | `flex min-h-screen` (AdminLayout, bg class removed in markup) | **`rgba(0, 0, 0, 0)`** |

So the scoped selector `#root > .bg-slate-50, #root > .bg-background` **matches the real rendered roots** and applies (unlayered rule → wins over Tailwind's layered `.bg-slate-50` utility; verified by computed style, not by reasoning alone).

### 4.5 Is the gradient on the element that fills the viewport?

**Confirmed:** `background-image` + `background-attachment: fixed` compute on `body`; `html` has no background, so the body background propagates to the canvas per CSS spec; `min-height: 100vh` on body; canvas fills scrolled content.

### 4.6 Pixel evidence that the gradient renders (programmatic; the audit model cannot view images directly)

Login page (no content in the margins — the cleanest probe surface), desktop 1440×900:

| Sample point | Measured | Intended tint | Verdict |
|---|---|---|---|
| (10, 70) left-top margin | `rgb(229,239,254)` | soft blue ≈ `rgb(229,240,254)` | ✅ matches model |
| (1430, 70) right-top margin | `rgb(238,237,254)` | lavender (R>G) | ✅ |
| (10, 700) left-bottom margin | `rgb(237,243,252)` | blue BL | ✅ |
| (1430, 860) right-bottom | `rgb(248,239,247)` | pink (G dip) | ✅ |
| (10, 450) mid-left | `rgb(245,247,253)` | near base | ✅ |
| Old flat background | `rgb(248,250,252)` | — | deltas ≈ 19–30 units at corners, ≤ 6 units mid-screen |

Landing page top corners measured `(252,253,255)` / `(254,252,255)` — **exactly** what the model predicts when the Navbar's `rgba(255,255,255,0.9)` sits over the corner tints (0.9×255 + 0.1×225 ≈ 252). The gradient is present; the Navbar hides ~90 % of the strongest tint.

### 4.7 Cascade / specificity / layers

- `.sidebar-glass` and the `#root >` rule are both in the bundle (regex-verified).
- The `#root >` rule sits **outside** any `@layer` after minification → unlayered styles beat layered utilities → wins. Browser computed style proves it (§4.4).
- No `body`/`html`/`#root` competing background rules exist (§4.3).
- Markup elements carrying `.sidebar-glass` have no competing `bg-*` class (verified in all four sidebars; computed `background-color` matches the hand-written value `rgba(255,255,255,0.78)` exactly).

---

## 5. Sidebar Component and CSS Trace

### 5.1 `.sidebar-glass` definition (compiled)

```css
.sidebar-glass{-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);background-color:#ffffffc7;box-shadow:4px 0 24px #94a3b81a}
@supports not ((-webkit-backdrop-filter:blur(2px)) or (backdrop-filter:blur(2px))){.sidebar-glass{background-color:#fffffff7}}
```

`#ffffffc7` = `rgba(255,255,255,0.78)` ✅, fallback `#fffffff7` = 0.97 ✅.

### 5.2 Runtime probes on the running dev server (CDP `getComputedStyle`)

| Sidebar | Route probed | Element found | Computed background | Computed backdrop-filter | Computed shadow | Position |
|---|---|---|---|---|---|---|
| StudentModeSidebar desktop | `/home` | `aside.sidebar-glass` `w-64 … sticky` | `rgba(255,255,255,0.78)` | **`blur(16px)`** | `rgba(148,163,184,0.1) 4px 0 24px` | sticky |
| StudentModeSidebar mobile drawer | `/home` | `aside.sidebar-glass lg:hidden … w-72` | `rgba(255,255,255,0.78)` | **`blur(16px)`** | same | fixed |
| AdminLayout sidebar | `/admin/dashboard` | `div.w-56.sidebar-glass.h-screen.fixed` | `rgba(255,255,255,0.78)` | **`blur(16px)`** | same | fixed |
| TPODashboard rail | `/tpo/dashboard` | `div.sidebar-glass … w-24 … fixed` | `rgba(255,255,255,0.78)` | **`blur(16px)`** | same | fixed |
| TPO Analytics page | `/tpo/analytics` | `glassCount: 0`, `asideCount: 0` — page has **no sidebar by design** (Navbar + own content) | — | — | — | — |

- **Expected component at runtime:** ✅ — `/home` renders `StudentModeSidebar` (aside `w-64`), `/admin/*` renders `AdminLayout`, `/tpo/dashboard` renders its inline rail; classes match the edited source.
- **Class defined in an imported stylesheet:** ✅ (`main.jsx → index.css`, the only stylesheet).
- **Overriding class/inline style:** ❌ none — computed values equal the hand-written CSS.
- **Mobile vs desktop:** both variants carry `sidebar-glass` (desktop + drawer proven for the student sidebar; TPO mobile menu is a modal overlay inside the header — it has never been a glass sidebar panel).
- **Role-specific layouts not covered by the five files:** **FacultyDashboard has no sidebar at all** (Navbar-only chrome — nothing to style). `StudentLayout.jsx` is a **dead import** in `Dashboard.jsx` (never rendered; `/dashboard` redirects to `/home`). The active student shell is `StudentModeLayout` (covered via neutralization rule + `StudentModeSidebar` glass).
- **TPO active-state detection:** source uses `location.pathname` for `/tpo/mock-drives`, `/tpo/students`, `/tpo/analytics`, `/profile` (desktop rail + mobile items); runtime rail probe confirms the rail with these classes renders on the probed URL. The active item pixel at `(32,75)` = `rgb(2,133,210)` (sky-600 icon region) and the student home active nav item at `(30,120)` = `rgb(223,242,254)` ≈ **`bg-sky-100` `(224,242,254)`** exactly — soft blue active states are rendered.

### 5.3 Why the glass is invisible in practice (confirmed by measurement)

- Sidebar over backdrop ≈ `rgb(246,248,253)`: composite = 0.78×255 + 0.22×246 ≈ **253** vs. the previous solid `255` → **Δ ≤ 7/255 ≈ 3 %**. Measured sidebar pixels: `(30,300)=rgb(253,254,255)`, `(200,600)=rgb(252,253,255)`.
- `backdrop-filter: blur(16px)` blurs what is *behind* the sidebar. Behind these sidebars is only a **flat pastel gradient** — blur of a flat field is by definition imperceptible.
- The TPO rail is **auto-height** (`fixed top-0`, no `h-screen`) ≈ 280 px tall: pixels below it are raw gradient (`(40,600)=rgb(235,241,252)`), i.e. most of that "sidebar column" never was a glass surface — this geometry predates the styling change (`bg-white` had the same auto height).
- The Admin sidebar dark→light conversion **is** a large visual change (measured left edge now `(249,252,255)`), so an admin-page observer would notice it; student/TPO observers would not notice ≤ 3 % deltas.

---

## 6. Page-by-Page Verification Table

Browser evidence = observed in headless Chrome against the running dev server (2026-10-18 00:40–00:57). Source evidence = static reading only.

| Page/layout | Actual wrapper (`#root` child) | Background class/style → computed | Sidebar component | Expected styling present? |
|---|---|---|---|---|
| Landing `/` | page root div | `bg-slate-50` → **transparent** (computed `rgba(0,0,0,0)` probed on `/login`; same selector) | none (Navbar) | Background: **browser-confirmed** (pixel tints) |
| Login `/login` | page root div | `bg-slate-50` → **transparent** (computed) | none | **Browser-confirmed** |
| Student home `/home` | `StudentModeLayout` root | `bg-slate-50` → **transparent** (computed) | `StudentModeSidebar` | Background ✅ + glass ✅ **browser-confirmed** (computed + pixels) |
| Practice/portfolio/other student-mode pages | `StudentModeLayout` (same component) | same as `/home` | `StudentModeSidebar` | Same as `/home` (source-identical path) |
| Instructions `/instructions` | page root (`bg-background`) | selector in bundle; root is direct child (route structure) | none | **Source-verified only** (not browser-probed) |
| TPO dashboard `/tpo/dashboard` | `TPODashboard` root | `bg-slate-50` → **transparent** (computed) | inline rail (glass, **auto-height ≈ 280 px**) | Background ✅ + rail glass ✅ **browser-confirmed**; small rail = visibility issue |
| TPO analytics `/tpo/analytics` | page root | `bg-slate-50` → **transparent** (computed) | **none by design** (`glassCount 0`) | Background ✅ **browser-confirmed**; no sidebar exists to glass |
| TPO students / mock drives | page root (source) | `bg-slate-50` → same selector | none by design | Source-verified (same root pattern as analytics) |
| Admin pages `/admin/*` | `AdminLayout` root (`flex min-h-screen`, no bg class) | **transparent** (computed) | `AdminLayout` sidebar (light glass) | **Browser-confirmed** — dark→light conversion visible in pixels |
| Dashboard `/dashboard` | `Navigate` → `/home` | — | — | — |
| Faculty dashboard | page root (source) | `bg-slate-50` → selector applies (direct child) | **none exists** | Not applicable — no sidebar in component |
| Dark pages: `CodingRoundV2`, `CodingResultPage`, `InterviewRoom`, `HumanLikeInterview`, `AdminLogin`, `AptitudeTest` | own dark/functional roots | **intentionally unchanged** (reported exceptions from implementation) | n/a | Background intentionally not applied (per approved plan) |
| Navbar (all light pages) | `nav` | already glass `bg-white/90 + backdrop-blur-md` (computed `oklab(… / 0.9)`) | n/a | Untouched by design |

Mobile width (390×844, DPR 2): `/home` screenshot left edge measured `rgb(220,231,252)` — gradient tint visible on mobile ✅ (drawer closed; drawer glass computed ✅ desktop session).

**Tooling statement:** Browser verification **was performed** using installed Google Chrome (headless) driven by the raw Chrome DevTools Protocol (no playwright/puppeteer available — none installed, none added). Screenshots were **pixel-analyzed programmatically** (`System.Drawing`) because this audit model cannot view image files directly; human eyeball confirmation of the screenshots is still recommended.

---

## 7. Build / Runtime / Browser Evidence

| Evidence | Result |
|---|---|
| `npx vite build` (implementation session, 00:23) | exit 0, no diagnostics |
| `npm test` (implementation session) | 34/34 pass (styling-independent — **not** used as visual proof) |
| Production CSS contains gradient / `.sidebar-glass` / `#root` rule / `fixed` | ✅ all four regex-verified in `dist/assets/index-E9V6L5xr.css` |
| **How the app is actually served** | Vite **dev server** PID 11684, cmdline `…\Multi-Round-Assessment\frontend\node_modules\.bin\..\vite\bin\vite.js`, port 5173 — *this* project. Backend uvicorn PID 21768, `app.main:app`, port 8000, **no StaticFiles mount** (API only). Dist build is irrelevant to what the user sees. |
| Fresh headless Chrome against the running server | Serves and applies the **current** CSS (computed styles prove it) → "running app = wrong directory / stale build" **disproven** |
| Browser cache / stale tab | **Unverified** for the user's specific tab (see §8 L1) |
| Dev server started 21:30, files edited 00:16–00:18 | Vite transforms on demand; fresh loads get current code (proven). A tab open from before the edits would need a working HMR push or manual reload. |
| DOM dump `/login` | `#root > div.min-h-screen.bg-slate-50…` — selector target confirmed in real DOM |

---

## 8. Root-Cause Classification

### Confirmed (proven by source, compiled CSS, DOM, computed styles, or pixels)

| ID | Cause |
|---|---|
| **C1** | **There is no functional defect.** Gradient, neutralization rule, and glass utilities are in the source, in the bundle, served by the running dev server, and applied per browser computed styles on `/login`, `/home`, `/tpo/dashboard`, `/tpo/analytics`, `/admin/dashboard`. |
| **C2** | **Perceptual invisibility of the glass:** `rgba(255,255,255,0.78)` over a near-white backdrop composites to ≤ 7 RGB units from the old `bg-white`; `blur(16px)` has no high-frequency content behind these sidebars (only a flat pastel), so blur is physically imperceptible. Measured: sidebar `(252–253, 253–254, 255)`. |
| **C3** | **Perceptual subtlety + masking of the gradient:** corner tints (Δ ≈ 19–30 units) are covered by the Navbar (`bg-white/90`, top corners measured `(252,253,255)` = 0.9 white + tint, exact model match) and by content cards/sections; mid-screen Δ ≤ 6 units. Gradient reads as "unchanged flat background" except in empty margins (login/analytics left edge measured `(228–232, 239–241, 254)`). |
| **C4** | **TPO rail is small:** auto-height ≈ 280 px, collapsed width 64 px → tiny glass area; the rest of the left column is raw gradient (pixel `(40,600)=rgb(235,241,252)`). Geometry unchanged from the old `bg-white` rail (pre-existing). |
| **C5** | **Ruled out with evidence:** stylesheet-not-imported; wrong entry point; second stylesheet overriding; `html`/`#root` opaque paint; selector mismatch vs real DOM; Tailwind purging `.sidebar-glass`; cascade/specificity override; opaque nested page container (roots compute transparent); wrong sidebar component rendered; app running from another directory/port; backend serving stale static build; changes absent from the running app (fresh Chrome loads current code). |

### Likely (supported, not directly observable)

| ID | Cause |
|---|---|
| **L1** | The user's browser tab served via HMR before the 00:16–00:18 edits and did not receive/reload the update (server started 21:30; tab state not observable). A hard reload would be required. |
| **L2** | Expectation mismatch: the reference image was never available to the implementer; the implementation deliberately followed the text spec ("restrained", "low-contrast", "soft"), which guarantees an easy-to-miss result on light pages. |

### Unverified (needs evidence the audit cannot obtain)

| ID | Item |
|---|---|
| **U1** | What the user actually looked at (page, viewport size, timing, hard-reload state, dev vs. dist). |
| **U2** | Content below the fold on very long pages (fixed-attachment background is spec-correct over the full canvas but was not screenshotted while scrolled). |
| **U3** | The contents of the original reference image (never present in conversation or on disk). |
| **U4** | Human aesthetic judgment of the captured screenshots (pixel data only was analyzed here). |

---

## 9. Minimal Recommended Fixes (priority order — do not implement yet)

1. **Increase gradient presence (index.css only).** Raise radial alphas (e.g. 0.55 → 0.7–0.8 for TL blue / TR lavender / BR pink) and/or shrink stop radii so tints survive below the Navbar and read at typical mid-screen margins; optionally add a faint tinted section behind content gutters. Keeps scope = one file.
2. **Make the glass read as glass (index.css only).** Because the backdrop is flat, blur alone can never show: give `.sidebar-glass` a slightly translucent base with a cool tint (e.g. `rgba(255,255,255,0.65–0.7)` + a 1–2 % blue tint), a visible hairline edge (`border`/inset ring already partially exists via `border-r border-slate-200`), and keep the shadow. Contrast vs. old white then exceeds the current ~3 %.
3. **TPO rail full height (`TPODashboard.jsx`, one class).** Add `h-screen` (or equivalent) so the glass column spans the viewport; today ≈ 280 px of glass hides the effect.
4. **Tell the user to hard-reload** (Ctrl+Shift+R) or restart the tab to eliminate L1 before re-judging.
5. **Verification protocol for the fix round:** re-run the same CDP probe + pixel sampling (target: sidebar vs. page-background delta ≥ 15 RGB units; corner tint ≥ 40 units below navbar) and obtain human confirmation from the screenshots.

## 10. Exact Next Steps for Implementation

1. Get user sign-off on fixes 1–3 in §9 (all are styling-only; files: `frontend/src/index.css`, optionally `frontend/src/pages/TPODashboard.jsx` for the single `h-screen` class).
2. Apply edits; re-run `npx vite build --logLevel error` and `npm test` (expect 34/34 — regression only, not visual proof).
3. Re-run the CDP probe scripts (saved at `C:\Users\Akshada\AppData\Local\Temp\opencode\audit\cdp_audit.ps1`, `cdp_admin.ps1`) against the running dev server; capture desktop + mobile screenshots; re-sample pixels against the targets in §9.5.
4. Present screenshots for human visual confirmation — the audit model cannot view them.
5. Only after that, consider this EDI5 item closed.

*End of report — no application code or configuration was modified during this audit.*
