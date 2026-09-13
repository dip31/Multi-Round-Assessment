/**
 * Role-aware navigation config for the dashboard shell.
 *
 * ROLE SOURCING: the app has no role concept in auth today — the JWT carries
 * only a binary `is_admin`. Each dashboard page therefore hardcodes its own
 * `role` prop and the shell reads its nav from this map. When a real
 * `useRole()` lands, only the page-level prop needs to change.
 *
 * Icons are lucide-react component names, resolved in the Sidebar.
 */

import {
  Award,
  BarChart3,
  BookOpen,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Settings,
  Target,
  TrendingUp,
  UserCircle,
  Users,
} from 'lucide-react';

export const dashboardNavigation = {
  student: [
    { label: 'Overview', to: '/student/dashboard', icon: LayoutDashboard, end: true },
    { label: 'Assessments', to: '/student/dashboard#assessments', icon: ClipboardList },
    { label: 'My Progress', to: '/student/dashboard#progress', icon: TrendingUp },
    { label: 'Practice', to: '/student/dashboard#practice', icon: BookOpen },
    { label: 'Upcoming', to: '/student/dashboard#upcoming', icon: CalendarDays },
    { label: 'Resume', to: '/resume-upload', icon: FileText },
    { label: 'Profile', to: '/profile', icon: UserCircle },
  ],
  faculty: [
    { label: 'Overview', to: '/faculty/dashboard', icon: LayoutDashboard, end: true },
    { label: 'My Students', to: '/faculty/dashboard#students', icon: Users },
    { label: 'Cohort Analytics', to: '/faculty/dashboard#analytics', icon: BarChart3 },
    { label: 'Interventions', to: '/faculty/dashboard#interventions', icon: Target },
    { label: 'Assessments', to: '/faculty/dashboard#assessments', icon: ClipboardList },
    { label: 'Reports', to: '/faculty/dashboard#reports', icon: FileText },
  ],
  tpo: [
    { label: 'Overview', to: '/tpo/dashboard', icon: LayoutDashboard, end: true },
    { label: 'Placement Pipeline', to: '/tpo/dashboard#pipeline', icon: Briefcase },
    { label: 'Companies', to: '/tpo/dashboard#companies', icon: Building2 },
    { label: 'Candidates', to: '/tpo/dashboard#candidates', icon: Users },
    { label: 'Departments', to: '/tpo/dashboard#departments', icon: GraduationCap },
    { label: 'Offers', to: '/tpo/dashboard#offers', icon: Award },
    { label: 'Reports', to: '/tpo/dashboard#reports', icon: FileText },
  ],
};

/** Human-readable labels for the shell header and the demo role switcher. */
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

export function getNavForRole(role) {
  return dashboardNavigation[role] ?? [];
}

export default dashboardNavigation;
