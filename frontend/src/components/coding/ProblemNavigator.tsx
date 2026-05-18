"use client";

import { cn } from "@/lib/utils";
import { Problem } from "@/types/api";
import { PROBLEM_STATUS_COLORS, PROBLEM_STATUS } from "@/lib/constants";
import { Bookmark } from "lucide-react";

interface ProblemNavigatorProps {
  problems: Problem[];
  activeProblemId: number;
  onSelectProblem: (id: number) => void;
  statuses: Record<number, string>;
  onToggleBookmark: (id: number) => void;
}

export function ProblemNavigator({
  problems,
  activeProblemId,
  onSelectProblem,
  statuses,
  onToggleBookmark,
}: ProblemNavigatorProps) {
  return (
    <div className="flex h-full w-[80px] flex-col items-center gap-4 bg-[#1A1040] py-6 shadow-[inset_-1px_0_0_rgba(255,255,255,0.1)]">
      {problems.map((problem, idx) => {
        const status = statuses[problem.id] || PROBLEM_STATUS.NOT_ATTEMPTED;
        const color = PROBLEM_STATUS_COLORS[status];
        const isActive = activeProblemId === problem.id;
        const isMarked = status === PROBLEM_STATUS.MARKED_FOR_REVIEW;

        return (
          <div key={problem.id} className="group relative flex flex-col items-center gap-2">
            
            {/* Tooltip */}
            <div className="absolute left-14 top-2 z-50 hidden whitespace-nowrap rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white shadow-xl group-hover:block">
              <div className="flex items-center gap-2">
                <span>{problem.title}</span>
                <span 
                  className="h-2 w-2 rounded-full" 
                  style={{ backgroundColor: color }} 
                />
              </div>
              {/* Tooltip Arrow */}
              <div className="absolute -left-1 top-1/2 -translate-y-1/2 border-y-4 border-r-4 border-y-transparent border-r-gray-900" />
            </div>

            {/* Problem Box */}
            <button
              onClick={() => onSelectProblem(problem.id)}
              className={cn(
                "relative flex h-12 w-12 items-center justify-center rounded-xl font-heading text-lg font-bold text-white transition-all hover:scale-105 active:scale-95",
                isActive && "ring-2 ring-accent ring-offset-2 ring-offset-[#1A1040]"
              )}
              style={{ backgroundColor: color }}
              aria-label={`Problem ${idx + 1}: ${problem.title}`}
            >
              {idx + 1}
            </button>

            {/* Bookmark Toggle */}
            <button
              onClick={() => onToggleBookmark(problem.id)}
              className="text-white/40 transition-colors hover:text-white"
              title="Toggle Mark for Review"
            >
              <Bookmark
                className="h-5 w-5"
                fill={isMarked ? "currentColor" : "none"}
                strokeWidth={isMarked ? 0 : 2}
              />
            </button>
            
          </div>
        );
      })}
    </div>
  );
}
