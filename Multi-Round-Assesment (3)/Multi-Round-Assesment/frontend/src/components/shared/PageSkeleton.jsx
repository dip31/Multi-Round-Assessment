import React from 'react';

export default function PageSkeleton({
    variant = 'dark',
    embedded = false,
    showTable = false,
    cardCount = 4,
}) {
    const isDark = variant === 'dark';

    const wrapperClass = isDark
        ? 'bg-background text-on-surface'
        : 'bg-slate-50 text-slate-900';

    const borderClass = isDark ? 'border-outline-variant/20' : 'border-slate-200';
    const panelClass = isDark ? 'bg-surface-container' : 'bg-white';
    const pulseClass = isDark ? 'bg-slate-700/60' : 'bg-slate-200';

    return (
        <div className={`${embedded ? '' : 'min-h-screen'} ${wrapperClass}`}>
            {!embedded && (
                <div className={`h-16 border-b ${borderClass} ${isDark ? 'bg-surface/80' : 'bg-white/80'} backdrop-blur-sm`} />
            )}

            <main className={`${embedded ? '' : 'pt-8'} mx-auto max-w-6xl px-6 pb-10`}> 
                <div className="animate-pulse space-y-8">
                    <div className="space-y-3 pt-2">
                        <div className={`h-10 w-72 rounded-xl ${pulseClass}`} />
                        <div className={`h-4 w-96 rounded-lg ${pulseClass}`} />
                    </div>

                    <div className={`grid grid-cols-1 md:grid-cols-2 ${cardCount >= 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-3'} gap-4`}>
                        {Array.from({ length: cardCount }).map((_, idx) => (
                            <div key={idx} className={`rounded-xl border ${borderClass} ${panelClass} p-5 space-y-3`}>
                                <div className={`h-3 w-24 rounded ${pulseClass}`} />
                                <div className={`h-8 w-16 rounded ${pulseClass}`} />
                                <div className={`h-2 w-full rounded ${pulseClass}`} />
                            </div>
                        ))}
                    </div>

                    {showTable ? (
                        <div className={`rounded-2xl border ${borderClass} ${panelClass} overflow-hidden`}>
                            <div className={`h-12 border-b ${borderClass} ${isDark ? 'bg-surface-container-high' : 'bg-slate-50'}`} />
                            <div className="p-4 space-y-3">
                                {Array.from({ length: 6 }).map((_, row) => (
                                    <div key={row} className={`h-10 rounded-lg ${pulseClass}`} />
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className={`rounded-2xl border ${borderClass} ${panelClass} p-6 space-y-4`}>
                            {Array.from({ length: 5 }).map((_, idx) => (
                                <div key={idx} className={`h-4 rounded ${pulseClass} ${idx % 2 === 0 ? 'w-full' : 'w-5/6'}`} />
                            ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
