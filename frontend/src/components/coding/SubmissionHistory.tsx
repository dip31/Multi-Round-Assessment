"use client";

import { useState, useEffect } from "react";
import { useSessionStore } from "@/store/sessionStore";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import API from "@/lib/api";

interface SubmissionItem {
  submission_id: number;
  status: string;
  score: number;
  submitted_at: string;
}

interface SubmissionHistoryProps {
  problemId: number;
}

const VERDICT_COLORS: Record<string, string> = {
  accepted: "bg-teal-100 text-teal-800",
  partial: "bg-amber-100 text-amber-800",
  wrong_answer: "bg-red-100 text-red-800",
  compilation_error: "bg-gray-100 text-gray-800",
  runtime_error: "bg-orange-100 text-orange-800",
  time_limit_exceeded: "bg-purple-100 text-purple-800",
};

export function SubmissionHistory({ problemId }: SubmissionHistoryProps) {
  const { activeRoundId } = useSessionStore();
  const [submissions, setSubmissions] = useState<SubmissionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!activeRoundId) return;
    setLoading(true);
    API.get(`/coding/submissions/${activeRoundId}/${problemId}`)
      .then((res) => setSubmissions(res.data))
      .catch(() => setSubmissions([]))
      .finally(() => setLoading(false));
  }, [activeRoundId, problemId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
      </div>
    );
  }

  if (submissions.length === 0) {
    return (
      <div className="text-center p-8 text-gray-500 text-sm">
        No submissions yet
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wider">
            <th className="px-4 py-3 text-left">#</th>
            <th className="px-4 py-3 text-left">Verdict</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3 text-right">Submitted At</th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((s, i) => (
            <tr key={s.submission_id} className="border-b border-gray-800/50 hover:bg-white/5">
              <td className="px-4 py-3 text-gray-300">{i + 1}</td>
              <td className="px-4 py-3">
                <span className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize",
                  VERDICT_COLORS[s.status] || "bg-gray-100 text-gray-800"
                )}>
                  {s.status.replace(/_/g, " ")}
                </span>
              </td>
              <td className="px-4 py-3 text-right font-mono text-gray-300">{s.score}</td>
              <td className="px-4 py-3 text-right text-gray-500">
                {new Date(s.submitted_at).toLocaleTimeString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
