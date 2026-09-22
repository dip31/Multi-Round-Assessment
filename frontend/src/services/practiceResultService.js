import api from './api';

export const getPracticeRoundResult = async (sessionId, roundId) => {
    const response = await api.get(`/practice/session/${sessionId}/round/${roundId}/result`);
    return response.data;
};

export const getPracticeRoundReview = async (sessionId, roundId) => {
    const response = await api.get(`/practice/session/${sessionId}/round/${roundId}/review`);
    return response.data;
};

export const getPracticeHistory = async () => {
    const response = await api.get('/practice/history');
    return response.data;
};
