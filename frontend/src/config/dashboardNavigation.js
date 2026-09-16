export const roleMeta = {
  student: {
    label: 'Student',
    home: '/student/dashboard',
    searchPlaceholder: 'Search assessments, practice sets, reports…',
  },
  faculty: {
    label: 'Faculty',
    home: '/faculty/dashboard',
    searchPlaceholder: 'Search students, cohorts, reports…',
  },
  tpo: {
    label: 'TPO',
    home: '/tpo/dashboard',
    searchPlaceholder: 'Search candidates, companies, drives…',
  },
};

export const roleOrder = ['student', 'faculty', 'tpo'];

export const dashboardNavigation = {
  student: [{ label: 'Overview', to: '/student/dashboard' }],
  faculty: [{ label: 'Overview', to: '/faculty/dashboard' }],
  tpo: [{ label: 'Overview', to: '/tpo/dashboard' }],
};

export function getNavForRole(role) {
  return dashboardNavigation[role] || [];
}

export default dashboardNavigation;
