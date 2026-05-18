"use client";

import { useTimer } from "@/hooks/useTimer";
import { cn } from "@/lib/utils";
import { Clock } from "lucide-react";

interface CountdownTimerProps {
  initialSeconds: number;
  onExpire: () => void;
}

export function CountdownTimer({ initialSeconds, onExpire }: CountdownTimerProps) {
  const { formattedTime, colorClass } = useTimer(initialSeconds, onExpire);

  return (
    <div className={cn("flex items-center gap-2 rounded-md bg-white/5 px-4 py-1.5", colorClass)}>
      <Clock className="h-4 w-4" />
      <span className="font-mono text-xl tracking-tight">{formattedTime}</span>
    </div>
  );
}
