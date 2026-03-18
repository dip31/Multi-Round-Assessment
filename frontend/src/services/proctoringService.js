import api from './api';

export const logProctorEvent = async (sessionId, eventType, metadata = {}) => {
    try {
        // Only log if we have a valid session ID
        if (!sessionId) {
            console.warn('No session ID provided for proctoring event');
            return null;
        }

        const response = await api.post('/proctoring/log-event', {
            session_id: sessionId,
            event_type: eventType,
            event_metadata: {
                ...metadata,
                timestamp: Date.now(),
                browser_info: navigator.userAgent,
            },
        });
        return response.data;
    } catch (error) {
        // Don't log proctoring errors to avoid spamming console
        if (error.response?.status === 422) {
            // 422 errors are expected during development
            console.debug('Proctoring event validation failed:', error.response?.data);
        } else if (error.response?.status === 404) {
            // 404 errors might mean the session doesn't exist
            console.debug('Proctoring session not found:', error.response?.data);
        } else {
            console.error('Failed to log proctoring event:', error);
        }
        // Don't throw error to avoid interrupting test flow
        return null;
    }
};

export const getProctoringEvents = async (sessionId) => {
    try {
        const response = await api.get(`/proctoring/events/${sessionId}`);
        return response.data;
    } catch (error) {
        console.error('Failed to fetch proctoring events:', error);
        return [];
    }
};
