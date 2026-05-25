import api from './api';

export const getNextQuestion = async () => {
    console.log('🔍 DEBUG: Calling getNextQuestion API...');
    try {
        const response = await api.get('/aptitude/next-question');
        console.log('🔍 DEBUG: API Response:', response);
        return response.data;
    } catch (error) {
        console.error('🔍 DEBUG: API Error:', error);
        throw error;
    }
};

export const submitAnswer = async (questionId, selectedOption, responseTime) => {
    const response = await api.post('/aptitude/submit-answer', {
        question_id: questionId,
        selected_option: selectedOption,
        response_time: responseTime,
    });
    return response.data;
};

export const getResult = async () => {
    const response = await api.get('/aptitude/result');
    return response.data;
};
