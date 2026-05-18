import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface SessionState {
  sessionId: number | null;
  activeRoundId: number | null;
  activeRoundType: string | null;
  setSession: (sessionId: number) => void;
  setActiveRound: (
    roundIdOrObj: number | { roundId: number; roundType: string },
    type?: string
  ) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: null,
      activeRoundId: null,
      activeRoundType: null,
      setSession: (sessionId) => set({ sessionId }),
      setActiveRound: (roundIdOrObj, type) => {
        if (typeof roundIdOrObj === "number") {
          set({ activeRoundId: roundIdOrObj, activeRoundType: type ?? null });
          return;
        }
        set({
          activeRoundId: roundIdOrObj.roundId,
          activeRoundType: roundIdOrObj.roundType,
        });
      },
      clearSession: () => set({ sessionId: null, activeRoundId: null, activeRoundType: null }),
    }),
    {
      name: "session-storage",
      storage: createJSONStorage(() => localStorage),
    }
  )
);
