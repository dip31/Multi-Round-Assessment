function formatPercent(value) {
    return `${value.toFixed(1)}%`;
}

export default function ImprovementInsights({ topicStats, fallbackInsights }) {
    const hasTopics = Array.isArray(topicStats) && topicStats.length > 0;

    if (!hasTopics) {
        return (
            <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-bold text-slate-900">Improvement Insights</h2>
                <p className="mt-2 text-sm text-slate-500">Signals derived from your performance pattern</p>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                    {fallbackInsights.map((insight) => (
                        <div key={insight} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-medium text-slate-700">
                            {insight}
                        </div>
                    ))}
                </div>
            </section>
        );
    }

    const strongestTopic = topicStats.reduce((best, current) => (current.accuracy > best.accuracy ? current : best), topicStats[0]);
    const weakestTopic = topicStats.reduce((worst, current) => (current.accuracy < worst.accuracy ? current : worst), topicStats[0]);
    const fastestTopic = topicStats.reduce((fastest, current) => (current.avg_response_time < fastest.avg_response_time ? current : fastest), topicStats[0]);
    const slowestTopic = topicStats.reduce((slowest, current) => (current.avg_response_time > slowest.avg_response_time ? current : slowest), topicStats[0]);

    const cards = [
        {
            title: 'Strongest topic',
            topic: strongestTopic.topic,
            value: formatPercent(strongestTopic.accuracy),
            tone: 'text-emerald-700 bg-emerald-50 border-emerald-200',
        },
        {
            title: 'Weakest topic',
            topic: weakestTopic.topic,
            value: formatPercent(weakestTopic.accuracy),
            tone: 'text-rose-700 bg-rose-50 border-rose-200',
        },
        {
            title: 'Fastest topic',
            topic: fastestTopic.topic,
            value: `${fastestTopic.avg_response_time.toFixed(1)}s`,
            tone: 'text-sky-700 bg-sky-50 border-sky-200',
        },
        {
            title: 'Slowest topic',
            topic: slowestTopic.topic,
            value: `${slowestTopic.avg_response_time.toFixed(1)}s`,
            tone: 'text-amber-700 bg-amber-50 border-amber-200',
        },
    ];

    return (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-5">
                <h2 className="text-lg font-bold text-slate-900">Improvement Insights</h2>
                <p className="text-sm text-slate-500">Topic-level signals that point to where practice will pay off</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {cards.map((card) => (
                    <article key={card.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <span className={`inline-block text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-md border mb-2 ${card.tone}`}>
                            {card.title}
                        </span>
                        <p className="text-sm font-semibold text-slate-900 truncate">{card.topic}</p>
                        <p className="mt-2 text-2xl font-black text-slate-900">{card.value}</p>
                    </article>
                ))}
            </div>
        </section>
    );
}