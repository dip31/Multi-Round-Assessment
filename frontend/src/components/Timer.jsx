import { useTimer } from '../hooks/useTimer';

export default function Timer({ initialSeconds, onExpire }) {
    const { timeRemaining } = useTimer(initialSeconds, onExpire);

    const minutes = Math.floor(timeRemaining / 60);
    const seconds = timeRemaining % 60;

    return (
        <div
            className="flex items-center gap-3 rounded-lg bg-[var(--color-nav-bg)] px-4 py-2 text-white border border-white/10"
            aria-label={`Timer: ${minutes} minutes and ${seconds} seconds remaining`}
        >
            <span className="hidden sm:inline text-sm font-semibold tracking-wide text-white/80">
                Aptitude Round
            </span>
            <div className="hidden sm:block h-4 w-[1px] bg-white/20" />
            <span className="font-mono text-[15px] font-bold tracking-tight text-white">
                {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')} remaining
            </span>
        </div>
    );
}
