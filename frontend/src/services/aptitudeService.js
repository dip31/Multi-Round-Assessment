import api from './api';

export const getNextQuestion = async (practiceType = null, subject = null, topic = null) => {
    try {
        const params = {};
        if (practiceType) params.practice_type = practiceType;
        if (subject && subject !== 'all') params.subject = subject;
        if (topic) params.topic = topic;

        const response = await api.get('/aptitude/next-question', { params });
        return response.data;
    } catch (error) {
        console.error('API Error in getNextQuestion:', error);
        throw error;
    }
};

export const submitAnswer = async (questionId, selectedOption, responseTime, practiceType = null, subject = null) => {
    const payload = {
        question_id: questionId,
        selected_option: selectedOption,
        response_time: responseTime,
    };
    if (practiceType) payload.practice_type = practiceType;
    if (subject && subject !== 'all') payload.subject = subject;

    const response = await api.post('/aptitude/submit-answer', payload);
    return response.data;
};

export const getResult = async () => {
    const response = await api.get('/aptitude/result');
    return response.data;
};
