"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export interface ScoreRingProps {
  score: number;
  size?: "sm" | "lg";
  label?: string;
  className?: string;
}

export function ScoreRing({ score, size = "sm", label, className }: ScoreRingProps) {
  const [animatedScore, setAnimatedScore] = useState(0);

  useEffect(() => {
    // Animate score from 0 to target over 1.2s
    const duration = 1200;
    const steps = 60;
    const stepTime = duration / steps;
    const increment = score / steps;

    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= score) {
        setAnimatedScore(score);
        clearInterval(timer);
      } else {
        setAnimatedScore(current);
      }
    }, stepTime);

    return () => clearInterval(timer);
  }, [score]);

  // Dimensions
  const sq = size === "lg" ? 120 : 64;
  const strokeWidth = size === "lg" ? 8 : 6;
  const radius = (sq - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (animatedScore / 100) * circumference;

  // Colors based on spec
  let ringColor = "text-teal-500";
  if (score < 40) ringColor = "text-coral-500";
  else if (score < 70) ringColor = "text-amber-500";

  return (
    <div className={cn("relative flex flex-col items-center justify-center", className)}>
      <svg width={sq} height={sq} className="rotate-[-90deg]">
        <circle
          cx={sq / 2}
          cy={sq / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="text-gray-200 dark:text-gray-800"
        />
        <circle
          cx={sq / 2}
          cy={sq / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn("transition-all duration-75 ease-linear", ringColor)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("font-heading font-bold", size === "lg" ? "text-2xl" : "text-sm")}>
          {Math.round(animatedScore)}
        </span>
        {size === "lg" && <span className="text-xs text-muted-foreground -mt-1">/ 100</span>}
      </div>
      {label && <span className="mt-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>}
    </div>
  );
}
