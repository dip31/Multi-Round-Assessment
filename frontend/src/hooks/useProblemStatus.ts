import { useState } from "react";
import { PROBLEM_STATUS } from "@/lib/constants";
import { MOCK_PROBLEM_STATUSES } from "@/lib/mockData";

export function useProblemStatus() {
  const [statuses, setStatuses] = useState<Record<number, string>>(MOCK_PROBLEM_STATUSES);

  // We maintain historical status to restore if unmarked
  const [historicalStatuses, setHistoricalStatuses] = useState<Record<number, string>>(
    { ...MOCK_PROBLEM_STATUSES }
  );

  const updateStatus = (problemId: number, newStatus: string) => {
    const isCurrentlyMarked = statuses[problemId] === PROBLEM_STATUS.MARKED_FOR_REVIEW;
    
    if (isCurrentlyMarked) {
      // Just update history, keep showing marked
      setHistoricalStatuses((prev) => ({ ...prev, [problemId]: newStatus }));
    } else {
      setHistoricalStatuses((prev) => ({ ...prev, [problemId]: newStatus }));
      setStatuses((prev) => ({ ...prev, [problemId]: newStatus }));
    }
  };

  const toggleMarkForReview = (problemId: number) => {
    const isMarked = statuses[problemId] === PROBLEM_STATUS.MARKED_FOR_REVIEW;
    
    if (isMarked) {
      // Restore historical status
      setStatuses((prev) => ({ ...prev, [problemId]: historicalStatuses[problemId] || PROBLEM_STATUS.NOT_ATTEMPTED }));
    } else {
      // Mark it!
      setStatuses((prev) => ({ ...prev, [problemId]: PROBLEM_STATUS.MARKED_FOR_REVIEW }));
    }
  };

  return { statuses, updateStatus, toggleMarkForReview };
}
