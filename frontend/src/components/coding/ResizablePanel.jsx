import { useState, useRef, useEffect } from 'react';

export default function ResizablePanel({
  left,
  right,
  defaultSize = 50,
  minSize = 25,
  maxSize = 50,
  onSizeChange,
  className = ''
}) {
  const [size, setSize] = useState(() => {
    const stored = localStorage.getItem('coding-panel-size');
    return stored ? parseInt(stored, 10) : defaultSize;
  });
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    localStorage.setItem('coding-panel-size', size.toString());
    onSizeChange?.(size);
  }, [size, onSizeChange]);

  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let newSize = ((e.clientX - rect.left) / rect.width) * 100;
      newSize = Math.max(minSize, Math.min(maxSize, newSize));
      setSize(newSize);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, minSize, maxSize]);

  return (
    <div
      ref={containerRef}
      className={`flex h-full w-full overflow-hidden ${className}`}
    >
      <div className="min-w-0 h-full" style={{ width: `${size}%` }}>
        {left}
      </div>

      <div
        onMouseDown={handleMouseDown}
        className="w-1.5 flex-shrink-0 cursor-col-resize bg-slate-800/80 hover:bg-cyan-500/60 active:bg-cyan-400 transition-colors relative"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize panels"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') setSize((s) => Math.max(minSize, s - 2));
          if (e.key === 'ArrowRight') setSize((s) => Math.min(maxSize, s + 2));
        }}
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <div className={`w-5 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center transition-all ${isDragging ? 'bg-cyan-400/30 border-cyan-400/60 scale-110' : ''}`}>
            <svg className="w-3 h-3 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 010-4h14a2 2 0 010 4M5 12a2 2 0 000 4h14a2 2 0 000-4z" />
            </svg>
          </div>
        </div>
      </div>

      <div className="flex-1 min-w-0 h-full">
        {right}
      </div>
    </div>
  );
}