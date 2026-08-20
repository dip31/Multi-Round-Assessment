import { useState, useEffect, useRef } from 'react';

/**
 * Single shared countdown-timer hook for the assessment flows.
 *
 * Time state model:
 *   null / undefined  → timer has NOT been initialized (still loading). Never counts down, never fires onExpire.
 *   > 0               → timer is running, decremented once per second.
 *   0                 → timer has genuinely expired. onExpire fires exactly once.
 *
 * The hook is always called from the top level of a component; it decides
 * internally whether a countdown should run. Pass a positive integer (loaded
 * from the session/backend) via `setTimeRemaining` when the session resolves.
 */
export function useTimer(initialSeconds, onExpire) {
    const [timeRemaining, setTimeRemaining] = useState(initialSeconds);
    const intervalRef = useRef(null);
    const onExpireRef = useRef(onExpire);
    const expiredRef = useRef(false);

    // Adjust state during render when the initial value changes, instead of
    // syncing it inside an effect (keeps the countdown's single-fire guard).
    const [prevInitial, setPrevInitial] = useState(initialSeconds);
    if (initialSeconds !== prevInitial) {
        setPrevInitial(initialSeconds);
        setTimeRemaining(initialSeconds);
    }

    // A fresh value must re-arm the single-fire guard so onExpire can fire
    // again if the new timer later reaches zero.
    useEffect(() => {
        expiredRef.current = false;
    }, [initialSeconds]);

    useEffect(() => {
        onExpireRef.current = onExpire;
    }, [onExpire]);

    useEffect(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);

        // Not initialized yet — do nothing. This is the loading state and it
        // MUST NOT be interpreted as expiration.
        if (timeRemaining === null || timeRemaining === undefined) {
            return;
        }

        // Genuinely expired.
        if (timeRemaining <= 0) {
            if (!expiredRef.current) {
                expiredRef.current = true;
                if (onExpireRef.current) onExpireRef.current();
            }
            return;
        }

        intervalRef.current = setInterval(() => {
            setTimeRemaining((prev) => {
                if (prev === null || prev === undefined) return prev;
                if (prev <= 1) {
                    clearInterval(intervalRef.current);
                    if (!expiredRef.current) {
                        expiredRef.current = true;
                        if (onExpireRef.current) onExpireRef.current();
                    }
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(intervalRef.current);
    }, [timeRemaining]);

    return { timeRemaining, setTimeRemaining };
}