import api from './api';

export const logProctorEvent = async (sessionId, eventType, metadata = {}) => {
    try {
        const response = await api.post('/proctoring/log-event', {
            session_id: sessionId,
            event_type: eventType,
            event_metadata: metadata,
        });
        return response.data;
    } catch (error) {
        console.error('Failed to log proctoring event:', error);
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
