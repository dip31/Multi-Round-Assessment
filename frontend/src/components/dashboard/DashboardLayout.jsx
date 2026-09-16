import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import TopHeader from './TopHeader';

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

  useEffect(() => {
    if (!location.hash) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: 'smooth' });
  }, [location.hash, location.pathname]);

  return (
    <div className="min-h-screen bg-slate-50">
      <TopHeader role={role} profile={profile} notifications={notifications} onOpenMobileNav={() => {}} />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {headerActions}
        </div>
        {children}
      </main>
    </div>
  );
}
