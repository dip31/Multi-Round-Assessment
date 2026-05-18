"use client";

import { useState } from "react";
import { ConfirmModal } from "../shared/ConfirmModal";
import { LogOut } from "lucide-react";

interface EndRoundButtonProps {
  onEndRound: () => void;
  allProblemsSolved?: boolean;
}

export function EndRoundButton({ onEndRound, allProblemsSolved = false }: EndRoundButtonProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const buttonText = "End Exam";
  const modalTitle = "End Exam";
  const modalMessage = allProblemsSolved
    ? "You have submitted all problems. End the exam and submit your final score?"
    : "You have not completed all problems. Unattempted questions will score zero. Are you sure you want to end the exam now?";

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className={`flex h-9 items-center gap-2 rounded-md border px-4 text-xs font-semibold transition-colors ${
          allProblemsSolved
            ? "border-green-500/50 bg-transparent text-green-500 hover:bg-green-500 hover:text-white"
            : "border-amber-500/50 bg-transparent text-amber-400 hover:bg-amber-500 hover:text-white"
        }`}
      >
        <LogOut className="h-4 w-4" />
        {buttonText}
      </button>

      <ConfirmModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onConfirm={onEndRound}
        title={modalTitle}
        message={modalMessage}
        confirmLabel={buttonText}
      />
    </>
  );
}
