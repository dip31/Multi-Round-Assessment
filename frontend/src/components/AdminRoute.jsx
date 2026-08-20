import { Navigate } from 'react-router-dom';

const parseJwt = (token) => {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
};

const AdminRoute = ({ children }) => {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    return <Navigate to="/admin/login" replace />;
  }

  const decoded = parseJwt(token);
  if (!decoded || !decoded.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

export default AdminRoute;
