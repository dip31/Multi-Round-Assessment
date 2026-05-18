"use client";

import { CheckCircle2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

interface MCQOptionProps {
  id: string;
  text: string;
  isSelected: boolean;
  onSelect: () => void;
  disabled?: boolean;
}

export function MCQOption({ id, text, isSelected, onSelect, disabled }: MCQOptionProps) {
  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-4 rounded-xl border p-4 text-left transition-all",
        isSelected
          ? "border-accent bg-accent/5 ring-1 ring-accent"
          : "border-gray-200 bg-white hover:border-accent/40 hover:bg-gray-50",
        disabled && "cursor-not-allowed opacity-60"
      )}
    >
      <div
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border",
          isSelected
            ? "border-accent text-accent"
            : "border-gray-300 text-transparent"
        )}
      >
        {isSelected ? <CheckCircle2 className="h-5 w-5" /> : <Circle className="h-5 w-5" />}
      </div>
      <span className="text-[15px] font-medium text-heading leading-relaxed font-sans">{text}</span>
    </button>
  );
}
