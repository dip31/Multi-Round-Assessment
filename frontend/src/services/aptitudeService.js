import api from './api';

export const getNextQuestion = async () => {
    const response = await api.get('/aptitude/next-question');
    return response.data;
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
