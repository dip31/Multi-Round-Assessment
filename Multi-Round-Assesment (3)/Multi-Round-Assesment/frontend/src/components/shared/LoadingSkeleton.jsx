import Navbar from '../Navbar';

export default function LoadingSkeleton() {
    return (
        <div className="flex h-screen flex-col overflow-hidden bg-[var(--color-bg-primary)]">
            <Navbar />
            <div className="mx-auto flex w-full max-w-6xl flex-1 items-start gap-8 overflow-hidden px-4 py-8 sm:px-6">
                <div className="flex w-full h-full flex-1 flex-col overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-surface)] shadow-sm animate-pulse">
                    <div className="flex-1 p-6 sm:p-8">
                        {/* Header */}
                        <div className="mb-6 flex items-center justify-between">
                            <div className="h-4 w-24 rounded bg-[var(--color-bg-elevated)]" />
                            <div className="h-6 w-16 rounded-full bg-[var(--color-bg-elevated)]" />
                        </div>
                        {/* Question text */}
                        <div className="mb-8 space-y-3">
                            <div className="h-6 w-full rounded bg-[var(--color-bg-elevated)]" />
                            <div className="h-6 w-3/4 rounded bg-[var(--color-bg-elevated)]" />
                        </div>
                        {/* Options */}
                        <div className="space-y-3">
                            {[1, 2, 3, 4].map((i) => (
                                <div key={i} className="flex w-full items-center gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-primary)] p-4">
                                    <div className="h-5 w-5 rounded-full border-2 border-[var(--color-border)]" />
                                    <div className="h-4 w-48 rounded bg-[var(--color-border)]" />
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
