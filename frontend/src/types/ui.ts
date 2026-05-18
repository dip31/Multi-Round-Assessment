import { Problem, RunResult, SubmissionResult } from "./api";

export interface DashboardProps {
  // Empty for now, will connect to store/API
}

export interface RoundCardProps {
  roundId: number;
  type: "aptitude" | "coding" | "interview";
  status: "pending" | "active" | "completed" | "terminated";
  score: number;
  roundNumber: number;
  onClick: () => void;
}

export interface ScoreRingProps {
  score: number;
  size?: "sm" | "lg";
  label?: string;
  className?: string;
}

export interface CodeEditorProps {
  problemId: number;
  language: string;
  onLanguageChange: (lang: string) => void;
  onRun: () => void;
  onSubmit: () => void;
  isSubmitting?: boolean;
}

export interface TestResultsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  runResults?: RunResult[];
  submitResult?: SubmissionResult;
  mode: "run" | "submit";
}
