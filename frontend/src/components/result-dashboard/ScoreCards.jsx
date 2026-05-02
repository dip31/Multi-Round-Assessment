export default function ScoreCards({ cards }) {
    return (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {cards.map((card) => (
                <article
                    key={card.label}
                    className="rounded-2xl border border-slate-200/10 bg-slate-900/70 p-5 shadow-[0_18px_60px_rgba(15,23,42,0.22)] backdrop-blur"
                >
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{card.label}</p>
                    <div className="mt-4 flex items-end justify-between gap-3">
                        <div>
                            <div className="text-3xl font-black tracking-tight text-white">{card.value}</div>
                            {card.subtext ? <p className="mt-2 text-sm text-slate-400">{card.subtext}</p> : null}
                        </div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${card.badgeClassName}`}>{card.badge}</span>
                    </div>
                </article>
            ))}
        </section>
    );
}