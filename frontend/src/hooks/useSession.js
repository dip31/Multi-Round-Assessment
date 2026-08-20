import { useState, useCallback } from 'react';
import { startSession as startSessionApi, getSessionStatus as getStatusApi } from '../services/sessionService';

export function useSession() {
    const [session, setSession] = useState(null);

    const startSession = useCallback(async () => {
        const data = await startSessionApi();
        setSession(data);
        return data;
    }, []);

    const getSessionStatus = useCallback(async () => {
        const data = await getStatusApi();
        setSession(data);
        return data;
    }, []);

    return { session, startSession, getSessionStatus };
}
