"use client";

import { RunResult, SubmissionResult } from "@/types/api";
import { CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { VerdictBanner } from "../shared/VerdictBanner";
import { useEffect } from "react";

interface TestResultsPanelProps {
  runResults?: RunResult[];
  submitResult?: SubmissionResult;
  mode: "run" | "submit" | null;
}

export function TestResultsPanel({ runResults, submitResult, mode }: TestResultsPanelProps) {
  // Debug logging to verify data structure
  useEffect(() => {
    if (runResults && runResults.length > 0) {
      console.log("=== TEST RESULTS DEBUG ===");
      console.log("Full runResults:", runResults);
      console.log("First result:", runResults[0]);
      console.log("First result actual_output:", runResults[0].actual_output);
      console.log("First result passed:", runResults[0].passed);
      console.log("========================");
    }
  }, [runResults]);

  if (!mode) return null;

  return (
    <div className="flex h-full flex-col bg-[#1e1e1e] text-gray-300">
      {/* Header Tabs Area */}
      <div className="flex h-11 shrink-0 items-center border-b border-gray-800 bg-[#242424] px-2">
        <div className={cn(
          "flex h-full items-center border-b-2 px-4 text-sm font-medium",
          mode === "run" ? "border-teal-400 text-teal-400" : "border-transparent text-gray-500"
        )}>
          Testcase
        </div>
        <div className={cn(
          "flex h-full items-center border-b-2 px-4 text-sm font-medium",
          mode === "submit" ? "border-teal-400 text-teal-400" : "border-transparent text-gray-500"
        )}>
          Test Result
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {mode === "submit" && submitResult && (
          <div className="space-y-6">
            <VerdictBanner verdict={submitResult.verdict} message={`Score: ${submitResult.score} / 100`} />

            <div className="grid grid-cols-3 gap-4 border-t border-gray-800 pt-4">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Passed Cases</p>
                <p className="font-mono text-lg font-semibold text-gray-200">{submitResult.passed_cases}/{submitResult.total_cases}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Runtime</p>
                <p className="font-mono text-lg font-semibold text-gray-200">{submitResult.execution_time}s</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Memory</p>
                <p className="font-mono text-lg font-semibold text-gray-200">{submitResult.memory_used} MB</p>
              </div>
            </div>
          </div>
        )}

        {mode === "run" && runResults && (
          <div className="space-y-4">
            {runResults.map((res, i) => (
              <div key={i} className={cn("rounded-lg border p-4", res.passed ? "border-teal-800 bg-teal-900/20" : "border-red-800 bg-red-900/20")}>
                <div className="flex items-center gap-2 mb-3">
                  {res.passed ? <CheckCircle2 className="h-5 w-5 text-teal-400" /> : <XCircle className="h-5 w-5 text-red-400" />}
                  <span className="font-semibold text-gray-200">Case {i + 1}</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                  <div>
                    <p className="text-gray-500 mb-1">Input</p>
                    <pre className="bg-[#161616] p-2 border border-gray-800 rounded whitespace-pre-wrap text-gray-300">{res.input}</pre>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Expected Output</p>
                    <pre className="bg-[#161616] p-2 border border-gray-800 rounded whitespace-pre-wrap text-gray-300">{res.expected_output}</pre>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Actual Output</p>
                    <pre className="bg-[#161616] p-2 border border-gray-800 rounded whitespace-pre-wrap text-gray-300">
                      {res.actual_output !== null && res.actual_output !== undefined 
                        ? res.actual_output 
                        : "(No output)"}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
