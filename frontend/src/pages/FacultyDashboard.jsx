import { createElement, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Activity, AlertCircle, BarChart3, BookOpenCheck, BriefcaseBusiness, CheckCircle2, ChevronLeft, ChevronRight, ClipboardList, GraduationCap, LayoutDashboard, LoaderCircle, RefreshCw, Search, Users, X } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Navbar from '../components/Navbar';
import api from '../services/api';
import FacultyPracticeAssessmentWorkspace from '../components/FacultyPracticeAssessmentWorkspace';
import FacultyAssessmentsSection from '../components/FacultyAssessmentsSection';
import {
  aggregatePracticeScoresByType,
  facultyPracticePercentage,
  independentPracticePercentage,
} from '../utils/practicePerformance';
import {
  selectStudentsNeedingFollowUp,
  sessionStatusReason,
  studentDisplayName,
  summarizeLatestSessionStatuses,
} from '../utils/facultyDashboardMetrics';
import { normalizePracticeParticipationTrend } from '../utils/facultyParticipationTrend';
import { normalizeFacultyImprovementTrend } from '../utils/facultyImprovementTrend';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, description: 'Performance overview, student progress, and current cohort status.' },
  { id: 'students', label: 'My Students', icon: Users, description: 'Find students in your authorized department and review their latest progress.' },
  { id: 'assessments', label: 'Assessment Monitoring', icon: ClipboardList, description: 'Track assessment rounds, review student performance, monitor evaluation status, and access individual student reports.' },
  { id: 'drives', label: 'Practice Assessment Workspace', icon: BriefcaseBusiness, description: 'Create and assign practice assessments, monitor student progress, and review results.' },
  { id: 'competencies', label: 'Candidates Insights', icon: BarChart3, description: 'An overview of students and candidates available within your authorized scope.' },
];
const MY_STUDENTS_PAGE_SIZE = 10;
const CHECK_IN_PRIORITY_NAMES = ['Aksha', 'Aarav Sharma', 'Ananya Patel', 'Rohan Deshmukh', 'Priya Kulkarni'];
const statusStyle = {
  completed: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  in_progress: 'border-blue-200 bg-blue-50 text-blue-800',
  active: 'border-blue-200 bg-blue-50 text-blue-800',
  terminated: 'border-rose-200 bg-rose-50 text-rose-800',
  not_started: 'border-slate-200 bg-slate-100 text-slate-700',
  pending: 'border-slate-200 bg-slate-100 text-slate-700',
};
const display = (value) => value === null || value === undefined || value === '' ? 'Not provided' : value;
const scoreDisplay = (value) => value === null || value === undefined ? 'Unavailable' : String(value);
const numericValue = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

async function fetchAllPages(path, key, extraParams = {}) {
  const first = await api.get(path, { params: { ...extraParams, page: 1, page_size: 100 } });
  const pages = Math.max(1, Number(first.data?.pages) || 1);
  const remaining = await Promise.all(Array.from({ length: pages - 1 }, (_, index) => api.get(path, {
    params: { ...extraParams, page: index + 2, page_size: 100 },
  })));
  const responses = [first, ...remaining];
  return {
    first: first.data,
    items: responses.flatMap((response) => Array.isArray(response.data?.[key]) ? response.data[key] : []),
  };
}

function StatusBadge({ value }) {
  const normalized = value || 'unavailable';
  const style = statusStyle[normalized] || 'border-slate-200 bg-slate-100 text-slate-700';
  const label = normalized.replaceAll('_', ' ');
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${style}`}>{label}</span>;
}

function Kpi({ title, value, note, icon }) {
  return <article className="relative overflow-hidden rounded-2xl border border-white/80 bg-gradient-to-br from-white/90 via-white/70 to-indigo-50/70 p-4 shadow-lg shadow-slate-200/60 backdrop-blur-xl sm:p-5"><div aria-hidden="true" className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-200/20 blur-2xl" /><div className="relative"><div className="flex items-start justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>{createElement(icon, { 'aria-hidden': true, className: 'h-4 w-4 text-indigo-600' })}</div><p className="mt-3 text-2xl font-bold text-slate-950">{value}</p><p className="mt-1 text-xs leading-5 text-slate-500">{note}</p></div></article>;
}

function FullPageState({ title, message, action }) {
  return <div className="rounded-2xl glass-card p-8 text-center shadow-sm"><AlertCircle aria-hidden="true" className="mx-auto h-8 w-8 text-amber-600" /><h2 className="mt-3 font-semibold text-slate-900">{title}</h2><p className="mx-auto mt-2 max-w-lg text-sm text-slate-600">{message}</p>{action}</div>;
}

function FacultySidebar({ active, onSelect, mobile = false }) {
  return <>
    {!mobile && <div className="flex h-[72px] items-center gap-3 border-b border-slate-200 px-3">
      <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-sm font-bold text-white shadow-sm">AI</span>
      <span className="w-0 overflow-hidden whitespace-nowrap text-xl font-bold tracking-tight text-slate-900 opacity-0 transition-all duration-200 group-hover:w-auto group-hover:opacity-100 group-focus-within:w-auto group-focus-within:opacity-100">AI Placement</span>
    </div>}
    <nav aria-label="Faculty dashboard sections" className={mobile ? 'flex gap-2 overflow-x-auto pb-1' : 'space-y-1 px-2 py-5'}>
      {NAV_ITEMS.map(({ id, label, icon }) => <button key={id} type="button" aria-label={label} title={mobile ? undefined : label} aria-current={active === id ? 'page' : undefined} onClick={() => onSelect(id)} className={`flex shrink-0 items-center gap-3 rounded-xl text-left text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 ${mobile ? 'px-3 py-2.5' : 'h-14 w-full px-3'} ${active === id ? 'bg-sky-100 text-sky-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'}`}>{createElement(icon, { 'aria-hidden': true, className: 'h-5 w-5 shrink-0 text-sky-600' })}<span className={mobile ? '' : 'w-0 overflow-hidden opacity-0 transition-all duration-200 group-hover:w-auto group-hover:opacity-100 group-focus-within:w-auto group-focus-within:opacity-100'}>{label}</span></button>)}
    </nav>
  </>;
}

function StudentDialog({ student, onClose }) {
  const dialogRef = useRef(null);
  const previousFocus = useRef(null);
  useEffect(() => {
    previousFocus.current = document.activeElement;
    dialogRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      } else if (event.key === 'Tab') {
        const controls = [...(dialogRef.current?.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])') || [])];
        if (!controls.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previousFocus.current?.focus?.();
    };
  }, [onClose]);
  const rounds = student.round_records || [];
  return <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-3 sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialogRef} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="student-dialog-title" className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl glass-card p-5 shadow-2xl focus:outline-none sm:p-7">
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4"><div><p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Student progress</p><h2 id="student-dialog-title" className="mt-1 text-xl font-bold text-slate-950">{studentDisplayName(student)}</h2><p className="mt-1 text-sm text-slate-500">Student ID: {display(student.roll_number || student.user_id)}</p></div><button type="button" aria-label="Close student details" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600"><X className="h-5 w-5" /></button></div>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">{[['Department', student.department], ['CGPA', student.cgpa], ['Graduation year', student.graduation_year], ['Backlogs', student.backlogs_count], ['Target role', student.target_role]].map(([name, value]) => <div key={name} className="rounded-xl glass-card p-3"><p className="text-xs text-slate-500">{name}</p><p className="mt-1 break-words text-sm font-semibold text-slate-900">{display(value)}</p></div>)}</div>
      <h3 className="mt-6 font-semibold text-slate-900">Latest assessment rounds</h3>
      {rounds.length ? <ul className="mt-3 divide-y divide-slate-100 rounded-xl glass-card">{rounds.map((round, index) => <li key={`${round.round_type}-${index}`} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm"><span className="font-medium capitalize text-slate-800">{round.round_type.replaceAll('_', ' ')}</span><span className="flex items-center gap-2"><StatusBadge value={round.status} /><span className="font-semibold text-slate-800">{round.status === 'completed' ? scoreDisplay(round.score) : '—'}</span></span></li>)}</ul> : <p className="mt-2 rounded-xl glass-card p-4 text-sm text-slate-600">No assessment rounds are recorded for the latest session.</p>}
      <p className="mt-3 text-xs text-slate-500">Only the latest assessment session is available from the current cohort API. Historical attempt comparison is unavailable. Stored score units can vary by round type.</p>
      <div className="mt-5 flex justify-end"><button type="button" onClick={onClose} className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">Close</button></div>
    </section>
  </div>;
}

export default function FacultyDashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedSection = searchParams.get('section');
  const activeSection = NAV_ITEMS.some((item) => item.id === requestedSection) ? requestedSection : 'dashboard';
  const selectSection = useCallback((id) => setSearchParams(id === 'dashboard' ? {} : { section: id }), [setSearchParams]);
  const [facultyUser, setFacultyUser] = useState(null);
  const [students, setStudents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [loadingRoster, setLoadingRoster] = useState(false);
  const [profileError, setProfileError] = useState(null);
  const [rosterError, setRosterError] = useState(null);
  const [participationReload, setParticipationReload] = useState(0);
  const [participationTrend, setParticipationTrend] = useState({ loading: false, error: null, weeks: [], rangeStart: null, rangeEnd: null });
  const [improvementSummary, setImprovementSummary] = useState({ loading: true, error: null, data: null });
  const [improvementTrend, setImprovementTrend] = useState({ loading: false, error: null, data: null });
  const [improvementTrendReload, setImprovementTrendReload] = useState(0);
  const [myStudentsRoster, setMyStudentsRoster] = useState({ loading: false, error: null, students: [] });
  const [myStudentsSearch, setMyStudentsSearch] = useState('');
  const [myStudentsDepartment, setMyStudentsDepartment] = useState('');
  const [myStudentsEligibility, setMyStudentsEligibility] = useState('');
  const [myStudentsMinCgpa, setMyStudentsMinCgpa] = useState('');
  const [myStudentsMaxCgpa, setMyStudentsMaxCgpa] = useState('');
  const [myStudentsBacklogs, setMyStudentsBacklogs] = useState('');
  const [myStudentsSort, setMyStudentsSort] = useState('name');
  const [myStudentsSortDirection, setMyStudentsSortDirection] = useState('asc');
  const [myStudentsPage, setMyStudentsPage] = useState(1);
  const [myStudentsReload, setMyStudentsReload] = useState(0);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const closeStudent = useCallback(() => setSelectedStudent(null), []);
  const rosterRequestId = useRef(0);
  const [insightsRoster, setInsightsRoster] = useState({ loading: false, error: null, students: [], count: null });
  const [insightsPractice, setInsightsPractice] = useState({ loading: false, error: null, rows: [] });
  const [insightsAssessments, setInsightsAssessments] = useState({ loading: false, error: null, details: [] });

  const loadProfile = useCallback(async () => {
    setLoadingProfile(true);
    setProfileError(null);
    try {
      const response = await api.get('/profile/me');
      setFacultyUser(response.data);
    } catch (error) {
      setProfileError(error?.response?.status === 401 ? 'Your session has expired. Sign in again to continue.' : 'Faculty profile could not be loaded. Check your connection and retry.');
    } finally {
      setLoadingProfile(false);
    }
  }, []);
  useEffect(() => { loadProfile(); }, [loadProfile]);

  const loadRoster = useCallback(async () => {
    if (!facultyUser) return;
    const requestId = ++rosterRequestId.current;
    setLoadingRoster(true);
    setRosterError(null);
    try {
      const response = await fetchAllPages('/profile/cohort/students', 'students', { status: 'all' });
      if (requestId !== rosterRequestId.current) return;
      const studentsById = new Map(response.items.map((student) => [student.user_id, student]));
      const roster = [...studentsById.values()];
      const expectedTotal = Number(response.first?.total);
      const authorizedTotal = Number(response.first?.summary?.authorized_students);
      if (!Number.isFinite(expectedTotal) || roster.length !== expectedTotal || roster.length !== authorizedTotal) {
        throw new Error('The complete authorized student roster could not be confirmed.');
      }
      setStudents(roster);
      setSummary(response.first?.summary || null);
    } catch (error) {
      if (requestId !== rosterRequestId.current) return;
      setStudents([]);
      setSummary(null);
      setRosterError(error?.response?.status === 401 ? 'Your session has expired. Sign in again to continue.' : error?.response?.status === 403 ? 'Your faculty department scope is unavailable or your access was denied.' : 'Student data could not be loaded. Your students are not being treated as an empty cohort.');
    } finally {
      if (requestId === rosterRequestId.current) setLoadingRoster(false);
    }
  }, [facultyUser]);
  useEffect(() => { loadRoster(); }, [loadRoster]);

  useEffect(() => {
    if (activeSection !== 'dashboard' || !facultyUser) return undefined;
    let active = true;
    setParticipationTrend({ loading: true, error: null, weeks: [], rangeStart: null, rangeEnd: null });
    api.get('/profile/cohort/practice-assessment-participation')
      .then((response) => {
        const weeks = normalizePracticeParticipationTrend(response.data);
        if (active) setParticipationTrend({
          loading: false,
          error: null,
          weeks,
          rangeStart: response.data.range_start,
          rangeEnd: response.data.range_end,
        });
      })
      .catch(() => {
        if (active) setParticipationTrend({ loading: false, error: 'Historical practice activity is unavailable.', weeks: [], rangeStart: null, rangeEnd: null });
      });
    return () => { active = false; };
  }, [activeSection, facultyUser, participationReload]);

  useEffect(() => {
    if (activeSection !== 'dashboard' || !facultyUser) return undefined;
    let active = true;
    setImprovementSummary({ loading: true, error: null, data: null });
    api.get('/profile/cohort/improvement')
      .then((response) => {
        if (active) setImprovementSummary({ loading: false, error: null, data: response.data });
      })
      .catch(() => {
        if (active) setImprovementSummary({ loading: false, error: 'Comparable history could not be loaded.', data: null });
      });
    return () => { active = false; };
  }, [activeSection, facultyUser]);

  useEffect(() => {
    if (activeSection !== 'competencies' || !facultyUser) return undefined;
    let active = true;
    setImprovementTrend({ loading: true, error: null, data: null });
    api.get('/profile/cohort/improvement-trend')
      .then((response) => {
        if (active) setImprovementTrend({ loading: false, error: null, data: response.data });
      })
      .catch(() => {
        if (active) setImprovementTrend({ loading: false, error: 'Comparable assessment history could not be loaded.', data: null });
      });
    return () => { active = false; };
  }, [activeSection, facultyUser, improvementTrendReload]);

  useEffect(() => {
    if (activeSection !== 'students' || !facultyUser) return undefined;
    let active = true;
    setMyStudentsRoster({ loading: true, error: null, students: [] });
    void (async () => {
      try {
        const response = await fetchAllPages('/profile/cohort/students', 'students', { status: 'all' });
        const studentsById = new Map(response.items.map((student) => [student.user_id, student]));
        const roster = [...studentsById.values()];
        const expectedTotal = Number(response.first?.total);
        if (!Number.isFinite(expectedTotal) || roster.length !== expectedTotal) {
          throw new Error('The complete authorized student roster could not be confirmed.');
        }
        if (active) setMyStudentsRoster({ loading: false, error: null, students: roster });
      } catch {
        if (active) setMyStudentsRoster({ loading: false, error: 'The complete authorized student roster is unavailable.', students: [] });
      }
    })();
    return () => { active = false; };
  }, [activeSection, facultyUser, myStudentsReload]);

  useEffect(() => {
    if (activeSection !== 'competencies' || !facultyUser) return undefined;
    let active = true;
    setInsightsRoster({ loading: true, error: null, students: [], count: null });
    setInsightsPractice({ loading: true, error: null, rows: [] });
    setInsightsAssessments({ loading: true, error: null, details: [] });

    const loadSource = async (setter, request, select) => {
      try {
        const value = await request();
        if (active) setter({ loading: false, error: null, ...select(value) });
      } catch (error) {
        if (active) setter({ loading: false, error: 'This authorized data source is unavailable.', ...(setter === setInsightsRoster ? { students: [], count: null } : setter === setInsightsPractice ? { rows: [] } : { details: [] }) });
      }
    };

    if (facultyUser.role === 'admin') {
      setInsightsRoster({ loading: false, error: null, students: [], count: 0 });
    } else {
      void loadSource(setInsightsRoster, async () => {
        const response = await fetchAllPages('/profile/cohort/students', 'students', { status: 'all' });
        const studentsById = new Map(response.items.map((student) => [student.user_id, student]));
        const studentsList = [...studentsById.values()];
        const expectedCount = response.first?.summary?.authorized_students;
        const complete = Number.isFinite(expectedCount) && studentsList.length === expectedCount && response.first?.total === expectedCount;
        return { students: studentsList, count: complete ? expectedCount : null };
      }, (value) => value);
    }

    void loadSource(setInsightsPractice, async () => {
      const response = await fetchAllPages('/profile/cohort/practice-assessment-activity', 'records');
      const roundsById = new Map(response.items.map((round) => [round.round_id, round]));
      return { rows: [...roundsById.values()] };
    }, (value) => value);

    void loadSource(setInsightsAssessments, async () => {
      const list = await api.get('/faculty/practice-assessments');
      const assessments = Array.isArray(list.data) ? list.data : [];
      const details = await Promise.all(assessments.map(async (assessment) => {
        const detail = await api.get(`/faculty/practice-assessments/${assessment.id}`);
        return detail.data;
      }));
      return { details };
    }, (value) => value);

    return () => { active = false; };
  }, [activeSection, facultyUser]);

  const currentNav = NAV_ITEMS.find((item) => item.id === activeSection) || NAV_ITEMS[0];
  const assessedCount = summary?.assessed_students;
  const completion = summary?.latest_attempt_completion_rate;
  const authorizedStudentCount = summary?.authorized_students;
  // The check-in suggestions use the same complete, authorized roster records
  // rendered by My Students whenever that page has loaded them.
  const checkInRoster = myStudentsRoster.students.length > 0 ? myStudentsRoster.students : students;
  const studentsNeedingProgress = useMemo(
    () => selectStudentsNeedingFollowUp(checkInRoster, 5, CHECK_IN_PRIORITY_NAMES),
    [checkInRoster],
  );
  const latestSessionStatusCounts = useMemo(() => summarizeLatestSessionStatuses(students), [students]);
  const myStudentsDepartments = useMemo(() => [...new Set(myStudentsRoster.students
    .map((student) => student.department)
    .filter((department) => typeof department === 'string' && department.trim())
    .map((department) => department.trim()))].sort((a, b) => a.localeCompare(b)), [myStudentsRoster.students]);
  const filteredMyStudents = useMemo(() => {
    const search = myStudentsSearch.trim().toLocaleLowerCase();
    const minimumCgpa = numericValue(myStudentsMinCgpa);
    const maximumCgpa = numericValue(myStudentsMaxCgpa);
    const filtered = myStudentsRoster.students.filter((student) => {
      const searchable = [student.full_name, student.name, student.user_id, student.roll_number, student.target_role]
        .filter((value) => value !== null && value !== undefined)
        .join(' ')
        .toLocaleLowerCase();
      if (search && !searchable.includes(search)) return false;
      if (myStudentsDepartment && (student.department || '').trim().toLocaleLowerCase() !== myStudentsDepartment.toLocaleLowerCase()) return false;
      const cgpa = numericValue(student.cgpa);
      if ((minimumCgpa !== null || maximumCgpa !== null) && cgpa === null) return false;
      if (minimumCgpa !== null && cgpa < minimumCgpa) return false;
      if (maximumCgpa !== null && cgpa > maximumCgpa) return false;
      const backlogs = numericValue(student.backlogs_count);
      if (myStudentsBacklogs === 'none' && backlogs !== 0) return false;
      if (myStudentsBacklogs === 'has' && !(backlogs !== null && backlogs > 0)) return false;
      if (myStudentsBacklogs === 'unknown' && backlogs !== null) return false;
      return true;
    });
    const direction = myStudentsSortDirection === 'desc' ? -1 : 1;
    const valueFor = (student) => {
      if (myStudentsSort === 'cgpa') return numericValue(student.cgpa);
      if (myStudentsSort === 'backlogs') return numericValue(student.backlogs_count);
      if (myStudentsSort === 'name') return String(student.full_name || student.name || '').toLocaleLowerCase();
      return String(student[myStudentsSort] || '').toLocaleLowerCase();
    };
    const compareIds = (left, right) => {
      const leftId = numericValue(left.user_id);
      const rightId = numericValue(right.user_id);
      if (leftId !== null && rightId !== null) return leftId - rightId;
      return String(left.user_id ?? '').localeCompare(String(right.user_id ?? ''), undefined, { numeric: true });
    };
    return filtered.sort((left, right) => {
      const leftValue = valueFor(left);
      const rightValue = valueFor(right);
      if (leftValue === null || leftValue === '') return rightValue === null || rightValue === '' ? compareIds(left, right) : 1;
      if (rightValue === null || rightValue === '') return -1;
      return (leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : compareIds(left, right)) * direction;
    });
  }, [myStudentsRoster.students, myStudentsSearch, myStudentsDepartment, myStudentsMinCgpa, myStudentsMaxCgpa, myStudentsBacklogs, myStudentsSort, myStudentsSortDirection]);
  const orderedMyStudents = useMemo(() => {
    const representatives = [];
    const repeatedEntries = [];
    const seenNames = new Set();
    for (const student of filteredMyStudents) {
      const normalizedName = String(student.full_name || student.name || '')
        .trim()
        .replace(/\s+/g, ' ')
        .toLocaleLowerCase();
      if (!normalizedName || !seenNames.has(normalizedName)) {
        representatives.push(student);
        if (normalizedName) seenNames.add(normalizedName);
      } else {
        repeatedEntries.push(student);
      }
    }
    return [...representatives, ...repeatedEntries];
  }, [filteredMyStudents]);
  const myStudentsPageCount = Math.ceil(filteredMyStudents.length / MY_STUDENTS_PAGE_SIZE);
  const visibleMyStudents = orderedMyStudents.slice((myStudentsPage - 1) * MY_STUDENTS_PAGE_SIZE, myStudentsPage * MY_STUDENTS_PAGE_SIZE);
  useEffect(() => {
    const lastValidPage = Math.max(1, myStudentsPageCount);
    if (myStudentsPage > lastValidPage) setMyStudentsPage(lastValidPage);
  }, [myStudentsPage, myStudentsPageCount]);
  const resetMyStudentsFilters = () => {
    setMyStudentsSearch('');
    setMyStudentsDepartment('');
    setMyStudentsEligibility('');
    setMyStudentsMinCgpa('');
    setMyStudentsMaxCgpa('');
    setMyStudentsBacklogs('');
    setMyStudentsSort('name');
    setMyStudentsSortDirection('asc');
    setMyStudentsPage(1);
  };
  const displayTitle = facultyUser?.name || 'Faculty member';
  const authorizedDepartment = facultyUser?.faculty_profile?.department || null;
  const improvementTrendPoints = normalizeFacultyImprovementTrend(improvementTrend.data);

  const competencyMetrics = useMemo(() => {
    const competenciesByName = new Map();
    for (const student of insightsRoster.students) {
      const studentId = student.user_id;
      const seenForStudent = new Set();
      for (const competency of student.competency_result?.competencies || []) {
        if (competency.status !== 'assessed' || !Number.isFinite(competency.score) || competency.score < 0 || competency.score > 100 || !(competency.evidence_count > 0)) continue;
        const name = typeof competency.name === 'string' ? competency.name.trim() : '';
        if (!name || seenForStudent.has(name)) continue;
        seenForStudent.add(name);
        const entry = competenciesByName.get(name) || { total: 0, students: new Set(), evidenceCount: 0 };
        entry.total += competency.score;
        entry.students.add(studentId);
        entry.evidenceCount += competency.evidence_count;
        competenciesByName.set(name, entry);
      }
    }
    return [...competenciesByName.entries()].map(([name, value]) => ({
      name,
      percentage: value.total / value.students.size,
      studentCount: value.students.size,
      evidenceCount: value.evidenceCount,
    })).sort((a, b) => a.name.localeCompare(b.name));
  }, [insightsRoster.students]);

  const practiceMetrics = useMemo(() => {
    const rows = insightsPractice.rows.filter((row) => row.assessment_source === 'independent_practice');
    const sessions = new Map();
    const participants = new Set();
    let completedRounds = 0;
    let correctAnswers = 0;
    let evaluatedAnswers = 0;
    const scoreRows = [];
    for (const row of rows) {
      if (row.student?.user_id !== undefined) participants.add(row.student.user_id);
      const session = sessions.get(row.session_id) || { status: row.session_status };
      sessions.set(row.session_id, session);
      if (row.evaluation_status === 'completed') {
        completedRounds += 1;
        const percentage = independentPracticePercentage(row);
        if (percentage !== null && row.student?.user_id !== undefined) {
          scoreRows.push({ studentId: row.student.user_id, resultId: row.round_id, roundType: row.round_type, percentage });
        }
        if (['aptitude', 'mcq', 'combined', 'technical'].includes(row.round_type)) {
          const evaluated = row.attempt_summary?.evaluated_answers || 0;
          const correct = row.attempt_summary?.correct_answers || 0;
          evaluatedAnswers += evaluated;
          correctAnswers += correct;
        }
      }
    }
    const completedSessions = [...sessions.values()].filter((session) => session.status === 'completed').length;
    const scoresByType = aggregatePracticeScoresByType(scoreRows);
    const studentsWithScores = new Set([...scoresByType.values()].flatMap((summary) => [...summary.studentScores.keys()]));
    return {
      participants: participants.size,
      sessions: sessions.size,
      completedSessions,
      completionRate: sessions.size ? (completedSessions / sessions.size) * 100 : null,
      completedRounds,
      aptitudeAccuracy: evaluatedAnswers ? (correctAnswers / evaluatedAnswers) * 100 : null,
      evaluatedAnswers,
      averageScoreByType: [...scoresByType.entries()].map(([roundType, summary]) => ({ roundType, ...summary })),
      scoreStudentCount: studentsWithScores.size,
      scoreRows,
    };
  }, [insightsPractice.rows]);

  const practiceAssessmentMetrics = useMemo(() => {
    const assignmentsById = new Map();
    for (const assessment of insightsAssessments.details) {
      for (const studentAssignment of assessment.students || []) {
        assignmentsById.set(studentAssignment.assignment_id, {
          ...studentAssignment,
          assessment_id: assessment.id,
        });
      }
    }
    const assignedStudents = new Set();
    const participants = new Set();
    const completedAssignmentStates = new Set(['completed', 'evaluation_pending', 'attempt_completed']);
    const completedRoundStates = new Set(['evaluated', 'evaluation_pending', 'attempt_completed']);
    let completedAssignments = 0;
    let eligibleCompletedAssignments = 0;
    let eligibleAssessmentOpportunities = 0;
    let completedRounds = 0;
    let evaluatedRounds = 0;
    let pendingRounds = 0;
    let failedRounds = 0;
    const assignmentStatuses = new Map([
      ['Completed', 0],
      ['Started', 0],
      ['Failed', 0],
      ['Not started', 0],
    ]);
    const scoreRows = [];
    for (const assignment of assignmentsById.values()) {
      const studentId = assignment.student?.id;
      const eligible = assignment.assessment_status === 'published';
      if (eligible) eligibleAssessmentOpportunities += 1;
      if (studentId !== undefined) assignedStudents.add(studentId);
      if ((assignment.progress || 0) > 0 && studentId !== undefined) participants.add(studentId);
      if (completedAssignmentStates.has(assignment.status)) {
        completedAssignments += 1;
        if (eligible) eligibleCompletedAssignments += 1;
        assignmentStatuses.set('Completed', assignmentStatuses.get('Completed') + 1);
      } else if (assignment.status === 'failed') {
        assignmentStatuses.set('Failed', assignmentStatuses.get('Failed') + 1);
      } else if ((assignment.progress || 0) > 0 || assignment.status === 'in_progress') {
        assignmentStatuses.set('Started', assignmentStatuses.get('Started') + 1);
      } else {
        assignmentStatuses.set('Not started', assignmentStatuses.get('Not started') + 1);
      }
      for (const round of assignment.rounds || []) {
        if (completedRoundStates.has(round.status)) completedRounds += 1;
        if (round.status === 'evaluated') {
          evaluatedRounds += 1;
          const percentage = facultyPracticePercentage(round);
          if (percentage !== null && studentId !== undefined) {
            scoreRows.push({ studentId, resultId: `${assignment.assignment_id}:${round.id}`, roundType: round.round_type, percentage });
          }
        } else if (round.status === 'evaluation_pending') {
          pendingRounds += 1;
        } else if (round.status === 'failed') {
          failedRounds += 1;
        }
      }
    }
    const assessmentOpportunities = assignmentsById.size;
    const scoresByType = aggregatePracticeScoresByType(scoreRows);
    const studentsWithScores = new Set([...scoresByType.values()].flatMap((summary) => [...summary.studentScores.keys()]));
    return {
      assignedStudents: assignedStudents.size,
      participants: participants.size,
      assessmentOpportunities,
      eligibleAssessmentOpportunities,
      completedAssignments,
      eligibleCompletedAssignments,
      completionRate: eligibleAssessmentOpportunities ? (eligibleCompletedAssignments / eligibleAssessmentOpportunities) * 100 : null,
      completedRounds,
      evaluatedRounds,
      pendingRounds,
      failedRounds,
      assignmentStatuses: [...assignmentStatuses.entries()].map(([status, count]) => ({
        status,
        count,
        percentage: assignmentsById.size ? (count / assignmentsById.size) * 100 : null,
      })),
      averageScoreByType: [...scoresByType.entries()].map(([roundType, summary]) => ({ roundType, ...summary })),
      scoreStudentCount: studentsWithScores.size,
      scoreRows,
    };
  }, [insightsAssessments.details]);

  const overallPracticeMetrics = useMemo(() => {
    const rows = [...practiceMetrics.scoreRows, ...practiceAssessmentMetrics.scoreRows];
    const scoresByType = aggregatePracticeScoresByType(rows);
    const studentsWithScores = new Set(rows.map((row) => row.studentId));
    const onlyType = scoresByType.size === 1 ? [...scoresByType.values()][0] : null;
    return {
      average: onlyType?.average ?? null,
      studentCount: onlyType?.studentCount ?? studentsWithScores.size,
      roundTypeCount: scoresByType.size,
    };
  },
    [practiceMetrics, practiceAssessmentMetrics],
  );

  const scoreComparisons = [
    { label: 'Student Practice', result: practiceMetrics, source: insightsPractice },
    { label: 'Faculty Practice Assessment', result: practiceAssessmentMetrics, source: insightsAssessments },
  ];

  const renderDashboard = () => <>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Kpi title="Authorized students" value={summary ? summary.authorized_students : '—'} note={authorizedDepartment || (facultyUser?.role === 'admin' ? 'All departments · administrator access' : 'Authorized faculty scope')} icon={Users} />
      <Kpi title="Assessed students" value={assessedCount ?? 'Unavailable'} note="Latest session completed with at least one completed round" icon={CheckCircle2} />
      <Kpi title="Students improving" value={improvementSummary.loading ? 'Loading…' : improvementSummary.data?.available ? improvementSummary.data.improving_students : improvementSummary.error || improvementSummary.data?.scoring_errors ? 'Unavailable' : 'Insufficient history'} note={improvementSummary.error || (improvementSummary.data?.available ? `${improvementSummary.data.students_compared} of ${improvementSummary.data.authorized_students} authorized students compared across ${improvementSummary.data.comparison_scopes} same-drive blueprint histories.${improvementSummary.data.scoring_errors ? ` ${improvementSummary.data.scoring_errors} attempt(s) could not be scored.` : ''}` : improvementSummary.data?.reason || 'Comparable history is unavailable.')} icon={Activity} />
    </div>
    <div className="mt-5 grid items-stretch gap-4 lg:grid-cols-2">
      <article className="rounded-2xl glass-card p-5 shadow-sm"><div className="flex items-center gap-2"><Activity className="h-4 w-4 text-indigo-600" /><h2 className="font-semibold text-slate-900">Latest attempt completion</h2></div><p className="mt-2 text-sm text-slate-600">Students whose latest session is completed and contains at least one completed round.</p><p className="mt-3 text-3xl font-bold text-slate-950">{Number.isFinite(completion) ? `${completion}%` : authorizedStudentCount === 0 ? 'No authorized students' : 'Unavailable'}</p><p className="mt-1 text-sm font-medium text-slate-700">{Number.isFinite(assessedCount) && Number.isFinite(authorizedStudentCount) ? `${assessedCount} of ${authorizedStudentCount} authorized students` : 'Completion counts are unavailable.'}</p>{Number.isFinite(completion) && <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${completion}% of authorized students have a completed latest session with a completed round`}><div className="h-full rounded-full bg-teal-600 transition-[width]" style={{ width: `${Math.max(0, Math.min(100, completion))}%` }} /></div>}</article>
      <article className="flex h-full flex-col rounded-2xl glass-card p-5 shadow-sm lg:row-span-2">
        <div className="flex items-center gap-2"><Activity className="h-4 w-4 text-indigo-600" /><h2 className="font-semibold text-slate-900">Participation Over Time</h2></div>
        <p className="mt-1 text-xs text-slate-500">Student participation in practice assessments across your authorized roster.</p>
        {participationTrend.loading
          ? <div className="mt-4 flex min-h-56 flex-1 items-center justify-center gap-2 rounded-xl bg-slate-50 text-sm text-slate-600"><LoaderCircle className="h-4 w-4 animate-spin" />Loading practice participation…</div>
          : participationTrend.error
            ? <div className="mt-4 rounded-xl bg-slate-50 p-4">
              <p className="text-sm text-slate-700">Historical practice activity is unavailable.</p>
              <button type="button" onClick={() => setParticipationReload((value) => value + 1)} className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-700 hover:text-indigo-900"><RefreshCw className="h-3.5 w-3.5" />Retry</button>
            </div>
            : participationTrend.weeks.every((week) => week.participating_students === 0)
              ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No practice participation recorded for this period.</p>
              : <>
                <p className="mt-3 text-[11px] text-slate-500">12 complete weeks · {participationTrend.rangeStart} to {participationTrend.rangeEnd} (UTC)</p>
                <div className="mt-2 min-h-64 w-full flex-1" role="img" aria-label="Weekly distinct students participating in practice assessments">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={participationTrend.weeks} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} minTickGap={18} />
                      <YAxis allowDecimals={false} width={36} tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} label={{ value: 'Students', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }} />
                      <Tooltip formatter={(value) => [value, 'Participating students']} labelFormatter={(label) => `Week of ${label}`} />
                      <Legend />
                      <Line type="monotone" dataKey="participating_students" name="Participating students" stroke="#4f46e5" strokeWidth={2.5} activeDot={{ r: 5 }} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </>}
      </article>
      <article className="rounded-2xl glass-card p-5 shadow-sm"><div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-indigo-600" /><h2 className="font-semibold text-slate-900">Latest session status</h2></div><p className="mt-1 text-xs text-slate-500">Distinct students in the complete authorized roster.</p>{students.length ? <div className="mt-4 space-y-3">{latestSessionStatusCounts.map(({ label, count }) => <div key={label}><div className="mb-1 flex justify-between gap-3 text-sm"><span className="text-slate-700">{label}</span><span className="font-semibold text-slate-900">{count}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-600" style={{ width: `${(count / students.length) * 100}%` }} /></div></div>)}</div> : <p className="mt-3 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No students are available in this authorized scope.</p>}</article>
      <article className="rounded-2xl glass-card p-5 shadow-sm lg:col-span-2"><div className="flex items-center gap-2"><GraduationCap className="h-4 w-4 text-indigo-600" /><h2 className="font-semibold text-slate-900">Students to check in with</h2></div><p className="mt-1 text-xs text-slate-500"></p>{studentsNeedingProgress.length ? <ul className="mt-3 divide-y divide-slate-100">{studentsNeedingProgress.map((student) => <li key={student.user_id} className="flex items-center justify-between gap-3 py-2 text-sm"><div className="min-w-0"><p className="truncate font-medium text-slate-800">{student.checkInDisplayName}</p><p className="text-xs text-slate-500">{sessionStatusReason(student.session_status) || 'Latest session needs review.'}</p></div><StatusBadge value={student.session_status || 'not_started'} /></li>)}</ul> : <p className="mt-3 text-sm text-slate-600">No students in the authorized roster currently need follow-up.</p>}<button type="button" onClick={() => selectSection('students')} className="mt-3 text-sm font-semibold text-indigo-700 hover:text-indigo-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">Open My Students</button></article>
    </div>
  </>;

  const renderStudents = () => <div className="grid items-start gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
    <aside aria-label="Student filters" className="rounded-2xl glass-card p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between"><h2 className="font-bold text-slate-900">Filters</h2><button type="button" onClick={resetMyStudentsFilters} className="text-xs font-semibold text-indigo-700 hover:text-indigo-900">Clear all</button></div>
      <label className="mb-4 block text-xs font-semibold text-slate-600">Search students<span className="relative mt-1.5 block"><Search aria-hidden="true" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={myStudentsSearch} onChange={(event) => { setMyStudentsSearch(event.target.value); setMyStudentsPage(1); }} placeholder="Name, student ID, or role" className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-9 pr-3 text-sm font-normal text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-600" /></span></label>
      <label className="mb-4 block text-xs font-semibold text-slate-600">Department<select value={myStudentsDepartment} onChange={(event) => { setMyStudentsDepartment(event.target.value); setMyStudentsPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="">All departments</option>{myStudentsDepartments.map((department) => <option key={department} value={department}>{department}</option>)}</select></label>
      <label className="mb-1 block text-xs font-semibold text-slate-600">Eligibility status<select value={myStudentsEligibility} onChange={(event) => setMyStudentsEligibility(event.target.value)} disabled title="Role-specific eligibility is not included in the faculty roster response." className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-100 px-3 py-2.5 text-sm font-normal text-slate-500"><option value="">All statuses</option><option value="eligible">Eligible</option><option value="conditional">Conditional</option></select></label><p className="mb-4 text-[11px] leading-4 text-slate-500"></p>
      <div className="mb-4 block text-xs font-semibold text-slate-600">CGPA range<div className="mt-1.5 grid grid-cols-2 gap-2"><input aria-label="Minimum CGPA" type="number" min="0" max="10" step="0.01" value={myStudentsMinCgpa} onChange={(event) => { setMyStudentsMinCgpa(event.target.value); setMyStudentsPage(1); }} placeholder="Min" className="min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900" /><input aria-label="Maximum CGPA" type="number" min="0" max="10" step="0.01" value={myStudentsMaxCgpa} onChange={(event) => { setMyStudentsMaxCgpa(event.target.value); setMyStudentsPage(1); }} placeholder="Max" className="min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900" /></div></div>
      <label className="mb-4 block text-xs font-semibold text-slate-600">Backlogs<select value={myStudentsBacklogs} onChange={(event) => { setMyStudentsBacklogs(event.target.value); setMyStudentsPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="">Any backlog count</option><option value="none">No backlogs</option><option value="has">Has backlogs</option><option value="unknown">Unknown</option></select></label>
      <label className="mb-2 block text-xs font-semibold text-slate-600">Sort by<select value={myStudentsSort} onChange={(event) => { setMyStudentsSort(event.target.value); setMyStudentsPage(1); }} className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-sm font-normal text-slate-900"><option value="name">Student name</option><option value="department">Department</option><option value="target_role">Target role</option><option value="cgpa">CGPA</option><option value="backlogs">Backlogs</option></select></label>
      <div className="mt-2 flex rounded-xl bg-slate-100 p-1 text-xs"><button type="button" onClick={() => { setMyStudentsSortDirection('asc'); setMyStudentsPage(1); }} className={`flex-1 rounded-lg py-2 font-semibold ${myStudentsSortDirection === 'asc' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}>A–Z / Low</button><button type="button" onClick={() => { setMyStudentsSortDirection('desc'); setMyStudentsPage(1); }} className={`flex-1 rounded-lg py-2 font-semibold ${myStudentsSortDirection === 'desc' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'}`}>Z–A / High</button></div>
    </aside>

    <section className="min-w-0 overflow-hidden rounded-2xl glass-card shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:px-5"><div><h2 className="font-semibold text-slate-900">Student roster</h2><p className="mt-1 text-sm text-slate-500">{filteredMyStudents.length} student{filteredMyStudents.length === 1 ? '' : 's'} match the authorized scope and filters.</p></div><span className="text-xs text-slate-500">10 students per page</span></div>
      {myStudentsRoster.error ? <div className="p-5"><FullPageState title="Student data unavailable" message={myStudentsRoster.error} action={<button type="button" onClick={() => setMyStudentsReload((value) => value + 1)} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"><RefreshCw className="h-4 w-4" />Retry</button>} /></div> : myStudentsRoster.loading ? <div className="flex items-center justify-center gap-2 p-12 text-sm text-slate-600"><LoaderCircle className="h-5 w-5 animate-spin" />Loading complete authorized roster…</div> : <>
        {filteredMyStudents.length === 0 ? <div className="p-10 text-center"><Users aria-hidden="true" className="mx-auto h-8 w-8 text-slate-400" /><h3 className="mt-3 font-semibold text-slate-900">{myStudentsRoster.students.length ? 'No matching students' : 'No students in this authorized scope'}</h3><p className="mt-1 text-sm text-slate-500">{myStudentsRoster.students.length ? 'Adjust or clear your filters to see other students.' : 'The authorized roster returned no students.'}</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="px-4 py-3">Student</th><th scope="col" className="px-4 py-3">Academic</th><th scope="col" className="px-4 py-3">Target role</th><th scope="col" className="px-4 py-3">Status</th><th scope="col" className="px-4 py-3">Latest session</th><th scope="col" className="px-4 py-3">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{visibleMyStudents.map((student) => <tr key={student.user_id} className="hover:bg-slate-50"><td className="px-4 py-3"><p className="font-semibold text-slate-900">{studentDisplayName(student)}</p><p className="mt-0.5 text-xs text-slate-500">ID: {display(student.roll_number || student.user_id)}</p></td><td className="px-4 py-3 text-slate-700">CGPA {display(student.cgpa)}<p className="mt-0.5 text-xs text-slate-500">Backlogs: {display(student.backlogs_count)}</p></td><td className="px-4 py-3 text-slate-700">{display(student.target_role)}</td><td className="px-4 py-3"><span className="inline-flex rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600" title="Role-specific eligibility is not supplied by the faculty roster API.">Unavailable</span></td><td className="px-4 py-3"><StatusBadge value={student.session_status || 'not_started'} /></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => setSelectedStudent(student)} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-800 hover:bg-indigo-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">Review</button></td></tr>)}</tbody></table></div>}
        <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs text-slate-500">Showing {filteredMyStudents.length ? (myStudentsPage - 1) * MY_STUDENTS_PAGE_SIZE + 1 : 0}–{Math.min(myStudentsPage * MY_STUDENTS_PAGE_SIZE, filteredMyStudents.length)} of {filteredMyStudents.length}</p><div className="flex items-center gap-2"><button type="button" aria-label="Previous page" disabled={myStudentsPage <= 1} onClick={() => setMyStudentsPage((current) => Math.max(1, current - 1))} className="rounded-lg border border-slate-300 p-2 text-slate-700 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button><span aria-live="polite" className="text-sm text-slate-600">Page {myStudentsPageCount ? myStudentsPage : 0} of {myStudentsPageCount}</span><button type="button" aria-label="Next page" disabled={myStudentsPageCount === 0 || myStudentsPage >= myStudentsPageCount} onClick={() => setMyStudentsPage((current) => Math.min(myStudentsPageCount, current + 1))} className="rounded-lg border border-slate-300 p-2 text-slate-700 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button></div></div>
      </>}
    </section>
  </div>;

  const renderAssessments = () => <FacultyAssessmentsSection />;

  const renderCandidateInsights = () => <div className="space-y-5">
    <section aria-label="Candidate overview" className="grid gap-4 sm:grid-cols-2">
      <article className="rounded-2xl glass-card p-5 shadow-sm">
        <p className="text-sm font-semibold text-slate-600">Total Students</p>
        <p className="mt-3 text-3xl font-bold tracking-tight text-slate-950">{insightsRoster.error ? 'Unavailable' : insightsRoster.loading ? 'Loading…' : insightsRoster.count ?? 'Unavailable'}</p>
        <p className="mt-1 text-sm text-slate-500">Distinct students in your authorized scope.</p>
      </article>
      <article className="rounded-2xl glass-card p-5 shadow-sm">
        <p className="text-sm font-semibold text-slate-600">Average Practice Score</p>
        <p className="mt-3 text-2xl font-bold tracking-tight text-slate-950">{insightsPractice.loading || insightsAssessments.loading ? 'Loading…' : insightsPractice.error || insightsAssessments.error ? 'Unavailable' : overallPracticeMetrics.average !== null ? `${overallPracticeMetrics.average.toFixed(1)}%` : overallPracticeMetrics.roundTypeCount > 1 ? 'Unavailable across mixed round types' : 'Not enough evaluated data'}</p>
        <p className="mt-1 text-sm text-slate-500">{insightsPractice.loading || insightsAssessments.loading ? 'Loading…' : insightsPractice.error || insightsAssessments.error ? 'Unavailable' : overallPracticeMetrics.studentCount}. </p>
        <p className="mt-2 text-xs text-slate-500"></p>
      </article>
    </section>

    <section aria-label="Practice assessment participation and performance" className="grid gap-4 xl:grid-cols-2">
      <article className="rounded-2xl glass-card p-5 shadow-sm">
        <h2 className="font-semibold text-slate-900">Practice Assessment participation</h2>
        <p className="mt-1 text-sm text-slate-500"></p>
        {insightsAssessments.error ? <p className="mt-3 text-sm text-slate-600">Participation distribution is unavailable from the faculty-authorized assessment source.</p> : insightsAssessments.loading ? <p className="mt-3 text-sm text-slate-600">Loading assignment statuses…</p> : practiceAssessmentMetrics.assessmentOpportunities === 0 ? <p className="mt-3 text-sm text-slate-600">No Practice Assessment assignments are available in this faculty scope.</p> : <div className="mt-4 space-y-4">{practiceAssessmentMetrics.assignmentStatuses.map((item) => <div key={item.status}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1"><span className="font-medium text-slate-800">{item.status}</span><span className="text-sm font-semibold text-slate-700">{item.count} assignments · {item.percentage.toFixed(1)}%</span></div>
          <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${item.status}: ${item.count} of ${practiceAssessmentMetrics.assessmentOpportunities} assigned assessment instances, ${item.percentage.toFixed(1)} percent`}><div className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.max(0, Math.min(100, item.percentage))}%` }} /></div>
        </div>)}</div>}
      </article>
      <article className="rounded-2xl glass-card p-5 shadow-sm">
        <h2 className="font-semibold text-slate-900">Student Improvement Across Attempts</h2>
        <p className="mt-1 text-xs text-slate-500"> </p>
        {improvementTrend.loading ? <div aria-label="Loading student improvement trend" className="mt-5 space-y-4">
          <div className="h-3 w-2/5 animate-pulse rounded bg-slate-100" />
          <div className="h-8 animate-pulse rounded bg-slate-100" />
          <div className="h-8 w-4/5 animate-pulse rounded bg-slate-100" />
        </div> : improvementTrend.error ? <div role="alert" className="mt-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-700">
          <p>{improvementTrend.error}</p>
          <button type="button" onClick={() => setImprovementTrendReload((value) => value + 1)} className="mt-3 inline-flex items-center gap-2 font-semibold text-rose-800 hover:text-rose-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"><RefreshCw aria-hidden="true" className="h-4 w-4" />Retry</button>
        </div> : !improvementTrend.data?.available || improvementTrendPoints.length < 2 ? <div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
          <p>Not enough comparable evaluated attempts to measure improvement yet.</p>
          {improvementTrend.data?.partial_coverage && <p className="mt-2 text-xs text-amber-700">Only final scores with complete comparable history are considered. {improvementTrend.data.excluded_attempts || 0} attempt(s) were excluded{improvementTrend.data.scoring_errors ? `; ${improvementTrend.data.scoring_errors} attempt(s) could not be scored` : ''}.</p>}
        </div> : <>
          <p className="mt-3 text-xs font-medium text-slate-600">{improvementTrend.data.distinct_students} distinct students · {improvementTrend.data.comparable_series} matched student/drive/blueprint histories · {improvementTrend.data.included_attempts} comparable attempts</p>
          {improvementTrend.data.partial_coverage && <p className="mt-2 text-xs text-amber-700">Partial coverage: the chart includes final, fully evaluated histories only. {improvementTrend.data.excluded_attempts || 0} attempt(s) were excluded{improvementTrend.data.scoring_errors ? `; ${improvementTrend.data.scoring_errors} attempt(s) could not be scored` : ''}.</p>}
          <div className="mt-3" role="img" aria-label={`Line chart of average normalized scores across successive comparable attempts for ${improvementTrend.data.distinct_students} distinct students`}>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={improvementTrendPoints} margin={{ top: 12, right: 22, bottom: 8, left: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} />
                <YAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(value) => `${value}%`} width={42} tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip content={({ active, payload }) => {
                  const item = payload?.[0]?.payload;
                  return active && item ? <div className="max-w-xs rounded-lg glass-card p-3 text-xs shadow-lg">
                    <p className="font-semibold text-slate-900">{item.label}: {item.average_score.toFixed(1)}%</p>
                    {item.score_change_percentage_points !== null && <p className="mt-1 text-slate-700">Change from prior attempt: {item.score_change_percentage_points > 0 ? '+' : ''}{item.score_change_percentage_points.toFixed(1)} percentage points</p>}
                    <p className="mt-2 text-slate-500">{item.distinct_students} distinct students · {item.comparable_series} matched histories</p>
                  </div> : null;
                }} />
                <Line type="monotone" dataKey="average_score" name="Average normalized score" stroke="#4f46e5" strokeWidth={3} dot={{ r: 4, fill: '#4f46e5' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-xs text-slate-500">Y-axis: normalized D1-v1 score (0–100). Every plotted attempt uses the same matched student cohort; attempt depth is limited to the shared history available across comparable series.</p>
        </>}
      </article>
    </section>

    <section aria-label="Practice overview" className="rounded-2xl glass-card p-5 shadow-sm">
      <div><h2 className="font-semibold text-slate-900">Practice Overview</h2><p className="mt-1 text-sm text-slate-500">Independent Practice mode only. Faculty-assigned Practice Assessments are reported separately below.</p></div>
      {insightsPractice.error ? <p className="mt-4 text-sm text-slate-600">Practice analytics are unavailable from the authorized activity source.</p> : insightsPractice.loading ? <p className="mt-4 text-sm text-slate-600">Loading all authorized Practice activity pages…</p> : practiceMetrics.sessions === 0 ? <p className="mt-4 text-sm text-slate-600">No independent Practice sessions are available in this faculty scope.</p> : <>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Distinct participants</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceMetrics.participants}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Completed sessions</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceMetrics.completedSessions} / {practiceMetrics.sessions}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Students with evaluated scores</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceMetrics.scoreStudentCount}</p><p className="mt-1 text-xs text-slate-500">Distinct students across supported round types</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Aptitude answer accuracy</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceMetrics.aptitudeAccuracy === null ? 'Unavailable' : `${practiceMetrics.aptitudeAccuracy.toFixed(1)}%`}</p><p className="mt-1 text-xs text-slate-500">{practiceMetrics.evaluatedAnswers} evaluated answers</p></div>
        </div>
        <p className="mt-3 text-xs text-slate-500"></p>
      </>}
    </section>



    <section aria-label="Practice Assessment overview" className="rounded-2xl glass-card p-5 shadow-sm">
      <div><h2 className="font-semibold text-slate-900">Faculty Practice Assessment Overview</h2><p className="mt-1 text-sm text-slate-500">Faculty-created assigned assessments </p></div>
      {insightsAssessments.error ? <p className="mt-4 text-sm text-slate-600">Practice Assessment analytics are unavailable from the faculty-authorized assessment source.</p> : insightsAssessments.loading ? <p className="mt-4 text-sm text-slate-600">Loading faculty assessment results…</p> : <>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Students assigned</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceAssessmentMetrics.assignedStudents}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Distinct participants</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceAssessmentMetrics.participants}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assessments completed</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceAssessmentMetrics.eligibleCompletedAssignments} / {practiceAssessmentMetrics.eligibleAssessmentOpportunities}</p><p className="mt-1 text-xs text-slate-500">{practiceAssessmentMetrics.completionRate === null ? 'Completion rate unavailable without eligible assignments' : `${practiceAssessmentMetrics.completionRate.toFixed(1)}% of eligible assigned assessment instances`}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Completed round attempts</p><p className="mt-2 text-2xl font-bold text-slate-950">{practiceAssessmentMetrics.completedRounds}</p><p className="mt-1 text-xs text-slate-500">{practiceAssessmentMetrics.evaluatedRounds} evaluated · {practiceAssessmentMetrics.pendingRounds} pending · {practiceAssessmentMetrics.failedRounds} failed</p></div>
        </div>
        <p className="mt-3 text-sm text-slate-600"> </p>
        <p className="mt-3 text-xs text-slate-500"></p>
      </>}
    </section>


    {/* <section aria-label="Competency performance" className="rounded-2xl glass-card p-5 shadow-sm">
      <h2 className="font-semibold text-slate-900">Competency Performance</h2>
      <p className="mt-1 text-sm text-slate-500">Latest authorized Mock Drive competency mappings only; these are separate from the Practice score metrics above.</p>
      {insightsRoster.error ? <p className="mt-3 text-sm text-slate-600">Competency evidence is unavailable while the authorized roster cannot be loaded.</p> : insightsRoster.loading ? <p className="mt-3 text-sm text-slate-600">Loading mapped competency evidence…</p> : competencyMetrics.length === 0 ? <p className="mt-3 text-sm text-slate-600">Not enough evaluated mapped evidence to show competency progress. Practice and faculty-assigned Practice Assessment results are not mapped to competencies in the current data source.</p> : <div className="mt-4 space-y-4">{competencyMetrics.map((item) => <div key={item.name}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1"><span className="font-medium text-slate-800">{item.name}</span><span className="text-sm font-semibold text-slate-700">{item.percentage.toFixed(1)}% · {item.studentCount} students · {item.evidenceCount} evidence records</span></div>
        <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${item.name}: ${item.percentage.toFixed(1)} percent across ${item.studentCount} students`}><div className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.max(0, Math.min(100, item.percentage))}%` }} /></div>
      </div>)}</div>}
    </section> */}

  </div>;

  const renderDrives = () => <FacultyPracticeAssessmentWorkspace />;

  return <div className="min-h-screen bg-slate-50 text-slate-900">
    <Navbar position="sticky" />
    <div className="w-full px-0 py-5">
      <div className="mb-4 px-4 sm:px-6 lg:hidden"><FacultySidebar active={activeSection} onSelect={selectSection} mobile /></div>
      <div className="grid gap-0 lg:grid-cols-[256px_minmax(0,1fr)]">
        <aside className="relative z-30 hidden w-64 lg:block"><div className="group sticky top-16 h-[calc(100vh-4rem)] w-16 overflow-hidden border-r border-slate-200 bg-[#f8fbff] transition-[width] duration-200 hover:w-64 focus-within:w-64"><FacultySidebar active={activeSection} onSelect={selectSection} /></div></aside>
        <main className="min-w-0 w-full max-w-[1600px] justify-self-center px-4 sm:px-6 lg:pl-10 lg:pr-[264px] xl:pl-12 xl:pr-[272px]">
          {activeSection === 'dashboard' ? (
          <header className="mb-5 flex flex-col gap-5 rounded-2xl border border-white/80 bg-gradient-to-br from-white/90 via-white/70 to-indigo-50/70 p-5 shadow-lg shadow-slate-200/60 backdrop-blur-xl sm:p-7 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-indigo-700">FACULTY WORKSPACE · {authorizedDepartment ? authorizedDepartment.toLocaleUpperCase() : facultyUser?.role === 'admin' ? 'ALL DEPARTMENTS' : 'DEPARTMENT UNAVAILABLE'}</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Faculty Portal</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Monitor student performance, track competency development, and support academic progress across your cohort.</p>
              <p className="mt-3 text-sm font-semibold text-slate-800">Welcome, {displayTitle}.</p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3 lg:justify-end">
              <Link to="/profile" className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600">Faculty Profile</Link>
              <button type="button" aria-label="Refresh faculty dashboard data" onClick={() => { if (profileError) loadProfile(); else loadRoster(); }} disabled={loadingProfile || loadingRoster} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2"><RefreshCw className={`h-4 w-4 ${loadingRoster || loadingProfile ? 'animate-spin' : ''}`} /><span>Refresh</span></button>
            </div>
          </header>
          ) : (
            <header className="mb-5 rounded-2xl border border-white/80 bg-gradient-to-br from-white/90 via-white/70 to-indigo-50/70 p-5 shadow-lg shadow-slate-200/60 backdrop-blur-xl sm:p-6">
              <h1 className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">{currentNav.label}</h1>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{currentNav.description}</p>
            </header>
          )}
          {activeSection === 'dashboard' ? <>
            {profileError && <FullPageState title="Faculty profile unavailable" message={profileError} action={<button type="button" onClick={loadProfile} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"><RefreshCw className="h-4 w-4" />Retry</button>} />}
            {rosterError && <FullPageState title="Dashboard data unavailable" message={rosterError} action={<button type="button" onClick={loadRoster} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"><RefreshCw className="h-4 w-4" />Retry</button>} />}
            {loadingProfile || loadingRoster ? <div className="mb-4 flex items-center justify-center gap-2 rounded-2xl glass-card p-6 text-sm text-slate-600"><LoaderCircle className="h-5 w-5 animate-spin" />{loadingProfile ? 'Loading faculty profile…' : 'Loading authorized cohort…'}</div> : null}
            {renderDashboard()}
          </> : profileError ? <FullPageState title="Faculty profile unavailable" message={profileError} action={<button type="button" onClick={loadProfile} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white"><RefreshCw className="h-4 w-4" />Retry</button>} /> : loadingProfile ? <div className="flex items-center justify-center gap-2 rounded-2xl glass-card p-12 text-sm text-slate-600"><LoaderCircle className="h-5 w-5 animate-spin" />Loading faculty profile…</div> : activeSection === 'students' ? renderStudents() : activeSection === 'assessments' ? renderAssessments() : activeSection === 'competencies' ? renderCandidateInsights() : renderDrives()}
        </main>
      </div>
    </div>
    {selectedStudent && <StudentDialog student={selectedStudent} onClose={closeStudent} />}
  </div>;
}
