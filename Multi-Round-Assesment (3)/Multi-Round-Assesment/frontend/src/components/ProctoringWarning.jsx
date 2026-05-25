import React from 'react';

const ProctoringWarning = ({ warning, onDismiss, onRetry }) => {
    const getSeverityColor = (severity) => {
        switch (severity) {
            case 'high':
                return 'bg-red-50 border-red-200 text-red-800';
            case 'medium':
                return 'bg-yellow-50 border-yellow-200 text-yellow-800';
            default:
                return 'bg-blue-50 border-blue-200 text-blue-800';
        }
    };

    const getIcon = (type) => {
        switch (type) {
            case 'camera_permission_denied':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                );
            case 'tab_switch':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                );
            case 'fullscreen_exit':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                    </svg>
                );
            case 'idle_activity':
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                );
            default:
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                );
        }
    };

    return (
        <div className={`rounded-lg border p-4 mb-4 ${getSeverityColor(warning.severity)}`}>
            <div className="flex items-start">
                <div className="flex-shrink-0">
                    {getIcon(warning.type)}
                </div>
                <div className="ml-3 flex-1">
                    <h3 className="text-sm font-medium">
                        {warning.type === 'camera_permission_denied' && 'Camera Access Required'}
                        {warning.type === 'tab_switch' && 'Tab Switch Detected'}
                        {warning.type === 'fullscreen_exit' && 'Fullscreen Mode Required'}
                        {warning.type === 'idle_activity' && 'No Activity Detected'}
                    </h3>
                    <div className="mt-1 text-sm">
                        <p>{warning.message}</p>
                        {warning.count > 1 && (
                            <p className="mt-1 font-medium">
                                This has occurred {warning.count} time(s).
                            </p>
                        )}
                    </div>
                    {warning.blocking && (
                        <div className="mt-3 flex gap-2">
                            <button
                                onClick={onRetry}
                                className="rounded bg-white px-3 py-1 text-sm font-medium border border-current hover:bg-gray-50"
                            >
                                Retry
                            </button>
                            <button
                                onClick={onDismiss}
                                className="rounded bg-white/50 px-3 py-1 text-sm font-medium border border-current/50 hover:bg-white/70"
                            >
                                Dismiss
                            </button>
                        </div>
                    )}
                </div>
                {!warning.blocking && (
                    <div className="ml-3 flex-shrink-0">
                        <button
                            onClick={onDismiss}
                            className="inline-flex rounded-md p-1.5 hover:bg-black/10"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ProctoringWarning;
