import { useState, useEffect, useRef } from 'react';

export function useTimer(initialSeconds, onExpire) {
    const [timeRemaining, setTimeRemaining] = useState(initialSeconds);
    const intervalRef = useRef(null);
    const onExpireRef = useRef(onExpire);

    useEffect(() => {
        onExpireRef.current = onExpire;
    }, [onExpire]);

    useEffect(() => {
        setTimeRemaining(initialSeconds);
    }, [initialSeconds]);

    useEffect(() => {
        // Clear any existing interval
        if (intervalRef.current) clearInterval(intervalRef.current);

        if (timeRemaining <= 0) {
            if (onExpireRef.current) onExpireRef.current();
            return;
        }

        intervalRef.current = setInterval(() => {
            setTimeRemaining((prev) => {
                if (prev <= 1) {
                    clearInterval(intervalRef.current);
                    if (onExpireRef.current) onExpireRef.current();
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(intervalRef.current);
    }, [timeRemaining]); // Restart if manually set

    return { timeRemaining };
}
