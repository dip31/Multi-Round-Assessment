import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

export default function PerformanceChart({ data }) {
    return (
        <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
            <div className="mb-5">
                <h2 className="text-lg font-bold text-white">Performance Breakdown</h2>
                <p className="text-sm text-slate-400">Correct versus incorrect answers by difficulty level</p>
            </div>

            <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" />
                        <XAxis dataKey="label" stroke="#94a3b8" tickLine={false} axisLine={false} />
                        <YAxis allowDecimals={false} stroke="#94a3b8" tickLine={false} axisLine={false} />
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
                        <Bar dataKey="correct" name="Correct" fill="#22c55e" radius={[8, 8, 0, 0]} />
                        <Bar dataKey="incorrect" name="Incorrect" fill="#ef4444" radius={[8, 8, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}