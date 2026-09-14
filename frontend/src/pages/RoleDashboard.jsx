import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BarChart3, ClipboardList, FileText, Users } from 'lucide-react';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { roleMeta } from '../config/dashboardNavigation';
import { useDashboardData } from '../hooks/useDashboardData';

const CONTENT = {
  faculty: {
    title: 'Faculty dashboard',
    subtitle: 'Monitor student participation, performance and skill gaps',
    sections: [
      ['students', 'Students', 'Review student progress and participation.', Users],
      ['analytics', 'Performance', 'Compare cohort scores and identify skill gaps.', BarChart3],
      ['assessments', 'Assessments', 'Manage assessments assigned to your cohorts.', ClipboardList],
      ['reports', 'Reports', 'Open faculty performance and intervention reports.', FileText],
    ],
  },
  tpo: {
    title: 'TPO dashboard',
    subtitle: 'Manage placement readiness, candidates, companies and offers',
    sections: [
      ['pipeline', 'Candidate pipeline', 'Track candidates through placement stages.', Users],
      ['companies', 'Companies', 'Review company drives and hiring requirements.', ClipboardList],
      ['analytics', 'Institution performance', 'View readiness and department analytics.', BarChart3],
      ['reports', 'Reports', 'Open placement activity and offer reports.', FileText],
    ],
  },
};

export default function RoleDashboard({ role }) {
  const content = CONTENT[role];
  const meta = roleMeta[role];
  const { data, loading, error, refetch } = useDashboardData(role);
  const profile = data?.profile;
  const notifications = useMemo(
    () => data?.alerts ?? [],
    [data],
  );

  return (
    <DashboardLayout
      role={role}
      title={content.title}
      subtitle={content.subtitle}
      profile={profile}
      notifications={notifications}
    >
      {loading && (
        <p className="mb-6 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">
          Loading live dashboard data...
        </p>
      )}
      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          Unable to load dashboard data. <button type="button" className="font-semibold underline" onClick={refetch}>Retry</button>
        </div>
      )}
      {!loading && !error && (
        <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {(data?.stats ?? []).map((stat) => (
            <div key={stat.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{stat.label}</p>
              <p className="mt-3 text-3xl font-black text-slate-900">
                {stat.value ?? '—'}{stat.unit === '%' ? '%' : stat.unit ? ` ${stat.unit}` : ''}
              </p>
              <p className="mt-2 text-xs text-slate-500">{stat.hint}</p>
            </div>
          ))}
        </section>
      )}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {content.sections.map(([id, title, description, Icon]) => (
          <Link
            key={id}
            to={`${meta.home}#${id}`}
            id={id}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-md"
          >
            <Icon className="mb-4 text-accent" size={22} aria-hidden="true" />
            <h2 className="font-display text-base font-semibold text-slate-900">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-accent">
              Open section <ArrowRight size={14} aria-hidden="true" />
            </span>
          </Link>
        ))}
      </section>
    </DashboardLayout>
  );
}
