import { Link, useLocation } from 'react-router-dom';
import { ChevronsLeft, GraduationCap, X } from 'lucide-react';

import { getNavForRole, roleMeta } from '../../config/dashboardNavigation';

/**
 * Role-driven dashboard sidebar.
 *
 * Desktop: fixed rail, collapsible between 16rem and 5rem.
 * Mobile:  off-canvas drawer with a click-through overlay (rendered by the parent).
 *
 * Active state is computed manually rather than via <NavLink isActive> because
 * several nav entries are same-page hash anchors — NavLink matches on pathname
 * only, so every hash item on the current page would light up at once.
 */
export default function Sidebar({
  role,
  collapsed = false,
  onToggleCollapse,
  mobileOpen = false,
  onCloseMobile,
}) {
  const location = useLocation();
  const navItems = getNavForRole(role);
  const meta = roleMeta[role] ?? { label: 'Dashboard', home: '/' };

  const isItemActive = (item) => {
    const [itemPath, itemHash] = item.to.split('#');
    if (location.pathname !== itemPath) return false;
    // "Overview" (end: true) owns the bare path with no hash.
    if (item.end) return !location.hash;
    return location.hash === `#${itemHash}`;
  };

  return (
    <aside
      className={[
        'fixed inset-y-0 left-0 z-50 flex flex-col border-r border-slate-200 bg-white',
        'transition-[width,transform] duration-200 ease-out',
        collapsed ? 'lg:w-20' : 'lg:w-64',
        'w-72 lg:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full',
      ].join(' ')}
      aria-label={`${meta.label} navigation`}
    >
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 px-5">
        <Link
          to={meta.home}
          className="flex min-w-0 items-center gap-3 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          onClick={onCloseMobile}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-white">
            <GraduationCap size={18} aria-hidden="true" />
          </span>
          {!collapsed && (
            <span className="min-w-0">
              <span className="block truncate font-display text-base font-bold leading-tight text-slate-900">
                EDI5
              </span>
              <span className="block truncate text-xs font-medium text-slate-500">
                {meta.label} portal
              </span>
            </span>
          )}
        </Link>

        {/* Mobile close */}
        <button
          type="button"
          onClick={onCloseMobile}
          className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent lg:hidden"
          aria-label="Close navigation"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isItemActive(item);
            return (
              <li key={item.to}>
                <Link
                  to={item.to}
                  onClick={onCloseMobile}
                  aria-current={active ? 'page' : undefined}
                  title={collapsed ? item.label : undefined}
                  className={[
                    'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                    collapsed ? 'lg:justify-center' : '',
                    active
                      ? 'bg-accent/10 text-accent'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  ].join(' ')}
                >
                  <Icon
                    size={18}
                    aria-hidden="true"
                    className={active ? 'text-accent' : 'text-slate-400 group-hover:text-slate-600'}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Collapse toggle — desktop only */}
      <div className="hidden shrink-0 border-t border-slate-200 p-3 lg:block">
        <button
          type="button"
          onClick={onToggleCollapse}
          className={[
            'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-500',
            'transition-colors hover:bg-slate-100 hover:text-slate-900',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent',
            collapsed ? 'justify-center' : '',
          ].join(' ')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronsLeft
            size={18}
            aria-hidden="true"
            className={`transition-transform duration-200 ${collapsed ? 'rotate-180' : ''}`}
          />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
