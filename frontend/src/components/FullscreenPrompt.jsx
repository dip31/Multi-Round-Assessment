import React from 'react';

const FullscreenPrompt = ({ onEnterFullscreen, onCancel }) => {
    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
            <div className="bg-white rounded-lg p-6 max-w-md mx-4 shadow-xl">
                <div className="text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 mb-4">
                        <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5 5m0 4v-4m0 0h-4m4 0l-5-5" />
                        </svg>
                    </div>
                    <h3 className="text-lg font-semibold mb-2">Fullscreen Required</h3>
                    <p className="text-gray-600 mb-6">
                        This test requires fullscreen mode to ensure test integrity and prevent distractions.
                    </p>
                    <div className="space-y-3">
                        <button
                            onClick={onEnterFullscreen}
                            className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
                        >
                            Enter Fullscreen Mode
                        </button>
                        <button
                            onClick={onCancel}
                            className="w-full bg-gray-200 text-gray-800 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors font-medium"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FullscreenPrompt;
