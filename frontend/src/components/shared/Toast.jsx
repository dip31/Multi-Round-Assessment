export default function Toast({ message, onRetry, onClose }) {
    if (!message) return null;

    return (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-4 rounded-xl border border-[var(--color-danger)]/50 bg-[var(--color-bg-surface)] px-6 py-4 shadow-lg shadow-[var(--color-danger)]/10">
            <div className="text-[var(--color-danger)]">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <span className="text-sm font-medium text-[var(--color-text-primary)]">{message}</span>
            <div className="flex items-center gap-2">
                {onRetry && (
                    <button
                        onClick={onRetry}
                        className="rounded-lg bg-[var(--color-danger)]/20 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-[var(--color-danger)] transition-colors hover:bg-[var(--color-danger)]/30"
                    >
                        Retry
                    </button>
                )}
                {onClose && (
                    <button onClick={onClose} className="p-1 text-[var(--color-text-secondary)] hover:text-white">
                        ✕
                    </button>
                )}
            </div>
        </div>
    );
}
