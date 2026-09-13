/**
 * DashboardSkeleton — layout-mirroring placeholder shown while
 * `useDashboardData` resolves. Mirrors the real grid so the page does not
 * reflow when data lands.
 */

function Shimmer({ className = '' }) {
  return <div className={`animate-pulse rounded-md bg-slate-200/80 ${className}`} />;
}

function Block({ children, className = '' }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 ${className}`}>
      {children}
    </div>
  );
}

export default function DashboardSkeleton({ statCount = 4 }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">Loading dashboard…</span>

      {/* Alerts */}
      <div className="mb-6 space-y-3">
        <div className="h-[74px] animate-pulse rounded-xl bg-slate-200/60" />
        <div className="h-[74px] animate-pulse rounded-xl bg-slate-200/60" />
      </div>

      {/* Stat strip */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: statCount }).map((_, i) => (
          <Block key={i} className="p-5">
            <div className="flex items-start justify-between">
              <Shimmer className="h-3 w-24" />
              <Shimmer className="h-9 w-9 rounded-lg" />
            </div>
            <Shimmer className="mt-4 h-7 w-16" />
            <Shimmer className="mt-3 h-3 w-28" />
          </Block>
        ))}
      </div>

      {/* Rounds */}
      <div className="mb-6">
        <Shimmer className="mb-4 h-5 w-40" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Block key={i} className="p-5">
              <div className="flex gap-3">
                <Shimmer className="h-10 w-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Shimmer className="h-4 w-32" />
                  <Shimmer className="h-3 w-full" />
                </div>
              </div>
              <div className="mt-5 grid grid-cols-3 gap-3 border-t border-slate-100 pt-4">
                {Array.from({ length: 3 }).map((__, j) => (
                  <div key={j} className="space-y-2">
                    <Shimmer className="h-2.5 w-14" />
                    <Shimmer className="h-5 w-10" />
                  </div>
                ))}
              </div>
              <Shimmer className="mt-5 h-8 w-full rounded-lg" />
            </Block>
          ))}
        </div>
      </div>

      {/* Trend chart + readiness donut */}
      <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Block className="xl:col-span-2">
          <Shimmer className="h-5 w-48" />
          <Shimmer className="mt-2 h-3 w-64" />
          <Shimmer className="mt-6 h-[280px] w-full rounded-lg" />
        </Block>
        <Block>
          <Shimmer className="h-5 w-32" />
          <Shimmer className="mx-auto mt-6 h-[180px] w-[180px] rounded-full" />
          <div className="mt-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Shimmer key={i} className="h-4 w-full" />
            ))}
          </div>
        </Block>
      </div>

      {/* Skills radar + recommendations */}
      <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Block>
          <Shimmer className="h-5 w-40" />
          <Shimmer className="mx-auto mt-6 h-[300px] w-full rounded-lg" />
        </Block>
        <Block>
          <Shimmer className="h-5 w-52" />
          <div className="mt-5 space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex gap-3">
                <Shimmer className="h-9 w-9 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Shimmer className="h-4 w-40" />
                  <Shimmer className="h-3 w-full" />
                </div>
              </div>
            ))}
          </div>
        </Block>
      </div>

      {/* Upcoming + activity */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Block key={i}>
            <Shimmer className="h-5 w-36" />
            <div className="mt-6 space-y-5">
              {Array.from({ length: 4 }).map((__, j) => (
                <div key={j} className="flex gap-3">
                  <Shimmer className="h-8 w-8 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Shimmer className="h-3.5 w-3/4" />
                    <Shimmer className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </Block>
        ))}
      </div>
    </div>
  );
}
