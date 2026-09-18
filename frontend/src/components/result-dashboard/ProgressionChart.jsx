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
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                    <h2 className="text-lg font-bold text-slate-900">Progression Chart</h2>
                    <p className="text-sm text-slate-500">Difficulty movement and answer correctness across the assessment</p>
                </div>
                <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-700">
                    Adaptive behavior
                </span>
            </div>

            <div className="h-[360px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="questionLabel" stroke="#64748b" tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                        <YAxis
                            yAxisId="left"
                            domain={[0, 3]}
                            ticks={[1, 2, 3]}
                            tickFormatter={(value) => difficultyLabels[value] || value}
                            stroke="#64748b"
                            tickLine={false}
                            axisLine={{ stroke: '#e2e8f0' }}
                        />
                        <YAxis
                            yAxisId="right"
                            orientation="right"
                            domain={[0, 1]}
                            ticks={[0, 1]}
                            stroke="#64748b"
                            tickLine={false}
                            axisLine={{ stroke: '#e2e8f0' }}
                        />
                        <Tooltip
                            contentStyle={{
                                background: '#ffffff',
                                border: '1px solid #e2e8f0',
                                borderRadius: '12px',
                                color: '#0f172a',
                                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            }}
                            labelStyle={{ color: '#475569', fontWeight: 600 }}
                        />
                        <Legend />
                        <Line
                            yAxisId="left"
                            type="monotone"
                            dataKey="difficultyValue"
                            name="Difficulty"
                            stroke="#4f46e5"
                            strokeWidth={3}
                            dot={{ r: 4, fill: '#4f46e5', strokeWidth: 0 }}
                        />
                        <Line
                            yAxisId="right"
                            type="monotone"
                            dataKey="performanceValue"
                            name="Correctness"
                            stroke="#10b981"
                            strokeWidth={2.5}
                            strokeDasharray="7 6"
                            dot={{ r: 4, fill: '#10b981', strokeWidth: 0 }}
                        />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}