/**
 * Debug component to test if basic proctoring hook works
 */

import React from 'react';
import { useBasicAdvancedProctoring } from '../hooks/useBasicAdvancedProctoring';

const DebugProctoring = () => {
    const basicProctoring = useBasicAdvancedProctoring(
        1, // test session ID
        (violation) => {
            console.log('Proctoring violation detected:', violation);
        }
    );

    return (
        <div className="p-4">
            <h2 className="text-xl font-bold mb-4">Proctoring Debug</h2>
            <div className="space-y-2">
                <p><strong>Initialized:</strong> {basicProctoring.isInitialized ? 'Yes' : 'No'}</p>
                <p><strong>Monitoring:</strong> {basicProctoring.isMonitoring ? 'Yes' : 'No'}</p>
                <p><strong>Risk Score:</strong> {basicProctoring.riskScore.toFixed(2)}</p>
                <p><strong>Violations:</strong> {basicProctoring.violations.length}</p>
            </div>
        </div>
    );
};

export default DebugProctoring;
