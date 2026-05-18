import { useState, useEffect, useCallback } from "react";

export function useTimer(initialSeconds: number, onExpire: () => void) {
  const [timeRemaining, setTimeRemaining] = useState(initialSeconds);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    // Sync initial state if it changes
    setTimeRemaining(initialSeconds);
  }, [initialSeconds]);

  useEffect(() => {
    if (timeRemaining <= 0) {
      if (!isExpired) {
        setIsExpired(true);
        onExpire();
      }
      return;
    }

    const interval = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (!isExpired) {
            setIsExpired(true);
            onExpire();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [timeRemaining, isExpired, onExpire]);

  // Format MM:SS or HH:MM:SS
  const formatTime = (totalSeconds: number) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const pad = (num: number) => num.toString().padStart(2, "0");

    if (hours > 0) {
      return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
    }
    return `${pad(minutes)}:${pad(seconds)}`;
  };

  let colorClass = "text-white";
  if (timeRemaining <= 300) { // < 5 mins
    colorClass = "text-coral-500 animate-pulse";
  } else if (timeRemaining <= 900) { // < 15 mins
    colorClass = "text-amber-400";
  }

  return {
    timeRemaining,
    formattedTime: formatTime(timeRemaining),
    colorClass,
    isExpired,
  };
}
