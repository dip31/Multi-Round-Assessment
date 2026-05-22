import React, { useEffect, useState } from "react";

const formatTime = (seconds) => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

export default function TimerComponent({
  duration,
  mode,
  onThinkingComplete,
  onEarlyStart,
  isRecording,
  recordingSeconds,
}) {
  const [secondsLeft, setSecondsLeft] = useState(duration || 0);

  useEffect(() => {
    setSecondsLeft(duration || 0);
  }, [duration]);

  useEffect(() => {
    if (mode !== "thinking") return;
    if (secondsLeft <= 0) {
      onThinkingComplete && onThinkingComplete();
      return;
    }
    const t = setTimeout(() => setSecondsLeft((p) => p - 1), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft, mode, onThinkingComplete]);

  const progress =
    mode === "thinking"
      ? Math.max(0, Math.min(1, secondsLeft / (duration || 1)))
      : Math.min(1, (recordingSeconds || 0) / 180);

  const ringColor = mode === "thinking" ? "#2563EB" : "#DC2626";

  return (
    <div className="flex items-center gap-4">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r="36" stroke="#111827" strokeWidth="6" fill="none" />
        <circle
          cx="48"
          cy="48"
          r="36"
          stroke={ringColor}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={226}
          strokeDashoffset={226 * (1 - progress)}
          transform="rotate(-90 48 48)"
          fill="none"
        />
        <text x="48" y="52" textAnchor="middle" fontSize="14" fill="#E5E7EB">
          {mode === "thinking" ? formatTime(secondsLeft) : formatTime(recordingSeconds || 0)}
        </text>
      </svg>
      <div>
        <div className="text-sm text-slate-400">{mode === "thinking" ? "Thinking Time" : "Recording"}</div>
        {mode === "thinking" && (
          <button
            className="mt-2 px-4 py-2 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-600/30 text-sm"
            onClick={() => onEarlyStart && onEarlyStart()}
          >
            Start Answering Early
          </button>
        )}
        {mode === "recording" && (
          <div className="mt-2 text-sm text-red-400 flex items-center gap-2">
            <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
            <span>{formatTime(recordingSeconds || 0)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
