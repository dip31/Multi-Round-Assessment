import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';
import Login from './pages/Login';
import Register from './pages/Register';
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
import AdminLogin from './pages/AdminLogin';
import AdminAnalyticsDashboard from './pages/AdminAnalyticsDashboard';
import AdminCandidateReports from './pages/AdminCandidateReports';
import AdminReview from './pages/AdminReview';
import AdminPools from './pages/AdminPools';
import AdminProctoringDashboard from './pages/AdminProctoringDashboard';
<<<<<<< Updated upstream
=======
import StudentDashboard from './pages/StudentDashboard';
import FacultyDashboard from './pages/FacultyDashboard';
import TPODashboard from './pages/TPODashboard';
>>>>>>> Stashed changes
import AdminRoute from './components/AdminRoute';
import RoleRoute from './components/RoleRoute';
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
          element={<Navigate to="/student/dashboard" replace />}
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
          path="/coding"
          element={
            <PrivateRoute>
              <CodingRound />
            </PrivateRoute>
          }
        />
        <Route
          path="/coding/result"
          element={
            <PrivateRoute>
              <CodingResultPage />
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
<<<<<<< Updated upstream
=======
        {/* Role dashboards are the primary authenticated entry points.
            RoleRoute resolves the backend-authenticated role and prevents
            users from opening another role's dashboard. */}
        <Route
          path="/student/dashboard"
          element={
            <RoleRoute role="student">
              <ErrorBoundary>
                <StudentDashboard />
              </ErrorBoundary>
            </RoleRoute>
          }
        />
        <Route
          path="/faculty/dashboard"
          element={
            <RoleRoute role="faculty">
              <FacultyDashboard />
            </RoleRoute>
          }
        />
        <Route
          path="/tpo/dashboard"
          element={
            <RoleRoute role="tpo">
              <TPODashboard />
            </RoleRoute>
          }
        />
>>>>>>> Stashed changes
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
