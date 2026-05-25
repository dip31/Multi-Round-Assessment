/**
 * Advanced AI-Based Online Proctoring Hook
 * 
 * Implements comprehensive proctoring with:
 * - Browser behavior monitoring
 * - Webcam video analysis with MediaPipe
 * - Microphone audio analysis with VAD
 * - Real-time violation detection
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { Camera } from '@mediapipe/camera_utils';
import { FaceDetection, FaceDetectionResults } from '@mediapipe/face_detection';
import { FaceMesh, FaceMeshResults } from '@mediapipe/face_mesh';
import { drawConnectors, drawLandmarks } from '@mediapipe/drawing_utils';
import { FACEMESH_FACE_OVAL, FACEMESH_LIPS, FACEMESH_LEFT_EYE, FACEMESH_RIGHT_EYE } from '@mediapipe/face_mesh';
import api from '../services/api';

// Pin MediaPipe asset URLs to the installed versions to avoid CDN 404s.
// These should match `frontend/package.json`.
const MEDIAPIPE_FACE_DETECTION_VERSION = '0.4.1646425229';
const MEDIAPIPE_FACE_MESH_VERSION = '0.4.1633559619';

const mediapipeCdn = (pkg, version, file) =>
  `https://cdn.jsdelivr.net/npm/${pkg}@${version}/${file}`;

const toUniqueLandmarkIndices = (connections) => {
  const indices = new Set();
  (connections || []).forEach((connection) => {
    if (Array.isArray(connection) && connection.length === 2) {
      indices.add(connection[0]);
      indices.add(connection[1]);
    }
  });
  return [...indices];
};

const CRITICAL_FACE_INDICES = toUniqueLandmarkIndices([
  ...FACEMESH_FACE_OVAL,
  ...FACEMESH_LEFT_EYE,
  ...FACEMESH_RIGHT_EYE,
  ...FACEMESH_LIPS,
]);

const toJsonSafe = (value) => {
  try {
    return JSON.parse(
      JSON.stringify(value, (k, v) => {
        if (typeof v === 'function') return undefined;
        if (typeof v === 'bigint') return v.toString();
        if (v instanceof Error) return { name: v.name, message: v.message };
        return v;
      })
    );
  } catch (_) {
    return { _non_serializable: true };
  }
};

// Advanced proctoring configuration
const PROCTORING_CONFIG = {
  // Video processing
  CAMERA_FPS: 30,
  PROCESSING_FPS: 5, // Process every 6th frame for performance
  VIDEO_WIDTH: 640,
  VIDEO_HEIGHT: 480,
  
  // Detection thresholds
  FACE_DETECTION_CONFIDENCE: 0.5,
  FACE_PRESENCE_CONFIDENCE: 0.5,
  MOUTH_MOVEMENT_THRESHOLD: 0.02,
  GAZE_DEVIATION_THRESHOLD: 0.3,
  HEAD_TURN_THRESHOLD: 35, // degrees
  
  // Audio settings
  AUDIO_SAMPLE_RATE: 16000,
  VAD_FRAME_SIZE: 512,
  VOICE_ACTIVITY_THRESHOLD: 0.5,
  
  // Violation thresholds
  VIOLATION_THRESHOLDS: {
    TAB_SWITCH: { max: 5, riskWeight: 0.3 },
    FULLSCREEN_EXIT: { max: 3, riskWeight: 0.4 },
    PAGE_RELOAD: { max: 1, riskWeight: 0.8 },
    IDLE_ACTIVITY: { max: 10, riskWeight: 0.2 },
    COPY_PASTE: { max: 0, riskWeight: 0.6 },
    NETWORK_DISCONNECT: { max: 0, riskWeight: 0.7 },
    DEVICE_CHANGE: { max: 0, riskWeight: 0.7 },
    MULTIPLE_PERSON_DETECTED: { max: 0, riskWeight: 0.9 },
    FACE_NOT_VISIBLE: { max: 5, riskWeight: 0.7 },
    MOUTH_MOVEMENT_DETECTED: { max: 8, riskWeight: 0.5 },
    LOOKING_AWAY: { max: 15, riskWeight: 0.3 },
    HEAD_TURN_DETECTED: { max: 10, riskWeight: 0.4 },
    VOICE_ACTIVITY_DETECTED: { max: 5, riskWeight: 0.6 },
    CAMERA_PERMISSION_DENIED: { max: 0, riskWeight: 0.8 },
    MICROPHONE_PERMISSION_DENIED: { max: 0, riskWeight: 0.6 },
  }
};

// Event types
const EVENT_TYPES = {
  // Browser events
  TAB_SWITCH: 'TAB_SWITCH',
  FULLSCREEN_EXIT: 'FULLSCREEN_EXIT',
  PAGE_RELOAD: 'PAGE_RELOAD',
  IDLE_ACTIVITY: 'IDLE_ACTIVITY',
  COPY_PASTE: 'COPY_PASTE',
  NETWORK_DISCONNECT: 'NETWORK_DISCONNECT',
  NETWORK_RECONNECT: 'NETWORK_RECONNECT',
  DEVICE_CHANGE: 'DEVICE_CHANGE',
  
  // Computer vision events
  MULTIPLE_PERSON_DETECTED: 'MULTIPLE_PERSON_DETECTED',
  FACE_NOT_VISIBLE: 'FACE_NOT_VISIBLE',
  MOUTH_MOVEMENT_DETECTED: 'MOUTH_MOVEMENT_DETECTED',
  LOOKING_AWAY: 'LOOKING_AWAY',
  HEAD_TURN_DETECTED: 'HEAD_TURN_DETECTED',
  
  // Audio events
  VOICE_ACTIVITY_DETECTED: 'VOICE_ACTIVITY_DETECTED',
  
  // System events
  CAMERA_PERMISSION_DENIED: 'CAMERA_PERMISSION_DENIED',
  MICROPHONE_PERMISSION_DENIED: 'MICROPHONE_PERMISSION_DENIED',
  PROCTORING_INITIALIZED: 'PROCTORING_INITIALIZED',
  PROCTORING_ERROR: 'PROCTORING_ERROR',
};

/**
 * Advanced Proctoring Hook
 */
export const useAdvancedProctoring = (sessionId, onViolation = null) => {
  // State management
  const [isInitialized, setIsInitialized] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const isMonitoringRef = useRef(false);
  const [violations, setViolations] = useState([]);
  const [riskScore, setRiskScore] = useState(0);
  const [cameraStream, setCameraStream] = useState(null);
  const [audioStream, setAudioStream] = useState(null);
  const cameraStreamRef = useRef(null);
  const audioStreamRef = useRef(null);
  const [detectionResults, setDetectionResults] = useState({
    faceCount: 0,
    faceVisible: false,
    visibilityRatio: 0,
    mouthMovement: false,
    gazeDirection: 'center',
    headPose: { pitch: 0, yaw: 0, roll: 0 },
    voiceActivity: false,
  });
  
  // ═══════════════════════════════════════════════════════════════════
  // METRICS TRACKING - Real-time behavioral metrics (no stale closure)
  // ═══════════════════════════════════════════════════════════════════
  const behaviorSnapshotRef = useRef({
    face_detected: false,
    eye_contact_pct: 0.5,
    head_stability: 0.5,
    looking_away_count: 0,
    response_time_sec: 0,
    dominant_emotion: 'neutral',
  });
  
  // Computed metrics state (for components that need reactive updates)
  const [metrics, setMetrics] = useState({
    eyeContactPercent: 0.5,
    headStability: 0.5,
    dominantEmotion: 'neutral',
    faceDetected: false,
    lookingAwayCount: 0,
  });
  
  // Track eye contact samples for averaging
  const eyeContactSamplesRef = useRef([]);
  const lookingAwayCountRef = useRef(0);
  
  // Refs for MediaPipe and streams
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const cameraRef = useRef(null);
  const faceDetectionRef = useRef(null);
  const faceMeshRef = useRef(null);
  const audioContextRef = useRef(null);
  const vadProcessorRef = useRef(null);
  const frameCountRef = useRef(0);
  const lastMouthStateRef = useRef({ open: false, time: 0 });
  const violationCountsRef = useRef({});
  const consecutiveNoFaceFramesRef = useRef(0);
  const consecutiveFaceFramesRef = useRef(0);
  const headYawBaselineRef = useRef({
    ready: false,
    samples: [],
    value: 0,
  });
  const consecutiveHeadTurnFramesRef = useRef(0);
  const isMountedRef = useRef(true);
  const initStartedRef = useRef(false);
  const lastEventSentAtRef = useRef({});
  const lastViolationCallbackAtRef = useRef({});

  // Keep latest onViolation callback without triggering effect loops
  const onViolationRef = useRef(onViolation);
  useEffect(() => {
    onViolationRef.current = onViolation;
  }, [onViolation]);

  const shouldSendEvent = useCallback((eventType, minIntervalMs) => {
    const now = Date.now();
    const last = lastEventSentAtRef.current[eventType] || 0;
    if (now - last < minIntervalMs) return false;
    lastEventSentAtRef.current[eventType] = now;
    return true;
  }, []);

  const shouldCallbackViolation = useCallback((eventType, minIntervalMs) => {
    const now = Date.now();
    const last = lastViolationCallbackAtRef.current[eventType] || 0;
    if (now - last < minIntervalMs) return false;
    lastViolationCallbackAtRef.current[eventType] = now;
    return true;
  }, []);

  // Update overall risk score
  const updateRiskScore = useCallback(() => {
    const counts = violationCountsRef.current;
    let totalRisk = 0;
    let totalEvents = 0;
    
    Object.entries(counts).forEach(([eventType, count]) => {
      const threshold = PROCTORING_CONFIG.VIOLATION_THRESHOLDS[eventType];
      if (threshold) {
        totalRisk += (count * threshold.riskWeight);
        totalEvents += count;
      }
    });
    
    const averageRisk = totalEvents > 0 ? totalRisk / totalEvents : 0;
    setRiskScore(Math.min(averageRisk, 1.0));
  }, []);

  // Log proctoring event to backend
  const logProctoringEvent = useCallback(async (eventType, metadata = {}) => {
    try {
      if (!sessionId) return;

      // Prevent event storms from CV/audio loops
      const minIntervalByType = {
        PROCTORING_INITIALIZED: 60000,
        PROCTORING_ERROR: 5000,
        TAB_SWITCH: 500,
        FULLSCREEN_EXIT: 500,
        PAGE_RELOAD: 500,
        IDLE_ACTIVITY: 1000,
        COPY_PASTE: 500,
        NETWORK_DISCONNECT: 1000,
        NETWORK_RECONNECT: 2000,
        DEVICE_CHANGE: 2000,
        MULTIPLE_PERSON_DETECTED: 5000,
        FACE_NOT_VISIBLE: 5000,
        MOUTH_MOVEMENT_DETECTED: 2000,
        LOOKING_AWAY: 5000,
        HEAD_TURN_DETECTED: 5000,
        VOICE_ACTIVITY_DETECTED: 3000,
        CAMERA_PERMISSION_DENIED: 60000,
        MICROPHONE_PERMISSION_DENIED: 60000,
      };
      const minIntervalMs = minIntervalByType[eventType] ?? 1500;
      if (!shouldSendEvent(eventType, minIntervalMs)) return;

      const confidence =
        typeof metadata.confidence === 'number' && Number.isFinite(metadata.confidence)
          ? Math.min(1, Math.max(0, metadata.confidence))
          : undefined;

      const eventData = {
        session_id: Number(sessionId),
        event_type: eventType,
        ...(confidence !== undefined ? { confidence } : {}),
        metadata: {
          ...toJsonSafe(metadata),
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
        const violationCount = violationCountsRef.current[eventType];
        const threshold = PROCTORING_CONFIG.VIOLATION_THRESHOLDS[eventType];
        const shouldTerminate = threshold ? violationCount >= threshold.max : false;
        
        // Calculate overall risk score
        updateRiskScore();
        
        // Call violation callback if provided (skip non-violations)
        const nonViolationTypes = new Set([
          EVENT_TYPES.PROCTORING_INITIALIZED,
          EVENT_TYPES.PROCTORING_ERROR,
          EVENT_TYPES.NETWORK_RECONNECT,
        ]);
        const currentViolationCallback = onViolationRef.current;
        if (currentViolationCallback && !nonViolationTypes.has(eventType) && shouldCallbackViolation(eventType, 1000)) {
          currentViolationCallback({
            eventType,
            riskScore: result.risk_score,
            metadata,
            violationCount,
            terminate: shouldTerminate,
          });
        }
    } catch (error) {
      console.error('Error logging proctoring event:', error);
    }
  }, [sessionId, shouldSendEvent, shouldCallbackViolation, updateRiskScore]);

  const waitForVideoElement = useCallback(async (timeoutMs = 12000) => {
    const start = Date.now();
    while (isMountedRef.current && !videoRef.current && Date.now() - start < timeoutMs) {
      // Wait a tick for React to mount the <video> element.
      await new Promise((r) => setTimeout(r, 50));
    }
    return videoRef.current;
  }, []);

  // Request fullscreen mode
  const enterFullscreen = useCallback(async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
        console.log('✅ Entered fullscreen mode');
      }
    } catch (error) {
      console.warn('⚠️ Could not enter fullscreen:', error.message);
    }
  }, []);
  
  // Keep latest logProctoringEvent in a ref to avoid recreating event handlers
  const logProctoringEventRef = useRef(logProctoringEvent);
  useEffect(() => {
    logProctoringEventRef.current = logProctoringEvent;
  }, [logProctoringEvent]);

  // Browser monitoring event handlers - create once and use ref for logProctoringEvent
  const handleVisibilityChange = useCallback(() => {
    if (document.hidden) {
      logProctoringEventRef.current(EVENT_TYPES.TAB_SWITCH, {
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
      });
    }
  }, []);
  
  const handleFullscreenChange = useCallback(() => {
    if (!document.fullscreenElement) {
      logProctoringEventRef.current(EVENT_TYPES.FULLSCREEN_EXIT, {
        timestamp: Date.now(),
        wasFullscreen: true,
      });
    }
  }, []);
  
  const handleBeforeUnload = useCallback((event) => {
    logProctoringEventRef.current(EVENT_TYPES.PAGE_RELOAD, {
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
    });
    
    // Show warning to user
    event.preventDefault();
    event.returnValue = 'Are you sure you want to leave? Your session will be flagged.';
  }, []);
  
  const handleUserActivity = useCallback(() => {
    // Reset idle timer
    if (window.idleTimer) {
      clearTimeout(window.idleTimer);
    }
    
    window.idleTimer = setTimeout(() => {
      logProctoringEventRef.current(EVENT_TYPES.IDLE_ACTIVITY, {
        timestamp: Date.now(),
        idleDuration: 60000, // 1 minute
      });
    }, 60000);
  }, []);

  const handleCopyPaste = useCallback((e) => {
    logProctoringEventRef.current(EVENT_TYPES.COPY_PASTE, {
      timestamp: Date.now(),
      action: e.type,
    });
  }, []);

  const handleDeviceChange = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      logProctoringEventRef.current(EVENT_TYPES.DEVICE_CHANGE, {
        timestamp: Date.now(),
        devices: devices.map(d => ({ kind: d.kind, label: d.label, deviceId: d.deviceId })),
      });
    } catch (error) {
      logProctoringEventRef.current(EVENT_TYPES.DEVICE_CHANGE, {
        timestamp: Date.now(),
        error: error.message,
      });
    }
  }, []);

  const handleNetworkOffline = useCallback(() => {
    logProctoringEventRef.current(EVENT_TYPES.NETWORK_DISCONNECT, {
      timestamp: Date.now(),
    });
  }, []);

  const handleNetworkOnline = useCallback(() => {
    logProctoringEventRef.current(EVENT_TYPES.NETWORK_RECONNECT, {
      timestamp: Date.now(),
    });
  }, []);
  
  // Initialize MediaPipe Face Detection
  const initializeFaceDetection = useCallback(async () => {
    try {
      faceDetectionRef.current = new FaceDetection({
        locateFile: (file) => {
          return mediapipeCdn('@mediapipe/face_detection', MEDIAPIPE_FACE_DETECTION_VERSION, file);
        },
      });
      
      faceDetectionRef.current.setOptions({
        model: 'short',
        minDetectionConfidence: PROCTORING_CONFIG.FACE_DETECTION_CONFIDENCE,
      });
      
      faceDetectionRef.current.onResults(onFaceDetectionResults);
      
      console.log('✅ Face detection initialized');
    } catch (error) {
      console.error('❌ Failed to initialize face detection:', error);
      logProctoringEvent(EVENT_TYPES.PROCTORING_ERROR, {
        error: 'FACE_DETECTION_INIT_FAILED',
        message: error.message,
      });
    }
  }, []);
  
  // Initialize MediaPipe Face Mesh
  const initializeFaceMesh = useCallback(async () => {
    try {
      faceMeshRef.current = new FaceMesh({
        locateFile: (file) => {
          return mediapipeCdn('@mediapipe/face_mesh', MEDIAPIPE_FACE_MESH_VERSION, file);
        },
      });
      
      faceMeshRef.current.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: PROCTORING_CONFIG.FACE_PRESENCE_CONFIDENCE,
        minTrackingConfidence: 0.5,
      });
      
      faceMeshRef.current.onResults(onFaceMeshResults);
      
      console.log('✅ Face mesh initialized');
    } catch (error) {
      console.error('❌ Failed to initialize face mesh:', error);
      logProctoringEvent(EVENT_TYPES.PROCTORING_ERROR, {
        error: 'FACE_MESH_INIT_FAILED',
        message: error.message,
      });
    }
  }, []);
  
  // Face detection results handler
  const onFaceDetectionResults = useCallback((results) => {
    if (results.detections.length === 0) {
      consecutiveFaceFramesRef.current = 0;
      consecutiveNoFaceFramesRef.current += 1;

      // Require consecutive missing frames to avoid flicker-based false warnings.
      if (consecutiveNoFaceFramesRef.current >= 3) {
        setDetectionResults(prev => ({ ...prev, faceCount: 0, faceVisible: false, visibilityRatio: 0 }));
        logProctoringEventRef.current(EVENT_TYPES.FACE_NOT_VISIBLE, {
          faceCount: 0,
          timestamp: Date.now(),
          confidence: 1.0,
          source: 'face_detection',
          missingFrames: consecutiveNoFaceFramesRef.current,
        });
      }
      return;
    }

    consecutiveNoFaceFramesRef.current = 0;
    consecutiveFaceFramesRef.current += 1;
    
    const faceCount = results.detections.length;
    
    // Check for multiple people
    if (faceCount > 1) {
      const detectionBoxes = results.detections.map((d) => {
        const b = d.boundingBox || {};
        return {
          xCenter: b.xCenter,
          yCenter: b.yCenter,
          width: b.width,
          height: b.height,
        };
      });
      logProctoringEventRef.current(EVENT_TYPES.MULTIPLE_PERSON_DETECTED, {
        faceCount,
        timestamp: Date.now(),
        confidence: 0.9,
        detectionBoxes,
      });
    }
    
    setDetectionResults(prev => ({
      ...prev,
      faceCount,
      faceVisible: true,
    }));
  }, []);
  
  // Analyze face visibility using critical landmarks
  const analyzeFaceVisibility = useCallback((landmarks) => {
    const visibleLandmarks = CRITICAL_FACE_INDICES.filter((index) => {
      const landmark = landmarks?.[index];
      if (!landmark) return false;
      // MediaPipe face mesh landmarks typically expose x/y/z, not visibility.
      // Treat a landmark as visible if it is in normalized frame bounds.
      return (
        Number.isFinite(landmark.x) &&
        Number.isFinite(landmark.y) &&
        landmark.x >= -0.1 &&
        landmark.x <= 1.1 &&
        landmark.y >= -0.1 &&
        landmark.y <= 1.1
      );
    });

    const totalCritical = CRITICAL_FACE_INDICES.length || 1;
    const visibilityRatio = visibleLandmarks.length / totalCritical;

    // Slightly relaxed threshold to reduce false negatives in low light/camera noise.
    if (visibilityRatio < 0.45) {
      logProctoringEventRef.current(EVENT_TYPES.FACE_NOT_VISIBLE, {
        visibilityRatio,
        timestamp: Date.now(),
        confidence: 1 - visibilityRatio,
      });
    }

    setDetectionResults(prev => ({
      ...prev,
      faceVisible: visibilityRatio >= 0.45,
      visibilityRatio,
    }));
  }, []);
  
  // Analyze mouth movement for speaking detection
  const analyzeMouthMovement = useCallback((landmarks) => {
    // Get upper and lower lip landmarks
    const upperLip = landmarks[13]; // Upper lip center
    const lowerLip = landmarks[14]; // Lower lip center
    
    if (!upperLip || !lowerLip) return;
    
    // Calculate mouth opening
    const mouthOpening = Math.abs(upperLip.y - lowerLip.y);
    const currentTime = Date.now();
    
    // Detect mouth movement
    const isMouthOpen = mouthOpening > PROCTORING_CONFIG.MOUTH_MOVEMENT_THRESHOLD;
    
    if (isMouthOpen !== lastMouthStateRef.current.open) {
      // State changed, log movement
      if (isMouthOpen && currentTime - lastMouthStateRef.current.time > 1000) {
        logProctoringEventRef.current(EVENT_TYPES.MOUTH_MOVEMENT_DETECTED, {
          mouthOpening,
          timestamp: currentTime,
          confidence: Math.min(mouthOpening * 10, 1.0),
        });
        
        lastMouthStateRef.current = { open: true, time: currentTime };
      } else {
        lastMouthStateRef.current = { open: false, time: currentTime };
      }
    }
    
    setDetectionResults(prev => ({
      ...prev,
      mouthMovement: isMouthOpen,
    }));
  }, []);
  
  // Analyze eye gaze direction
  const analyzeEyeGaze = useCallback((landmarks) => {
    // Get eye landmarks for gaze estimation
    const leftEyeCenter = getEyeCenter(landmarks, FACEMESH_LEFT_EYE);
    const rightEyeCenter = getEyeCenter(landmarks, FACEMESH_RIGHT_EYE);
    
    if (!leftEyeCenter || !rightEyeCenter) return;
    
    // Estimate gaze direction based on eye position
    const faceCenter = {
      x: (leftEyeCenter.x + rightEyeCenter.x) / 2,
      y: (leftEyeCenter.y + rightEyeCenter.y) / 2,
    };
    
    // Simple gaze estimation (can be enhanced with more sophisticated algorithms)
    let gazeDirection = 'center';
    const deviation = Math.abs(faceCenter.x - 0.5);
    
    if (faceCenter.x < 0.5 - PROCTORING_CONFIG.GAZE_DEVIATION_THRESHOLD) {
      gazeDirection = 'left';
    } else if (faceCenter.x > 0.5 + PROCTORING_CONFIG.GAZE_DEVIATION_THRESHOLD) {
      gazeDirection = 'right';
    } else if (faceCenter.y > 0.5 + PROCTORING_CONFIG.GAZE_DEVIATION_THRESHOLD) {
      gazeDirection = 'down';
    }
    
    // Log looking away violations
    if (gazeDirection !== 'center') {
      logProctoringEventRef.current(EVENT_TYPES.LOOKING_AWAY, {
        gazeDirection,
        deviation,
        timestamp: Date.now(),
        confidence: Math.min(deviation * 2, 1.0),
      });
    }
    
    setDetectionResults(prev => ({
      ...prev,
      gazeDirection,
    }));
  }, []);
  
  // Estimate head pose using facial landmarks with baseline calibration
  const estimateHeadPose = useCallback((landmarks) => {
    const noseTip = landmarks?.[1];
    const leftOuterEye = landmarks?.[33];
    const rightOuterEye = landmarks?.[263];

    if (!noseTip || !leftOuterEye || !rightOuterEye) return;

    const eyeCenterX = (leftOuterEye.x + rightOuterEye.x) / 2;
    const rawYawNorm = noseTip.x - eyeCenterX;

    // Build a short per-user baseline so natural posture/camera angle doesn't trigger violations.
    if (!headYawBaselineRef.current.ready) {
      headYawBaselineRef.current.samples.push(rawYawNorm);
      if (headYawBaselineRef.current.samples.length >= 20) {
        const sum = headYawBaselineRef.current.samples.reduce((a, b) => a + b, 0);
        headYawBaselineRef.current.value = sum / headYawBaselineRef.current.samples.length;
        headYawBaselineRef.current.ready = true;
      }
    }

    const calibratedYawNorm = rawYawNorm - headYawBaselineRef.current.value;
    const headYaw = calibratedYawNorm * 120;

    // Require sustained deviation to avoid one-frame spikes.
    const yawThresholdNorm = 0.12;
    if (Math.abs(calibratedYawNorm) > yawThresholdNorm) {
      consecutiveHeadTurnFramesRef.current += 1;
    } else {
      consecutiveHeadTurnFramesRef.current = 0;
    }

    if (consecutiveHeadTurnFramesRef.current >= 5) {
      logProctoringEventRef.current(EVENT_TYPES.HEAD_TURN_DETECTED, {
        headYaw,
        calibratedYawNorm,
        timestamp: Date.now(),
        confidence: Math.min(Math.abs(calibratedYawNorm) / 0.2, 1.0),
      });
      consecutiveHeadTurnFramesRef.current = 0;
    }

    setDetectionResults(prev => ({
      ...prev,
      headPose: {
        pitch: 0, // Would need more complex calculation
        yaw: headYaw,
        roll: 0, // Would need more complex calculation
      },
    }));
  }, []);

  // Face mesh results handler
  const onFaceMeshResults = useCallback((results) => {
    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
      const landmarks = results.multiFaceLandmarks[0];
      
      // Analyze face visibility
      analyzeFaceVisibility(landmarks);
      
      // Analyze mouth movement
      analyzeMouthMovement(landmarks);
      
      // Analyze eye gaze
      analyzeEyeGaze(landmarks);
      
      // Estimate head pose
      estimateHeadPose(landmarks);
      
      // ═══════════════════════════════════════════════════════════════
      // COMPUTE REAL BEHAVIORAL METRICS (not mocked)
      // ═══════════════════════════════════════════════════════════════
      
      // Head stability: Based on nose tip deviation from center (0.5)
      const nose = landmarks[1]; // Nose tip
      const headStability = nose ? Math.max(0, Math.min(1, 1 - Math.abs(nose.x - 0.5) * 2)) : 0.5;
      
      // Eye contact: Check if eyes are roughly centered (looking at camera)
      const leftEyeCenter = landmarks[33];  // Left eye inner corner
      const rightEyeCenter = landmarks[263]; // Right eye inner corner
      
      let eyeContact = 0.5; // Default
      if (leftEyeCenter && rightEyeCenter) {
        const eyeMidX = (leftEyeCenter.x + rightEyeCenter.x) / 2;
        const eyeMidY = (leftEyeCenter.y + rightEyeCenter.y) / 2;
        
        // Check if looking roughly at camera (within tolerance)
        const isLookingAtCamera = 
          Math.abs(eyeMidX - 0.5) < 0.15 && 
          Math.abs(eyeMidY - 0.4) < 0.15; // Eyes typically in upper portion
        
        eyeContact = isLookingAtCamera ? 1.0 : 0.0;
        
        // Track looking away count
        if (!isLookingAtCamera) {
          lookingAwayCountRef.current += 1;
        }
      }
      
      // Update eye contact samples for averaging (rolling window of 30 samples)
      eyeContactSamplesRef.current.push(eyeContact);
      if (eyeContactSamplesRef.current.length > 30) {
        eyeContactSamplesRef.current.shift();
      }
      
      // Calculate average eye contact percentage
      const avgEyeContact = eyeContactSamplesRef.current.length > 0
        ? eyeContactSamplesRef.current.reduce((a, b) => a + b, 0) / eyeContactSamplesRef.current.length
        : 0.5;
      
      // Update behavioral snapshot ref (for interval access - no stale closure)
      behaviorSnapshotRef.current = {
        face_detected: true,
        eye_contact_pct: avgEyeContact,
        head_stability: headStability,
        looking_away_count: lookingAwayCountRef.current,
        response_time_sec: behaviorSnapshotRef.current.response_time_sec,
        dominant_emotion: 'neutral', // Simplified - would need emotion model
      };
      
      // Update reactive metrics state (for component updates)
      setMetrics({
        eyeContactPercent: avgEyeContact,
        headStability: headStability,
        dominantEmotion: 'neutral',
        faceDetected: true,
        lookingAwayCount: lookingAwayCountRef.current,
      });
      
    } else {
      consecutiveFaceFramesRef.current = 0;
      consecutiveNoFaceFramesRef.current += 1;
      consecutiveHeadTurnFramesRef.current = 0;

      if (consecutiveNoFaceFramesRef.current >= 3) {
        setDetectionResults(prev => ({ ...prev, faceVisible: false, visibilityRatio: 0 }));
        logProctoringEventRef.current(EVENT_TYPES.FACE_NOT_VISIBLE, {
          timestamp: Date.now(),
          confidence: 0.95,
          source: 'face_mesh',
          missingFrames: consecutiveNoFaceFramesRef.current,
        });
      }
      
      // Update metrics to reflect no face detected
      behaviorSnapshotRef.current.face_detected = false;
      setMetrics(prev => ({ ...prev, faceDetected: false }));
    }
  }, [analyzeFaceVisibility, analyzeMouthMovement, analyzeEyeGaze, estimateHeadPose]);
  
  // Helper function to get eye center
  const getEyeCenter = (landmarks, eyeIndices) => {
    const eyeLandmarks = eyeIndices.map(index => landmarks[index]).filter(Boolean);
    if (eyeLandmarks.length === 0) return null;
    
    const sumX = eyeLandmarks.reduce((sum, landmark) => sum + landmark.x, 0);
    const sumY = eyeLandmarks.reduce((sum, landmark) => sum + landmark.y, 0);
    
    return {
      x: sumX / eyeLandmarks.length,
      y: sumY / eyeLandmarks.length,
    };
  };
  
  // Simple Voice Activity Detection (simplified implementation)
  const initializeSimpleVAD = useCallback((source) => {
    const analyser = audioContextRef.current.createAnalyser();
    analyser.fftSize = PROCTORING_CONFIG.VAD_FRAME_SIZE;
    source.connect(analyser);
    
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let voiceActivityDetected = false;
    let voiceStartTime = null;
    
    const detectVoiceActivity = () => {
      analyser.getByteFrequencyData(dataArray);
      
      // Calculate average amplitude
      const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
      const normalizedAmplitude = average / 255;
      
      // Simple threshold-based VAD
      const isVoiceActive = normalizedAmplitude > PROCTORING_CONFIG.VOICE_ACTIVITY_THRESHOLD;
      
      if (isVoiceActive && !voiceActivityDetected) {
        // Voice activity started
        voiceActivityDetected = true;
        voiceStartTime = Date.now();
        
        logProctoringEvent(EVENT_TYPES.VOICE_ACTIVITY_DETECTED, {
          timestamp: voiceStartTime,
          amplitude: normalizedAmplitude,
          confidence: Math.min(normalizedAmplitude * 2, 1.0),
        });
        
        setDetectionResults(prev => ({ ...prev, voiceActivity: true }));
      } else if (!isVoiceActive && voiceActivityDetected) {
        // Voice activity ended
        voiceActivityDetected = false;
        const duration = Date.now() - voiceStartTime;
        
        // Log additional metadata about voice activity duration
        if (duration > 5000) { // Longer than 5 seconds
          logProctoringEvent(EVENT_TYPES.VOICE_ACTIVITY_DETECTED, {
            timestamp: Date.now(),
            duration,
            amplitude: normalizedAmplitude,
            confidence: Math.min(normalizedAmplitude * 2, 1.0),
            metadata: { long_duration: true },
          });
        }
        
        setDetectionResults(prev => ({ ...prev, voiceActivity: false }));
      }
      
      // Continue monitoring
      if (isMonitoring) {
        requestAnimationFrame(detectVoiceActivity);
      }
    };
    
    detectVoiceActivity();
  }, [isMonitoring]);

  // Initialize audio monitoring with VAD
  const initializeAudioMonitoring = useCallback(async () => {
    try {
      // Get microphone access
      const audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: PROCTORING_CONFIG.AUDIO_SAMPLE_RATE,
          channelCount: 1,
        },
      });
      
      setAudioStream(audioStream);
      audioStreamRef.current = audioStream;
      
      // Create audio context
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContextRef.current.createMediaStreamSource(audioStream);
      
      // Initialize VAD (Voice Activity Detection)
      // Note: In production, you would use a proper VAD library like Silero VAD
      // This is a simplified implementation
      initializeSimpleVAD(source);
      
      console.log('✅ Audio monitoring initialized');
    } catch (error) {
      console.error('❌ Failed to initialize audio monitoring:', error);
      
      if (error.name === 'NotAllowedError') {
        logProctoringEvent(EVENT_TYPES.MICROPHONE_PERMISSION_DENIED, {
          timestamp: Date.now(),
          error: error.name,
        });
      } else {
        logProctoringEvent(EVENT_TYPES.PROCTORING_ERROR, {
          error: 'AUDIO_INIT_FAILED',
          message: error.message,
        });
      }
    }
  }, [logProctoringEvent, initializeSimpleVAD]);
  
  // Initialize camera and video processing
  const initializeCamera = useCallback(async () => {
    try {
      const videoEl = await waitForVideoElement();
      if (!videoEl) {
        throw new Error('Video element not ready');
      }

      // Get camera access
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: PROCTORING_CONFIG.VIDEO_WIDTH,
          height: PROCTORING_CONFIG.VIDEO_HEIGHT,
          facingMode: 'user',
        },
      });
      
      setCameraStream(stream);
      cameraStreamRef.current = stream;
      
      // Attach stream to the mounted <video> element
      videoEl.srcObject = stream;
      
      // Initialize MediaPipe camera
      cameraRef.current = new Camera(videoEl, {
        onFrame: async () => {
          // Process frames at reduced rate for performance
          frameCountRef.current++;
          if (frameCountRef.current % (30 / PROCTORING_CONFIG.PROCESSING_FPS) === 0) {
            await faceDetectionRef.current?.send({ image: videoEl });
            await faceMeshRef.current?.send({ image: videoEl });
          }
        },
        width: PROCTORING_CONFIG.VIDEO_WIDTH,
        height: PROCTORING_CONFIG.VIDEO_HEIGHT,
      });
      
      cameraRef.current.start();
      
      console.log('✅ Camera initialized');
    } catch (error) {
      console.error('❌ Failed to initialize camera:', error);
      
      if (error.name === 'NotAllowedError') {
        logProctoringEvent(EVENT_TYPES.CAMERA_PERMISSION_DENIED, {
          timestamp: Date.now(),
          error: error.name,
        });
      } else {
        logProctoringEvent(EVENT_TYPES.PROCTORING_ERROR, {
          error: 'CAMERA_INIT_FAILED',
          message: error.message,
        });
      }
    }
  }, [waitForVideoElement]);
  

  
  // Initialize all monitoring systems
  const initializeProctoring = useCallback(async () => {
    try {
      if (initStartedRef.current) return;
      initStartedRef.current = true;

      console.log('🚀 Initializing advanced proctoring system...');
      
      // Initialize browser monitoring - only add each listener once
      const addEventListenerOnce = (target, event, handler) => {
        target.removeEventListener(event, handler);
        target.addEventListener(event, handler);
      };
      
      addEventListenerOnce(document, 'visibilitychange', handleVisibilityChange);
      addEventListenerOnce(document, 'fullscreenchange', handleFullscreenChange);
      addEventListenerOnce(window, 'beforeunload', handleBeforeUnload);
      addEventListenerOnce(window, 'mousemove', handleUserActivity);
      addEventListenerOnce(window, 'keydown', handleUserActivity);
      addEventListenerOnce(window, 'touchstart', handleUserActivity);
      addEventListenerOnce(document, 'copy', handleCopyPaste);
      addEventListenerOnce(document, 'paste', handleCopyPaste);
      addEventListenerOnce(document, 'cut', handleCopyPaste);
      addEventListenerOnce(window, 'offline', handleNetworkOffline);
      addEventListenerOnce(window, 'online', handleNetworkOnline);
      navigator.mediaDevices?.removeEventListener?.('devicechange', handleDeviceChange);
      navigator.mediaDevices?.addEventListener?.('devicechange', handleDeviceChange);
      
      // Request fullscreen mode for the test
      await enterFullscreen();

      // Initialize computer vision (non-fatal — camera preview still works if CV fails)
      try {
        await initializeFaceDetection();
        await initializeFaceMesh();
      } catch (cvError) {
        console.warn('⚠️ Computer vision init failed (non-fatal):', cvError.message);
      }

      // Initialize camera (non-fatal — browser monitoring still works)
      try {
        await initializeCamera();
      } catch (camError) {
        console.warn('⚠️ Camera init failed (non-fatal):', camError.message);
      }
      
      // Initialize audio monitoring (non-fatal)
      try {
        await initializeAudioMonitoring();
      } catch (audioError) {
        console.warn('⚠️ Audio monitoring init failed (non-fatal):', audioError.message);
      }
      
      // Log initialization
      logProctoringEvent(EVENT_TYPES.PROCTORING_INITIALIZED, {
        timestamp: Date.now(),
        config: {
          CAMERA_FPS: PROCTORING_CONFIG.CAMERA_FPS,
          PROCESSING_FPS: PROCTORING_CONFIG.PROCESSING_FPS,
          VIDEO_WIDTH: PROCTORING_CONFIG.VIDEO_WIDTH,
          VIDEO_HEIGHT: PROCTORING_CONFIG.VIDEO_HEIGHT,
        },
      });
      
      setIsInitialized(true);
      setIsMonitoring(true);
      
      console.log('✅ Advanced proctoring system initialized successfully');
    } catch (error) {
      console.error('❌ Failed to initialize proctoring system:', error);
      logProctoringEvent(EVENT_TYPES.PROCTORING_ERROR, {
        error: 'INITIALIZATION_FAILED',
        message: error.message,
      });
      // Still enable monitoring for browser-level proctoring even if some subsystems failed
      setIsInitialized(true);
      setIsMonitoring(true);
    }
  }, [
    enterFullscreen,
    handleVisibilityChange,
    handleFullscreenChange,
    handleBeforeUnload,
    handleUserActivity,
    initializeFaceDetection,
    initializeFaceMesh,
    initializeCamera,
    initializeAudioMonitoring,
    logProctoringEvent,
  ]);
  
  // Cleanup function
  const cleanup = useCallback(() => {
    // Don't cleanup if still monitoring
    if (isMonitoringRef.current) {
      console.log('⚠️ Skipping cleanup - still monitoring');
      return;
    }
    
    console.log('🧹 Cleaning up proctoring system...');
    
    setIsMonitoring(false);
    isMonitoringRef.current = false;
    
    // Stop camera
    if (cameraRef.current) {
      cameraRef.current.stop();
    }
    
    // Stop streams
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(track => track.stop());
      cameraStreamRef.current = null;
    }
    
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      audioStreamRef.current = null;
    }
    
    // Close audio context
    if (audioContextRef.current) {
      try {
        if (audioContextRef.current.state !== 'closed') {
          audioContextRef.current.close();
        }
      } catch (_) {
        // ignore double-close / invalid state during rapid mounts/unmounts
      }
    }
    
    // Remove event listeners
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    document.removeEventListener('fullscreenchange', handleFullscreenChange);
    window.removeEventListener('beforeunload', handleBeforeUnload);
    window.removeEventListener('mousemove', handleUserActivity);
    window.removeEventListener('keydown', handleUserActivity);
    window.removeEventListener('touchstart', handleUserActivity);
      document.removeEventListener('copy', handleCopyPaste);
      document.removeEventListener('paste', handleCopyPaste);
      document.removeEventListener('cut', handleCopyPaste);
      window.removeEventListener('offline', handleNetworkOffline);
      window.removeEventListener('online', handleNetworkOnline);
      navigator.mediaDevices?.removeEventListener?.('devicechange', handleDeviceChange);
    
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
    handleCopyPaste,
    handleDeviceChange,
    handleNetworkOffline,
    handleNetworkOnline,
  ]);
  
  // Store latest initializeProctoring in ref
  const initializeProctoringRef = useRef();
  useEffect(() => {
    initializeProctoringRef.current = initializeProctoring;
  }, [initializeProctoring]);

  // Initialize on mount - only depends on sessionId to prevent cleanup/reinit cycles
  useEffect(() => {
    isMountedRef.current = true;
    
    // Only initialize if not already initialized
    if (sessionId && !isInitialized && !initStartedRef.current) {
      initializeProctoring();
    }
    
    return () => {
      // Only cleanup on final unmount
      isMountedRef.current = false;
    };
  }, [sessionId, isInitialized, initializeProctoring]);

  // Cleanup only on final unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);
  
  // Stop monitoring (call this when interview is complete)
  const stopMonitoring = useCallback(() => {
    console.log('🛑 Stopping proctoring monitoring...');
    setIsMonitoring(false);
    isMonitoringRef.current = false;
    cleanup();
  }, [cleanup]);
  
  // Helper to reset metrics (call when starting new recording)
  const resetMetrics = useCallback(() => {
    eyeContactSamplesRef.current = [];
    lookingAwayCountRef.current = 0;
    behaviorSnapshotRef.current = {
      face_detected: false,
      eye_contact_pct: 0.5,
      head_stability: 0.5,
      looking_away_count: 0,
      response_time_sec: 0,
      dominant_emotion: 'neutral',
    };
    setMetrics({
      eyeContactPercent: 0.5,
      headStability: 0.5,
      dominantEmotion: 'neutral',
      faceDetected: false,
      lookingAwayCount: 0,
    });
  }, []);
  
  // Get current snapshot (for interval polling - avoids stale closure)
  const getBehaviorSnapshot = useCallback(() => {
    return { ...behaviorSnapshotRef.current };
  }, []);
  
  return {
    // State
    isInitialized,
    isMonitoring,
    violations,
    riskScore,
    detectionResults,
    
    // ═══════════════════════════════════════════════════════════════════
    // COMPUTED METRICS (what InterviewRoom expects)
    // ═══════════════════════════════════════════════════════════════════
    metrics,                    // Reactive state for component renders
    behaviorSnapshotRef,        // Ref for interval polling (no stale closure)
    getBehaviorSnapshot,        // Function to get current snapshot
    resetMetrics,               // Reset when starting new recording
    
    // Refs for video elements
    videoRef,
    canvasRef,
    
    // Methods
    initializeProctoring,
    stopMonitoring,
    cleanup,
    logProctoringEvent,
    enterFullscreen,
    
    // Configuration
    config: PROCTORING_CONFIG,
    eventTypes: EVENT_TYPES,
  };
};

export default useAdvancedProctoring;
