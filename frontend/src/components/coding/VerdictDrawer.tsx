"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { VerdictBanner } from "../shared/VerdictBanner";
import { SubmissionResult } from "@/types/api";
import { cn } from "@/lib/utils";
import { VERDICT } from "@/lib/constants";

interface VerdictDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  result: SubmissionResult | null;
  problemTitle: string;
  onNextProblem?: () => void;
  isLastProblem?: boolean;
}

export function VerdictDrawer({
  isOpen,
  onClose,
  result,
  problemTitle,
  onNextProblem,
  isLastProblem = false,
}: VerdictDrawerProps) {
  const [animatedScore, setAnimatedScore] = useState(0);

  useEffect(() => {
    if (isOpen && result) {
      setAnimatedScore(0);
      const duration = 1500;
      const steps = 60;
      const stepTime = duration / steps;
      const increment = result.score / steps;

      let current = 0;
      const timer = setInterval(() => {
        current += increment;
        if (current >= result.score) {
          setAnimatedScore(result.score);
          clearInterval(timer);
        } else {
          setAnimatedScore(current);
        }
      }, stepTime);

      return () => clearInterval(timer);
    }
  }, [isOpen, result]);

  if (!isOpen || !result) return null;

  const isAccepted = result.verdict === VERDICT.ACCEPTED;
  const isPartial = result.verdict === VERDICT.PARTIAL || result.verdict === VERDICT.TIME_LIMIT_EXCEEDED;
  const isError = !isAccepted && !isPartial;

  return (
    <>
      {/* Background Overlay */}
      <div 
        className="fixed inset-0 z-40 bg-black/75 transition-opacity" 
        onClick={onClose}
        aria-hidden="true" 
      />

      {/* Drawer */}
      <div className={cn(
        "fixed bottom-0 left-0 right-0 z-50 flex h-[340px] flex-col rounded-t-2xl bg-white shadow-2xl transition-transform duration-300 ease-out",
        isOpen ? "translate-y-0" : "translate-y-full"
      )}>
        <div className="flex h-14 items-center justify-between border-b px-6">
          <h2 className="font-heading text-lg font-bold text-heading">{problemTitle}</h2>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
          
          <VerdictBanner 
            verdict={result.verdict} 
            message={result.verdict.replace(/_/g, " ").toUpperCase()} 
            className="w-auto flex-none justify-center border-none px-6 py-2 mb-4 drop-shadow-sm" 
          />

          <div className="font-mono text-[64px] font-bold leading-none tracking-tight">
            <span className={cn(
              isAccepted ? "text-teal-500" : isPartial ? "text-amber-500" : "text-coral-500"
            )}>
              {Math.round(animatedScore)}
            </span>
          </div>

          <div className="mt-4 w-full max-w-md">
            <div className="mb-2 flex justify-between text-sm font-medium text-gray-500">
              <span>Test Cases: {result.passed_cases} / {result.total_cases} passed</span>
              <span>{Math.round((result.passed_cases / Math.max(result.total_cases, 1)) * 100)}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={cn("h-full transition-all duration-1000", isError ? "bg-coral-500" : "bg-teal-500")}
                style={{ width: `${(result.passed_cases / Math.max(result.total_cases, 1)) * 100}%` }}
              />
            </div>
          </div>

          <div className="mt-6 flex gap-6 text-xs font-medium text-gray-400 font-mono">
            <span>Runtime: {result.execution_time}s</span>
            <span>Memory: {result.memory_used} MB</span>
            <span>Language: {result.language}</span>
          </div>
        </div>

        <div className="flex h-16 shrink-0 items-center justify-center gap-4 border-t bg-gray-50/50 px-6">
          <button onClick={onClose} className="rounded-lg border px-6 py-2 text-sm font-semibold transition-colors hover:bg-white text-gray-700">
            View Details
          </button>
          {!isAccepted && (
            <button onClick={onClose} className="rounded-lg bg-white border px-6 py-2 text-sm font-semibold transition-colors hover:bg-gray-50 text-gray-900 shadow-sm">
              Try Again
            </button>
          )}
          {isAccepted && (
            <button
              onClick={onNextProblem ?? onClose}
              className="rounded-lg bg-accent px-6 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-accent/90"
            >
              {isLastProblem ? "End Exam" : "Next Problem →"}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
