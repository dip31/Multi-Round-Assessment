import { useState, useCallback } from 'react';
import { loginUser, registerUser } from '../services/authService';

export function useAuth() {
    const [token, setToken] = useState(localStorage.getItem('access_token'));

    const isAuthenticated = !!token;

    const login = useCallback(async (email, password) => {
        const data = await loginUser(email, password);
        localStorage.setItem('access_token', data.access_token);
        setToken(data.access_token);
        return data;
    }, []);

    const register = useCallback(async (name, email, password) => {
        const data = await registerUser(name, email, password);
        return data;
    }, []);

    const logout = useCallback(() => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        localStorage.removeItem('user_name');
        localStorage.removeItem('full_name');
        localStorage.removeItem('user_email');
        localStorage.removeItem('email');
        setToken(null);
    }, []);

    return { token, login, register, logout, isAuthenticated };
}
