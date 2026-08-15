import api from './api';

export async function getProblems() {
  const resp = await api.get('/coding/problems');
  return resp.data;
}

export async function startRound() {
  const resp = await api.post('/coding/start');
  return resp.data;
}

export async function runCode(payload) {
  const resp = await api.post('/coding/run', payload);
  return resp.data;
}

export async function submitCode(payload) {
  const resp = await api.post('/coding/submit', payload);
  return resp.data;
}

export async function getSubmission(id) {
  const resp = await api.get(`/coding/submission/${id}`);
  return resp.data;
}

export async function finishRound() {
  const resp = await api.post('/coding/finish');
  return resp.data;
}
