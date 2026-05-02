function formatPercent(value) {
    return `${value.toFixed(1)}%`;
}

export default function ImprovementInsights({ topicStats, fallbackInsights }) {
    const hasTopics = Array.isArray(topicStats) && topicStats.length > 0;

    if (!hasTopics) {
        return (
            <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
                <h2 className="text-lg font-bold text-white">Improvement Insights</h2>
                <p className="mt-2 text-sm text-slate-400">Fallback signals derived from the result pattern</p>
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                    {fallbackInsights.map((insight) => (
                        <div key={insight} className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4 text-sm text-slate-200">
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
        },
        {
            title: 'Weakest topic',
            topic: weakestTopic.topic,
            value: formatPercent(weakestTopic.accuracy),
        },
        {
            title: 'Fastest topic',
            topic: fastestTopic.topic,
            value: `${fastestTopic.avg_response_time.toFixed(1)}s`,
        },
        {
            title: 'Slowest topic',
            topic: slowestTopic.topic,
            value: `${slowestTopic.avg_response_time.toFixed(1)}s`,
        },
    ];

    return (
        <section className="rounded-3xl border border-slate-200/10 bg-slate-900/70 p-6 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur">
            <div className="mb-5">
                <h2 className="text-lg font-bold text-white">Improvement Insights</h2>
                <p className="text-sm text-slate-400">Topic-level signals that point to where practice will pay off</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {cards.map((card) => (
                    <article key={card.title} className="rounded-2xl border border-slate-200/10 bg-slate-950/40 p-4">
                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{card.title}</p>
                        <p className="mt-3 text-sm text-slate-500">{card.topic}</p>
                        <p className="mt-2 text-2xl font-black text-white">{card.value}</p>
                    </article>
                ))}
            </div>
        </section>
    );
}