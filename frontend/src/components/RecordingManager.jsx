import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

const RecordingManager = forwardRef(({ onRecordingComplete, isDisabled, maxSeconds = 180 }, ref) => {
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);
  const startTimeRef = useRef(null);
  const maxTimerRef = useRef(null);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);

  useImperativeHandle(ref, () => ({
    startRecording,
    stopRecording,
  }));

  async function startRecording() {
    if (isDisabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;
      audioChunksRef.current = [];
      mediaRecorderRef.current = new MediaRecorder(stream);
      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mediaRecorderRef.current.onstop = async () => {
        setRecording(false);
        setProcessing(true);
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const responseTimeSec = (Date.now() - startTimeRef.current) / 1000;
        if (onRecordingComplete) await onRecordingComplete(audioBlob, responseTimeSec);
        setProcessing(false);
      };
      mediaRecorderRef.current.start(1000);
      startTimeRef.current = Date.now();
      setRecording(true);
      maxTimerRef.current = setTimeout(() => stopRecording(true), maxSeconds * 1000);
    } catch (err) {
      console.error("Microphone permission denied or error:", err);
      // Fire onRecordingComplete with null? Instead, call onRecordingComplete with empty blob and 0
      if (onRecordingComplete) {
        // Log mic_denied via service elsewhere (hook)
      }
    }
  }

  function stopRecording(auto = false) {
    clearTimeout(maxTimerRef.current);
    try {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    } catch (e) {
      console.error("Error stopping recording", e);
    }
  }

  useEffect(() => {
    return () => {
      clearTimeout(maxTimerRef.current);
      try {
        streamRef.current?.getTracks().forEach((t) => t.stop());
      } catch (e) {}
    };
  }, []);

  if (!recording) return null;

  return (
    <div>
      <button
        className="px-8 py-3 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-semibold flex items-center gap-3"
        onClick={() => stopRecording(false)}
        disabled={processing}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <rect x="5" y="5" width="14" height="14" rx="2" fill="white" />
        </svg>
        Done Speaking
      </button>
    </div>
  );
});

export default RecordingManager;
