const severityStyles = {
    green: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
    amber: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
    red: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
};

function getSeverity(count) {
    if (count === 0) return 'green';
    if (count <= 2) return 'amber';
    return 'red';
}

function getOverallStatus(total, maxCount) {
    if (total === 0) return 'Clean';
    if (maxCount >= 3 || total >= 5) return 'Review Required';
    return 'Minor Issues';
}

export default function ProctoringSummary({ proctoring }) {
    const entries = [
        { label: 'Tab switches', value: proctoring.tab_switch },
        { label: 'Fullscreen exits', value: proctoring.fullscreen_exit },
        { label: 'Idle events', value: proctoring.idle_events },
    ];

    const total = entries.reduce((sum, entry) => sum + entry.value, 0);
    const maxCount = Math.max(...entries.map((entry) => entry.value), 0);
    const status = getOverallStatus(total, maxCount);

    return (
        <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
            <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                    <h2 className="text-lg font-bold text-white">Proctoring Summary</h2>
                    <p className="text-sm text-slate-400">Monitoring signals captured during the session</p>
                </div>
                <span
                    className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] ${
                        status === 'Clean' ? severityStyles.green : status === 'Minor Issues' ? severityStyles.amber : severityStyles.red
                    }`}
                >
                    {status}
                </span>
            </div>

            <div className="space-y-3">
                {entries.map((entry) => {
                    const severity = getSeverity(entry.value);
                    return (
                        <div key={entry.label} className="flex items-center justify-between rounded-2xl border border-slate-200/10 bg-slate-950/40 px-4 py-3">
                            <div>
                                <p className="text-sm font-medium text-slate-200">{entry.label}</p>
                                <p className="text-xs text-slate-500">{entry.value === 0 ? 'No signal recorded' : 'Recorded during assessment'}</p>
                            </div>
                            <span className={`rounded-full border px-3 py-1 text-sm font-bold ${severityStyles[severity]}`}>
                                {entry.value}
                            </span>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}