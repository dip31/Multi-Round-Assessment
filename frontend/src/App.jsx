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
import InterviewReport from './pages/InterviewReport';
import LandingPage from './pages/LandingPage';
import Analytics from './pages/Analytics';
import AdminLogin from './pages/AdminLogin';
import AdminAnalyticsDashboard from './pages/AdminAnalyticsDashboard';
import AdminCandidateReports from './pages/AdminCandidateReports';
import AdminReview from './pages/AdminReview';
import AdminPools from './pages/AdminPools';
import AdminProctoringDashboard from './pages/AdminProctoringDashboard';
import AdminRoute from './components/AdminRoute';
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
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
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
          path="/instructions"
          element={
            <PrivateRoute>
              <Instructions />
            </PrivateRoute>
          }
        />
        <Route
          path="/aptitude"
          element={
            <PrivateRoute>
              <ErrorBoundary>
                <AptitudeTest />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route
          path="/result"
          element={
            <PrivateRoute>
              <ResultPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/resume-upload"
          element={
            <PrivateRoute>
              <ResumeUpload />
            </PrivateRoute>
          }
        />
        <Route
          path="/interview"
          element={
            <PrivateRoute>
              <HumanLikeInterview />
            </PrivateRoute>
          }
        />
        <Route
          path="/interview/report/:interviewId"
          element={
            <PrivateRoute>
              <InterviewReport />
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
