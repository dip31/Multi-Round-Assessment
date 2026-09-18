import api from './api';

export const getAnalytics = async () => {
    const response = await api.get('/report/analytics');
    return response.data;
};

export const getStudentAnalytics = async () => {
    const response = await api.get('/report/student-analytics');
    return response.data;
};

export default {
    getAnalytics,
    getStudentAnalytics,
};
