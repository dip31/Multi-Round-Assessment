export function LoadingSkeleton({ lines = 3, className = '' }) {
  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-gradient-to-r from-slate-200 to-slate-100 rounded-lg animate-pulse"
          style={{
            width: `${100 - (i * 15)}%`,
            animation: `pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite`,
            animationDelay: `${i * 0.1}s`
          }}
        />
      ))}
    </div>
  );
}
