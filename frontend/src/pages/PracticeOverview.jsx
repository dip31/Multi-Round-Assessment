import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import StudentModeLayout from '../components/StudentModeLayout';
import { startPractice } from '../services/sessionService';
import api from '../services/api';
import { formatAvailabilityDate, getAssignmentAvailabilityMessage } from '../utils/assignedAssessmentAvailability';

export default function PracticeOverview() {
    const navigate = useNavigate();
    const location = useLocation();
    const [starting, setStarting] = useState(null);
    const [assignedAssessments, setAssignedAssessments] = useState([]);
    const [assignmentsLoading, setAssignmentsLoading] = useState(true);
    const [assignmentsError, setAssignmentsError] = useState(null);

    const loadAssignments = async () => {
        setAssignmentsLoading(true);
        setAssignmentsError(null);
        try {
            const response = await api.get('/student/practice-assignments');
            setAssignedAssessments(Array.isArray(response.data) ? response.data : []);
        } catch (error) {
            setAssignmentsError(error?.response?.status === 403
                ? 'Assigned practice assessments are available to student accounts only.'
                : 'Assigned assessments could not be loaded. Retry to check again.');
        } finally {
            setAssignmentsLoading(false);
        }
    };
    useEffect(() => { loadAssignments(); }, []);

    // Detect which practice type is selected from URL
    const getSelectedPracticeType = () => {
        const path = location.pathname;
        if (path === '/practice/mcq') return 'mcq';
        if (path === '/practice/technical-mcq') return 'technical';
        if (path === '/practice/combined-mcq') return 'combined';
        if (path === '/practice/coding') return 'coding';
        if (path === '/practice/interview') return 'interview';
        return null; // Overview mode
    };

    const selectedType = getSelectedPracticeType();

    const handleStartPractice = async (practiceType, subject = null, assignment = null, assignedRound = null) => {
        const startKey = assignment ? `${assignment.assignment_id}-${assignedRound.id}` : practiceType;
        setStarting(startKey);
        try {
            const config = { practice_type: practiceType, subject: subject };
            localStorage.setItem('edi5_practice_config', JSON.stringify(config));

            let roundType = "aptitude";
            if (practiceType === 'coding') roundType = "coding";
            if (practiceType === 'interview') roundType = "interview";

            if (assignment && assignedRound) {
                roundType = assignedRound.round_type;
                await startPractice(roundType, assignedRound.practice_type, {
                    assignment_id: assignment.assignment_id,
                    assessment_round_id: assignedRound.id,
                });
            } else {
                await startPractice(roundType, practiceType);
            }

            // Navigate to appropriate assessment page
            if (practiceType === 'mcq' || practiceType === 'technical' || practiceType === 'combined') {
                navigate('/aptitude', { state: { facultyAssignment: Boolean(assignment) } });
            } else if (practiceType === 'coding') {
                navigate('/coding');
            } else if (practiceType === 'interview') {
                navigate('/resume-upload');
            }
        } catch (error) {
            console.error('Failed to start practice:', error);
            if (error.response && error.response.status === 409) {
                alert(error.response.data.detail || 'An active practice session is already in progress. Please complete it before starting a new one.');
            } else {
                alert('Failed to start practice session. Please try again.');
            }
        } finally {
            setStarting(null);
        }
    };

    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-6 py-8">
                <div className="mb-8">
                    <h1 className="text-3xl font-black text-slate-900 tracking-tight mb-2">Practice Mode</h1>
                    <p className="text-slate-600 text-sm">
                        {selectedType
                            ? `Practice ${
                                selectedType === 'mcq'
                                    ? 'MCQ'
                                    : selectedType === 'technical'
                                    ? 'Technical MCQ'
                                    : selectedType === 'combined'
                                    ? 'Combined MCQ'
                                    : selectedType === 'coding'
                                    ? 'Coding Challenges'
                                    : 'Interview'
                            } independently. Each practice session is separate and repeatable.`
                            : 'Practice independently across different assessment types. Each practice session is separate and repeatable.'}
                    </p>
                </div>

                {!selectedType && <section aria-labelledby="assigned-practice-title" className="mb-8 rounded-2xl border border-indigo-100 bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 id="assigned-practice-title" className="text-lg font-bold text-slate-900">Assigned Practice Assessments</h2><p className="mt-1 text-sm text-slate-600">Complete assigned rounds in order. Independent practice remains available below.</p></div><button type="button" onClick={loadAssignments} disabled={assignmentsLoading} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50">Refresh</button></div>
                    {assignmentsError ? <div role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{assignmentsError}<button type="button" onClick={loadAssignments} className="ml-2 font-semibold underline">Retry</button></div> : assignmentsLoading ? <p className="mt-4 text-sm text-slate-500">Loading assigned assessments…</p> : !assignedAssessments.length ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">You have no assigned practice assessments.</p> : <div className="mt-4 space-y-3">{assignedAssessments.map((assignment) => <article key={assignment.assignment_id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-slate-900">{assignment.title}</h3>{assignment.description && <p className="mt-1 text-sm text-slate-600">{assignment.description}</p>}{assignment.instructions && <p className="mt-2 text-xs text-slate-600"><span className="font-semibold">Instructions:</span> {assignment.instructions}</p>}<p className="mt-2 text-xs text-slate-500">{assignment.availability_start ? formatAvailabilityDate(assignment.availability_start) : 'Available now'}{assignment.availability_end ? ` – ${formatAvailabilityDate(assignment.availability_end)}` : ''}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${assignment.status === 'completed' ? 'bg-emerald-50 text-emerald-800' : assignment.status === 'in_progress' ? 'bg-blue-50 text-blue-800' : 'bg-slate-100 text-slate-700'}`}>{assignment.status.replaceAll('_', ' ')}</span></div><ol className="mt-3 flex flex-wrap gap-2">{assignment.rounds.map((round) => <li key={round.id} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">{round.sequence}. {round.round_type === 'aptitude' ? `Aptitude · ${round.practice_type}` : round.round_type} · {round.status.replaceAll('_', ' ')}</li>)}</ol>{assignment.next_round ? <button type="button" disabled={starting === `${assignment.assignment_id}-${assignment.next_round.id}`} onClick={() => handleStartPractice(assignment.next_round.practice_type, null, assignment, assignment.next_round)} className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{starting === `${assignment.assignment_id}-${assignment.next_round.id}` ? 'Opening…' : assignment.next_round.status === 'in_progress' ? 'Resume assigned round' : `Start ${assignment.next_round.round_type === 'aptitude' ? 'Aptitude' : assignment.next_round.round_type} round`}</button> : <p className="mt-3 text-xs font-medium text-slate-600">{assignment.status === 'completed' ? 'All assigned rounds are complete.' : getAssignmentAvailabilityMessage(assignment)}</p>}</article>)}</div>}
                </section>}

                {/* Show only selected practice type, or all if on overview */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* MCQ Card */}
                    {(!selectedType || selectedType === 'mcq') && (
                        <div className="bg-white border border-slate-200 hover:border-indigo-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                    Aptitude
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">MCQ Round</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Quantitative, logical, verbal, and reasoning-based questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('mcq')}
                                disabled={starting === 'mcq'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'mcq' ? 'Starting...' : 'Start MCQ Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Technical MCQ Card */}
                    {(!selectedType || selectedType === 'technical') && (
                        <div className="bg-white border border-slate-200 hover:border-blue-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                    Technical
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Technical MCQ</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                OS, CN, OOPS, DBMS, and Data Structures questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('technical', 'all')}
                                disabled={starting === 'technical'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'technical' ? 'Starting...' : 'Start Technical Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Combined MCQ Card */}
                    {(!selectedType || selectedType === 'combined') && (
                        <div className="bg-white border border-slate-200 hover:border-purple-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                                    Combined
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Combined MCQ</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                50% Aptitude + 50% Technical questions
                            </p>
                            <button
                                onClick={() => handleStartPractice('combined')}
                                disabled={starting === 'combined'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-purple-600 hover:bg-purple-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'combined' ? 'Starting...' : 'Start Combined Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Coding Card */}
                    {(!selectedType || selectedType === 'coding') && (
                        <div className="bg-white border border-slate-200 hover:border-emerald-300 rounded-2xl p-6 shadow-sm transition-all">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Coding
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Coding Challenge</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Solve algorithmic problems with full proctoring
                            </p>
                            <button
                                onClick={() => handleStartPractice('coding')}
                                disabled={starting === 'coding'}
                                className="w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'coding' ? 'Starting...' : 'Start Coding Practice →'}
                            </button>
                        </div>
                    )}

                    {/* Interview Card */}
                    {(!selectedType || selectedType === 'interview') && (
                        <div className="bg-white border border-slate-200 hover:border-amber-300 rounded-2xl p-6 shadow-sm transition-all md:col-span-2">
                            <div className="flex items-center justify-between mb-4">
                                <div className="w-12 h-12 rounded-xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600">
                                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                    </svg>
                                </div>
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                    Interview
                                </span>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2">Interview Practice</h3>
                            <p className="text-sm text-slate-600 mb-4">
                                Practice technical, HR, or communication interviews with AI
                            </p>
                            <button
                                onClick={() => handleStartPractice('interview')}
                                disabled={starting === 'interview'}
                                className="w-full max-w-xs py-2.5 px-4 rounded-xl text-sm font-bold bg-amber-600 hover:bg-amber-700 text-white transition-all disabled:opacity-50"
                            >
                                {starting === 'interview' ? 'Starting...' : 'Start Interview Practice →'}
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </StudentModeLayout>
    );
}
