import {
    CartesianGrid,
    ComposedChart,
    Legend,
    Line,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

const difficultyLabels = {
    1: 'Easy',
    2: 'Medium',
    3: 'Hard',
};

export default function ProgressionChart({ data }) {
    return (
        <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
            <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                    <h2 className="text-lg font-bold text-white">Progression Chart</h2>
                    <p className="text-sm text-slate-400">Difficulty movement and answer correctness across the assessment</p>
                </div>
                <span className="rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-sky-300">
                    Adaptive behavior
                </span>
            </div>

            <div className="h-[360px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" />
                        <XAxis dataKey="questionLabel" stroke="#94a3b8" tickLine={false} axisLine={false} />
                        <YAxis
                            yAxisId="left"
                            domain={[0, 3]}
                            ticks={[1, 2, 3]}
                            tickFormatter={(value) => difficultyLabels[value] || value}
                            stroke="#94a3b8"
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            yAxisId="right"
                            orientation="right"
                            domain={[0, 1]}
                            ticks={[0, 1]}
                            stroke="#94a3b8"
                            tickLine={false}
                            axisLine={false}
                        />
                        <Tooltip
                            contentStyle={{
                                background: 'rgba(15, 23, 42, 0.98)',
                                border: '1px solid rgba(148,163,184,0.18)',
                                borderRadius: '14px',
                                color: '#fff',
                            }}
                            labelStyle={{ color: '#cbd5e1' }}
                        />
                        <Legend />
                        <Line
                            yAxisId="left"
                            type="monotone"
                            dataKey="difficultyValue"
                            name="Difficulty"
                            stroke="#60a5fa"
                            strokeWidth={3}
                            dot={{ r: 4, fill: '#60a5fa', strokeWidth: 0 }}
                        />
                        <Line
                            yAxisId="right"
                            type="monotone"
                            dataKey="performanceValue"
                            name="Correctness"
                            stroke="#22c55e"
                            strokeWidth={2.5}
                            strokeDasharray="7 6"
                            dot={{ r: 4, fill: '#22c55e', strokeWidth: 0 }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}