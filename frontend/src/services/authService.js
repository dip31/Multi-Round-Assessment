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

export const registerUser = async (name, email, password, role = 'student') => {
    const response = await api.post('/auth/register', { name, email, password, role });

    // Persist mapping so future logins can resolve display name from email.
    const normalizedEmail = email.trim().toLowerCase();
    const existingMap = readUserNameMap();
    existingMap[normalizedEmail] = name.trim();
    writeUserNameMap(existingMap);

    return response.data;
};

export const loginUser = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    
    if (response.data.access_token) {
        const normalizedEmail = email.trim().toLowerCase();
        const userNameMap = readUserNameMap();
        const apiUser = response.data.user;
        const role = response.data.role || apiUser?.role || 'student';
        const resolvedName = apiUser?.name || userNameMap[normalizedEmail] || email.split('@')[0] || 'User';

        const userData = {
            id: apiUser?.id,
            name: resolvedName,
            email: normalizedEmail,
            role: role,
        };

        localStorage.setItem('access_token', response.data.access_token);
        localStorage.setItem('user_email', normalizedEmail);
        localStorage.setItem('email', normalizedEmail);
        localStorage.setItem('user_name', resolvedName);
        localStorage.setItem('full_name', resolvedName);
        localStorage.setItem('role', role);
        localStorage.setItem('user', JSON.stringify(userData));

        const existingMap = readUserNameMap();
        existingMap[normalizedEmail] = resolvedName;
        writeUserNameMap(existingMap);

        // Fetch /auth/me to refresh full details if needed
        api.get('/auth/me', { skipAuthRedirect: true })
            .then((meResponse) => {
                if (meResponse.data) {
                    const me = meResponse.data;
                    const mergedUser = { ...userData, ...me };
                    localStorage.setItem('user', JSON.stringify(mergedUser));
                    localStorage.setItem('role', me.role || role);
                }
            })
            .catch(() => {});

        return { ...response.data, user: userData, role };
    }
    
    return response.data;
};
