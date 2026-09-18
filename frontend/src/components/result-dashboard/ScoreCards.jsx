export default function ScoreCards({ cards }) {
    return (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {cards.map((card) => (
                <article
                    key={card.label}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                >
                    <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">{card.label}</p>
                    <div className="mt-4 flex items-end justify-between gap-3">
                        <div>
                            <div className="text-3xl font-black tracking-tight text-slate-900">{card.value}</div>
                            {card.subtext ? <p className="mt-2 text-xs font-medium text-slate-500">{card.subtext}</p> : null}
                        </div>
                        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${card.badgeClassName}`}>{card.badge}</span>
                    </div>
                </article>
            ))}
        </section>
    );
}