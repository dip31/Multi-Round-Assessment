import { useEffect } from 'react';

export function Toast({ type = 'success', message, onClose, duration = 3000 }) {
  useEffect(() => {
    if (!duration) return;
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const bgColor = type === 'success' ? 'bg-green-50' : type === 'error' ? 'bg-red-50' : 'bg-blue-50';
  const borderColor = type === 'success' ? 'border-green-200' : type === 'error' ? 'border-red-200' : 'border-blue-200';
  const textColor = type === 'success' ? 'text-green-800' : type === 'error' ? 'text-red-800' : 'text-blue-800';
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  const iconBg = type === 'success' ? 'text-green-600' : type === 'error' ? 'text-red-600' : 'text-blue-600';

  return (
    <div className="fixed top-4 right-4 z-50">
      <div className={`${bgColor} border ${borderColor} rounded-lg px-4 py-3 flex items-start gap-3 shadow-lg`}>
        <span className={`text-lg font-bold ${iconBg} flex-shrink-0`}>{icon}</span>
        <p className={`${textColor} text-sm font-medium`}>{message}</p>
        <button
          onClick={onClose}
          className={`ml-2 ${textColor} hover:opacity-70 transition-opacity flex-shrink-0`}
          aria-label="Close"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
