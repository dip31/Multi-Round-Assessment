const difficultySteps = ['E', 'M', 'H', 'M'];

export default function RLInsights({ summary }) {
    return (
        <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
            <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                    <h2 className="text-lg font-bold text-white">RL Insights</h2>
                    <p className="text-sm text-slate-400">Interpreting how the system adjusted difficulty</p>
                </div>
                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">
                    {summary.final_difficulty}
                </span>
            </div>

            <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4 text-center">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Increases</p>
                        <p className="mt-2 text-3xl font-black text-sky-300">↑ {summary.increases}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4 text-center">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Decreases</p>
                        <p className="mt-2 text-3xl font-black text-amber-300">↓ {summary.decreases}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4 text-center">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Peak</p>
                        <p className="mt-2 text-2xl font-bold text-white capitalize">{summary.peak_difficulty}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4 text-center">
                        <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Final</p>
                        <p className="mt-2 text-2xl font-bold text-white capitalize">{summary.final_difficulty}</p>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4">
                    <p className="mb-4 text-xs uppercase tracking-[0.22em] text-slate-400">Difficulty path</p>
                    <div className="flex items-center justify-between gap-2 text-center">
                        {difficultySteps.map((step, index) => (
                            <div key={`${step}-${index}`} className="flex flex-1 items-center justify-center gap-2">
                                <span
                                    className={`flex h-12 w-12 items-center justify-center rounded-full border text-sm font-bold ${
                                        step === 'H'
                                            ? 'border-sky-400/30 bg-sky-400/10 text-sky-300'
                                            : step === 'M'
                                                ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                                                : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                                    }`}
                                >
                                    {step}
                                </span>
                                {index < difficultySteps.length - 1 ? <span className="text-slate-500">→</span> : null}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </section>
    );
}