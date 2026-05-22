/**
 * Simplified Advanced Proctoring Hook (Basic Version)
 * 
 * This is a simplified version that works without MediaPipe dependencies
 * for immediate testing while we set up the full system.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';

// Simplified proctoring configuration
const BASIC_PROCTORING_CONFIG = {
  // Browser monitoring
  IDLE_TIMEOUT: 60000, // 60 seconds
  VIOLATION_THRESHOLDS: {
    TAB_SWITCH: { max: 5, riskWeight: 0.3 },
    FULLSCREEN_EXIT: { max: 3, riskWeight: 0.4 },
    PAGE_RELOAD: { max: 1, riskWeight: 0.8 },
    IDLE_ACTIVITY: { max: 10, riskWeight: 0.2 },
  }
};

// Event types (simplified)
const BASIC_EVENT_TYPES = {
  TAB_SWITCH: 'TAB_SWITCH',
  FULLSCREEN_EXIT: 'FULLSCREEN_EXIT',
  PAGE_RELOAD: 'PAGE_RELOAD',
  IDLE_ACTIVITY: 'IDLE_ACTIVITY',
  PROCTORING_INITIALIZED: 'PROCTORING_INITIALIZED',
  PROCTORING_ERROR: 'PROCTORING_ERROR',
};

/**
 * Simplified Advanced Proctoring Hook (Basic Version)
 */
export const useBasicAdvancedProctoring = (sessionId, onViolation = null) => {
  // State management
  const [isInitialized, setIsInitialized] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [violations, setViolations] = useState([]);
  const [riskScore, setRiskScore] = useState(0);
  const [detectionResults, setDetectionResults] = useState({
    faceCount: 0,
    faceVisible: false,
    mouthMovement: false,
    gazeDirection: 'center',
    headPose: { pitch: 0, yaw: 0, roll: 0 },
    voiceActivity: false,
  });
  
  const violationCountsRef = useRef({});
  
  // Update overall risk score (MOVED UP - declared before use)
  const updateRiskScore = useCallback(() => {
    const counts = violationCountsRef.current;
    let totalRisk = 0;
    let totalEvents = 0;
    
    Object.entries(counts).forEach(([eventType, count]) => {
      const threshold = BASIC_PROCTORING_CONFIG.VIOLATION_THRESHOLDS[eventType];
      if (threshold) {
        totalRisk += (count * threshold.riskWeight);
        totalEvents += count;
      }
    });
    
    const averageRisk = totalEvents > 0 ? totalRisk / totalEvents : 0;
    setRiskScore(Math.min(averageRisk, 1.0));
  }, []);
  
  // Log proctoring event to backend (MOVED UP - declared before use)
  const logProctoringEvent = useCallback(async (eventType, metadata = {}) => {
    try {
      const eventData = {
        session_id: sessionId,
        event_type: eventType,
        confidence: metadata.confidence || 1.0,
        metadata: {
          ...metadata,
          timestamp: metadata.timestamp || Date.now(),
          browserInfo: navigator.userAgent,
          screenResolution: `${screen.width}x${screen.height}`,
        },
      };
      
      // Send to backend using the shared API client (unified base URL + token + 401 handling)
      const response = await api.post('/advanced-proctoring/log-event', eventData);
      const result = response.data;
        
        // Update local state
        setViolations(prev => [...prev, {
          id: result.event_id,
          eventType,
          confidence: eventData.confidence,
          riskScore: result.risk_score,
          timestamp: new Date().toISOString(),
          metadata,
        }]);
        
        // Update violation counts
        violationCountsRef.current[eventType] = (violationCountsRef.current[eventType] || 0) + 1;
        
        // Calculate overall risk score
        updateRiskScore();
        
        // Call violation callback if provided
        if (onViolation) {
          onViolation({
            eventType,
            riskScore: result.risk_score,
            metadata,
            violationCount: violationCountsRef.current[eventType],
          });
        }
    } catch (error) {
      console.error('Error logging proctoring event:', error);
    }
  }, [sessionId, onViolation, updateRiskScore]);
  
  // Browser monitoring event handlers
  const handleVisibilityChange = useCallback(() => {
    if (document.hidden) {
      logProctoringEvent(BASIC_EVENT_TYPES.TAB_SWITCH, {
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
      });
    }
  }, [logProctoringEvent]);
  
  const handleFullscreenChange = useCallback(() => {
    if (!document.fullscreenElement) {
      logProctoringEvent(BASIC_EVENT_TYPES.FULLSCREEN_EXIT, {
        timestamp: Date.now(),
        wasFullscreen: true,
      });
    }
  }, [logProctoringEvent]);
  
  const handleBeforeUnload = useCallback((event) => {
    logProctoringEvent(BASIC_EVENT_TYPES.PAGE_RELOAD, {
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
    });
    
    // Show warning to user
    event.preventDefault();
    event.returnValue = 'Are you sure you want to leave? Your session will be flagged.';
  }, [logProctoringEvent]);
  
  const handleUserActivity = useCallback(() => {
    // Reset idle timer
    if (window.idleTimer) {
      clearTimeout(window.idleTimer);
    }
    
    window.idleTimer = setTimeout(() => {
      logProctoringEvent(BASIC_EVENT_TYPES.IDLE_ACTIVITY, {
        timestamp: Date.now(),
        idleDuration: BASIC_PROCTORING_CONFIG.IDLE_TIMEOUT,
      });
    }, BASIC_PROCTORING_CONFIG.IDLE_TIMEOUT);
  }, [logProctoringEvent]);
    
  
  // Initialize all monitoring systems
  const initializeProctoring = useCallback(async () => {
    try {
      console.log('🚀 Initializing basic advanced proctoring system...');
      
      // Initialize browser monitoring
      document.addEventListener('visibilitychange', handleVisibilityChange);
      document.addEventListener('fullscreenchange', handleFullscreenChange);
      window.addEventListener('beforeunload', handleBeforeUnload);
      window.addEventListener('mousemove', handleUserActivity);
      window.addEventListener('keydown', handleUserActivity);
      window.addEventListener('touchstart', handleUserActivity);
      
      // Log initialization
      await logProctoringEvent(BASIC_EVENT_TYPES.PROCTORING_INITIALIZED, {
        timestamp: Date.now(),
        config: BASIC_PROCTORING_CONFIG,
      });
      
      setIsInitialized(true);
      setIsMonitoring(true);
      
      console.log('✅ Basic advanced proctoring system initialized successfully');
    } catch (error) {
      console.error('❌ Failed to initialize proctoring system:', error);
      await logProctoringEvent(BASIC_EVENT_TYPES.PROCTORING_ERROR, {
        error: 'INITIALIZATION_FAILED',
        message: error.message,
      });
    }
  }, [
    handleVisibilityChange,
    handleFullscreenChange,
    handleBeforeUnload,
    handleUserActivity,
    logProctoringEvent,
  ]);
  
  // Cleanup function
  const cleanup = useCallback(() => {
    console.log('🧹 Cleaning up proctoring system...');
    
    setIsMonitoring(false);
    
    // Remove event listeners
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    document.removeEventListener('fullscreenchange', handleFullscreenChange);
    window.removeEventListener('beforeunload', handleBeforeUnload);
    window.removeEventListener('mousemove', handleUserActivity);
    window.removeEventListener('keydown', handleUserActivity);
    window.removeEventListener('touchstart', handleUserActivity);
    
    // Clear timers
    if (window.idleTimer) {
      clearTimeout(window.idleTimer);
    }
    
    console.log('✅ Proctoring system cleaned up');
  }, [
    handleVisibilityChange,
    handleFullscreenChange,
    handleBeforeUnload,
    handleUserActivity,
  ]);
  
  // Initialize on mount
  useEffect(() => {
    if (sessionId) {
      initializeProctoring();
    }
    
    return cleanup;
  }, [sessionId, initializeProctoring, cleanup]);
  
  return {
    // State
    isInitialized,
    isMonitoring,
    violations,
    riskScore,
    detectionResults,
    
    // Refs (for compatibility with full version)
    videoRef: useRef(null),
    canvasRef: useRef(null),
    
    // Methods
    initializeProctoring,
    cleanup,
    logProctoringEvent,
    
    // Configuration
    config: BASIC_PROCTORING_CONFIG,
    eventTypes: BASIC_EVENT_TYPES,
  };
};

export default useBasicAdvancedProctoring;
