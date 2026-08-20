import { useState, useCallback, useRef, useEffect } from 'react';
import { logProctorEvent } from '../services/proctoringService';

// Event types for proctoring
export const PROCTORING_EVENTS = {
    CAMERA_PERMISSION_DENIED: 'camera_permission_denied',
    TAB_SWITCH: 'tab_switch',
    FULLSCREEN_EXIT: 'fullscreen_exit',
    PAGE_RELOAD: 'page_reload',
    IDLE_ACTIVITY: 'idle_activity',
};

// Warning thresholds
export const WARNING_THRESHOLDS = {
    TAB_SWITCH: 3,
    FULLSCREEN_EXIT: 3,
    IDLE_ACTIVITY: 5,
};

export const useProctoring = (sessionId, onWarning) => {
    const [isInitialized, setIsInitialized] = useState(false);
    const [eventCounts, setEventCounts] = useState({});
    const [warnings, setWarnings] = useState([]);
    const [showFullscreenPrompt, setShowFullscreenPrompt] = useState(false);
    const [mediaStream, setMediaStream] = useState(null);
    const mediaStreamRef = useRef(null);
    
    const idleTimerRef = useRef(null);
    const tabSwitchCountRef = useRef(0);
    const fullscreenExitCountRef = useRef(0);
    const idleCountRef = useRef(0);
    const isActiveRef = useRef(true);

    // Handle idle activity detection (MOVED UP - declared before use)
    const handleIdleActivity = useCallback(async () => {
        idleCountRef.current += 1;
        const count = idleCountRef.current;
        
        setEventCounts(prev => ({ ...prev, idle_activity: count }));
        
        // Log the event
        try {
            await logProctorEvent(sessionId, PROCTORING_EVENTS.IDLE_ACTIVITY, {
                count,
                duration_seconds: 60,
            });
        } catch (error) {
            // Don't let proctoring errors interrupt the test
            console.debug('Failed to log idle activity:', error);
        }

        // Check warning threshold
        if (count >= WARNING_THRESHOLDS.IDLE_ACTIVITY) {
            const warning = {
                type: PROCTORING_EVENTS.IDLE_ACTIVITY,
                message: 'No activity detected for 60 seconds. Please stay active during the test.',
                count,
                severity: count >= WARNING_THRESHOLDS.IDLE_ACTIVITY * 2 ? 'high' : 'medium',
            };
            
            setWarnings(prev => [...prev, warning]);
            if (onWarning) onWarning(warning);
        }

        // Reset timer for next detection
        isActiveRef.current = false;
    }, [sessionId, onWarning]);

    // Reset idle timer
    const resetIdleTimer = useCallback(() => {
        if (idleTimerRef.current) {
            clearTimeout(idleTimerRef.current);
        }
        
        isActiveRef.current = true;
        
        idleTimerRef.current = setTimeout(() => {
            if (isActiveRef.current) {
                handleIdleActivity();
            }
        }, 60000); // 60 seconds
    }, [handleIdleActivity]);

    // Handle tab switching and loss of window focus (e.g. popups)
    const handleFocusLoss = useCallback(async () => {
        // Prevent double counting if blur and visibilitychange fire simultaneously
        if (isActiveRef.current === false) return;
        isActiveRef.current = false;

        tabSwitchCountRef.current += 1;
        const count = tabSwitchCountRef.current;
        
        setEventCounts(prev => ({ ...prev, tab_switch: count }));
        
        // Log the event
        try {
            await logProctorEvent(sessionId, PROCTORING_EVENTS.TAB_SWITCH, {
                count,
                timestamp: new Date().toISOString(),
            });
        } catch (error) {
            console.debug('Failed to log tab switch:', error);
        }

        // Check warning threshold
        if (count >= WARNING_THRESHOLDS.TAB_SWITCH) {
            const warning = {
                type: PROCTORING_EVENTS.TAB_SWITCH,
                message: `You switched tabs or lost focus (${count}/${WARNING_THRESHOLDS.TAB_SWITCH}). The test will now be terminated.`,
                count,
                severity: 'high',
                terminate: true,
            };
            
            setWarnings(prev => [...prev, warning]);
            if (onWarning) onWarning(warning);
        } else {
            const warning = {
                type: PROCTORING_EVENTS.TAB_SWITCH,
                message: `You switched tabs or lost window focus. Ensure no popups are active (${count}/${WARNING_THRESHOLDS.TAB_SWITCH}).`,
                count,
                severity: count === WARNING_THRESHOLDS.TAB_SWITCH - 1 ? 'high' : 'medium',
            };
            
            setWarnings(prev => [...prev, warning]);
            if (onWarning) onWarning(warning);
        }

        // Re-enable focus tracking after a short cooldown
        setTimeout(() => {
            isActiveRef.current = true;
        }, 1000);
    }, [sessionId, onWarning]);

    const handleVisibilityChange = useCallback(async () => {
        if (document.hidden) {
            await handleFocusLoss();
        }
    }, [handleFocusLoss]);

    // Request fullscreen
    const requestFullscreen = useCallback(async () => {
        try {
            // Check if fullscreen is already active
            const isDOMFullscreen = document.fullscreenElement || 
                               document.webkitFullscreenElement || 
                               document.mozFullScreenElement || 
                               document.msFullscreenElement ||
                               document.webkitIsFullScreen ||
                               document.mozFullScreen;

            const isNativeFullscreen = Math.abs(window.innerHeight - window.screen.height) <= 5 && 
                                       Math.abs(window.innerWidth - window.screen.width) <= 5;

            if (isDOMFullscreen || isNativeFullscreen) {
                return true;
            }
            
            // Show prompt for user to initiate fullscreen
            setShowFullscreenPrompt(true);
            return false;
        } catch (error) {
            console.error('Failed to enter fullscreen:', error);
            
            // Log fullscreen failure
            try {
                await logProctorEvent(sessionId, PROCTORING_EVENTS.FULLSCREEN_EXIT, {
                    error: error.name,
                    message: error.message,
                    timestamp: new Date().toISOString(),
                });
            } catch (logError) {
                console.debug('Failed to log fullscreen exit:', logError);
            }
            
            return false;
        }
    }, [sessionId]);

    // Actually enter fullscreen (called from prompt)
    const enterFullscreen = useCallback(async () => {
        try {
            const element = document.documentElement;
            
            if (element.requestFullscreen) {
                await element.requestFullscreen();
            } else if (element.webkitRequestFullscreen) {
                await element.webkitRequestFullscreen();
            } else if (element.msRequestFullscreen) {
                await element.msRequestFullscreen();
            } else if (element.mozRequestFullScreen) {
                await element.mozRequestFullScreen();
            }
            
            setShowFullscreenPrompt(false);
            return true;
        } catch (error) {
            console.error('Failed to enter fullscreen:', error);
            setShowFullscreenPrompt(false);
            return false;
        }
    }, []);

    const handleFullscreenChange = useCallback(async () => {
        // Use a small delay to ensure the fullscreen state is updated
        setTimeout(async () => {
            const isDOMFullscreen = document.fullscreenElement || 
                               document.webkitFullscreenElement || 
                               document.mozFullScreenElement || 
                               document.msFullscreenElement ||
                               document.webkitIsFullScreen ||
                               document.mozFullScreen;

            const isNativeFullscreen = Math.abs(window.innerHeight - window.screen.height) <= 5 && 
                                       Math.abs(window.innerWidth - window.screen.width) <= 5;

            if (!isDOMFullscreen && !isNativeFullscreen) {
                fullscreenExitCountRef.current += 1;
                const count = fullscreenExitCountRef.current;
                
                setEventCounts(prev => ({ ...prev, fullscreen_exit: count }));
                
                // Log the event
                try {
                    await logProctorEvent(sessionId, PROCTORING_EVENTS.FULLSCREEN_EXIT, {
                        count,
                        timestamp: new Date().toISOString(),
                    });
                } catch (logError) {
                    console.debug('Failed to log fullscreen exit:', logError);
                }

                // Check warning threshold
                if (count >= WARNING_THRESHOLDS.FULLSCREEN_EXIT) {
                    const warning = {
                        type: PROCTORING_EVENTS.FULLSCREEN_EXIT,
                        message: 'Fullscreen mode is required for the test. Please enter fullscreen mode.',
                        count,
                        severity: count >= WARNING_THRESHOLDS.FULLSCREEN_EXIT * 2 ? 'high' : 'medium',
                    };
                    
                    setWarnings(prev => [...prev, warning]);
                    if (onWarning) onWarning(warning);
                    
                    // Try to re-enter fullscreen after a short delay
                    setTimeout(() => {
                        requestFullscreen();
                    }, 1000);
                }
            }
        }, 100);
    }, [sessionId, onWarning, requestFullscreen]);

    // Handle page reload/exit
    const handleBeforeUnload = useCallback(async (event) => {
        // Log the event
        try {
            await logProctorEvent(sessionId, PROCTORING_EVENTS.PAGE_RELOAD, {
                timestamp: new Date().toISOString(),
            });
        } catch (error) {
            console.debug('Failed to log page reload:', error);
        }

        // Show warning message
        const message = 'Reloading the page will be logged as a proctoring violation. Are you sure?';
        event.returnValue = message;
        return message;
    }, [sessionId]);

    // Check webcam permission
    const checkWebcamPermission = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            // Keep stream active
            setMediaStream(stream);
            mediaStreamRef.current = stream;
            return true;
        } catch (error) {
            // Log permission denied
            try {
                await logProctorEvent(sessionId, PROCTORING_EVENTS.CAMERA_PERMISSION_DENIED, {
                    error: error.name,
                    timestamp: new Date().toISOString(),
                });
            } catch (logError) {
                console.debug('Failed to log camera permission denied:', logError);
            }

            const warning = {
                type: PROCTORING_EVENTS.CAMERA_PERMISSION_DENIED,
                message: 'Camera permission is required for the test. Please allow camera access to continue.',
                severity: 'high',
                blocking: true, // This prevents test start
            };
            
            setWarnings(prev => [...prev, warning]);
            if (onWarning) onWarning(warning);
            
            return false;
        }
    }, [sessionId, onWarning]);

    // Setup activity listeners
    const setupActivityListeners = useCallback(() => {
        const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
        
        const handleActivity = () => {
            resetIdleTimer();
        };

        events.forEach(event => {
            document.addEventListener(event, handleActivity, true);
        });

        return () => {
            events.forEach(event => {
                document.removeEventListener(event, handleActivity, true);
            });
        };
    }, [resetIdleTimer]);

    const initializeProctoring = useCallback(async () => {
        if (isInitialized) return;

        try {
            // 1. Unconditionally Setup event listeners FIRST so they are active immediately
            document.addEventListener('visibilitychange', handleVisibilityChange);
            window.addEventListener('blur', handleFocusLoss);
            
            document.addEventListener('fullscreenchange', handleFullscreenChange);
            document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
            document.addEventListener('msfullscreenchange', handleFullscreenChange);
            document.addEventListener('mozfullscreenchange', handleFullscreenChange);
            window.addEventListener('resize', handleFullscreenChange); // Catch native F11 resizes
            window.addEventListener('beforeunload', handleBeforeUnload);
            
            const cleanupActivityListeners = setupActivityListeners();
            
            // 2. Start idle timer immediately
            resetIdleTimer();

            setIsInitialized(true);

            // 3. Request fullscreen next (this is less blocking than camera)
            await requestFullscreen();

            // 4. Finally, Check webcam permission (which can block/deny indefinitely)
            // Even if this evaluates to false, the tab tracking is already running above.
            await checkWebcamPermission();

            // Return cleanup function
            return () => {
                document.removeEventListener('visibilitychange', handleVisibilityChange);
                window.removeEventListener('blur', handleFocusLoss);
                
                document.removeEventListener('fullscreenchange', handleFullscreenChange);
                document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
                document.removeEventListener('msfullscreenchange', handleFullscreenChange);
                document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
                window.removeEventListener('resize', handleFullscreenChange);
                window.removeEventListener('beforeunload', handleBeforeUnload);
                cleanupActivityListeners();
                
                if (idleTimerRef.current) {
                    clearTimeout(idleTimerRef.current);
                }
                if (mediaStreamRef.current) {
                    mediaStreamRef.current.getTracks().forEach(t => t.stop());
                    mediaStreamRef.current = null;
                }
                setIsInitialized(false);
            };
        } catch (error) {
            console.error('Failed to initialize proctoring:', error);
            setIsInitialized(true);
        }
    }, [isInitialized, checkWebcamPermission, requestFullscreen, handleFocusLoss, handleVisibilityChange, handleFullscreenChange, handleBeforeUnload, setupActivityListeners, resetIdleTimer]);

    // Cleanup on unmount for timers only
    useEffect(() => {
        return () => {
            if (idleTimerRef.current) {
                clearTimeout(idleTimerRef.current);
            }
        };
    }, []);

    return {
        isInitialized,
        eventCounts,
        warnings,
        initializeProctoring,
        requestFullscreen,
        mediaStream,
        clearWarnings: () => setWarnings([]),
    };
};
