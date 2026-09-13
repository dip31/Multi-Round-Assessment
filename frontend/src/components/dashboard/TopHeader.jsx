import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  CircleHelp,
  LogOut,
  Menu,
  Search,
  UserCircle,
  Users,
} from 'lucide-react';

import { roleMeta, roleOrder } from '../../config/dashboardNavigation';

/** Closes the popover when a click lands outside the referenced element. */
function useClickOutside(ref, onOutside, active) {
  useEffect(() => {
    if (!active) return undefined;
    const handleClick = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onOutside();
    };
    const handleKey = (event) => {
      if (event.key === 'Escape') onOutside();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [ref, onOutside, active]);
}

function Popover({ open, onClose, children, className = '' }) {
  const ref = useRef(null);
  useClickOutside(ref, onClose, open);
  if (!open) return null;
  return (
    <div
      ref={ref}
      className={`absolute right-0 top-full z-50 mt-2 rounded-xl border border-slate-200 bg-white shadow-lg shadow-slate-900/5 ${className}`}
      role="menu"
    >
      {children}
    </div>
  );
}

/**
 * Dashboard top header: mobile brand + menu, global search, notifications,
 * help, and a profile dropdown that doubles as the DEMO role switcher.
 *
 * The role switcher exists only because there is no role backend yet — it
 * simply navigates between the three dashboard routes so all can be verified.
 * It is visually flagged as "Demo" so it is not mistaken for a real feature.
 */
export default function TopHeader({
  role,
  profile,
  notifications = [],
  onOpenMobileNav,
}) {
  const navigate = useNavigate();
  const meta = roleMeta[role] ?? { label: 'Dashboard', searchPlaceholder: 'Search…' };

  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [query, setQuery] = useState('');

  const unread = notifications.filter((n) => !n.read).length;
  const displayName = profile?.name ?? 'User';
  const initials =
    profile?.initials ??
    displayName
      .split(' ')
      .map((p) => p[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();

  const submitSearch = (e) => {
    e.preventDefault();
    // UI-only: search is a client-side affordance over mock data.
    // Intentionally a no-op at the header level; sections filter locally.
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
      {/* Mobile: open nav */}
      <button
        type="button"
        onClick={onOpenMobileNav}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent lg:hidden"
        aria-label="Open navigation"
      >
        <Menu size={20} aria-hidden="true" />
      </button>

      {/* Search */}
      <form onSubmit={submitSearch} className="relative min-w-0 flex-1 max-w-xl" role="search">
        <Search
          size={18}
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={meta.searchPlaceholder}
          aria-label="Search"
          className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-accent focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
      </form>

      <div className="ml-auto flex items-center gap-1 sm:gap-2">
        {/* Help */}
        <button
          type="button"
          className="hidden rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:inline-flex"
          aria-label="Help"
          title="Help"
        >
          <CircleHelp size={20} aria-hidden="true" />
        </button>

        {/* Notifications */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setNotifOpen((v) => !v);
              setProfileOpen(false);
            }}
            className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
            aria-expanded={notifOpen}
          >
            <Bell size={20} aria-hidden="true" />
            {unread > 0 && (
              <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unread}
              </span>
            )}
          </button>
          <Popover open={notifOpen} onClose={() => setNotifOpen(false)} className="w-80">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <span className="font-display text-sm font-bold text-slate-900">Notifications</span>
              {unread > 0 && (
                <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent">
                  {unread} new
                </span>
              )}
            </div>
            <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
              {notifications.length === 0 && (
                <li className="px-4 py-6 text-center text-sm text-slate-500">
                  You&apos;re all caught up.
                </li>
              )}
              {notifications.map((n) => (
                <li
                  key={n.id}
                  className={`px-4 py-3 text-sm ${n.read ? 'bg-white' : 'bg-accent/5'}`}
                >
                  <p className="font-medium text-slate-900">{n.title}</p>
                  {n.detail && <p className="mt-0.5 text-slate-500">{n.detail}</p>}
                  {n.time && <p className="mt-1 text-xs text-slate-400">{n.time}</p>}
                </li>
              ))}
            </ul>
          </Popover>
        </div>

        {/* Profile + demo role switcher */}
        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setProfileOpen((v) => !v);
              setNotifOpen(false);
            }}
            className="flex items-center gap-2 rounded-xl p-1 pr-2 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Account menu"
            aria-expanded={profileOpen}
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-sm font-semibold text-white">
              {initials}
            </span>
            <span className="hidden text-left sm:block">
              <span className="block max-w-[10rem] truncate text-sm font-semibold leading-tight text-slate-900">
                {displayName}
              </span>
              <span className="block text-xs capitalize text-slate-500">{meta.label}</span>
            </span>
          </button>
          <Popover open={profileOpen} onClose={() => setProfileOpen(false)} className="w-64">
            <div className="border-b border-slate-200 px-4 py-3">
              <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
              {profile?.email && (
                <p className="truncate text-xs text-slate-500">{profile.email}</p>
              )}
            </div>
            <div className="p-1">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(false);
                  navigate('/profile');
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                role="menuitem"
              >
                <UserCircle size={16} aria-hidden="true" className="text-slate-400" />
                View profile
              </button>
            </div>

            {/* Demo role switcher */}
            <div className="border-t border-slate-200 p-3">
              <div className="mb-2 flex items-center gap-1.5">
                <Users size={13} aria-hidden="true" className="text-slate-400" />
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Switch view
                </span>
                <span className="ml-auto rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-700">
                  Demo
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                {roleOrder.map((r) => {
                  const active = r === role;
                  return (
                    <button
                      key={r}
                      type="button"
                      onClick={() => {
                        setProfileOpen(false);
                        navigate(roleMeta[r].home);
                      }}
                      aria-current={active ? 'true' : undefined}
                      className={[
                        'rounded-lg px-2 py-1.5 text-xs font-medium capitalize transition-colors',
                        active
                          ? 'bg-accent text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
                      ].join(' ')}
                    >
                      {roleMeta[r].label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="border-t border-slate-200 p-1">
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(false);
                  navigate('/login');
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                role="menuitem"
              >
                <LogOut size={16} aria-hidden="true" className="text-slate-400" />
                Sign out
              </button>
            </div>
          </Popover>
        </div>
      </div>
    </header>
  );
}
