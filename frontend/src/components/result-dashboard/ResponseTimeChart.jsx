import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

export default function ResponseTimeChart({ data }) {
    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5">
                <h2 className="text-lg font-bold text-slate-900">Response Time Analysis</h2>
                <p className="text-sm text-slate-500">Per-question latency with benchmark thresholds at 5s and 15s</p>
            </div>

            <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis dataKey="questionLabel" stroke="#64748b" tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
                        <YAxis stroke="#64748b" tickLine={false} axisLine={{ stroke: '#e2e8f0' }} />
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
                        <ReferenceLine y={5} stroke="#10b981" strokeDasharray="6 6" />
                        <ReferenceLine y={15} stroke="#f59e0b" strokeDasharray="6 6" />
                        <Bar dataKey="time" name="Seconds" radius={[8, 8, 0, 0]}>
                            {data.map((entry) => (
                                <Cell key={entry.question} fill={entry.fill} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </section>
    );
}