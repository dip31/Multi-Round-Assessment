import api from './api';

export const getPortfolio = async () => {
    const response = await api.get('/portfolio/me');
    return response.data;
};

export const updatePortfolio = async (payload) => {
    const response = await api.put('/portfolio/me', payload);
    return response.data;
};

export const addProject = async (project) => {
    const response = await api.post('/portfolio/project', project);
    return response.data;
};

export const updateProject = async (id, project) => {
    const response = await api.put(`/portfolio/project/${id}`, project);
    return response.data;
};

export const deleteProject = async (id) => {
    const response = await api.delete(`/portfolio/project/${id}`);
    return response.data;
};

export const addCertification = async (cert) => {
    const response = await api.post('/portfolio/certification', cert);
    return response.data;
};

export const deleteCertification = async (id) => {
    const response = await api.delete(`/portfolio/certification/${id}`);
    return response.data;
};

export const addExperience = async (exp) => {
    const response = await api.post('/portfolio/experience', exp);
    return response.data;
};

export const deleteExperience = async (id) => {
    const response = await api.delete(`/portfolio/experience/${id}`);
    return response.data;
};

export const addAchievement = async (ach) => {
    const response = await api.post('/portfolio/achievement', ach);
    return response.data;
};

export const deleteAchievement = async (id) => {
    const response = await api.delete(`/portfolio/achievement/${id}`);
    return response.data;
};

export const addResearch = async (res) => {
    const response = await api.post('/portfolio/research', res);
    return response.data;
};

export const deleteResearch = async (id) => {
    const response = await api.delete(`/portfolio/research/${id}`);
    return response.data;
};

export const addPatent = async (patent) => {
    const response = await api.post('/portfolio/patent', patent);
    return response.data;
};

export const deletePatent = async (id) => {
    const response = await api.delete(`/portfolio/patent/${id}`);
    return response.data;
};

export const updateExternalProfiles = async (links) => {
    const response = await api.put('/portfolio/external-profiles', links);
    return response.data;
};
