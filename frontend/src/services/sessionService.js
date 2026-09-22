import api from './api';

export const startSession = async () => {
    const response = await api.post('/session/start');
    return response.data;
};

export const getSessionStatus = async () => {
    console.log('🔍 DEBUG: Calling getSessionStatus...');
    try {
        const response = await api.get(`/session/status?t=${Date.now()}`);
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

export const startCodingAfterAptitude = async () => {
    const response = await api.post('/coding/start-after-aptitude');
    return response.data;
};

export const startFreshSession = async () => {
    const response = await api.post('/session/fresh');
    return response.data;
};

export const startPractice = async (roundType) => {
    const response = await api.post('/practice/start', { round_type: roundType });
    return response.data;
};
