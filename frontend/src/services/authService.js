import api from './api';

const USER_NAME_MAP_KEY = 'user_name_map';

const readUserNameMap = () => {
    try {
        const raw = localStorage.getItem(USER_NAME_MAP_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch {
        return {};
    }
};

const writeUserNameMap = (map) => {
    localStorage.setItem(USER_NAME_MAP_KEY, JSON.stringify(map));
};

export const registerUser = async (name, email, password) => {
    const response = await api.post('/auth/register', { name, email, password });

    // Persist mapping so future logins can resolve display name from email.
    const normalizedEmail = email.trim().toLowerCase();
    const existingMap = readUserNameMap();
    existingMap[normalizedEmail] = name.trim();
    writeUserNameMap(existingMap);

    return response.data;
};

export const loginUser = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    
    // Store the access token first so /auth/me can use it via interceptor.
    if (response.data.access_token) {
        const normalizedEmail = email.trim().toLowerCase();
        const userNameMap = readUserNameMap();
        const resolvedName = userNameMap[normalizedEmail] || email.split('@')[0] || 'Candidate';

        localStorage.setItem('access_token', response.data.access_token);

        try {
            const meResponse = await api.get('/auth/me');
            const me = meResponse.data;

            const finalName = me?.name || resolvedName;
            const finalEmail = (me?.email || normalizedEmail).toLowerCase();

            localStorage.setItem('user_email', finalEmail);
            localStorage.setItem('email', finalEmail);
            localStorage.setItem('user_name', finalName);
            localStorage.setItem('full_name', finalName);
            localStorage.setItem('user', JSON.stringify(me));

            const existingMap = readUserNameMap();
            existingMap[finalEmail] = finalName;
            writeUserNameMap(existingMap);
        } catch {
            // Fallback when /auth/me is temporarily unavailable.
            localStorage.setItem('user_email', normalizedEmail);
            localStorage.setItem('email', normalizedEmail);
            localStorage.setItem('user_name', resolvedName);
            localStorage.setItem('full_name', resolvedName);
            localStorage.setItem('user', JSON.stringify({ name: resolvedName, email: normalizedEmail }));
        }
    }
    
    return response.data;
};
