import api from './api';

const ROLE_KEY = 'user_role';

const ALIASES = {
  candidate: 'student',
  teacher: 'faculty',
  professor: 'faculty',
  staff: 'faculty',
  tpo_officer: 'tpo',
  placement_officer: 'tpo',
  placement: 'tpo',
};

export function normalizeRole(role) {
  const normalized = String(role || '').trim().toLowerCase();
  const resolved = ALIASES[normalized] || normalized;
  return ['student', 'faculty', 'tpo', 'admin'].includes(resolved) ? resolved : null;
}

export function getCachedRole() {
  return normalizeRole(localStorage.getItem(ROLE_KEY));
}

export function homeForRole(role) {
  return {
    student: '/student/dashboard',
    faculty: '/faculty/dashboard',
    tpo: '/tpo/dashboard',
    admin: '/admin/dashboard',
  }[normalizeRole(role)] || '/login';
}

export async function resolveRole({ force = false } = {}) {
  if (!force) {
    const cached = getCachedRole();
    if (cached) return cached;
  }
  const response = await api.get('/auth/me', { skipAuthRedirect: true });
  const role = normalizeRole(response.data?.role);
  if (role) localStorage.setItem(ROLE_KEY, role);
  return role;
}

export function clearCachedRole() {
  localStorage.removeItem(ROLE_KEY);
}
