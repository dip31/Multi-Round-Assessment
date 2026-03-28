/**
 * Advanced Proctoring Monitor Component
 * 
 * Displays real-time proctoring status, violations, and risk assessment
 * with visual feedback for different violation types.
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, Eye, EyeOff, Mic, MicOff, Camera, CameraOff, Activity } from 'lucide-react';

const AdvancedProctoringMonitor = ({ 
  proctoringData, 
  violations = [], 
  riskScore = 0,
  detectionResults,
  isMonitoring = false,
  className = ''
}) => {
  const [expanded, setExpanded] = useState(false);
  const [recentViolations, setRecentViolations] = useState([]);

  // Update recent violations
  useEffect(() => {
    if (!violations || !Array.isArray(violations)) {
      setRecentViolations([]);
      return;
    }
    const sortedViolations = [...violations]
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
      .slice(0, 5);
    setRecentViolations(sortedViolations);
  }, [violations]);

  // Get risk level color
  const getRiskLevelColor = (score) => {
    if (score < 0.3) return 'text-green-600';
    if (score < 0.6) return 'text-yellow-600';
    if (score < 0.8) return 'text-orange-600';
    return 'text-red-600';
  };

  // Get risk level background
  const getRiskLevelBg = (score) => {
    if (score < 0.3) return 'bg-green-100';
    if (score < 0.6) return 'bg-yellow-100';
    if (score < 0.8) return 'bg-orange-100';
    return 'bg-red-100';
  };

  // Get violation icon
  const getViolationIcon = (eventType) => {
    const iconMap = {
      'TAB_SWITCH': AlertTriangle,
      'FULLSCREEN_EXIT': AlertTriangle,
      'PAGE_RELOAD': AlertTriangle,
      'IDLE_ACTIVITY': Activity,
      'MULTIPLE_PERSON_DETECTED': AlertTriangle,
      'FACE_NOT_VISIBLE': EyeOff,
      'MOUTH_MOVEMENT_DETECTED': Mic,
      'LOOKING_AWAY': Eye,
      'HEAD_TURN_DETECTED': AlertTriangle,
      'VOICE_ACTIVITY_DETECTED': Mic,
      'CAMERA_PERMISSION_DENIED': CameraOff,
      'MICROPHONE_PERMISSION_DENIED': MicOff,
    };
    
    const Icon = iconMap[eventType] || AlertTriangle;
    return <Icon className="w-4 h-4" />;
  };

  // Get violation color
  const getViolationColor = (eventType) => {
    const colorMap = {
      'MULTIPLE_PERSON_DETECTED': 'text-red-600',
      'FACE_NOT_VISIBLE': 'text-orange-600',
      'PAGE_RELOAD': 'text-red-600',
      'CAMERA_PERMISSION_DENIED': 'text-red-600',
      'VOICE_ACTIVITY_DETECTED': 'text-yellow-600',
      'MOUTH_MOVEMENT_DETECTED': 'text-yellow-600',
      'LOOKING_AWAY': 'text-blue-600',
      'HEAD_TURN_DETECTED': 'text-orange-600',
      'TAB_SWITCH': 'text-yellow-600',
      'FULLSCREEN_EXIT': 'text-yellow-600',
      'IDLE_ACTIVITY': 'text-gray-600',
    };
    
    return colorMap[eventType] || 'text-gray-600';
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  // Get event type display name
  const getEventDisplayName = (eventType) => {
    const nameMap = {
      'TAB_SWITCH': 'Tab Switch',
      'FULLSCREEN_EXIT': 'Fullscreen Exit',
      'PAGE_RELOAD': 'Page Reload',
      'IDLE_ACTIVITY': 'Idle Activity',
      'MULTIPLE_PERSON_DETECTED': 'Multiple People',
      'FACE_NOT_VISIBLE': 'Face Not Visible',
      'MOUTH_MOVEMENT_DETECTED': 'Mouth Movement',
      'LOOKING_AWAY': 'Looking Away',
      'HEAD_TURN_DETECTED': 'Head Turn',
      'VOICE_ACTIVITY_DETECTED': 'Voice Activity',
      'CAMERA_PERMISSION_DENIED': 'Camera Denied',
      'MICROPHONE_PERMISSION_DENIED': 'Microphone Denied',
    };
    
    return nameMap[eventType] || eventType;
  };

  if (!isMonitoring) {
    return (
      <div className={`bg-gray-100 border border-gray-300 rounded-lg p-4 ${className}`}>
        <div className="flex items-center justify-center text-gray-600">
          <CameraOff className="w-5 h-5 mr-2" />
          <span>Proctoring system not active</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center">
              <Camera className={`w-5 h-5 mr-2 ${detectionResults.faceVisible ? 'text-green-600' : 'text-red-600'}`} />
              <span className="text-sm font-medium text-gray-900">Proctoring Active</span>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Face Status */}
              <div className="flex items-center">
                {detectionResults.faceVisible ? (
                  <Eye className="w-4 h-4 text-green-600 mr-1" />
                ) : (
                  <EyeOff className="w-4 h-4 text-red-600 mr-1" />
                )}
                <span className="text-xs text-gray-600">
                  {detectionResults.faceVisible ? 'Face Visible' : 'Face Not Visible'}
                </span>
              </div>
              
              {/* Microphone Status */}
              <div className="flex items-center">
                {detectionResults.voiceActivity ? (
                  <Mic className="w-4 h-4 text-red-600 mr-1" />
                ) : (
                  <MicOff className="w-4 h-4 text-gray-600 mr-1" />
                )}
                <span className="text-xs text-gray-600">
                  {detectionResults.voiceActivity ? 'Voice Active' : 'Silent'}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            {/* Risk Score */}
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskLevelBg(riskScore)} ${getRiskLevelColor(riskScore)}`}>
              Risk: {Math.round(riskScore * 100)}%
            </div>
            
            {/* Expand/Collapse Button */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 space-y-4">
          {/* Detection Results */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{detectionResults.faceCount}</div>
              <div className="text-xs text-gray-600">Faces Detected</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{detectionResults.gazeDirection}</div>
              <div className="text-xs text-gray-600">Gaze Direction</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">
                {Math.abs(detectionResults.headPose.yaw)}°
              </div>
              <div className="text-xs text-gray-600">Head Turn</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{violations.length}</div>
              <div className="text-xs text-gray-600">Total Violations</div>
            </div>
          </div>

          {/* Recent Violations */}
          {recentViolations.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-2">Recent Violations</h4>
              <div className="space-y-2">
                {recentViolations.map((violation, index) => (
                  <div key={violation.id || index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                    <div className="flex items-center space-x-2">
                      <div className={getViolationColor(violation.eventType)}>
                        {getViolationIcon(violation.eventType)}
                      </div>
                      <span className="text-sm text-gray-900">
                        {getEventDisplayName(violation.eventType)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-gray-500">
                        {formatTimestamp(violation.timestamp)}
                      </span>
                      <span className="text-xs font-medium text-gray-600">
                        {Math.round(violation.riskScore * 100)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risk Assessment */}
          <div className={`p-3 rounded-lg ${getRiskLevelBg(riskScore)}`}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-900">Risk Assessment</span>
              <span className={`text-sm font-bold ${getRiskLevelColor(riskScore)}`}>
                {riskScore < 0.3 ? 'Low Risk' : 
                 riskScore < 0.6 ? 'Medium Risk' : 
                 riskScore < 0.8 ? 'High Risk' : 'Critical Risk'}
              </span>
            </div>
            <div className="mt-2">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    riskScore < 0.3 ? 'bg-green-600' :
                    riskScore < 0.6 ? 'bg-yellow-600' :
                    riskScore < 0.8 ? 'bg-orange-600' : 'bg-red-600'
                  }`}
                  style={{ width: `${riskScore * 100}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdvancedProctoringMonitor;
