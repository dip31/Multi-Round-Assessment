import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Profile from './pages/Profile';
import Instructions from './pages/Instructions';
import AptitudeTest from './pages/AptitudeTest';
import ResultPage from './pages/ResultPage';
import ResumeUpload from './pages/ResumeUpload';
import HumanLikeInterview from './pages/HumanLikeInterview';
import CodingRound from './pages/CodingRound';
import CodingResultPage from './pages/CodingResultPage';
import InterviewReport from './pages/InterviewReport';
import LandingPage from './pages/LandingPage';
import Analytics from './pages/Analytics';
import Portfolio from './pages/Portfolio';
import AdminLogin from './pages/AdminLogin';
import AdminAnalyticsDashboard from './pages/AdminAnalyticsDashboard';
import AdminCandidateReports from './pages/AdminCandidateReports';
import AdminReview from './pages/AdminReview';
import AdminPools from './pages/AdminPools';
import AdminProctoringDashboard from './pages/AdminProctoringDashboard';
import AdminRoute from './components/AdminRoute';
import RoleRoute from './components/RoleRoute';
import FacultyDashboard from './pages/FacultyDashboard';
import TPODashboard from './pages/TPODashboard';
import { ErrorBoundary } from './components/ErrorBoundary';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route 
          path="/admin/dashboard" 
          element={
            <AdminRoute>
              <AdminAnalyticsDashboard />
            </AdminRoute>
          } 
        />
        <Route 
          path="/admin/analytics" 
          element={
            <AdminRoute>
              <AdminCandidateReports />
            </AdminRoute>
          } 
        />
        <Route 
          path="/admin/review" 
          element={
            <AdminRoute>
              <AdminReview />
            </AdminRoute>
          } 
        />
        <Route 
          path="/admin/pools"
          element={
            <AdminRoute>
              <AdminPools />
            </AdminRoute>
          }
        />
        <Route 
          path="/admin/proctoring" 
          element={
            <AdminRoute>
              <AdminProctoringDashboard />
            </AdminRoute>
          } 
        />
        {/* Role-Based Dashboards */}
        <Route
          path="/dashboard"
          element={
            <RoleRoute allowedRoles={['student']}>
              <Dashboard />
            </RoleRoute>
          }
        />
        <Route
          path="/faculty/dashboard"
          element={
            <RoleRoute allowedRoles={['faculty', 'admin']}>
              <FacultyDashboard />
            </RoleRoute>
          }
        />
        <Route
          path="/tpo/dashboard"
          element={
            <RoleRoute allowedRoles={['tpo', 'admin']}>
              <TPODashboard />
            </RoleRoute>
          }
        />

        <Route
          path="/profile"
          element={
            <PrivateRoute>
              <Profile />
            </PrivateRoute>
          }
        />
        <Route
          path="/analytics"
          element={
            <PrivateRoute>
              <Analytics />
            </PrivateRoute>
          }
        />
        <Route
          path="/portfolio"
          element={
            <RoleRoute allowedRoles={['student']}>
              <Portfolio />
            </RoleRoute>
          }
        />
        <Route
          path="/instructions"
          element={
            <RoleRoute allowedRoles={['student']}>
              <Instructions />
            </RoleRoute>
          }
        />
        <Route
          path="/aptitude"
          element={
            <RoleRoute allowedRoles={['student']}>
              <ErrorBoundary>
                <AptitudeTest />
              </ErrorBoundary>
            </RoleRoute>
          }
        />
        <Route
          path="/coding"
          element={
            <RoleRoute allowedRoles={['student']}>
              <CodingRound />
            </RoleRoute>
          }
        />
        <Route
          path="/coding/result"
          element={
            <RoleRoute allowedRoles={['student']}>
              <CodingResultPage />
            </RoleRoute>
          }
        />
        <Route
          path="/result"
          element={
            <RoleRoute allowedRoles={['student']}>
              <ResultPage />
            </RoleRoute>
          }
        />
        <Route
          path="/resume-upload"
          element={
            <RoleRoute allowedRoles={['student']}>
              <ResumeUpload />
            </RoleRoute>
          }
        />
        <Route
          path="/interview"
          element={
            <RoleRoute allowedRoles={['student']}>
              <HumanLikeInterview />
            </RoleRoute>
          }
        />
        <Route
          path="/interview/report/:interviewId"
          element={
            <RoleRoute allowedRoles={['student', 'faculty', 'tpo', 'admin']}>
              <InterviewReport />
            </RoleRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
