import api from './api';

/**
 * Portfolio Builder Assessment API Service
 * 
 * Orchestrates the 6-stage assessment journey:
 * 1. Aptitude & Logical Reasoning
 * 2. Technical Knowledge MCQ
 * 3. Combined Aptitude & Technical MCQ
 * 4. DSA Coding Assessment
 * 5. Resume-Based Interview
 * 6. Consolidated Competency Results
 */

// ─── Portfolio Builder Attempt ────────────────────────────────────────

export const getOrInitializePortfolioBuilder = async () => {
    const response = await api.get('/portfolio-builder');
    return response.data;
};

export const getPortfolioBuilderProgress = async () => {
    const response = await api.get('/portfolio-builder/progress');
    return response.data;
};

// ─── Stage Management ────────────────────────────────────────────────

export const startStage = async (stageKey) => {
    const response = await api.post('/portfolio-builder/stage/start', { stage_key: stageKey });
    return response.data;
};

export const completeStage = async (stageKey) => {
    const response = await api.post('/portfolio-builder/stage/complete', { stage_key: stageKey });
    return response.data;
};

export const getStageResults = async (stageKey) => {
    const response = await api.get(`/portfolio-builder/stage/${stageKey}/results`);
    return response.data;
};

// ─── Consolidated Results ────────────────────────────────────────────

export const getConsolidatedResults = async () => {
    const response = await api.get('/portfolio-builder/results');
    return response.data;
};

// ─── Stage Constants ─────────────────────────────────────────────────

export const STAGE_KEYS = {
    APTITUDE: 'APTITUDE',
    TECHNICAL_MCQ: 'TECHNICAL_MCQ',
    COMBINED_MCQ: 'COMBINED_MCQ',
    DSA_CODING: 'DSA_CODING',
    RESUME_INTERVIEW: 'RESUME_INTERVIEW',
    COMPETENCY_RESULTS: 'COMPETENCY_RESULTS',
};

export const STAGE_ORDER = [
    STAGE_KEYS.APTITUDE,
    STAGE_KEYS.TECHNICAL_MCQ,
    STAGE_KEYS.COMBINED_MCQ,
    STAGE_KEYS.DSA_CODING,
    STAGE_KEYS.RESUME_INTERVIEW,
    STAGE_KEYS.COMPETENCY_RESULTS,
];

export const STAGE_DISPLAY = {
    [STAGE_KEYS.APTITUDE]: {
        number: 1,
        title: 'Aptitude & Logical Reasoning',
        description: 'Quantitative aptitude, logical reasoning, and verbal ability assessment',
        duration_minutes: 30,
        icon: '🧮',
    },
    [STAGE_KEYS.TECHNICAL_MCQ]: {
        number: 2,
        title: 'Technical Knowledge Assessment',
        description: 'Core CS subjects: OS, DBMS, Networks, OOP, DSA fundamentals',
        duration_minutes: 30,
        icon: '💻',
    },
    [STAGE_KEYS.COMBINED_MCQ]: {
        number: 3,
        title: 'Combined Aptitude & Technical Assessment',
        description: 'Integrated assessment combining aptitude and technical questions',
        duration_minutes: 45,
        icon: '🔄',
    },
    [STAGE_KEYS.DSA_CODING]: {
        number: 4,
        title: 'DSA Coding Assessment',
        description: 'Data Structures & Algorithms coding challenges with automated evaluation',
        duration_minutes: 60,
        icon: '👨‍💻',
    },
    [STAGE_KEYS.RESUME_INTERVIEW]: {
        number: 5,
        title: 'Resume-Based Interview',
        description: 'AI-powered technical interview grounded in your resume and projects',
        duration_minutes: 30,
        icon: '🎙️',
    },
    [STAGE_KEYS.COMPETENCY_RESULTS]: {
        number: 6,
        title: 'Consolidated Competency Results',
        description: 'Evidence-backed competency profile with strengths, gaps, and recommendations',
        duration_minutes: 0,
        icon: '📊',
    },
};

export const STAGE_STATUS = {
    LOCKED: 'LOCKED',
    AVAILABLE: 'AVAILABLE',
    IN_PROGRESS: 'IN_PROGRESS',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
};

// ─── Helper Functions ────────────────────────────────────────────────

export const getStageDisplay = (stageKey) => {
    return STAGE_DISPLAY[stageKey] || { number: 0, title: stageKey, description: '', duration_minutes: 0, icon: '❓' };
};

export const getStageActionText = (status) => {
    switch (status) {
        case STAGE_STATUS.AVAILABLE:
            return 'Start';
        case STAGE_STATUS.IN_PROGRESS:
            return 'Resume';
        case STAGE_STATUS.COMPLETED:
            return 'View Results';
        case STAGE_STATUS.LOCKED:
            return 'Locked';
        case STAGE_STATUS.FAILED:
            return 'Retry';
        default:
            return 'Unknown';
    }
};

export const getStageActionVariant = (status) => {
    switch (status) {
        case STAGE_STATUS.AVAILABLE:
            return 'primary';
        case STAGE_STATUS.IN_PROGRESS:
            return 'secondary';
        case STAGE_STATUS.COMPLETED:
            return 'success';
        case STAGE_STATUS.LOCKED:
            return 'ghost';
        case STAGE_STATUS.FAILED:
            return 'danger';
        default:
            return 'default';
    }
};

export const getStageStatusColor = (status) => {
    switch (status) {
        case STAGE_STATUS.COMPLETED:
            return 'text-green-600 bg-green-100';
        case STAGE_STATUS.IN_PROGRESS:
            return 'text-blue-600 bg-blue-100';
        case STAGE_STATUS.AVAILABLE:
            return 'text-yellow-600 bg-yellow-100';
        case STAGE_STATUS.LOCKED:
            return 'text-gray-600 bg-gray-100';
        case STAGE_STATUS.FAILED:
            return 'text-red-600 bg-red-100';
        default:
            return 'text-gray-600 bg-gray-100';
    }
};