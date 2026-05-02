import api from './api';

export const fetchAdminQuestions = async (params) => {
    const response = await api.get('/admin/questions', { params });
    return response.data;
};

export const fetchAdminQuestionById = async (questionId) => {
    const response = await api.get(`/admin/questions/${questionId}`);
    return response.data;
};

export const updateAdminQuestionStatus = async (questionId, status) => {
    const response = await api.put(`/admin/questions/${questionId}/status`, { status });
    return response.data;
};

export const saveAdminQuestionFeedback = async (questionId, payload) => {
    const response = await api.post(`/admin/questions/${questionId}/feedback`, payload);
    return response.data;
};
