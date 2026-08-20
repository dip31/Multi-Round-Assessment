/**
 * Basic Proctoring Hook for Interview Round
 * 
 * Provides only camera feed without advanced AI analysis
 * No API calls, no event logging - just video display
 */

import { useState, useEffect, useRef } from 'react';

export const useBasicProctoring = () => {
  const [cameraReady, setCameraReady] = useState(false);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    let mounted = true;

    const initCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: 640,
            height: 480,
            facingMode: 'user',
          },
          audio: false,
        });

        if (!mounted) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }

        streamRef.current = stream;

        // Wait for video element to be ready
        const checkVideo = setInterval(() => {
          if (videoRef.current && mounted) {
            clearInterval(checkVideo);
            videoRef.current.srcObject = stream;
            setCameraReady(true);
          }
        }, 100);

        // Cleanup check after 5 seconds
        setTimeout(() => clearInterval(checkVideo), 5000);

      } catch (err) {
        console.error('Camera access failed:', err);
        if (mounted) {
          setError(err.message);
        }
      }
    };

    initCamera();

    return () => {
      mounted = false;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      setCameraReady(false);
    }
  };

  return {
    videoRef,
    cameraReady,
    error,
    stopCamera,
  };
};

export default useBasicProctoring;
