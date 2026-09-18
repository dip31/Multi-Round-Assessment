import { Navigate } from 'react-router-dom';

export default function RoleRoute({ children, allowedRoles = [] }) {
    const token = localStorage.getItem('access_token');

    if (!token) {
        return <Navigate to="/login" replace />;
    }

    if (allowedRoles.length === 0) {
        return children;
    }

    let role = localStorage.getItem('role');
    if (!role) {
        try {
            const storedUser = localStorage.getItem('user');
            if (storedUser) {
                const user = JSON.parse(storedUser);
                role = user.role;
            }
        } catch (e) {
            // fallback
        }
    }

    role = role || 'student';

    if (!allowedRoles.includes(role)) {
        if (role === 'faculty') {
            return <Navigate to="/faculty/dashboard" replace />;
        }
        if (role === 'tpo') {
            return <Navigate to="/tpo/dashboard" replace />;
        }
        if (role === 'admin') {
            return <Navigate to="/admin/dashboard" replace />;
        }
        return <Navigate to="/dashboard" replace />;
    }

    return children;
}
