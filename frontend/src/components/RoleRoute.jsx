import { useEffect, useRef, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { getCachedRole, homeForRole, resolveRole } from '../services/roleService';

/**
 * RoleRoute — gates a dashboard to a single role.
 *
 * Modeled on the existing `AdminRoute`, with one important difference: admin
 * status is a JWT claim and can be read synchronously, whereas `role` is not in
 * the token and may require an async `/auth/me` round-trip (see roleService).
 * So this component has three outcomes rather than two:
 *
 *   - no token            -> /login
 *   - role known, wrong   -> that user's own dashboard (never a dead end)
 *   - role not yet known  -> a brief checking state, then one of the above
 *
 * SECURITY NOTE, stated plainly: this is a *client-side* guard. It controls
 * which UI renders, nothing more. A determined user can edit localStorage and
 * reach another role's dashboard — which is harmless today because these pages
 * render mock data with no real records in them. The moment these dashboards
 * are wired to live endpoints, the backend must enforce role on every request;
 * this component must not be the only thing standing between a student and
 * another cohort's data.
 */
export default function RoleRoute({ role: requiredRole, children }) {
  const location = useLocation();
  const hasToken = Boolean(localStorage.getItem('access_token'));

  // Synchronous first guess. Usually populated, so the common path never
  // flashes a spinner; null only right after a fresh login.
  const [role, setRole] = useState(() => getCachedRole());
  const [checking, setChecking] = useState(() => hasToken && !getCachedRole());
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!hasToken || role) return;

    let cancelled = false;

    (async () => {
      const resolved = await resolveRole();
      if (cancelled || !mountedRef.current) return;
      setRole(resolved);
      setChecking(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [hasToken, role]);

  if (!hasToken) {
    // Preserve intent so login can send them back here afterwards.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (checking) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center bg-slate-50"
      >
        <div className="flex flex-col items-center gap-3">
          <div
            aria-hidden="true"
            className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-accent"
          />
          <p className="text-sm text-slate-500">Checking your access…</p>
        </div>
      </div>
    );
  }

  // Role resolved but not the one this route serves. Redirect to where they
  // *do* belong rather than showing a bare "denied" screen.
  if (role && role !== requiredRole) {
    return <Navigate to={homeForRole(role)} replace />;
  }

  // A dashboard role must come from the authenticated backend identity. Do not
  // render a role-specific surface when that identity cannot be resolved.
  if (!role) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
