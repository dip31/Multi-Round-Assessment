export const REPORT_SCENARIOS = [
  {
    id: 'full', label: 'A · Full assessment', company: 'TechNova Solutions', role: 'Software Development Engineer',
    drive: 'Campus Placement Practice Drive', date: '18 February 2026',
    rounds: [
      { id: 'aptitude', name: 'Aptitude Assessment', type: 'aptitude', status: 'completed', evaluated: true,
        questions: [
          { number: 1, topic: 'Logical Reasoning', difficulty: 'Easy', text: 'Find the next number: 3, 6, 12, 24, __.', selected: '48', correct: '48', state: 'correct', explanation: 'Each term doubles.', seconds: 42 },
          { number: 2, topic: 'Data Interpretation', difficulty: 'Medium', text: 'A value rises from 80 to 100. What is the percentage increase?', selected: '20%', correct: '25%', state: 'incorrect', explanation: 'The increase is 20, divided by the original value 80.', seconds: 68 },
          { number: 3, topic: 'Logical Reasoning', difficulty: 'Medium', text: 'If all roses are flowers, which statement must be true?', selected: 'All flowers are roses', correct: 'All roses are flowers', state: 'incorrect', explanation: 'The premise only guarantees that every rose is a flower.', seconds: 55 },
          { number: 4, topic: 'Data Interpretation', difficulty: 'Easy', text: 'What is the average of 4, 6, and 8?', selected: '6', correct: '6', state: 'correct', explanation: 'Their sum is 18; 18 divided by 3 is 6.', seconds: 31 },
          { number: 5, topic: 'Logical Reasoning', difficulty: 'Easy', text: 'Which item does not belong: square, triangle, circle, metre?', selected: 'metre', correct: 'metre', state: 'correct', explanation: 'A metre is a unit of length; the others are shapes.', seconds: 28 },
          { number: 6, topic: 'Data Interpretation', difficulty: 'Medium', text: 'A team completes 3 of 5 tasks. What fraction remains?', selected: '2/5', correct: '2/5', state: 'correct', explanation: 'Five tasks total minus three complete leaves two.', seconds: 39 },
          { number: 7, topic: 'Logical Reasoning', difficulty: 'Medium', text: 'A is taller than B, and B is taller than C. Who is shortest?', selected: 'C', correct: 'C', state: 'correct', explanation: 'The ordering is A, then B, then C from tallest to shortest.', seconds: 47 },
          { number: 8, topic: 'Data Interpretation', difficulty: 'Hard', text: 'A chart value changes from 50 to 65. What is the increase?', selected: null, correct: '30%', state: 'unanswered', explanation: 'The increase is 15/50 × 100 = 30%.', seconds: null },
        ],
      },
      { id: 'coding', name: 'Coding Assessment', type: 'coding', status: 'completed', evaluated: true,
        problems: [
          { title: 'Pair Sum', difficulty: 'Easy', attempted: true, solved: true, passed: 10, failed: 0, total: 10, description: 'All 10 of 10 sample test cases passed.', practice: 'Try a follow-up using a hash map to compare approaches.' },
          { title: 'Longest Unique Window', difficulty: 'Medium', attempted: true, solved: false, passed: 5, failed: 3, total: 8, description: 'Three of eight sample test cases failed; the sample indicates an edge-case gap.', practice: 'Practice sliding-window problems with repeated characters and boundary cases.' },
        ],
      },
      { id: 'technical', name: 'Technical Interview', type: 'interview', status: 'completed', evaluated: true,
        rubric: [{ name: 'Technical correctness', score: 4, outOf: 5, note: 'Responses correctly described indexing and query filtering.' }, { name: 'Problem solving', score: 3, outOf: 5, note: 'The approach was sound; edge-case discussion was brief.' }, { name: 'Explanation clarity', score: 4, outOf: 5, note: 'The solution steps were explained in a clear sequence.' }],
        questions: [{ prompt: 'How would you find duplicate values in a table?', feedback: 'The response identified grouping as an approach; add how the count condition filters duplicates.' }, { prompt: 'What is the difference between a process and a thread?', feedback: 'The response distinguished execution units and mentioned shared process resources.' }],
      },
    ],
  },
  {
    id: 'technical-drive', label: 'B · Technical drive', company: 'Northstar Digital', role: 'Backend Engineer', drive: 'Technical Practice Drive', date: '12 February 2026',
    rounds: [
      { id: 'coding', name: 'Coding Assessment', type: 'coding', status: 'completed', evaluated: true, problems: [{ title: 'Merge Sorted Lists', difficulty: 'Medium', attempted: true, solved: true, passed: 7, failed: 0, total: 7, description: 'All 7 of 7 sample test cases passed.', practice: 'Compare iterative and recursive merge implementations.' }] },
      { id: 'technical', name: 'Technical Interview', type: 'interview', status: 'completed', evaluated: true, rubric: [{ name: 'Technical correctness', score: 3, outOf: 5, note: 'The response covered the core concept; include a concrete example.' }, { name: 'Problem solving', score: 4, outOf: 5, note: 'The answer broke the problem into clear steps.' }], questions: [{ prompt: 'How would you handle a slow database query?', feedback: 'The response suggested examining the query plan; also consider indexes and measured query cost.' }] },
    ],
  },
  {
    id: 'coding-only', label: 'C · Coding-only drive', company: 'Maple Systems', role: 'Junior Developer', drive: 'Coding Skills Practice', date: '9 February 2026',
    rounds: [{ id: 'coding', name: 'Coding Assessment', type: 'coding', status: 'completed', evaluated: true, problems: [{ title: 'Balanced Brackets', difficulty: 'Easy', attempted: true, solved: false, passed: 4, failed: 2, total: 6, description: 'Two of six sample test cases failed, including a nested input.', practice: 'Practice stack-based parsing with nested and empty inputs.' }] }],
  },
  {
    id: 'incomplete', label: 'D · Incomplete drive', company: 'Cedar Labs', role: 'Software Engineer', drive: 'Multi-round Practice Drive', date: '20 February 2026',
    rounds: [
      { id: 'coding', name: 'Coding Assessment', type: 'coding', status: 'completed', evaluated: true, problems: [{ title: 'Array Rotation', difficulty: 'Medium', attempted: true, solved: true, passed: 6, failed: 0, total: 6, description: 'All 6 of 6 sample test cases passed.', practice: 'Explore the in-place approach and its space complexity.' }] },
      { id: 'technical', name: 'Technical Interview', type: 'interview', status: 'pending', evaluated: false, questions: [] },
    ],
  },
  {
    id: 'evaluation-pending', label: 'E · Evaluation pending', company: 'Harbor Analytics', role: 'Data Engineer', drive: 'Assessment Review Preview', date: '21 February 2026',
    rounds: [
      { id: 'coding', name: 'Coding Assessment', type: 'coding', status: 'evaluation-pending', attempted: true, evaluated: false, problems: [] },
      { id: 'technical', name: 'Technical Interview', type: 'interview', status: 'pending', evaluated: false, questions: [] },
    ],
  },
];

export function getScenario(id) {
  return REPORT_SCENARIOS.find((scenario) => scenario.id === id) || REPORT_SCENARIOS[0];
}

export function getRoundSummary(rounds) {
  const completed = rounds.filter((round) => round.status === 'completed').length;
  const results = rounds.filter((round) => round.evaluated).length;
  const attemptedPending = rounds.some((round) => round.status === 'evaluation-pending' || (round.status === 'completed' && !round.evaluated));
  const fullyCompleted = rounds.length > 0 && completed === rounds.length && results === rounds.length;
  return {
    configured: rounds.length,
    completed,
    results,
    completionPercent: rounds.length ? completed / rounds.length * 100 : 0,
    status: fullyCompleted ? 'Completed' : attemptedPending ? 'Awaiting evaluation' : 'In progress',
  };
}

export function getAptitudeStats(round) {
  const questions = round?.questions || [];
  const correct = questions.filter((question) => question.state === 'correct').length;
  const incorrect = questions.filter((question) => question.state === 'incorrect').length;
  const unanswered = questions.filter((question) => question.state === 'unanswered').length;
  const answered = correct + incorrect;
  const topics = Object.groupBy ? Object.groupBy(questions, (question) => question.topic) : questions.reduce((result, question) => {
    (result[question.topic] ||= []).push(question);
    return result;
  }, {});
  const topicStats = Object.entries(topics).map(([name, items]) => {
    const topicCorrect = items.filter((question) => question.state === 'correct').length;
    const topicAnswered = items.filter((question) => question.state === 'correct' || question.state === 'incorrect').length;
    return { name, correct: topicCorrect, answered: topicAnswered, accuracy: topicAnswered ? topicCorrect / topicAnswered * 100 : null };
  });
  const timedQuestions = questions.filter((question) => Number.isFinite(question.seconds));
  const averageSeconds = timedQuestions.length
    ? timedQuestions.reduce((sum, question) => sum + question.seconds, 0) / timedQuestions.length
    : null;
  return { total: questions.length, correct, incorrect, unanswered, answered, accuracy: answered ? correct / answered * 100 : null, topicStats, averageSeconds };
}

export function getCodingStats(round) {
  const problems = round?.problems || [];
  const attempted = problems.filter((problem) => problem.attempted).length;
  const passed = problems.reduce((sum, problem) => sum + (problem.passed || 0), 0);
  const failed = problems.reduce((sum, problem) => sum + (problem.failed || 0), 0);
  const reportedTotal = problems.reduce((sum, problem) => sum + (problem.total || 0), 0);
  const evaluated = passed + failed;
  return { assigned: problems.length, attempted, solved: problems.filter((problem) => problem.solved).length, passed, failed, total: reportedTotal, evaluated, passRate: evaluated ? passed / evaluated * 100 : null };
}

export function getScenarioInsights(scenario) {
  const insights = [];
  scenario.rounds.forEach((round) => {
    if (!round.evaluated) return;
    if (round.type === 'aptitude') {
      const stats = getAptitudeStats(round);
      const comparable = stats.topicStats.filter((topic) => topic.accuracy !== null);
      if (comparable.length > 1) {
        const strongest = [...comparable].sort((a, b) => b.accuracy - a.accuracy)[0];
        const focus = [...comparable].sort((a, b) => a.accuracy - b.accuracy)[0];
        if (strongest.name !== focus.name) insights.push({ title: `${strongest.name} is a relative strength`, evidence: `${strongest.correct}/${strongest.answered} graded answers correct (${Math.round(strongest.accuracy)}%); ${focus.name}: ${focus.correct}/${focus.answered} (${Math.round(focus.accuracy)}%).`, why: 'The comparison uses only answered, graded questions in each topic.', action: `Review the missed ${focus.name} questions and practice similar examples.`, round: round.name, topic: focus.name, tone: 'strength' });
      }
      if (stats.unanswered) insights.push({ title: 'Some questions were left unanswered', evidence: `${stats.unanswered} of ${stats.total} questions were unanswered.`, why: 'Unanswered items do not count as incorrect, but they leave less evidence of topic mastery.', action: 'Practice pacing with a timed question set.', round: round.name, topic: null, tone: 'opportunity' });
    }
    if (round.type === 'coding') round.problems.forEach((problem) => {
      if (problem.failed > 0) insights.push({ title: `${problem.title} needs edge-case review`, evidence: `${problem.passed}/${problem.total} recorded sample test cases passed; ${problem.failed} failed.`, why: 'Failed samples point to cases worth checking; this test-case rate is not an overall coding score.', action: problem.practice, round: round.name, topic: problem.title, tone: 'opportunity' });
      else if (problem.attempted && problem.solved && problem.total > 0) insights.push({ title: `${problem.title} passed its recorded sample cases`, evidence: `${problem.passed}/${problem.total} recorded sample test cases passed.`, why: 'This supports a positive finding on the available sample cases, but does not establish hidden test performance.', action: problem.practice, round: round.name, topic: problem.title, tone: 'strength' });
    });
    if (round.type === 'interview') round.rubric?.forEach((item) => {
      if (item.score < item.outOf) insights.push({ title: `Develop ${item.name.toLowerCase()}`, evidence: `${item.score}/${item.outOf}: ${item.note}`, why: 'This is a rubric-specific coaching signal from the illustrative interview evaluation.', action: `Practice the ${item.name.toLowerCase()} dimension with one focused response.`, round: round.name, topic: item.name, tone: 'opportunity' });
    });
  });
  return insights.slice(0, 4);
}
