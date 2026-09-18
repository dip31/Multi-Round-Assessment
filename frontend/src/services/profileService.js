import api from './api';

export const getProfile = async () => {
    const response = await api.get('/profile/me');
    return response.data;
};

export const getStudentProfile = async () => {
    const response = await api.get('/profile/student/me');
    return response.data;
};

export const updateStudentProfile = async (payload) => {
    const response = await api.put('/profile/student/me', payload);
    return response.data;
};

export default {
    getProfile,
    getStudentProfile,
    updateStudentProfile,
};
