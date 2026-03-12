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
    
    const idleTimerRef = useRef(null);
    const tabSwitchCountRef = useRef(0);
    const fullscreenExitCountRef = useRef(0);
    const idleCountRef = useRef(0);
    const isActiveRef = useRef(true);

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
    }, []);

    // Handle idle activity detection
    const handleIdleActivity = useCallback(async () => {
        idleCountRef.current += 1;
        const count = idleCountRef.current;
        
        setEventCounts(prev => ({ ...prev, idle_activity: count }));
        
        // Log the event
        await logProctorEvent(sessionId, PROCTORING_EVENTS.IDLE_ACTIVITY, {
            count,
            duration_seconds: 60,
        });

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
        resetIdleTimer();
    }, [sessionId, onWarning, resetIdleTimer]);

    // Handle tab switching
    const handleVisibilityChange = useCallback(async () => {
        if (document.hidden) {
            tabSwitchCountRef.current += 1;
            const count = tabSwitchCountRef.current;
            
            setEventCounts(prev => ({ ...prev, tab_switch: count }));
            
            // Log the event
            await logProctorEvent(sessionId, PROCTORING_EVENTS.TAB_SWITCH, {
                count,
                timestamp: new Date().toISOString(),
            });

            // Check warning threshold
            if (count >= WARNING_THRESHOLDS.TAB_SWITCH) {
                const warning = {
                    type: PROCTORING_EVENTS.TAB_SWITCH,
                    message: 'You switched tabs. Please stay on the test page.',
                    count,
                    severity: count >= WARNING_THRESHOLDS.TAB_SWITCH * 2 ? 'high' : 'medium',
                };
                
                setWarnings(prev => [...prev, warning]);
                if (onWarning) onWarning(warning);
            }
        }
    }, [sessionId, onWarning]);

    // Request fullscreen
    const requestFullscreen = useCallback(async () => {
        try {
            // Check if fullscreen is already active
            if (document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement) {
                return true;
            }
            
            // Show prompt for user to initiate fullscreen
            setShowFullscreenPrompt(true);
            return false;
        } catch (error) {
            console.error('Failed to enter fullscreen:', error);
            
            // Log fullscreen failure
            await logProctorEvent(sessionId, PROCTORING_EVENTS.FULLSCREEN_EXIT, {
                error: error.name,
                message: error.message,
                timestamp: new Date().toISOString(),
            });
            
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

    // Handle fullscreen changes
    const handleFullscreenChange = useCallback(async () => {
        // Use a small delay to ensure the fullscreen state is updated
        setTimeout(async () => {
            if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
                fullscreenExitCountRef.current += 1;
                const count = fullscreenExitCountRef.current;
                
                setEventCounts(prev => ({ ...prev, fullscreen_exit: count }));
                
                // Log the event
                await logProctorEvent(sessionId, PROCTORING_EVENTS.FULLSCREEN_EXIT, {
                    count,
                    timestamp: new Date().toISOString(),
                });

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
        await logProctorEvent(sessionId, PROCTORING_EVENTS.PAGE_RELOAD, {
            timestamp: new Date().toISOString(),
        });

        // Show warning message
        const message = 'Reloading the page will be logged as a proctoring violation. Are you sure?';
        event.returnValue = message;
        return message;
    }, [sessionId]);

    // Check webcam permission
    const checkWebcamPermission = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            // Close the stream immediately after getting permission
            stream.getTracks().forEach(track => track.stop());
            return true;
        } catch (error) {
            // Log permission denied
            await logProctorEvent(sessionId, PROCTORING_EVENTS.CAMERA_PERMISSION_DENIED, {
                error: error.name,
                timestamp: new Date().toISOString(),
            });

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
            document.addEventListener('fullscreenchange', handleFullscreenChange);
            document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
            document.addEventListener('msfullscreenchange', handleFullscreenChange);
            document.addEventListener('mozfullscreenchange', handleFullscreenChange);
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
                document.removeEventListener('fullscreenchange', handleFullscreenChange);
                document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
                document.removeEventListener('msfullscreenchange', handleFullscreenChange);
                document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
                window.removeEventListener('beforeunload', handleBeforeUnload);
                cleanupActivityListeners();
                
                if (idleTimerRef.current) {
                    clearTimeout(idleTimerRef.current);
                }
            };
        } catch (error) {
            console.error('Failed to initialize proctoring:', error);
            setIsInitialized(true);
        }
    }, [isInitialized, checkWebcamPermission, requestFullscreen]);

    // Cleanup on unmount
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
        clearWarnings: () => setWarnings([]),
    };
};
