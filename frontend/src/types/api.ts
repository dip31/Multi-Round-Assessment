export interface User {
  id: number;
  name: string;
  email: string;
}

export interface Round {
  id: number;
  round_type: "aptitude" | "coding" | "interview";
  status: "pending" | "active" | "completed" | "terminated";
  score: number;
}

export interface Session {
  id: number;
  status: "pending" | "in_progress" | "completed";
  total_score: number;
  rounds: Round[];
}

export interface TestCase {
  id: string;
  input_data: string;
  expected_output: string;
}

export interface Example {
  input: string;
  output: string;
  explanation?: string;
}

export interface Problem {
  id: number;
  title: string;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
  description: string;
  input_format: string;
  output_format: string;
  constraints: string;
  examples: Example[];
  visible_test_cases: TestCase[];
}

export interface CodingSession {
  round_id: number;
  status: "pending" | "active" | "completed" | "terminated";
  time_remaining_seconds: number;
  end_time: string;
  problems: Problem[];
}

export interface SubmissionResult {
  verdict: string;
  score: number;
  passed_cases: number;
  total_cases: number;
  execution_time: number;
  memory_used: number;
  language: string;
}

export interface RunResult {
  input: string;
  expected_output: string;
  actual_output: string;
  passed: boolean;
}
