import api from './api';

export const startSession = async () => {
    const response = await api.post('/session/start');
    return response.data;
};

export const getSessionStatus = async () => {
    console.log('🔍 DEBUG: Calling getSessionStatus...');
    try {
        const response = await api.get('/session/status');
        console.log('🔍 DEBUG: Session status response:', response);
        return response.data;
    } catch (error) {
        console.error('🔍 DEBUG: Session status error:', error);
        throw error;
    }
};

export const completeSession = async () => {
    const response = await api.post('/session/complete');
    return response.data;
};
