import { Clock, Shield, Monitor, Maximize2, Minimize2 } from 'lucide-react';
import { useMemo } from 'react';

function formatTime(seconds) {
  if (seconds === null || seconds === undefined) return '--:--';
  const clamped = Math.max(0, Math.floor(seconds));
  const m = Math.floor(clamped / 60);
  const s = clamped % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function CodingHeader({ 
  currentQuestion, 
  totalQuestions, 
  timeRemaining, 
  onFullscreenToggle,
  isFullscreen,
  proctoringStatus,
  questionNumbers,
  onQuestionSelect,
  canNavigate,
  onFinish,
  isFinishing
}) {
  // Derive the warning level from timeRemaining instead of syncing it to state.
  const warningState = useMemo(() => {
    if (timeRemaining === null || timeRemaining === undefined) return 'normal';
    if (timeRemaining <= 300) return 'critical';
    if (timeRemaining <= 600) return 'warning';
    return 'normal';
  }, [timeRemaining]);

  const getTimerColor = () => {
    switch (warningState) {
      case 'critical': return 'text-red-400 animate-pulse';
      case 'warning': return 'text-yellow-400';
      default: return 'text-cyan-400';
    }
  };

  const getTimerBg = () => {
    switch (warningState) {
      case 'critical': return 'bg-red-400/10 border-red-400/30';
      case 'warning': return 'bg-yellow-400/10 border-yellow-400/30';
      default: return 'bg-cyan-400/10 border-cyan-400/30';
    }
  };

  return (
    <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 px-4 py-3 border-b border-white/10 bg-slate-950/80 backdrop-blur sticky top-0 z-20">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center">
            <Monitor className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-cyan-300/70 font-semibold">EDI5</p>
            <h1 className="text-lg font-black text-white">Coding Assessment</h1>
          </div>
        </div>
        
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl border border-white/10 bg-white/5">
          <span className="text-xs font-semibold text-slate-400">Question</span>
          <span className="text-sm font-bold text-white">{currentQuestion} of {totalQuestions}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2">
        {canNavigate && questionNumbers.map((num, idx) => (
          <button
            key={num}
            onClick={() => onQuestionSelect?.(idx)}
            disabled={idx === currentQuestion - 1}
            className={`
              w-8 h-8 rounded-xl text-sm font-semibold transition-all
              ${idx === currentQuestion - 1 
                ? 'bg-cyan-400/20 border border-cyan-400/40 text-cyan-200 shadow-lg shadow-cyan-950/20'
                : 'bg-white/5 border border-white/10 text-slate-400 hover:bg-white/10 hover:border-white/20'}
            `}
            aria-label={`Question ${num}`}
            aria-current={idx === currentQuestion - 1 ? 'true' : 'false'}
          >
            {num}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <div
          className={`flex items-center gap-2 transition-opacity ${
            proctoringStatus === 'active' ? 'opacity-100' : 'opacity-50'
          }`}
        >
          <Shield className={`w-4 h-4 ${proctoringStatus === 'active' ? 'text-emerald-400' : 'text-slate-400'}`} />
          <span className={`text-xs font-medium hidden sm:block ${proctoringStatus === 'active' ? 'text-emerald-300' : 'text-slate-400'}`}>
            {proctoringStatus === 'active' ? 'Proctoring Active' : 'Proctoring Connecting'}
          </span>
        </div>

        <div 
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border font-mono text-sm font-semibold ${getTimerBg()} ${getTimerColor()}`}
          role="timer"
          aria-live={warningState === 'critical' ? 'assertive' : 'polite'}
          aria-label={`Time remaining: ${formatTime(timeRemaining)}`}
        >
          <Clock className="w-4 h-4" />
          <span className="tabular-nums min-w-[5ch] text-right">{formatTime(timeRemaining)}</span>
        </div>

        <button
          onClick={onFullscreenToggle}
          className="p-2 rounded-xl border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:border-white/20 transition-all"
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
        </button>

        <button
          onClick={onFinish}
          disabled={isFinishing}
          className="px-4 py-1.5 rounded-xl border border-red-400/40 bg-red-400/10 text-red-300 hover:bg-red-400/20 hover:border-red-400/60 transition-all font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Finish coding round early"
        >
          {isFinishing ? 'Finishing...' : 'Finish Round'}
        </button>
      </div>
    </header>
  );
}