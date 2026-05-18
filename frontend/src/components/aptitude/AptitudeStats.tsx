"use client";

import { CheckCircle2, HelpCircle } from "lucide-react";

interface AptitudeStatsProps {
  answeredCount: number;
  totalCount: number;
}

export function AptitudeStats({ answeredCount, totalCount }: AptitudeStatsProps) {
  const remainingCount = totalCount - answeredCount;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
      <h3 className="font-heading text-lg font-bold text-heading text-center">Section Stats</h3>
      
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-teal-600">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Answered</span>
          </div>
          <span className="font-mono text-lg font-bold text-heading">{answeredCount}</span>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-gray-500">
            <HelpCircle className="h-5 w-5" />
            <span className="text-sm font-medium">Unanswered</span>
          </div>
          <span className="font-mono text-lg font-bold text-heading">{remainingCount}</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-4 flex flex-col gap-2">
        <div className="flex justify-between text-xs font-semibold text-gray-400 uppercase tracking-widest">
          <span>Progress</span>
          <span>{Math.round((answeredCount / totalCount) * 100)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full bg-teal-500 transition-all duration-500 ease-out"
            style={{ width: `${(answeredCount / totalCount) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
