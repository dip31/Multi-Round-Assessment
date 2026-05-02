/**
 * Admin Proctoring Dashboard
 * 
 * Comprehensive dashboard for monitoring proctoring violations,
 * risk assessment, and candidate behavior analysis.
 */

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  AlertTriangle, 
  Activity, 
  Eye,
  TrendingUp,
  Calendar,
  Filter,
  Download,
  Search
} from 'lucide-react';
import advancedProctoringService from '../services/advancedProctoringService';
import AdminLayout from '../components/AdminLayout';

const AdminProctoringDashboard = () => {
  const [sessions, setSessions] = useState([]);
  const [highRiskSessions, setHighRiskSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [riskThreshold, setRiskThreshold] = useState(0.7);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });

  // Load dashboard data
  useEffect(() => {
    loadDashboardData();
  }, [riskThreshold]);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      
      // Load high-risk sessions
      const highRiskData = await advancedProctoringService.getHighRiskSessions(riskThreshold, 50);
      setHighRiskSessions(highRiskData.sessions);
      
      // TODO: Load all sessions with pagination
      // const allSessionsData = await proctoringService.getAllSessions();
      // setSessions(allSessionsData);
      
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load session details
  const loadSessionDetails = async (sessionId) => {
    try {
      const summary = await advancedProctoringService.getSessionSummary(sessionId);
      const violations = await advancedProctoringService.checkViolationThresholds(sessionId);
      
      setSelectedSession({
        ...summary,
        violations: violations,
      });
    } catch (error) {
      console.error('Failed to load session details:', error);
    }
  };

  // Get risk level color
  const getRiskLevelColor = (score) => {
    if (score < 0.3) return 'text-green-600 bg-green-100';
    if (score < 0.6) return 'text-yellow-600 bg-yellow-100';
    if (score < 0.8) return 'text-orange-600 bg-orange-100';
    return 'text-red-600 bg-red-100';
  };

  // Get violation icon
  const getViolationIcon = (eventType) => {
    const iconMap = {
      'MULTIPLE_PERSON_DETECTED': Users,
      'FACE_NOT_VISIBLE': Eye,
      'VOICE_ACTIVITY_DETECTED': Activity,
      'TAB_SWITCH': AlertTriangle,
      'PAGE_RELOAD': AlertTriangle,
      'CAMERA_PERMISSION_DENIED': AlertTriangle,
    };
    
    const Icon = iconMap[eventType] || AlertTriangle;
    return <Icon className="w-4 h-4" />;
  };

  // Format date
  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  // Export data
  const exportData = () => {
    const csvContent = [
      ['Session ID', 'Risk Score', 'Event Count', 'Violations', 'Last Activity'],
      ...highRiskSessions.map(session => [
        session.session_id,
        session.avg_risk_score.toFixed(3),
        session.event_count,
        Object.keys(session.violation_counts).join(';'),
        new Date().toISOString(),
      ])
    ].map(row => row.join(',')).join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `proctoring_report_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Proctoring Dashboard</h1>
          <p className="text-gray-600">Monitor candidate behavior and assessment integrity</p>
        </div>
        <button
          onClick={exportData}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center space-x-2"
        >
          <Download className="w-4 h-4" />
          <span>Export Report</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Sessions</p>
              <p className="text-2xl font-bold text-gray-900">{highRiskSessions.length}</p>
            </div>
            <Users className="w-8 h-8 text-blue-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">High Risk Sessions</p>
              <p className="text-2xl font-bold text-red-600">{highRiskSessions.length}</p>
            </div>
            <AlertTriangle className="w-8 h-8 text-red-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Violations</p>
              <p className="text-2xl font-bold text-gray-900">
                {highRiskSessions.reduce((sum, session) => sum + session.total_violations, 0)}
              </p>
            </div>
            <Activity className="w-8 h-8 text-orange-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Avg Risk Score</p>
              <p className="text-2xl font-bold text-gray-900">
                {highRiskSessions.length > 0 
                  ? (highRiskSessions.reduce((sum, session) => sum + session.avg_risk_score, 0) / highRiskSessions.length).toFixed(2)
                  : '0.00'
                }
              </p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-600" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Search className="w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <label className="text-sm text-gray-600">Risk Threshold:</label>
            <select
              value={riskThreshold}
              onChange={(e) => setRiskThreshold(parseFloat(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={0.5}>Medium (0.5)</option>
              <option value={0.7}>High (0.7)</option>
              <option value={0.8}>Critical (0.8)</option>
            </select>
          </div>
          
          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-gray-500" />
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-gray-500">to</span>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Sessions Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">High-Risk Sessions</h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Session ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Risk Score
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Events
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Violations
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {highRiskSessions.map((session) => (
                <tr key={session.session_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    #{session.session_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className={`px-2 py-1 rounded-full text-xs font-medium ${getRiskLevelColor(session.avg_risk_score)}`}>
                      {(session.avg_risk_score * 100).toFixed(1)}%
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {session.event_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(session.violation_counts).slice(0, 2).map(([type, count]) => (
                        <div key={type} className="flex items-center space-x-1 px-2 py-1 bg-gray-100 rounded text-xs">
                          {getViolationIcon(type)}
                          <span>{count}</span>
                        </div>
                      ))}
                      {Object.keys(session.violation_counts).length > 2 && (
                        <span className="text-xs text-gray-500">+{Object.keys(session.violation_counts).length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
                      Flagged
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button
                      onClick={() => loadSessionDetails(session.session_id)}
                      className="text-blue-600 hover:text-blue-900 mr-3"
                    >
                      View Details
                    </button>
                    <button className="text-gray-600 hover:text-gray-900">
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Session Details Modal */}
      {selectedSession && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto m-4">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Session #{selectedSession.session_id} Details</h2>
                <button
                  onClick={() => setSelectedSession(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            <div className="p-6 space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Total Events</p>
                  <p className="text-2xl font-bold text-gray-900">{selectedSession.total_events}</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Risk Score</p>
                  <p className="text-2xl font-bold text-red-600">{(selectedSession.risk_score * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-600">Violation Types</p>
                  <p className="text-2xl font-bold text-gray-900">{Object.keys(selectedSession.violation_counts).length}</p>
                </div>
              </div>
              
              {/* Violation Breakdown */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Violation Breakdown</h3>
                <div className="space-y-3">
                  {Object.entries(selectedSession.violation_counts).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className="text-gray-600">
                          {getViolationIcon(type)}
                        </div>
                        <span className="text-sm font-medium text-gray-900">{type}</span>
                      </div>
                      <span className="text-sm text-gray-600">{count} occurrences</span>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Recent Events */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Events</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {selectedSession.events.slice(0, 10).map((event) => (
                    <div key={event.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm text-gray-900">{event.event_type}</span>
                        <span className="text-xs text-gray-500">{formatDate(event.created_at)}</span>
                      </div>
                      <span className="text-xs text-gray-600">{Math.round(event.risk_score * 100)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
    </AdminLayout>
  );
};

export default AdminProctoringDashboard;
