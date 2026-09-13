import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';

import Sidebar from './Sidebar';
import TopHeader from './TopHeader';

const COLLAPSE_KEY = 'edi5.dashboard.sidebarCollapsed';

/**
 * Shared shell for every role dashboard.
 *
 * Owns sidebar collapse (persisted) and mobile drawer state, scroll-to-hash
 * behaviour for the anchor-style nav items, and body scroll locking while the
 * mobile drawer is open.
 *
 * Props:
 *   role           'student' | 'faculty' | 'tpo'
 *   title          page heading
 *   subtitle       supporting line under the heading
 *   headerActions  node rendered right of the page heading
 *   profile        { name, initials, email }
 *   notifications  [{ id, title, detail, time, read }]
 */
export default function DashboardLayout({
  role,
  title,
  subtitle,
  headerActions,
  profile,
  notifications = [],
  children,
}) {
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_KEY, String(next));
      } catch {
        // localStorage unavailable (private mode) — collapse just won't persist.
      }
      return next;
    });
  }, []);

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  // Close the drawer on navigation.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.hash]);

  // Lock body scroll while the drawer is open.
  useEffect(() => {
    if (!mobileOpen) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mobileOpen]);

  // React Router does not scroll to hash targets on its own.
  useEffect(() => {
    if (!location.hash) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    const el = document.getElementById(location.hash.slice(1));
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [location.hash, location.pathname]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        role={role}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
        mobileOpen={mobileOpen}
        onCloseMobile={closeMobile}
      />

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={closeMobile}
          aria-hidden="true"
        />
      )}

      <div
        className={[
          'flex min-h-screen flex-col transition-[padding] duration-200 ease-out',
          collapsed ? 'lg:pl-20' : 'lg:pl-64',
        ].join(' ')}
      >
        <TopHeader
          role={role}
          profile={profile}
          notifications={notifications}
          onOpenMobileNav={() => setMobileOpen(true)}
        />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {(title || headerActions) && (
            <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                {title && (
                  <h1 className="font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                    {title}
                  </h1>
                )}
                {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
              </div>
              {headerActions && (
                <div className="flex shrink-0 flex-wrap items-center gap-2">{headerActions}</div>
              )}
            </div>
          )}

          {children}
        </main>
      </div>
    </div>
  );
}
