import CodingEditor from '../components/CodingEditor';

export default function CodingRound() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950 px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1600px]">
        <div className="mb-4 flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-300/70">Coding Challenge</p>
            <h1 className="mt-1 text-2xl font-black tracking-tight text-white sm:text-3xl">Solve, run, and submit in one workspace</h1>
          </div>
          <div className="hidden rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-emerald-200 md:block">
            HackerRank-style UI
          </div>
        </div>
      <CodingEditor />
      </div>
    </div>
  );
}
