"use client";

import React from "react";
import { Brain, Code2, MessageSquare } from "lucide-react";
import { ScoreRing } from "./ScoreRing";
import { useRouter } from "next/navigation";

type RoundStatus = "pending" | "active" | "completed";
type RoundType = "aptitude" | "coding" | "interview";

export interface RoundCardRound {
  id: number;
  round_type: RoundType;
  status: RoundStatus;
  score?: number | null;
}

const ROUND_CONFIG: Record<
  RoundType,
  {
    icon: React.ReactNode;
    title: string;
    subtitle: string;
    route: string;
  }
> = {
  aptitude: {
    icon: <Brain className="w-8 h-8" />,
    title: "Aptitude Round",
    subtitle: "Round 1 of 3",
    route: "/round/aptitude",
  },
  coding: {
    icon: <Code2 className="w-8 h-8" />,
    title: "Coding Round",
    subtitle: "Round 2 of 3",
    route: "/round/coding",
  },
  interview: {
    icon: <MessageSquare className="w-8 h-8" />,
    title: "Interview Round",
    subtitle: "Round 3 of 3",
    route: "/round/interview",
  },
};

const STATUS_CONFIG: Record<
  RoundStatus,
  {
    badge: string;
    badgeColor: string;
    borderColor: string;
    buttonLabel: string;
    buttonDisabled: boolean;
    showScore: boolean;
  }
> = {
  pending: {
    badge: "Locked",
    badgeColor: "bg-gray-200 text-gray-500",
    borderColor: "border-gray-200",
    buttonLabel: "Locked",
    buttonDisabled: true,
    showScore: false,
  },
  active: {
    badge: "In Progress",
    badgeColor: "bg-amber-100 text-amber-700",
    borderColor: "border-amber-400",
    buttonLabel: "Continue Round",
    buttonDisabled: false,
    showScore: false,
  },
  completed: {
    badge: "Completed",
    badgeColor: "bg-teal-100 text-teal-700",
    borderColor: "border-teal-400",
    buttonLabel: "View Results",
    buttonDisabled: false,
    showScore: true,
  },
};

export function RoundCard({ round }: { round: RoundCardRound }) {
  const router = useRouter();
  const config = ROUND_CONFIG[round.round_type];
  const statusCfg = STATUS_CONFIG[round.status] ?? STATUS_CONFIG.pending;
  const isCodingRound = round.round_type === "coding";

  if (!config) return null;

  return (
    <div
      className={`bg-white rounded-xl border-t-4 ${statusCfg.borderColor} shadow-sm p-6 ${
        round.status !== "pending"
          ? "hover:-translate-y-1 transition-transform cursor-pointer"
          : "opacity-70"
      }`}
    >
      <div className="flex justify-between items-start mb-4">
        <div
          className={
            round.status === "pending" ? "text-gray-400" : "text-[#6C63FF]"
          }
        >
          {config.icon}
        </div>
        <span
          className={`text-xs font-semibold px-3 py-1 rounded-full ${statusCfg.badgeColor}`}
        >
          {statusCfg.badge}
        </span>
      </div>

      <h3 className="font-bold text-[#1A1040] text-lg">{config.title}</h3>
      <p className="text-gray-400 text-sm mb-4">{config.subtitle}</p>

      {statusCfg.showScore && (
        <div className="mb-4">
          <ScoreRing score={round.score ?? 0} size="sm" />
        </div>
      )}

      <button
        disabled={statusCfg.buttonDisabled && !isCodingRound}
        onClick={() =>
          (!statusCfg.buttonDisabled || isCodingRound) &&
          router.push(config.route)
        }
        className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
          statusCfg.buttonDisabled && !isCodingRound
            ? "bg-gray-100 text-gray-400 cursor-not-allowed"
            : "bg-[#6C63FF] text-white hover:bg-[#5a52e0]"
        }`}
      >
        {statusCfg.buttonDisabled && !isCodingRound
          ? statusCfg.buttonLabel
          : statusCfg.buttonLabel}
      </button>
      </div>
  );
}
