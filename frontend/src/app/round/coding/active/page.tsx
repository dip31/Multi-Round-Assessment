"use client";

import { X, Loader2, WifiOff } from "lucide-react";
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/store/sessionStore";
import { CodingLayout } from "@/components/coding/CodingLayout";
import { CountdownTimer } from "@/components/coding/CountdownTimer";
import { EndRoundButton } from "@/components/coding/EndRoundButton";
import { ProblemNavigator } from "@/components/coding/ProblemNavigator";
import { ProblemDescription } from "@/components/coding/ProblemDescription";
import { CodeEditor } from "@/components/coding/CodeEditor";
import { TestResultsPanel } from "@/components/coding/TestResultsPanel";
import { VerdictDrawer } from "@/components/coding/VerdictDrawer";
import { PROBLEM_STATUS, LANGUAGE } from "@/lib/constants";
import {
  MOCK_CODING_SESSION,
  MOCK_PROBLEMS,
  MOCK_RUN_RESULTS,
  MOCK_SUBMISSION_RESULT,
  MOCK_SUBMISSION_RESULT_PARTIAL
} from "@/lib/mockData";
import { SubmissionResult, Problem, RunResult } from "@/types/api";
import { useToast } from "@/components/shared/Toast";
import API from "@/lib/api";

/* ── Types for backend responses ─────────────────────────── */
interface ProblemListItem {
  id: number;
  title: string;
  difficulty: string;
  tags: string[];
  problem_order: number;
  status: string;
  marked_for_review: boolean;
}

interface SessionStatus {
  round_id: number;
  status: string;
  time_limit_minutes: number;
  end_time: string;
  time_remaining_seconds: number;
  problems: ProblemListItem[];
  all_problems_solved: boolean;
}

interface ProblemDetail {
  id: number;
  title: string;
  description: string;
  difficulty: string;
  tags: string[];
  input_format: string | null;
  output_format: string | null;
  constraints: string | null;
  visible_test_cases: { id: number; input_data: string; expected_output: string; case_order: number }[];
}

export default function ActiveCodingRoundPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { activeRoundId, setActiveRound } = useSessionStore();

  // Core state
  const [loading, setLoading] = useState(true);
  const [sessionData, setSessionData] = useState<SessionStatus | null>(null);
  const [problemList, setProblemList] = useState<ProblemListItem[]>([]);
  const [activeProblemId, setActiveProblemId] = useState<number | null>(null);
  const [problemDetail, setProblemDetail] = useState<ProblemDetail | null>(null);
  const [problemCache, setProblemCache] = useState<Record<number, ProblemDetail>>({});
  const [loadingProblem, setLoadingProblem] = useState(false);

  // Editor state
  const [language, setLanguage] = useState<string>(LANGUAGE.PYTHON);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitDisabled, setSubmitDisabled] = useState(false);
  const [panelMode, setPanelMode] = useState<"run" | "submit" | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [submissionResult, setSubmissionResult] = useState<SubmissionResult | null>(null);
  const [runResults, setRunResults] = useState<RunResult[]>([]);
  const [roundEnded, setRoundEnded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);

  // Determine round_id — from store or try to discover from session
  const roundId = activeRoundId;

  /* ── Initial Load: Fetch Session Status ─────────────────── */
  const fetchSession = useCallback(async (rid: number) => {
    try {
      const res = await API.get(`/coding/session/${rid}`);
      const data: SessionStatus = res.data;
      setSessionData(data);
      setProblemList(data.problems);

      if (data.status === "completed" || data.status === "terminated") {
        setRoundEnded(true);
        toast({ title: "Round Complete", description: "This round has ended." });
        setTimeout(() => router.push(`/round/coding/result`), 3000);
        return;
      }

      // Set first problem as active if none selected
      if (!activeProblemId && data.problems.length > 0) {
        setActiveProblemId(data.problems[0].id);
      }
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError("Coding session not found. Please start from the dashboard.");
      } else if (err.response?.status === 401) {
        window.dispatchEvent(new CustomEvent("auth:expired"));
      } else {
        // Fallback to mock data on error
        setSessionData(null);
        setProblemList(MOCK_PROBLEMS.map((p, i) => ({
          id: p.id, title: p.title, difficulty: p.difficulty,
          tags: p.tags, problem_order: i + 1,
          status: "not_attempted", marked_for_review: false
        })));
        if (!activeProblemId) setActiveProblemId(MOCK_PROBLEMS[0].id);
        toast({ title: "Connection issue", description: "Using cached data. Will retry.", variant: "destructive" });
      }
    } finally {
      setLoading(false);
    }
  }, [activeProblemId, router, toast]);

  useEffect(() => {
    if (roundId) {
      fetchSession(roundId);
    } else {
      // No round_id in store — try to get from session status
      API.get("/session/status").then(res => {
        const codingRound = res.data.rounds?.find((r: any) => r.round_type === "coding" && (r.status === "active" || r.status === "in_progress"));
        if (codingRound) {
          setActiveRound(codingRound.id, "coding");
          fetchSession(codingRound.id);
        } else {
          setError("No active coding round. Please start from the dashboard.");
          setLoading(false);
        }
      }).catch(() => {
        // Last fallback to mocks
        setLoading(false);
        setProblemList(MOCK_PROBLEMS.map((p, i) => ({
          id: p.id, title: p.title, difficulty: p.difficulty,
          tags: p.tags, problem_order: i + 1,
          status: "not_attempted", marked_for_review: false
        })));
        setActiveProblemId(MOCK_PROBLEMS[0].id);
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Poll session status every 60s for timer sync ──────── */
  useEffect(() => {
    if (!roundId || roundEnded) return;
    statusPollRef.current = setInterval(() => {
      API.get(`/coding/session/${roundId}`).then(res => {
        const data: SessionStatus = res.data;
        setSessionData(data);
        if (data.status === "completed" || data.status === "terminated") {
          setRoundEnded(true);
          toast({ title: "Time's Up", description: "Submissions are now closed.", variant: "destructive" });
          setTimeout(() => router.push("/round/coding/result"), 5000);
        }
      }).catch(() => { /* silently skip poll failure */ });
    }, 60000);
    return () => { if (statusPollRef.current) clearInterval(statusPollRef.current); };
  }, [roundId, roundEnded, router, toast]);

  /* ── Poll problem statuses every 30s ───────────────────── */
  useEffect(() => {
    if (!roundId || roundEnded) return;
    pollRef.current = setInterval(() => {
      API.get(`/coding/problems/${roundId}`).then(res => {
        setProblemList(res.data);
      }).catch(() => {});
    }, 30000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [roundId, roundEnded]);

  /* ── Fetch Problem Detail ──────────────────────────────── */
  const fetchProblemDetail = useCallback(async (pid: number) => {
    if (problemCache[pid]) {
      setProblemDetail(problemCache[pid]);
      return;
    }
    if (!roundId) return;
    setLoadingProblem(true);
    try {
      const res = await API.get(`/coding/problem/${roundId}/${pid}`);
      const detail: ProblemDetail = res.data;
      setProblemDetail(detail);
      setProblemCache(prev => ({ ...prev, [pid]: detail }));
    } catch (err: any) {
      if (err.response?.status === 403) {
        toast({ title: "Error", description: "This problem is not part of your assessment.", variant: "destructive" });
        if (problemList.length > 0) setActiveProblemId(problemList[0].id);
      } else {
        // Fallback to mock
        const mock = MOCK_PROBLEMS.find(p => p.id === pid);
        if (mock) setProblemDetail(mock as any);
      }
    } finally {
      setLoadingProblem(false);
    }
  }, [roundId, problemCache, problemList, toast]);

  useEffect(() => {
    if (activeProblemId) fetchProblemDetail(activeProblemId);
  }, [activeProblemId, fetchProblemDetail]);

  /* ── Derive display data ───────────────────────────────── */
  const statuses: Record<number, string> = {};
  for (const p of problemList) {
    statuses[p.id] = p.marked_for_review ? PROBLEM_STATUS.MARKED_FOR_REVIEW : p.status;
  }

  // Bridge ProblemListItem → Problem shape for ProblemNavigator
  const navigatorProblems: Problem[] = problemList.map(p => ({
    id: p.id,
    title: p.title,
    difficulty: p.difficulty as "easy" | "medium" | "hard",
    tags: p.tags,
    description: "",
    input_format: "",
    output_format: "",
    constraints: "",
    examples: [],
    visible_test_cases: [],
  }));

  // Bridge ProblemDetail → Problem shape for ProblemDescription
  const activeProblemForDesc: Problem | null = problemDetail ? {
    id: problemDetail.id,
    title: problemDetail.title,
    difficulty: problemDetail.difficulty as "easy" | "medium" | "hard",
    tags: problemDetail.tags,
    description: problemDetail.description,
    input_format: problemDetail.input_format || "",
    output_format: problemDetail.output_format || "",
    constraints: problemDetail.constraints || "",
    examples: [],
    visible_test_cases: problemDetail.visible_test_cases.map(tc => ({
      id: String(tc.id),
      input_data: tc.input_data,
      expected_output: tc.expected_output,
    })),
  } : null;

  const isMarked = activeProblemId ? statuses[activeProblemId] === PROBLEM_STATUS.MARKED_FOR_REVIEW : false;

  const sortedProblems = [...problemList].sort(
    (a, b) => a.problem_order - b.problem_order
  );
  const activeProblemIndex = activeProblemId
    ? sortedProblems.findIndex((p) => p.id === activeProblemId)
    : -1;
  const isLastProblem =
    activeProblemIndex >= 0 && activeProblemIndex === sortedProblems.length - 1;

  const resetEditorPanels = useCallback(() => {
    setPanelMode(null);
    setRunResults([]);
    setSubmissionResult(null);
    setIsDrawerOpen(false);
  }, []);

  const handleSelectProblem = useCallback(
    (pid: number) => {
      if (pid === activeProblemId) return;
      resetEditorPanels();
      setActiveProblemId(pid);
    },
    [activeProblemId, resetEditorPanels]
  );

  const goToNextProblemOrEnd = useCallback(
    async (currentList: ProblemListItem[], currentProblemId: number) => {
      const sorted = [...currentList].sort(
        (a, b) => a.problem_order - b.problem_order
      );
      const idx = sorted.findIndex((p) => p.id === currentProblemId);
      const next = idx >= 0 ? sorted[idx + 1] : undefined;

      resetEditorPanels();

      if (next) {
        setActiveProblemId(next.id);
        toast({
          title: "Correct!",
          description: `Moving to: ${next.title}`,
        });
        return;
      }

      if (!roundId) return;
      try {
        await API.post(`/coding/session/${roundId}/end`);
        setRoundEnded(true);
        toast({
          title: "All problems solved!",
          description: "Your coding round has been submitted.",
        });
        router.push("/round/coding/result");
      } catch (err: any) {
        toast({
          title: "Error",
          description:
            err.response?.data?.detail || "Failed to end round.",
          variant: "destructive",
        });
      }
    },
    [resetEditorPanels, roundId, router, toast]
  );

  /* ── Run Code ──────────────────────────────────────────── */
  const handleRun = async (code: string) => {
    if (!activeProblemId || !roundId) return;
    setIsSubmitting(true);
    setPanelMode(null);
    setIsDrawerOpen(false);

    try {
      const res = await API.post("/coding/run", {
        round_id: roundId,
        problem_id: activeProblemId,
        code,
        language,
      });
      setRunResults(res.data.results.map((r: any) => ({
        input: r.input_data,
        expected_output: r.expected_output,
        actual_output: r.actual_output,
        passed: r.passed,
      })));
      setPanelMode("run");
    } catch (err: any) {
      if (err.response?.status === 503) {
        toast({
          title: "Execution Unavailable",
          description:
            "Code execution service is temporarily unavailable. Judge0 may be starting up. Please wait 30 seconds and try again.",
          variant: "destructive",
          duration: 6000,
        });
      } else if (err.response?.status === 403) {
        toast({
          title: "Time's Up",
          description: "Round time has expired. Submissions are closed.",
          variant: "destructive",
        });
        setRoundEnded(true);
        setSubmitDisabled(true);
      } else {
        toast({
          title: "Run Failed",
          description: "Run failed. Your code is preserved. Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ── Submit Code ───────────────────────────────────────── */
  const handleSubmit = async (code: string) => {
    if (!activeProblemId || !roundId) return;
    setIsSubmitting(true);
    setPanelMode(null);
    setIsDrawerOpen(false);

    try {
      const res = await API.post("/coding/submit", {
        round_id: roundId,
        problem_id: activeProblemId,
        code,
        language,
      });
      const result = res.data;
      setSubmissionResult({
        verdict: result.verdict,
        score: result.score,
        passed_cases: result.passed_cases,
        total_cases: result.total_cases,
        execution_time: result.execution_time || 0,
        memory_used: result.memory_used || 0,
        language,
      });
      setPanelMode("submit");
      setIsDrawerOpen(true);

      // Refresh problem statuses and session after submit
      try {
        const [problemsRes, sessionRes] = await Promise.all([
          API.get(`/coding/problems/${roundId}`),
          API.get(`/coding/session/${roundId}`),
        ]);
        setProblemList(problemsRes.data);
        setSessionData(sessionRes.data);
      } catch {
        /* keep local list if refresh fails */
      }
    } catch (err: any) {
      if (err.response?.status === 503) {
        toast({
          title: "Submission Failed",
          description:
            "Submission failed — code execution unavailable. This was NOT counted. Please try again shortly.",
          variant: "destructive",
          duration: 8000,
        });
        setSubmitDisabled(false);
      } else if (err.response?.status === 403) {
        toast({
          title: "Time's Up",
          description: "Round time has expired. Submissions are closed.",
          variant: "destructive",
        });
        setRoundEnded(true);
        setSubmitDisabled(true);
      } else {
        toast({
          title: "Submit Failed",
          description: "Submission failed. Your code is saved. Please retry.",
          variant: "destructive",
        });
        setSubmitDisabled(false);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ── Mark for Review (optimistic) ──────────────────────── */
  const handleToggleBookmark = async (pid: number) => {
    if (!roundId) return;
    // Optimistic update
    setProblemList(prev => prev.map(p =>
      p.id === pid ? { ...p, marked_for_review: !p.marked_for_review } : p
    ));
    try {
      await API.post(`/coding/problem/${roundId}/${pid}/mark-review`);
    } catch {
      // Revert on error
      setProblemList(prev => prev.map(p =>
        p.id === pid ? { ...p, marked_for_review: !p.marked_for_review } : p
      ));
      toast({ title: "Error", description: "Could not update review status.", variant: "destructive" });
    }
  };

  /* ── End Round ─────────────────────────────────────────── */
  const handleEndRound = async () => {
    if (!roundId) return;
    try {
      await API.post(`/coding/session/${roundId}/end`);
      setRoundEnded(true);
      toast({ title: "Round Ended", description: "Your coding round has been submitted successfully." });
      router.push("/round/coding/result");
    } catch (err: any) {
      toast({ title: "Error", description: err.response?.data?.detail || "Failed to end round.", variant: "destructive" });
    }
  };

  const handleTimerExpire = () => {
    setRoundEnded(true);
    toast({ title: "Time's Up", description: "Submissions are now closed. Redirecting...", variant: "destructive" });
    setTimeout(() => router.push("/round/coding/result"), 5000);
  };

  /* ── Error & Loading States ────────────────────────────── */
  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a] text-white">
        <div className="text-center space-y-4">
          <WifiOff className="h-12 w-12 text-red-400 mx-auto" />
          <h2 className="text-xl font-bold">{error}</h2>
          <button onClick={() => router.push("/dashboard")} className="rounded-lg bg-accent px-6 py-2 text-white font-semibold">
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
        <Loader2 className="h-8 w-8 animate-spin text-accent" />
      </div>
    );
  }

  const timerSeconds = sessionData?.time_remaining_seconds ?? MOCK_CODING_SESSION.time_remaining_seconds;

  return (
    <CodingLayout>
      {/* Header Bar */}
      <header className="sticky top-0 z-50 flex h-14 w-full shrink-0 flex-col bg-[#0A0F1E] shadow-sm">
        <div className="flex h-full w-full items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-accent/20 text-accent">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="font-heading text-sm font-semibold text-accent-300">Coding Round</span>
          </div>

          <div className="absolute left-1/2 -translate-x-1/2">
            <CountdownTimer initialSeconds={timerSeconds} onExpire={handleTimerExpire} />
          </div>

          {sessionData && !roundEnded && (
            <EndRoundButton 
              onEndRound={handleEndRound} 
              allProblemsSolved={sessionData.all_problems_solved}
            />
          )}
          
        </div>
        <div className="h-[3px] w-full bg-[#1A1040]">
          <div className="h-full w-[85%] bg-accent transition-all duration-[60s]" />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex h-[calc(100vh-56px)] w-full overflow-hidden bg-[#0a0a0a]">
        <ProblemNavigator
          problems={navigatorProblems}
          activeProblemId={activeProblemId || 0}
          onSelectProblem={handleSelectProblem}
          statuses={statuses}
          onToggleBookmark={handleToggleBookmark}
        />

        <div className="flex flex-1 relative bg-[#1a1a1a] gap-[2px]">
          {/* Left: Problem Description */}
          <div className="w-[45%] h-full shrink-0 z-10">
            {loadingProblem ? (
              <div className="flex h-full items-center justify-center bg-[#1a1a1a]">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : activeProblemForDesc ? (
              <ProblemDescription
                problem={activeProblemForDesc}
                isMarked={isMarked}
                onToggleBookmark={() => activeProblemId && handleToggleBookmark(activeProblemId)}
              />
            ) : (
              <div className="flex h-full items-center justify-center bg-[#1a1a1a] text-gray-500">
                Select a problem to view
              </div>
            )}
          </div>

          {/* Right: Editor + Terminal */}
          <div className="flex min-w-0 flex-1 flex-col relative z-0 bg-[#1e1e1e]">
            <div className="w-full relative transition-all overflow-hidden" style={{ height: panelMode ? "55%" : "100%" }}>
              <CodeEditor
                key={activeProblemId ?? "none"}
                problemId={activeProblemId || 0}
                language={language}
                onLanguageChange={setLanguage}
                onRun={handleRun}
                onSubmit={handleSubmit}
                isSubmitting={isSubmitting}
                submitDisabled={submitDisabled}
              />
            </div>

            <div
              className="w-full bg-[#1e1e1e] transition-all duration-300 ease-in-out border-t border-gray-800"
              style={{ height: panelMode ? "45%" : "0", opacity: panelMode ? 1 : 0, overflow: panelMode ? "visible" : "hidden" }}
            >
              <div className="flex h-full w-full flex-col relative">
                <div className="absolute top-2 right-4 z-10" style={{ display: panelMode ? "block" : "none" }}>
                  <button onClick={() => setPanelMode(null)} className="rounded p-1 text-gray-500 hover:bg-gray-700 hover:text-white transition-colors" title="Close Panel">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <TestResultsPanel
                  mode={panelMode}
                  runResults={runResults.length > 0 ? runResults : (MOCK_RUN_RESULTS as any)}
                  submitResult={submissionResult as any}
                />
              </div>
            </div>
          </div>
        </div>
      </main>

      <VerdictDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        result={submissionResult as any}
        problemTitle={activeProblemForDesc?.title || ""}
        isLastProblem={isLastProblem}
        onNextProblem={() => {
          if (activeProblemId) {
            goToNextProblemOrEnd(problemList, activeProblemId);
          }
        }}
      />

      {/* Rounded ended banner */}
      {roundEnded && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80">
          <div className="text-center space-y-4">
            <h2 className="text-3xl font-bold text-white">Time is Up</h2>
            <p className="text-gray-400">Submissions are closed. Redirecting to results...</p>
            <Loader2 className="h-6 w-6 animate-spin text-accent mx-auto" />
          </div>
        </div>
      )}
    </CodingLayout>
  );
}
