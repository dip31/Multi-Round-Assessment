/**
 * Advanced Proctoring Service for AI-Based Online Proctoring System
 * 
 * Handles API communication for advanced proctoring events,
 * violation analysis, and risk assessment.
 */

import api from './api';

export const advancedProctoringService = {
  async logEvent(eventData) {
    const response = await api.post('/advanced-proctoring/log-event', eventData);
    return response.data;
  },

  async getSessionSummary(sessionId) {
    const response = await api.get(`/advanced-proctoring/session/${sessionId}/summary`);
    return response.data;
  },

  async getHighRiskSessions(threshold = 0.7, limit = 50) {
    const response = await api.get('/advanced-proctoring/high-risk-sessions', {
      params: { risk_threshold: threshold, limit },
    });
    return response.data;
  },

  async checkViolationThresholds(sessionId) {
    const response = await api.get(`/advanced-proctoring/session/${sessionId}/violations`);
    return response.data;
  },

  async getSupportedEventTypes() {
    const response = await api.get('/advanced-proctoring/event-types');
    return response.data;
  },
};

export default advancedProctoringService;
