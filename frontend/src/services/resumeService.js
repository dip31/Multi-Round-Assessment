import api from './api';

export const getResumes = async () => {
    const response = await api.get('/profile/resumes');
    return response.data;
};

export const uploadResume = async (formData) => {
    const response = await api.post('/profile/resumes', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const deleteResume = async (resumeId) => {
    const response = await api.delete(`/profile/resumes/${resumeId}`);
    return response.data;
};

export const viewResumeFile = async (resumeId) => {
    try {
        const response = await api.get(`/profile/resumes/${resumeId}/file`, {
            responseType: 'blob',
        });
        const file = new Blob([response.data], { type: 'application/pdf' });
        const fileURL = URL.createObjectURL(file);
        window.open(fileURL, '_blank');
        setTimeout(() => URL.revokeObjectURL(fileURL), 60000);
    } catch (err) {
        console.error('Failed to load resume blob, opening direct URL:', err);
        window.open(getResumeFileUrl(resumeId), '_blank');
    }
};

export const getResumeFileUrl = (resumeId) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL
        ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
        : '/api/v1';
    const token = localStorage.getItem('token') || localStorage.getItem('access_token');
    return `${baseUrl}/profile/resumes/${resumeId}/file${token ? `?token=${encodeURIComponent(token)}` : ''}`;
};

export default {
    getResumes,
    uploadResume,
    deleteResume,
    getResumeFileUrl,
    viewResumeFile,
};
