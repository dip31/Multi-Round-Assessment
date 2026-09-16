import { Link, useNavigate } from 'react-router-dom';
import DashboardLayout from '../components/dashboard/DashboardLayout';
import { useDashboardData } from '../hooks/useDashboardData';

function formatValue(stat) {
  if (stat.value === null || stat.value === undefined) return '—';
  return `${stat.value}${stat.unit === '%' ? '%' : stat.unit ? ` ${stat.unit}` : ''}`;
}

export default function StudentDashboard() {
  const { data, loading, error, refetch } = useDashboardData('student');
  const navigate = useNavigate();
  const profile = data?.profile;

  return (
    <DashboardLayout
      role="student"
      title={profile ? `Welcome back, ${profile.name.split(' ')[0]}` : 'Placement readiness'}
      subtitle="Your assessment progress, skills and next steps"
      profile={profile}
      notifications={data?.alerts ?? []}
    >
      {loading && <p className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-500">Loading dashboard data...</p>}
      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
          <p>Dashboard data could not be loaded.</p>
          <button type="button" onClick={refetch} className="mt-3 font-semibold underline">Retry</button>
        </div>
      )}
      {!loading && !error && data && (
        <>
          <section id="overview" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {data.stats.map((stat) => (
              <article key={stat.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{stat.label}</p>
                <p className="mt-3 text-3xl font-black text-slate-900">{formatValue(stat)}</p>
                <p className="mt-2 text-xs text-slate-500">{stat.hint}</p>
              </article>
            ))}
          </section>

          <section id="assessments" className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Assessment rounds</h2>
            {data.rounds.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No assessment rounds yet. Start your first assessment when you are ready.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {data.rounds.map((round) => (
                  <div key={round.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4">
                    <div>
                      <p className="font-semibold text-slate-900">{round.title}</p>
                      <p className="text-sm capitalize text-slate-500">{round.status}</p>
                    </div>
                    {round.route && (
                      <button type="button" onClick={() => navigate(round.route)} className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white">
                        Open round
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            <Link to="/instructions" className="mt-5 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white">
              Start assessment
            </Link>
          </section>

          <section id="progress" className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Progress</h2>
            <p className="mt-3 text-sm text-slate-500">
              {data.performanceTrend.length ? 'Your recorded assessment performance is shown here.' : 'Complete an assessment to see your performance trend.'}
            </p>
          </section>
        </>
      )}
    </DashboardLayout>
  );
}
