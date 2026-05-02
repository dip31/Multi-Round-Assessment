import axios from 'axios';

// Use a single base URL strategy across the app:
// - If `VITE_API_BASE_URL` is set, use it (e.g. https://api.example.com)
// - Otherwise, use a relative URL so the Vite `/api` proxy can handle local dev
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
    ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
    : '/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor — attach JWT
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor — handle 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Do not redirect if the failure happened during login itself
            if (!error.config.url.includes('/auth/login')) {
                localStorage.removeItem('access_token');
                if (window.location.pathname.startsWith('/admin')) {
                    window.location.href = '/admin/login';
                } else {
                    window.location.href = '/login';
                }
            }
        }
        return Promise.reject(error);
    }
);

export default api;
