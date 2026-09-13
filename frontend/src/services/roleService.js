import api from './api';

/**
 * roleService — the single source of truth for "what role is this user?".
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * Role is genuinely awkward to obtain in this app, and every awkward part is a
 * bug waiting to happen if callers improvise:
 *
 *   1. `POST /auth/login` returns ONLY an access token. The JWT payload is
 *      `{sub, is_admin}` — it does NOT carry `role`. So you cannot decode the
 *      token to learn whether someone is faculty.
 *   2. Role lives on `GET /auth/me` (`UserResponse.role`).
 *   3. `authService.loginUser` already calls `/auth/me`, but in a detached
 *      `.then()` — it does not await it. So for a few hundred milliseconds
 *      after login, `localStorage.user` holds a *fallback* identity with no
 *      role at all.
 *
 * That third point is the trap: a naive `localStorage.getItem('user').role`
 * read immediately after login returns undefined, and the user gets bounced to
 * the wrong dashboard. `resolveRole()` closes that race by awaiting `/auth/me`
 * whenever the cached role is missing.
 *
 * This module is additive — it does not modify `api.js` or `authService.js`.
 */

/** Every role the UI knows how to route to. */
export const ROLES = ['student', 'faculty', 'tpo'];

export const DEFAULT_ROLE = 'student';

/** Where each role lands after login, and what a RoleRoute bounces to. */
export const ROLE_HOME = {
  student: '/student/dashboard',
  faculty: '/faculty/dashboard',
  tpo: '/tpo/dashboard',
};

export const ROLE_LABEL = {
  student: 'Student',
  faculty: 'Faculty',
  tpo: 'TPO',
};

/**
 * Coerce whatever the backend stored into a role this UI can route to.
 *
 * `User.role` is a free-form `String(20)` with no enum or CHECK constraint, so
 * it can legitimately hold 'Student', 'TPO ', 'placement_officer', or 'admin'.
 * Anything unrecognised falls back to student — the least-privileged surface.
 */
export function normalizeRole(raw) {
  if (!raw || typeof raw !== 'string') return null;

  const value = raw.trim().toLowerCase();
  if (!value) return null;

  if (ROLES.includes(value)) return value;

  // Tolerate the spellings a seeding script or admin panel might plausibly use.
  const aliases = {
    tpo_officer: 'tpo',
    placement_officer: 'tpo',
    placement: 'tpo',
    teacher: 'faculty',
    professor: 'faculty',
    staff: 'faculty',
    candidate: 'student',
  };

  return aliases[value] ?? null;
}

/** The cached user object written by authService. Never throws. */
export function readCachedUser() {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    // Corrupt/legacy value — treat as absent rather than breaking the render.
    return null;
  }
}

/**
 * Role from cache only. Synchronous, may be null right after login.
 * Use this for instant paints; use `resolveRole()` when correctness matters.
 */
export function getCachedRole() {
  return normalizeRole(readCachedUser()?.role);
}

/** Mirror the role into its own key so later reads are cheap and unambiguous. */
function cacheRole(role) {
  try {
    localStorage.setItem('user_role', role);

    const user = readCachedUser();
    if (user) {
      localStorage.setItem('user', JSON.stringify({ ...user, role }));
    }
  } catch {
    // Storage full or blocked (private mode) — non-fatal, we just re-fetch.
  }
}

/**
 * The authoritative role, fetching `/auth/me` when the cache has none.
 *
 * @param {{ force?: boolean }} [options] `force: true` skips the cache — use it
 *   immediately after login, where a stale role from a previous session could
 *   otherwise route the new user to the wrong dashboard.
 * @returns {Promise<string|null>} normalized role, or null if not signed in.
 */
export async function resolveRole({ force = false } = {}) {
  if (!localStorage.getItem('access_token')) return null;

  if (!force) {
    const cached = getCachedRole() ?? normalizeRole(localStorage.getItem('user_role'));
    if (cached) return cached;
  }

  try {
    // skipAuthRedirect: a 401 here should surface to the caller, not trigger
    // the global interceptor's hard redirect mid-login.
    const { data } = await api.get('/auth/me', { skipAuthRedirect: true });
    const role = normalizeRole(data?.role) ?? DEFAULT_ROLE;
    cacheRole(role);
    return role;
  } catch {
    // Offline or /auth/me unavailable. Fall back to anything cached rather
    // than locking a legitimate user out of their own dashboard.
    return getCachedRole() ?? normalizeRole(localStorage.getItem('user_role'));
  }
}

/** Post-login destination for a role. */
export function homeForRole(role) {
  return ROLE_HOME[normalizeRole(role) ?? DEFAULT_ROLE] ?? ROLE_HOME[DEFAULT_ROLE];
}

export default {
  ROLES,
  ROLE_HOME,
  ROLE_LABEL,
  DEFAULT_ROLE,
  normalizeRole,
  getCachedRole,
  resolveRole,
  homeForRole,
  readCachedUser,
};
