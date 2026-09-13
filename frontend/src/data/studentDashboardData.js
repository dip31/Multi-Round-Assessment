/**
 * Mock data for the Student placement-prep dashboard (`/student/dashboard`).
 *
 * SHAPE CONTRACT
 * --------------
 * Field names deliberately mirror the backend ORM vocabulary so that swapping
 * this file for a real `api.get('/dashboard/student')` call is mechanical:
 *   - `roundType`  ->  AssessmentRound.round_type  ('aptitude' | 'coding' | 'interview')
 *   - `status`     ->  AssessmentRound.status      ('pending' | 'active' | 'completed' | 'terminated')
 *   - `score`      ->  AssessmentRound.score       (float, 0-100)
 *   - ISO-8601 strings for every timestamp (the API returns naive ISO datetimes).
 *
 * NOTE: This is UI-only mock data. No engine, no persistence, no real scoring.
 */

export const studentDashboardData = {
  // ── Identity ───────────────────────────────────────────────────────
  profile: {
    id: 'stu_10428',
    name: 'Ananya Sharma',
    initials: 'AS',
    rollNumber: '21CSE1042',
    department: 'Computer Science & Engineering',
    departmentShort: 'CSE',
    graduationYear: 2027,
    email: 'ananya.sharma@college.edu',
    avatarUrl: null,
  },

  // ── Headline readiness score ───────────────────────────────────────
  readiness: {
    score: 71,
    band: 'On track',          // 'At risk' | 'Developing' | 'On track' | 'Placement ready'
    delta: 6,                  // points vs. previous evaluation
    deltaLabel: 'vs. last month',
    roundsCounted: 2,
    roundsTotal: 3,
    updatedAt: '2026-09-09T18:30:00',
    breakdown: [
      { label: 'Aptitude', score: 78, weight: 0.3 },
      { label: 'Coding', score: 64, weight: 0.45 },
      { label: 'Interview', score: null, weight: 0.25 },
    ],
  },

  // ── Top-of-page stat strip ─────────────────────────────────────────
  stats: [
    {
      id: 'assessments-taken',
      label: 'Assessments taken',
      value: 12,
      unit: null,
      delta: 3,
      trend: 'up',
      hint: '3 more than last month',
    },
    {
      id: 'avg-score',
      label: 'Average score',
      value: 71,
      unit: '%',
      delta: 6,
      trend: 'up',
      hint: 'Across all completed rounds',
    },
    {
      id: 'practice-hours',
      label: 'Practice hours',
      value: 28.5,
      unit: 'h',
      delta: 4.5,
      trend: 'up',
      hint: 'Logged this semester',
    },
    {
      id: 'batch-percentile',
      label: 'Batch percentile',
      value: 68,
      unit: 'th',
      delta: -2,
      trend: 'down',
      hint: 'Among 240 CSE students',
    },
  ],

  // ── The three assessment rounds ────────────────────────────────────
  rounds: [
    {
      id: 'rnd_aptitude',
      roundType: 'aptitude',
      title: 'Aptitude Test',
      description: 'Adaptive reasoning, quantitative and verbal ability.',
      status: 'completed',
      score: 78,
      maxScore: 100,
      durationMinutes: 30,
      questionsAttempted: 20,
      questionsTotal: 20,
      attemptedAt: '2026-08-28T10:15:00',
      route: '/aptitude',
    },
    {
      id: 'rnd_coding',
      roundType: 'coding',
      title: 'Coding Challenge',
      description: 'Algorithmic problem solving with live evaluation.',
      status: 'completed',
      score: 64,
      maxScore: 100,
      durationMinutes: 30,
      questionsAttempted: 2,
      questionsTotal: 3,
      attemptedAt: '2026-09-02T14:40:00',
      route: '/coding',
    },
    {
      id: 'rnd_interview',
      roundType: 'interview',
      title: 'AI Mock Interview',
      description: 'Voice-based conversational interview, resume-aware.',
      status: 'pending',
      score: null,
      maxScore: 100,
      durationMinutes: 25,
      questionsAttempted: 0,
      questionsTotal: 8,
      attemptedAt: null,
      route: '/resume-upload',
    },
  ],

  // ── Performance over time (line / area chart) ──────────────────────
  performanceTrend: [
    { date: '2026-04-12', label: 'Apr', aptitude: 52, coding: 38, interview: null, overall: 46 },
    { date: '2026-05-10', label: 'May', aptitude: 58, coding: 44, interview: null, overall: 52 },
    { date: '2026-06-14', label: 'Jun', aptitude: 63, coding: 49, interview: 55, overall: 56 },
    { date: '2026-07-12', label: 'Jul', aptitude: 69, coding: 53, interview: 61, overall: 61 },
    { date: '2026-08-09', label: 'Aug', aptitude: 74, coding: 58, interview: 64, overall: 65 },
    { date: '2026-09-06', label: 'Sep', aptitude: 78, coding: 64, interview: 68, overall: 71 },
  ],

  // ── Skill breakdown (radar / horizontal bars) ──────────────────────
  skills: [
    { skill: 'Quantitative', score: 82, benchmark: 70 },
    { skill: 'Logical Reasoning', score: 76, benchmark: 70 },
    { skill: 'Verbal Ability', score: 71, benchmark: 68 },
    { skill: 'Data Structures', score: 64, benchmark: 72 },
    { skill: 'Algorithms', score: 58, benchmark: 72 },
    { skill: 'Communication', score: 68, benchmark: 65 },
  ],

  // ── Scheduled / upcoming work ──────────────────────────────────────
  upcoming: [
    {
      id: 'up_001',
      title: 'Mock Interview — Round 3',
      type: 'interview',
      scheduledFor: '2026-09-15T11:00:00',
      durationMinutes: 25,
      status: 'scheduled',
      mandatory: true,
      location: 'Online — proctored',
    },
    {
      id: 'up_002',
      title: 'TCS NQT Practice Set',
      type: 'aptitude',
      scheduledFor: '2026-09-18T09:30:00',
      durationMinutes: 45,
      status: 'open',
      mandatory: false,
      location: 'Online',
    },
    {
      id: 'up_003',
      title: 'Placement Drive — Infosys',
      type: 'drive',
      scheduledFor: '2026-09-24T10:00:00',
      durationMinutes: 180,
      status: 'registration-open',
      mandatory: false,
      location: 'Campus — Block C Auditorium',
    },
  ],

  // ── Personalised practice recommendations ──────────────────────────
  recommendations: [
    {
      id: 'rec_001',
      title: 'Graph traversal patterns',
      reason: 'Algorithms is your lowest skill at 58, 14 points below batch benchmark.',
      category: 'Algorithms',
      difficulty: 'medium',
      estimatedMinutes: 40,
      ctaLabel: 'Start practice',
    },
    {
      id: 'rec_002',
      title: 'Time & work — speed drills',
      reason: 'You averaged 94s per question vs. the 60s target in your last aptitude round.',
      category: 'Quantitative',
      difficulty: 'easy',
      estimatedMinutes: 20,
      ctaLabel: 'Start drills',
    },
    {
      id: 'rec_003',
      title: 'STAR-method answer framing',
      reason: 'Interview feedback flagged unstructured responses on behavioural questions.',
      category: 'Communication',
      difficulty: 'easy',
      estimatedMinutes: 25,
      ctaLabel: 'Review guide',
    },
    {
      id: 'rec_004',
      title: 'Dynamic programming — knapsack family',
      reason: 'Appeared in 3 of your last 5 target-company question sets.',
      category: 'Algorithms',
      difficulty: 'hard',
      estimatedMinutes: 60,
      ctaLabel: 'Start practice',
    },
  ],

  // ── Recent activity feed ───────────────────────────────────────────
  activity: [
    {
      id: 'act_001',
      type: 'coding',
      title: 'Completed Coding Challenge',
      detail: 'Scored 64% — 2 of 3 problems solved',
      timestamp: '2026-09-02T14:40:00',
      status: 'completed',
    },
    {
      id: 'act_002',
      type: 'resume',
      title: 'Resume updated',
      detail: 'Parsed successfully — 3 new skills detected',
      timestamp: '2026-08-30T09:12:00',
      status: 'completed',
    },
    {
      id: 'act_003',
      type: 'aptitude',
      title: 'Completed Aptitude Test',
      detail: 'Scored 78% — personal best',
      timestamp: '2026-08-28T10:15:00',
      status: 'completed',
    },
    {
      id: 'act_004',
      type: 'interview',
      title: 'Mock Interview attempt ended early',
      detail: 'Session terminated — microphone permission denied',
      timestamp: '2026-08-21T16:05:00',
      status: 'terminated',
    },
    {
      id: 'act_005',
      type: 'aptitude',
      title: 'Completed Aptitude Test',
      detail: 'Scored 74% — improved 5 points',
      timestamp: '2026-08-09T11:30:00',
      status: 'completed',
    },
  ],

  // ── Actionable alerts ──────────────────────────────────────────────
  alerts: [
    {
      id: 'alr_001',
      severity: 'warning',
      title: 'Interview round not attempted',
      message:
        'Your placement readiness is capped until you complete the mock interview round.',
      actionLabel: 'Start interview',
      actionRoute: '/resume-upload',
    },
    {
      id: 'alr_002',
      severity: 'info',
      title: 'Infosys drive registration closes in 6 days',
      message: 'Eligibility requires a readiness score of 70 or above. You are at 71.',
      actionLabel: 'View drive',
      actionRoute: null,
    },
  ],
};

export default studentDashboardData;
