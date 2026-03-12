import api from './api';

export const startSession = async () => {
    const response = await api.post('/session/start');
    return response.data;
};

export const getSessionStatus = async () => {
    const response = await api.get('/session/status');
    return response.data;
};
