/**
 * Proctoring Video Display Component
 * 
 * Displays the webcam feed with real-time face detection overlays
 * and privacy-focused video processing.
 */

import React, { useRef, useEffect, useState } from 'react';
import { Camera, CameraOff, Eye, EyeOff } from 'lucide-react';

const ProctoringVideoDisplay = ({ 
  videoRef, 
  canvasRef, 
  isMonitoring, 
  detectionResults,
  showVideo = true,
  className = ''
}) => {
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [showPrivacyOverlay, setShowPrivacyOverlay] = useState(true);

  // Handle video load
  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      const handleLoadedMetadata = () => {
        setIsVideoReady(true);
      };
      
      video.addEventListener('loadedmetadata', handleLoadedMetadata);
      
      return () => {
        video.removeEventListener('loadedmetadata', handleLoadedMetadata);
      };
    }
  }, [videoRef]);

  // Toggle privacy overlay
  const togglePrivacyOverlay = () => {
    setShowPrivacyOverlay(!showPrivacyOverlay);
  };

  if (!showVideo) {
    return (
      <div className={`bg-gray-900 rounded-lg flex items-center justify-center ${className}`}>
        <div className="text-center text-gray-400">
          <CameraOff className="w-12 h-12 mx-auto mb-2" />
          <p className="text-sm">Video monitoring disabled</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative bg-gray-900 rounded-lg overflow-hidden ${className}`}>
      {/* Video Element */}
      <video
        ref={videoRef}
        className={`w-full h-full object-cover ${showPrivacyOverlay ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
        autoPlay
        playsInline
        muted
      />
      
      {/* Canvas for Face Detection Overlay */}
      <canvas
        ref={canvasRef}
        className="absolute top-0 left-0 w-full h-full pointer-events-none"
        style={{ display: showPrivacyOverlay ? 'block' : 'none' }}
      />
      
      {/* Privacy Overlay */}
      {showPrivacyOverlay && (
        <div className="absolute top-0 left-0 w-full h-full bg-gray-800 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <Eye className="w-12 h-12 mx-auto mb-2" />
            <p className="text-sm">Video monitoring active</p>
            <p className="text-xs mt-1">Your privacy is protected</p>
          </div>
        </div>
      )}
      
      {/* Status Indicators */}
      <div className="absolute top-4 left-4 space-y-2">
        {/* Monitoring Status */}
        <div className={`px-3 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${
          isMonitoring ? 'bg-green-600 text-white' : 'bg-gray-600 text-white'
        }`}>
          <div className={`w-2 h-2 rounded-full ${isMonitoring ? 'bg-white' : 'bg-gray-300'} animate-pulse`} />
          <span>{isMonitoring ? 'Monitoring' : 'Inactive'}</span>
        </div>
        
        {/* Face Detection Status */}
        {isMonitoring && (
          <div className={`px-3 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${
            detectionResults.faceVisible ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
          }`}>
            {detectionResults.faceVisible ? (
              <Eye className="w-3 h-3" />
            ) : (
              <EyeOff className="w-3 h-3" />
            )}
            <span>{detectionResults.faceVisible ? 'Face Detected' : 'No Face'}</span>
          </div>
        )}
      </div>
      
      {/* Privacy Toggle */}
      <div className="absolute bottom-4 right-4">
        <button
          onClick={togglePrivacyOverlay}
          className="px-3 py-1 bg-gray-800 bg-opacity-80 text-white text-xs rounded-full hover:bg-opacity-100 transition-all duration-200"
        >
          {showPrivacyOverlay ? 'Show Video' : 'Hide Video'}
        </button>
      </div>
      
      {/* Face Count Indicator */}
      {isMonitoring && detectionResults.faceCount > 1 && (
        <div className="absolute top-4 right-4">
          <div className="px-3 py-1 bg-red-600 text-white text-xs rounded-full font-medium">
            {detectionResults.faceCount} Faces
          </div>
        </div>
      )}
      
      {/* Loading State */}
      {!isVideoReady && (
        <div className="absolute top-0 left-0 w-full h-full bg-gray-900 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <Camera className="w-8 h-8 mx-auto mb-2 animate-pulse" />
            <p className="text-sm">Initializing camera...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProctoringVideoDisplay;
